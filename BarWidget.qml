import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "lalo.oma-bs"

  property bool popupOpen: false
  property bool expanded: false
  readonly property bool opened: popupOpen
  property bool recording: false
  property string captureMode: "window"
  property string audioMode: "both"
  property bool webcam: false
  property bool cameraOpen: false
  property bool starting: false
  property bool busy: false
  property bool stopping: false
  property bool externalRecording: false
  property bool settingsLoaded: false
  property bool inputsExpanded: false
  property string microphoneId: "default_input"
  property string cameraId: ""
  property string webcamSize: "medium"
  property int captureFps: 60
  property bool separateAudio: true
  property bool broadcastEnabled: false
  property bool streamCapable: false
  property string streamState: "off"
  property var streamStatus: ({})
  property string latestSourcesFolder: ""
  property var microphones: [{value: "default_input", label: "System default microphone"}]
  property var cameras: [{value: "", label: "Automatic (first camera)"}]
  property string deviceNotice: ""
  property string lastSessionMessage: ""
  property string galleryKind: "video"
  property var mediaItems: []
  property string message: "Ready to capture"
  readonly property string backend: Quickshell.env("HOME") + "/.config/omarchy/plugins/lalo.oma-bs/scripts/oma-bs"

  function close() { popupOpen = false }
  function open() { popupOpen = true; refreshStatus(); refreshGallery(); refreshDevices() }
  function toggle() { popupOpen ? close() : open() }
  function showGallery(item) {
    expanded = true
    if (item && !nativeGallery.exporting) {
      nativeGallery.switchSection(item.kind)
      nativeGallery.choose(item)
    }
    nativeGallery.refresh()
  }
  function run(args) {
    if (actionProc.running) return
    actionProc.command = [backend].concat(args)
    actionProc.running = true
  }
  function refreshStatus() {
    if (!statusProc.running) statusProc.running = true
  }
  function refreshDevices() { if (!deviceProc.running) deviceProc.running = true }
  function refreshGallery() {
    if (!galleryProc.running) {
      galleryProc.command = [backend, "list", galleryKind, "--limit", "6", "--thumbnails"]
      galleryProc.running = true
    }
  }
  function startRecording() {
    if (busy || externalRecording || actionProc.running) return
    var args = ["start", "--capture", captureMode, "--audio", audioMode,
                "--microphone", microphoneId, "--camera", cameraId,
                "--webcam-size", webcamSize, "--fps", String(captureFps)]
    if (webcam) args.push("--webcam")
    if (separateAudio) args.push("--separate-audio")
    run(args)
    message = captureMode === "window" ? "Choose a window or display…" : "Starting capture…"
  }
  function toggleStreaming() {
    if (actionProc.running || stopping) return
    if (broadcastEnabled) { run(["stop-stream"]); return }
    var args = ["start-stream", "--capture", captureMode, "--audio", audioMode,
                "--microphone", microphoneId, "--camera", cameraId,
                "--webcam-size", webcamSize, "--fps", String(captureFps)]
    if (webcam) args.push("--webcam")
    run(args)
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Timer {
    interval: root.busy || root.recording ? 1000 : 4000
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: root.refreshStatus()
  }

  Process {
    id: statusProc
    command: [root.backend, "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var data = JSON.parse(text)
          root.recording = data.recording === true
          root.cameraOpen = data.cameraOpen === true
          root.starting = data.starting === true
          root.busy = data.busy === true || root.recording || root.starting
          root.stopping = data.stopping === true
          root.externalRecording = data.externalRecording === true
          root.broadcastEnabled = data.broadcastEnabled === true
          root.streamCapable = data.streamCapable === true
          root.streamState = data.streamState || "off"
          root.streamStatus = {enabled:root.broadcastEnabled, state:root.streamState, destinations:data.state ? data.state.destinations || [] : []}
          if (!root.settingsLoaded && data.config) {
            var config = data.config
            root.captureMode = config.capture || "window"
            root.audioMode = config.audio || "both"
            root.microphoneId = config.microphone || "default_input"
            root.cameraId = config.camera || ""
            root.webcamSize = config.webcamSize || "medium"
            root.captureFps = config.fps === 30 ? 30 : 60
            root.separateAudio = config.separateAudio !== false
            root.settingsLoaded = true
          }
          var stateMessage = data.state ? (data.state.message || "") : ""
          root.latestSourcesFolder = data.state && data.state.sourcesReady ? (data.state.sourcesFolder || "") : ""
          if (stateMessage !== root.lastSessionMessage) {
            root.lastSessionMessage = stateMessage
            if (stateMessage) root.message = stateMessage
            if (!root.busy) { root.refreshGallery(); if (root.expanded) nativeGallery.refresh() }
          }
        } catch (e) {}
      }
    }
  }

  Process {
    id: deviceProc
    command: [root.backend, "devices"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var data = JSON.parse(text)
          root.microphones = (data.microphones || []).map(function(item) { return {value: item.id, label: item.label} })
          root.cameras = [{value: "", label: "Automatic (first camera)"}].concat((data.cameras || []).map(function(item) { return {value: item.id, label: item.label} }))
          root.deviceNotice = (data.warnings || []).join("\n")
        } catch (e) { root.deviceNotice = "Could not refresh devices." }
      }
    }
  }

  Process {
    id: galleryProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try { root.mediaItems = JSON.parse(text).items || [] } catch (e) { root.mediaItems = [] }
      }
    }
  }

  Process {
    id: actionProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var data = JSON.parse(text)
          root.message = data.ok ? (data.message || "Done") : (data.error || "Action failed")
        } catch (e) { root.message = "Action complete" }
      }
    }
    onExited: function() {
      root.refreshStatus()
      root.refreshGallery()
    }
  }

  IpcHandler {
    target: "lalo.oma-bs"
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function record(): void { root.startRecording() }
    function stop(): void { root.run(["stop"]) }
    function studio(): void { root.run(["studio"]) }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.recording ? "󰻂" : "󰑋"
    slotSize: Style.bar.statusSlot
    tooltipText: root.recording ? "OMA-BS · recording · right-click to stop" : "OMA-BS Studio"
    onPressed: function(b) {
      if (b === Qt.RightButton && root.recording) root.run(["stop"])
      else root.toggle()
    }
  }

  PopupCard {
    id: popup
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.popupOpen
    contentWidth: popup.fittedContentWidth(Style.space(root.expanded ? 780 : 390))
    contentHeight: popup.fittedContentHeight(content.implicitHeight + footer.implicitHeight + Style.space(12))

    Item {
    anchors.fill: parent
    Flickable {
      id: contentScroll
      anchors.top: parent.top
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: footer.top
      anchors.bottomMargin: Style.space(12)
      contentWidth: width
      contentHeight: content.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      Controls.ScrollBar.vertical: StudioScrollBar { foreground: root.bar.foreground }
    Column {
      id: content
      width: parent.width - (contentScroll.contentHeight > contentScroll.height ? Style.space(12) : 0)
      spacing: Style.space(12)

      RowLayout {
        width: parent.width
        Column {
          Layout.fillWidth: true
          spacing: Style.space(2)
          Text { text: "OMA-BS · 0.7.1"; color: root.bar.foreground; font.family: root.bar.fontFamily; font.pixelSize: Style.font.heading; font.bold: true }
          Text { text: root.broadcastEnabled ? "STREAM · " + root.streamState.toUpperCase() : root.recording ? "RECORDING ACTIVE" : "OMARCHY BROADCAST STUDIO"; color: root.recording ? Color.urgent : Qt.darker(root.bar.foreground, 1.35); font.family: root.bar.fontFamily; font.pixelSize: Style.font.caption; font.letterSpacing: 1.4 }
        }
        Rectangle { width: Style.space(9); height: width; radius: width / 2; color: root.recording ? Color.urgent : Qt.rgba(root.bar.foreground.r, root.bar.foreground.g, root.bar.foreground.b, 0.25) }
      }

      PanelSeparator { width: parent.width; foreground: root.bar.foreground }

      RowLayout {
        width: parent.width
        StudioButton { text: root.expanded ? "Back to capture" : "Gallery & edit"; foreground: root.bar.foreground; bordered: true; onClicked: root.expanded ? root.expanded = false : root.showGallery(null) }
        Item { Layout.fillWidth: true }
        StudioButton { visible: root.expanded && root.busy; text: root.stopping ? "Saving…" : "Stop capture"; foreground: Color.urgent; enabled: !actionProc.running && !root.stopping; onClicked: root.run(["stop"]) }
        Text { visible: nativeGallery.exporting; text: "Exporting…"; color: root.bar.foreground; font.pixelSize: Style.font.caption }
      }

      NativeGallery {
        id: nativeGallery
        streamStatus: root.streamStatus
        width: parent.width
        height: Math.max(Style.space(520), nativeGallery.implicitHeight)
        visible: root.expanded
        panelOpen: root.popupOpen && visible
        bar: root.bar
        backend: root.backend
      }

      Column {
        width: parent.width
        spacing: Style.space(12)
        visible: !root.expanded
      StudioSection {
        width: parent.width
        foreground: root.bar.foreground
      Text { text: "CAPTURE"; color: Qt.darker(root.bar.foreground, 1.35); font.family: root.bar.fontFamily; font.pixelSize: Style.font.caption; font.bold: true; font.letterSpacing: 1.2 }
      Row {
        width: parent.width
        enabled: !root.busy
        spacing: Style.space(6)
        Repeater {
          model: [{id:"display", label:"Display"}, {id:"window", label:"Window"}, {id:"region", label:"Region"}]
          StudioButton {
            required property var modelData
            text: modelData.label
            foreground: root.bar.foreground
            selected: root.captureMode === modelData.id
            onClicked: root.captureMode = modelData.id
          }
        }
      }

      }
      StudioSection {
        width: parent.width
        foreground: root.bar.foreground
      Text { text: "AUDIO"; color: Qt.darker(root.bar.foreground, 1.35); font.family: root.bar.fontFamily; font.pixelSize: Style.font.caption; font.bold: true; font.letterSpacing: 1.2 }
      Row {
        width: parent.width
        enabled: !root.busy
        spacing: Style.space(6)
        Repeater {
          model: [{id:"none", label:"Silent"}, {id:"desktop", label:"Desktop"}, {id:"microphone", label:"Mic"}, {id:"both", label:"Both"}]
          StudioButton {
            required property var modelData
            text: modelData.label
            foreground: root.bar.foreground
            selected: root.audioMode === modelData.id
            onClicked: root.audioMode = modelData.id
          }
        }
      }

      }
      StudioSection {
        width: parent.width
        foreground: root.bar.foreground
      RowLayout {
        width: parent.width
        Text { text: root.busy ? "󰄀  Webcam overlay" : "󰄀  Webcam on next take"; color: root.bar.foreground; font.family: root.bar.fontFamily; font.pixelSize: Style.font.body; Layout.fillWidth: true }
        StudioButton {
          text: root.busy ? (root.cameraOpen ? "On" : "Off") : (root.webcam ? "On" : "Off")
          selected: root.busy ? root.cameraOpen : root.webcam
          enabled: !root.busy || root.cameraOpen
          foreground: root.bar.foreground
          focusable: true
          onClicked: {
            if (root.busy) { root.webcam = false; root.run(["webcam-off"]) }
            else {
              root.webcam = !root.webcam
              if (!root.webcam && root.cameraOpen) root.run(["webcam-off"])
            }
          }
        }
      }

      }
      StudioButton {
        width: parent.width
        text: root.inputsExpanded ? "Hide input settings" : "Inputs & camera · " + root.captureFps + " fps"
        foreground: root.bar.foreground
        onClicked: { root.inputsExpanded = !root.inputsExpanded; if (root.inputsExpanded) root.refreshDevices() }
      }
      StudioSection {
        foreground: root.bar.foreground
        width: parent.width
        visible: root.inputsExpanded
        spacing: Style.space(10)
        StudioDropdown {
          width: parent.width
          label: "MICROPHONE"
          value: root.microphoneId
          options: root.microphones
          foreground: root.bar.foreground
          enabled: !root.busy
          onChanged: function(value) { root.microphoneId = value }
        }
        StudioDropdown {
          width: parent.width
          label: "CAMERA"
          value: root.cameraId
          options: root.cameras
          foreground: root.bar.foreground
          enabled: !root.busy
          onChanged: function(value) { root.cameraId = value }
        }
        RowLayout {
          width: parent.width
          enabled: !root.busy
          StudioDropdown {
            Layout.fillWidth: true
            label: "OVERLAY SIZE"
            value: root.webcamSize
            options: [{value:"small", label:"Small"}, {value:"medium", label:"Medium"}, {value:"large", label:"Large"}]
            foreground: root.bar.foreground
            onChanged: function(value) { root.webcamSize = value }
          }
          StudioDropdown {
            Layout.fillWidth: true
            label: "FRAME RATE"
            value: String(root.captureFps)
            options: [{value:"30", label:"30 fps"}, {value:"60", label:"60 fps"}]
            foreground: root.bar.foreground
            onChanged: function(value) { root.captureFps = Number(value) }
          }
        }
        StudioButton { width: parent.width; text: "Separate audio files: " + (root.separateAudio ? "On" : "Off"); selected: root.separateAudio; foreground: root.bar.foreground; enabled: !root.busy; onClicked: root.separateAudio = !root.separateAudio }
        Text { width: parent.width; visible: root.separateAudio; text: "Keeps a multitrack source plus separate mic/desktop audio files. Uses extra disk space."; wrapMode: Text.Wrap; color: Qt.darker(root.bar.foreground, 1.35); font.pixelSize: Style.font.caption }
        StudioButton { text: deviceProc.running ? "Refreshing…" : "Refresh devices"; foreground: root.bar.foreground; enabled: !deviceProc.running; onClicked: root.refreshDevices() }
        Text { width: parent.width; visible: root.deviceNotice !== ""; text: root.deviceNotice; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: root.bar.foreground; font.pixelSize: Style.font.caption }
        Text { width: parent.width; text: "Choices apply to the next take. Your system default microphone stays unchanged."; wrapMode: Text.Wrap; color: Qt.darker(root.bar.foreground, 1.35); font.pixelSize: Style.font.caption }
      }
      Text { width: parent.width; visible: root.webcam && root.captureMode === "window"; text: "A single-window capture excludes the webcam overlay. Choose a display or region to include it."; wrapMode: Text.Wrap; color: root.bar.foreground; font.pixelSize: Style.font.caption }

      RowLayout {
        width: parent.width
        spacing: Style.space(8)
        StudioButton {
          Layout.fillWidth: true
          Layout.preferredHeight: Style.space(42)
          radius: height / 2
          text: root.stopping ? "Saving…" : root.starting ? "Cancel capture" : root.busy ? (root.broadcastEnabled ? "Stop both & save" : "Stop & save") : "Start recording"
          enabled: !actionProc.running && !root.stopping && !root.externalRecording && root.settingsLoaded
          iconText: root.recording ? "󰓛" : "󰑊"
          foreground: root.recording ? Color.urgent : root.bar.foreground
          tooltipText: root.broadcastEnabled ? "Stop streaming and save the recording" : "Start or stop the local recording"
          onClicked: root.busy ? root.run(["stop"]) : root.startRecording()
        }
        StudioButton {
          Layout.preferredWidth: Math.max(implicitWidth, Style.space(100))
          Layout.preferredHeight: Style.space(42)
          radius: height / 2
          text: root.broadcastEnabled ? "End live" : "Stream"
          iconText: root.broadcastEnabled ? "󰓛" : "󰑋"
          foreground: root.broadcastEnabled ? Color.urgent : root.bar.foreground
          active: root.broadcastEnabled
          enabled: !actionProc.running && !root.stopping && !root.externalRecording && root.settingsLoaded && (!root.busy || root.streamCapable)
          tooltipText: root.broadcastEnabled ? "Stop streaming; the local recording continues" : "Stream to saved enabled destinations with a local backup"
          Accessible.name: root.broadcastEnabled ? "Stop streaming; keep recording" : "Start streaming and local backup"
          onClicked: root.toggleStreaming()
        }
      }
      Text { width: parent.width; visible: root.broadcastEnabled; text: "Stream: " + root.streamState + ". Check each channel’s dashboard to confirm your audience is live. Local recording continues if a destination fails."; color: root.bar.foreground; wrapMode: Text.Wrap; font.pixelSize: Style.font.caption }
      Text { width: parent.width; visible: root.busy && !root.streamCapable; text: "To stream, finish this take and start the next one with the Stream button."; color: root.bar.foreground; opacity: 0.65; wrapMode: Text.Wrap; font.pixelSize: Style.font.caption }

      Text { width: parent.width; visible: root.externalRecording; text: "Another recorder is active. Stop it in its own app before starting OMA-BS."; wrapMode: Text.Wrap; color: root.bar.foreground; font.pixelSize: Style.font.caption }

      Text { width: parent.width; text: root.message; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: Qt.darker(root.bar.foreground, 1.35); font.family: root.bar.fontFamily; font.pixelSize: Style.font.caption }
      StudioButton { width: parent.width; visible: !root.busy && root.latestSourcesFolder !== ""; text: "Open last take’s source files"; foreground: root.bar.foreground; onClicked: root.run(["open", root.latestSourcesFolder]) }

      PanelSeparator { width: parent.width; foreground: root.bar.foreground }

      MediaDock {
        width: parent.width
        section: root.galleryKind
        foreground: root.bar.foreground
        enabled: !nativeGallery.exporting
        onChosen: function(section) {
          root.expanded = true
          nativeGallery.switchSection(section)
          if (section === "video" || section === "image" || section === "audio") { root.galleryKind = section; root.refreshGallery() }
        }
      }

      Column {
        width: parent.width
        spacing: Style.space(3)
        Text { visible: root.mediaItems.length === 0; text: "No " + root.galleryKind + "s yet"; color: Qt.darker(root.bar.foreground, 1.5); font.family: root.bar.fontFamily; font.pixelSize: Style.font.bodySmall }
        Repeater {
          model: root.mediaItems
          Rectangle {
            required property var modelData
            width: parent.width
            border.width: 1
            border.color: Qt.rgba(root.bar.foreground.r, root.bar.foreground.g, root.bar.foreground.b, 0.18)
            height: Style.space(38)
            radius: Style.cornerRadius
            color: mediaMouse.containsMouse ? Style.hoverFillFor(root.bar.foreground, Color.accent) : "transparent"
            RowLayout {
              anchors.fill: parent
              anchors.leftMargin: Style.space(8)
              anchors.rightMargin: Style.space(8)
              Image { Layout.preferredWidth: Style.space(44); Layout.preferredHeight: Style.space(32); source: modelData.thumbnail || ""; fillMode: Image.PreserveAspectFit; asynchronous: true }
              Column { Layout.fillWidth: true; Text { width: parent.width; text: modelData.name; color: root.bar.foreground; font.family: root.bar.fontFamily; font.pixelSize: Style.font.bodySmall; elide: Text.ElideMiddle } Text { text: modelData.modified; color: Qt.darker(root.bar.foreground, 1.5); font.family: root.bar.fontFamily; font.pixelSize: Style.font.caption } }
            }
            MouseArea { id: mediaMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.showGallery(modelData) }
          }
        }
      }

      }
    }
    }
    Column {
      id: footer
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      spacing: Style.space(6)
      PanelSeparator { width: parent.width; foreground: root.bar.foreground }
      StudioButton { width: parent.width; text: "Open " + ({video:"recordings", image:"images", audio:"source audio"}[root.expanded ? nativeGallery.kind : root.galleryKind]) + " folder"; iconText: "󰉋"; foreground: root.bar.foreground; onClicked: root.run(["folder", root.expanded ? nativeGallery.kind : root.galleryKind]) }
      StudioButton { width: parent.width; text: "Advanced studio · opens in browser"; iconText: "󰕧"; foreground: root.bar.foreground; onClicked: root.run(["studio"]) }
    }
    }
  }
}
