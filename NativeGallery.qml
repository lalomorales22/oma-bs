import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import Quickshell.Io
import qs.Ui
import qs.Commons

Item {
  id: root
  implicitHeight: galleryLayout.implicitHeight
  property var bar: null
  property string backend: ""
  property bool panelOpen: false
  property var streamStatus: ({})
  property string kind: "video"
  property string section: "video"
  readonly property bool editing: section === "editor"
  readonly property bool browsing: section === "video" || section === "image" || section === "audio"
  property string query: ""
  property var items: []
  property var selected: null
  property var info: ({})
  property bool pendingList: false
  property bool pendingInspect: false
  property bool muteExport: false
  property string notice: "Choose a recording to preview or trim."
  readonly property bool exporting: exportProc.running || editor.renderBusy
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.65)
  readonly property var filteredItems: items.filter(function(item) { return item.name.toLowerCase().indexOf(root.query.toLowerCase()) >= 0 })

  function refresh() {
    if (listProc.running) { pendingList = true; return }
    listProc.command = [backend, "list", kind, "--limit", "50", "--thumbnails"]
    listProc.running = true
  }
  function choose(item) {
    if (exporting) return
    selected = item
    info = ({})
    muteExport = false
    startField.text = "0"
    endField.text = ""
    notice = "Reading media…"
    inspect()
  }
  function switchSection(value) {
    section = value
    if (value === "video" || value === "image" || value === "audio") kind = value
  }
  function useMedia(base) {
    if (editor.add(info, base)) switchSection("editor")
    else notice = editor.notice
  }
  function inspect() {
    if (!selected) return
    if (inspectProc.running) { pendingInspect = true; return }
    inspectProc.command = [backend, "inspect", selected.path]
    inspectProc.running = true
  }
  function openExternally() {
    if (!selected || openProc.running) return
    openProc.command = [backend, "open", selected.path]
    openProc.running = true
  }
  function openSources() {
    if (!info.sourcesFolder || openProc.running) return
    openProc.command = [backend, "open", info.sourcesFolder]
    openProc.running = true
  }
  function exportClip() {
    if (!selected || exporting || !info.ok) return
    var start = Number(startField.text), end = Number(endField.text)
    if (!startField.text.trim() || !endField.text.trim() || !isFinite(start) || !isFinite(end) || start < 0 || start >= info.duration || end <= start || end > info.duration + 0.05) {
      notice = "Enter start and end seconds within the video."
      return
    }
    if (preview.item) preview.item.pause()
    exportProc.command = [backend, "export", selected.path, "--start", String(start), "--end", String(end)]
    if (muteExport) exportProc.command = exportProc.command.concat(["--mute"])
    notice = "Exporting a new MP4… your original is kept."
    exportProc.running = true
  }
  onPanelOpenChanged: if (panelOpen) refresh()
  onKindChanged: { items = []; if (!exporting) { selected = null; info = ({}) }; refresh() }

  Process {
    id: listProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try { var result = JSON.parse(text); if (result.kind === root.kind) root.items = result.items || [] }
        catch (e) { root.notice = "Could not load the gallery." }
      }
    }
    onExited: { if (root.pendingList) { root.pendingList = false; Qt.callLater(root.refresh) } }
  }
  Process {
    id: inspectProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var result = JSON.parse(text)
          if (root.pendingInspect) return
          if (result.ok && root.selected && result.path === root.selected.path) {
            root.info = result
            endField.text = Number(result.duration).toFixed(3)
            root.notice = result.kind === "image" ? "Image preview" : result.kind === "audio" ? "Waveform shows the first 30 seconds. Play listens to the whole file." : "Preview, choose a range, then export a new MP4."
          } else if (!result.ok) root.notice = result.error || "Cannot inspect media."
        } catch (e) { root.notice = "Could not inspect this file." }
      }
    }
    onExited: { if (root.pendingInspect) { root.pendingInspect = false; Qt.callLater(root.inspect) } }
  }
  Process {
    id: exportProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try { var result = JSON.parse(text); root.notice = result.ok ? "Saved " + result.name + " — original kept." : (result.error || "Export failed.") }
        catch (e) { root.notice = "Export ended without a result. Original kept." }
      }
    }
    onExited: root.refresh()
  }
  Process { id: openProc }

  ColumnLayout {
    id: galleryLayout
    anchors.fill: parent
    spacing: Style.space(10)
    MediaDock {
      Layout.fillWidth: true
      section: root.section
      foreground: root.foreground
      enabled: !root.exporting
      onChosen: function(section) { root.switchSection(section) }
    }
    EditorPane {
      id: editor
      Layout.fillWidth: true
      visible: root.editing
      backend: root.backend
      foreground: root.foreground
      onBrowse: function(kind) { root.switchSection(kind); root.notice = "Choose a file, then Add layer." }
      onRendered: function(media) { Qt.callLater(function() { root.switchSection("video"); root.choose(media); root.refresh() }) }
    }
    StreamPane {
      liveStatus: root.streamStatus
      Layout.fillWidth: true
      visible: root.section === "stream"
      panelOpen: root.panelOpen && visible
      backend: root.backend
      foreground: root.foreground
    }
    RowLayout {
      visible: root.browsing
      Layout.fillWidth: true
      Layout.fillHeight: true
      Layout.minimumHeight: Style.space(430)
      spacing: Style.space(14)
      ColumnLayout {
        Layout.preferredWidth: root.width < 550 ? Style.space(150) : Style.space(220)
        Layout.fillHeight: true
        Field { Layout.fillWidth: true; placeholder: "Search filenames"; onTextChanged: root.query = text }
        StudioButton { text: "Refresh"; foreground: root.foreground; onClicked: root.refresh() }
        ListView {
          id: fileList
          Controls.ScrollBar.vertical: StudioScrollBar { foreground: root.foreground }
          Layout.fillWidth: true
          Layout.fillHeight: true
          clip: true
          spacing: Style.space(5)
          model: root.filteredItems
          boundsBehavior: Flickable.StopAtBounds
          Text { visible: root.filteredItems.length === 0; text: listProc.running ? "Loading…" : "No matching files"; color: root.dim; width: parent.width; wrapMode: Text.Wrap; font.pixelSize: Style.font.caption }
          delegate: Rectangle {
            required property var modelData
            width: fileList.width - (fileList.contentHeight > fileList.height ? Style.space(12) : 0)
            height: Style.space(62)
            border.width: 1
            border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, root.selected && root.selected.path === modelData.path ? 0.65 : 0.2)
            radius: Style.cornerRadius
            color: root.selected && root.selected.path === modelData.path ? Style.selectedFillFor(root.foreground, Color.accent) : (hit.containsMouse ? Style.hoverFillFor(root.foreground, Color.accent) : "transparent")
            RowLayout {
              anchors.fill: parent
              anchors.margins: Style.space(8)
              spacing: Style.space(4)
              Image { Layout.preferredWidth: Style.space(48); Layout.preferredHeight: Style.space(36); source: modelData.thumbnail || ""; fillMode: Image.PreserveAspectFit; asynchronous: true }
              Column {
              Layout.fillWidth: true
              Text { width: parent.width; text: modelData.name; color: root.foreground; elide: Text.ElideMiddle; textFormat: Text.PlainText; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
              Text { width: parent.width; text: modelData.modified + " · " + (modelData.size / 1048576).toFixed(1) + " MB"; color: root.dim; elide: Text.ElideRight; font.pixelSize: Style.font.caption }
              }
            }
            MouseArea { id: hit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; enabled: !root.exporting; onClicked: root.choose(modelData) }
          }
        }
      }
      ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Text { Layout.fillWidth: true; text: root.selected ? root.selected.name : "Your next cut starts here"; color: root.foreground; textFormat: Text.PlainText; elide: Text.ElideMiddle; font.family: Style.font.family; font.pixelSize: Style.font.body; font.bold: true }
        Rectangle {
          Layout.fillWidth: true
          Layout.fillHeight: true
          Layout.minimumHeight: Style.space(120)
          border.width: 1
          border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.22)
          color: "#101216"
          radius: Style.cornerRadius
          clip: true
          Image {
            anchors.margins: 1
            anchors.fill: parent
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            source: root.info.thumbnail || ""
            visible: root.info.kind === "image" || preview.status !== Loader.Ready
          }
          Loader {
            id: preview
            anchors.margins: 1
            anchors.fill: parent
            active: root.panelOpen && root.browsing && root.info.ok === true && (root.info.kind === "video" || root.info.kind === "audio")
            source: Qt.resolvedUrl("VideoPreview.qml")
            onLoaded: { item.mediaUrl = root.info.uri; item.foreground = root.foreground; item.audioMode = root.info.kind === "audio"; item.thumbnailUrl = root.info.thumbnail || "" }
          }
          Connections {
            target: root
            function onInfoChanged() { if (preview.item) { preview.item.mediaUrl = root.info.uri || ""; preview.item.audioMode = root.info.kind === "audio"; preview.item.thumbnailUrl = root.info.thumbnail || "" } }
          }
          Text {
            anchors.centerIn: parent
            width: parent.width - 24
            horizontalAlignment: Text.AlignHCenter
            text: root.selected ? (inspectProc.running ? "Reading media…" : "") : "Select a file to preview here"
            color: "#bec9d0"
            font.pixelSize: Style.font.body
          }
        }
        Text {
          visible: preview.status === Loader.Error
          Layout.fillWidth: true
          text: "Inline playback needs Qt Multimedia. You can still trim here or open your video player."
          color: root.dim
          wrapMode: Text.Wrap
          font.pixelSize: Style.font.caption
        }
        Text { visible: root.info.ok === true; text: root.info.kind === "audio" ? root.info.channels + " channels · " + Number(root.info.duration).toFixed(2) + " seconds" : (root.info.width || 0) + " × " + (root.info.height || 0) + (root.info.kind === "video" ? " · " + Number(root.info.duration).toFixed(2) + " seconds" : ""); color: root.dim; font.pixelSize: Style.font.caption }
        RowLayout {
          Layout.fillWidth: true
          enabled: root.info.ok === true && !root.exporting
          StudioButton { Layout.fillWidth: true; visible: root.info.kind !== "audio"; text: "Use as base"; foreground: root.foreground; onClicked: root.useMedia(true) }
          StudioButton { Layout.fillWidth: true; text: "Add layer"; foreground: root.foreground; onClicked: root.useMedia(false) }
        }
        RowLayout {
          visible: root.info.kind === "video"
          Layout.fillWidth: true
          enabled: !root.exporting
          ColumnLayout {
            Layout.fillWidth: true
            Text { text: "START · seconds"; color: root.dim; font.pixelSize: Style.font.caption }
            Field { id: startField; Layout.fillWidth: true; text: "0" }
          }
          ColumnLayout {
            Layout.fillWidth: true
            Text { text: "END · seconds"; color: root.dim; font.pixelSize: Style.font.caption }
            Field { id: endField; Layout.fillWidth: true }
          }
        }
        RowLayout {
          visible: root.info.kind === "video"
          enabled: !root.exporting
          StudioButton { text: "Set start here"; foreground: root.foreground; enabled: preview.item !== null; onClicked: startField.text = preview.item.positionSeconds.toFixed(3) }
          StudioButton { text: "Set end here"; foreground: root.foreground; enabled: preview.item !== null; onClicked: endField.text = preview.item.positionSeconds.toFixed(3) }
        }
        RowLayout {
          Layout.fillWidth: true
          StudioButton { visible: root.info.kind === "video"; text: root.muteExport ? "Audio removed" : "Keep audio"; selected: root.muteExport; enabled: !root.exporting; foreground: root.foreground; onClicked: root.muteExport = !root.muteExport }
          Item { Layout.fillWidth: true }
          StudioButton { text: "Open in player"; foreground: root.foreground; enabled: root.selected !== null; onClicked: root.openExternally() }
        }
        StudioButton {
          Layout.fillWidth: true
          visible: root.info.kind === "video"
          text: root.exporting ? "Exporting…" : "Export selected range · MP4"
          enabled: root.info.ok === true && !root.exporting
          foreground: root.foreground
          bordered: true
          onClicked: root.exportClip()
        }
        StudioButton { Layout.fillWidth: true; visible: !!root.info.sourcesFolder; text: "Open source audio files"; foreground: root.foreground; onClicked: root.openSources() }
      }
    }
    Text { visible: root.browsing; Layout.fillWidth: true; text: root.notice; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: root.dim; font.family: Style.font.family; font.pixelSize: Style.font.caption; maximumLineCount: 3; elide: Text.ElideRight }
  }

  component Field: Rectangle {
    property alias text: input.text
    property string placeholder: ""
    implicitHeight: Style.space(34)
    radius: Style.cornerRadius
    color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.06)
    border.color: input.activeFocus ? Color.accent : root.dim
    border.width: 1
    TextInput {
      id: input
      anchors.fill: parent
      anchors.margins: Style.space(7)
      color: root.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      clip: true
      selectByMouse: true
      activeFocusOnTab: true
    }
    Text { anchors.fill: input; text: parent.placeholder; visible: input.text === ""; color: root.dim; font.pixelSize: Style.font.caption }
  }
}
