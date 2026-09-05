import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs.Ui
import qs.Commons

Item {
  id: root
  property string backend: ""
  property color foreground: Color.foreground
  property bool panelOpen: false
  property var liveStatus: ({})
  property var destinations: []
  property bool loaded: false
  property bool dirty: false
  property bool showKeys: false
  property string notice: ""
  readonly property var platforms: [{value:"twitch",label:"Twitch"}, {value:"youtube",label:"YouTube"}, {value:"kick",label:"Kick"}, {value:"x",label:"X"}, {value:"tiktok",label:"TikTok"}, {value:"custom",label:"Custom"}]
  readonly property int configured: destinations.filter(function(d) { return d.enabled && d.url.trim() && d.key.trim() }).length
  implicitHeight: layout.implicitHeight
  onPanelOpenChanged: { if (!panelOpen) showKeys = false; else if (!loaded && !loadProc.running) loadProc.running = true }
  function change(index, key, value) {
    var copy = JSON.parse(JSON.stringify(destinations))
    copy[index][key] = value
    if (key === "platform") { copy[index].url = ""; copy[index].key = "" }
    destinations = copy; dirty = true
  }
  function add() {
    if (destinations.length >= 16) return
    destinations = destinations.concat([{id:"dest-" + Date.now() + "-" + Math.floor(Math.random() * 1000000), platform:"custom",url:"",key:"",enabled:true}])
    dirty = true
  }
  function remove(index) { var copy = destinations.slice(); copy.splice(index, 1); destinations = copy; dirty = true }
  function save(openStudio) {
    root.forceActiveFocus()
    saveProc.payload = JSON.stringify({version:1,destinations:destinations})
    saveProc.openAfterSave = openStudio
    saveProc.running = true
  }
  Process {
    id: loadProc
    command: [root.backend, "stream-load"]
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: {
      try {
        var result = JSON.parse(text)
        if (result.ok) { root.destinations = result.destinations; root.loaded = true; root.notice = "Saved destinations are local to this device." }
        else root.notice = result.error || "Could not load destinations."
      } catch (e) { root.notice = "Could not load destinations." }
    } }
  }
  Process {
    id: saveProc
    property string payload: ""
    property bool openAfterSave: false
    property bool succeeded: false
    command: [root.backend, "stream-save"]
    stdinEnabled: true
    onStarted: { write(payload + "\n"); payload = "" }
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: {
      try {
        var result = JSON.parse(text)
        saveProc.succeeded = result.ok === true
        root.notice = result.ok ? "Destinations saved. Use the Stream button beside Record to start." : result.error
        if (result.ok) root.dirty = false
      } catch (e) { root.notice = "Save ended without a result." }
    } }
    onExited: {
      if (succeeded && openAfterSave) studioProc.running = true
      succeeded = false; openAfterSave = false; payload = ""
    }
  }
  Process { id: studioProc; command: [root.backend, "studio"] }
  ColumnLayout {
    id: layout
    width: parent.width
    spacing: Style.space(12)
    Text { text: "STREAM DESTINATIONS"; color: root.foreground; font.pixelSize: Style.font.body; font.bold: true; font.letterSpacing: 1 }
    Text { Layout.fillWidth: true; text: "Save your channels here, then use the Stream button beside Record. It uses your capture, camera, and audio choices and keeps a local backup."; color: root.foreground; opacity: 0.7; wrapMode: Text.Wrap; font.pixelSize: Style.font.bodySmall }
    Text { Layout.fillWidth: true; text: root.liveStatus.enabled ? "BROADCAST · " + String(root.liveStatus.state).toUpperCase() : "NOT STREAMING"; color: root.foreground; font.pixelSize: Style.font.caption; font.bold: true }
    Repeater {
      model: root.liveStatus.destinations || []
      Text { required property var modelData; Layout.fillWidth: true; text: modelData.platform.toUpperCase() + " · " + modelData.state + (modelData.message ? " — " + modelData.message : ""); color: root.foreground; wrapMode: Text.Wrap; textFormat: Text.PlainText; font.pixelSize: Style.font.caption }
    }
    RowLayout {
      Layout.fillWidth: true
      Text { Layout.fillWidth: true; text: root.configured + " enabled & configured" + (root.dirty ? " · unsaved changes" : ""); color: root.foreground; font.pixelSize: Style.font.caption }
      StudioButton { text: root.showKeys ? "Hide keys" : "Show keys"; foreground: root.foreground; onClicked: root.showKeys = !root.showKeys }
    }
    Text { visible: root.loaded && root.destinations.length === 0; text: "Add your first destination below."; color: root.foreground; font.pixelSize: Style.font.bodySmall }
    Repeater {
      model: root.destinations.length
      Rectangle {
        id: card
        required property int index
        readonly property var destination: root.destinations[index] || ({platform:"custom",url:"",key:"",enabled:false})
        Layout.fillWidth: true
        implicitHeight: fields.implicitHeight + Style.space(24)
        color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
        border.width: 1
        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.2)
        radius: Style.cornerRadius
        ColumnLayout {
          id: fields
          anchors.fill: parent
          anchors.margins: Style.space(12)
          spacing: Style.space(8)
          enabled: !saveProc.running
          RowLayout {
            Layout.fillWidth: true
            StudioDropdown { Layout.fillWidth: true; label: "DESTINATION " + (card.index + 1); value: card.destination.platform; options: root.platforms; foreground: root.foreground; onChanged: function(value) { root.forceActiveFocus(); root.change(card.index, "platform", value) } }
            StudioButton { text: card.destination.enabled ? "Enabled" : "Disabled"; selected: card.destination.enabled; foreground: root.foreground; onClicked: { root.forceActiveFocus(); root.change(card.index, "enabled", !card.destination.enabled) } }
            StudioButton { text: "Remove"; foreground: root.foreground; onClicked: { root.forceActiveFocus(); root.remove(card.index) } }
          }
          Field { Layout.fillWidth: true; label: "SERVER URL · RTMP / RTMPS"; value: card.destination.url; placeholder: "Paste the server URL from your live dashboard"; onEdited: function(value) { root.change(card.index, "url", value) } }
          Field { Layout.fillWidth: true; label: "STREAM KEY"; value: card.destination.key; secret: !root.showKeys; placeholder: "Paste your stream key"; onEdited: function(value) { root.change(card.index, "key", value) } }
        }
      }
    }
    StudioButton { Layout.fillWidth: true; text: "+ Add destination"; enabled: root.loaded && !saveProc.running && root.destinations.length < 16; foreground: root.foreground; bordered: true; onClicked: { root.forceActiveFocus(); root.add() } }
    Text { Layout.fillWidth: true; text: "Use the RTMP or encrypted RTMPS ingest address supplied by each platform, rather than its HTTPS website address. Incomplete destinations can be saved for later."; color: root.foreground; opacity: 0.65; wrapMode: Text.Wrap; font.pixelSize: Style.font.caption }
    RowLayout {
      Layout.fillWidth: true
      StudioButton { Layout.fillWidth: true; text: saveProc.running ? "Saving…" : "Save destinations"; enabled: root.loaded && !saveProc.running; foreground: root.foreground; onClicked: root.save(false) }
      StudioButton { Layout.fillWidth: true; text: "Save & open browser studio"; enabled: root.loaded && !saveProc.running && !studioProc.running; foreground: root.foreground; bordered: true; onClicked: root.save(true) }
    }
    Text { Layout.fillWidth: true; text: root.notice; color: root.foreground; textFormat: Text.PlainText; wrapMode: Text.Wrap; font.pixelSize: Style.font.caption }
    Text { Layout.fillWidth: true; text: "Changes apply on the next stream start. Keys stay in owner-only local files; browser import also stores them in that browser profile. Saving does not start a broadcast."; color: root.foreground; opacity: 0.65; wrapMode: Text.Wrap; font.pixelSize: Style.font.caption }
  }
  component Field: Column {
    id: field
    property string label: ""
    property string value: ""
    property string placeholder: ""
    property bool secret: false
    signal edited(string value)
    spacing: Style.space(4)
    Text { text: field.label; color: root.foreground; opacity: 0.7; font.pixelSize: Style.font.caption }
    Rectangle {
      width: parent.width; height: Style.space(36)
      color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04); radius: Style.cornerRadius
      border.width: 1; border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, input.activeFocus ? 0.9 : 0.3)
      TextInput {
        id: input
        anchors.fill: parent; anchors.margins: Style.space(8)
        text: field.value; color: root.foreground; font.pixelSize: Style.font.bodySmall
        echoMode: field.secret ? TextInput.Password : TextInput.Normal
        maximumLength: 2048; clip: true; selectByMouse: true; activeFocusOnTab: true
        onEditingFinished: { field.edited(text); text = Qt.binding(function() { return field.value }) }
      }
      Text { anchors.fill: input; text: field.placeholder; visible: input.text === ""; color: root.foreground; opacity: 0.4; font.pixelSize: Style.font.caption; elide: Text.ElideRight }
    }
  }
}
