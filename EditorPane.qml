import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs.Ui
import qs.Commons

Item {
  id: root
  property string backend: ""
  property color foreground: Color.foreground
  property var project: ({version:1, ratio:"16:9", duration:10, base:null, layers:[]})
  property int selectedTrack: -1
  property string notice: "Choose a video or image in the gallery, then Use as base."
  readonly property bool renderBusy: renderProc.running
  readonly property var track: selectedTrack < 0 ? project.base : project.layers[selectedTrack]
  readonly property real aspect: Number(project.ratio.split(":")[0]) / Number(project.ratio.split(":")[1])
  signal rendered(var media)
  signal browse(string kind)
  implicitHeight: layout.implicitHeight

  function clone() { return JSON.parse(JSON.stringify(project)) }
  function add(info, base) {
    if (renderBusy || !info || !info.ok) return false
    if (!base && !project.base) { notice = "First choose a video or image and Use as base."; return false }
    if (!base && project.layers.length >= 8) { notice = "This edit supports eight layers. Remove one before adding another."; return false }
    var p = clone()
    var item = JSON.parse(JSON.stringify(info))
    item.mediaIn = 0; item.at = 0; item.volume = base || info.kind === "audio" ? 1 : 0
    item.fit = "crop"; item.panX = 0.5; item.panY = 0.5
    item.x = 0.65; item.y = 0.65; item.w = 0.3; item.h = 0.3
    if (base) {
      p.base = item; p.layers = []; p.duration = info.kind === "image" ? 10 : info.duration
      selectedTrack = -1
    } else {
      item.length = info.kind === "image" ? p.duration : Math.min(p.duration, info.duration)
      p.layers.push(item); selectedTrack = p.layers.length - 1
      if (info.kind === "audio" && p.base.sourcesFolder && info.path.indexOf(p.base.sourcesFolder + "/") === 0) p.base.volume = 0
    }
    project = p
    notice = base ? "Base set. Choose a shape, drag to frame the crop, or add a layer from the gallery." : info.kind === "audio" && p.base.sourcesFolder && info.path.indexOf(p.base.sourcesFolder + "/") === 0 ? "Source audio added; the base mix is muted to avoid doubling." : "Layer added. Select its track to adjust timing, crop, size, or volume."
    return true
  }
  function normalize(p) {
    var maxDuration = p.base && p.base.kind !== "image" ? p.base.duration - p.base.mediaIn : 21600
    p.duration = Math.max(0.1, Math.min(maxDuration, p.duration))
    for (var i = 0; i < p.layers.length; i++) {
      var t = p.layers[i]
      t.at = Math.max(0, Math.min(t.at, p.duration - 0.05))
      var remaining = t.kind === "image" ? p.duration : t.duration - t.mediaIn
      t.length = Math.max(0.05, Math.min(t.length, p.duration - t.at, remaining))
    }
    return p
  }
  function setting(key, value) {
    if (renderBusy) return
    if (typeof value === "number" && !isFinite(value)) { notice = "Enter a valid number."; return }
    var p = clone(); p[key] = value; project = normalize(p)
  }
  function change(key, value) {
    if (!track || renderBusy) return
    if (typeof value === "number" && !isFinite(value)) { notice = "Enter a valid number."; return }
    var p = clone(), t = selectedTrack < 0 ? p.base : p.layers[selectedTrack]
    if (key === "mediaIn") value = Math.max(0, Math.min(value, t.kind === "image" ? 0 : t.duration - (selectedTrack < 0 ? 0.1 : 0.05)))
    if (key === "volume") value = Math.max(0, Math.min(2, value))
    if (key === "panX" || key === "panY") value = Math.max(0, Math.min(1, value))
    if (key === "w" || key === "h") value = Math.max(0.02, Math.min(1, value))
    t[key] = value
    if (t.kind !== "audio") { t.x = Math.min(t.x, 1 - t.w); t.y = Math.min(t.y, 1 - t.h) }
    project = normalize(p)
  }
  function remove() {
    if (renderBusy || selectedTrack < 0) return
    var p = clone(); p.layers.splice(selectedTrack, 1); selectedTrack = -1; project = p
  }
  function raiseLayer() {
    if (renderBusy || selectedTrack < 0 || selectedTrack >= project.layers.length - 1) return
    var p = clone(), t = p.layers.splice(selectedTrack, 1)[0]; p.layers.push(t)
    project = p; selectedTrack = p.layers.length - 1
  }
  function render(draft) {
    if (!project.base || renderBusy) return
    root.forceActiveFocus() // Commit any numeric field before serializing.
    renderProc.command = [backend, "render-project", "--json", JSON.stringify(project)]
    if (draft) renderProc.command = renderProc.command.concat(["--draft"])
    notice = draft ? "Rendering a small preview…" : "Rendering your composition… originals stay untouched."
    renderProc.running = true
  }
  Component.onCompleted: loadProc.running = true
  Process {
    id: loadProc
    command: [root.backend, "project-load"]
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: {
      try { var r = JSON.parse(text); if (!root.project.base && r.ok && r.project.version === 1 && r.project.base && Array.isArray(r.project.layers)) { root.project = r.project; root.notice = "Saved edit restored." } } catch (e) {}
    } }
  }
  Process {
    id: saveProc
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: { try { var r = JSON.parse(text); root.notice = r.ok ? "Edit saved. Your original files are unchanged." : r.error } catch (e) { root.notice = "Could not save edit." } } }
  }
  Process {
    id: renderProc
    property var result: null
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: { try { renderProc.result = JSON.parse(text) } catch (e) { renderProc.result = null } } }
    onExited: {
      if (result && result.ok) { root.notice = "Saved " + result.name; root.rendered(result) }
      else root.notice = result ? result.error : "Render ended without a result. Source files are unchanged."
      result = null
    }
  }

  ColumnLayout {
    id: layout
    width: parent.width
    spacing: Style.space(10)
    RowLayout {
      Layout.fillWidth: true
      Text { text: "CANVAS"; color: root.foreground; font.pixelSize: Style.font.caption; font.letterSpacing: 1; Layout.fillWidth: true }
      Repeater {
        model: ["16:9", "9:16", "1:1", "19:6"]
        StudioButton { required property string modelData; text: modelData; selected: root.project.ratio === modelData; foreground: root.foreground; enabled: !root.renderBusy; onClicked: root.setting("ratio", modelData) }
      }
    }
    Rectangle {
      Layout.fillWidth: true
      Layout.preferredHeight: Style.space(220)
      border.width: 1
      border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.22)
      color: "#0b0e12"
      radius: Style.cornerRadius
      Item {
        id: canvas
        width: Math.min(parent.width - 2, (parent.height - 2) * root.aspect)
        height: width / root.aspect
        anchors.centerIn: parent
        clip: true
        Visual { anchors.fill: parent; media: root.project.base; index: -1 }
        Repeater {
          model: root.project.layers.length
          Visual {
            required index
            media: root.project.layers[index] || null
            visible: !!media && media.kind !== "audio"
            x: media ? media.x * canvas.width : 0; y: media ? media.y * canvas.height : 0
            width: media ? media.w * canvas.width : 0; height: media ? media.h * canvas.height : 0
          }
        }
      }
      Text { anchors.centerIn: parent; visible: !root.project.base; text: "Add a base from Video or Images"; color: root.foreground; font.pixelSize: Style.font.bodySmall }
    }
    Text { Layout.fillWidth: true; text: "Layout preview · drag base to frame its crop; drag overlays to position. Render preview for motion and sound."; wrapMode: Text.Wrap; color: root.foreground; opacity: 0.65; font.pixelSize: Style.font.caption }
    RowLayout {
      Layout.fillWidth: true
      enabled: !root.renderBusy
      EditorField { Layout.fillWidth: true; label: "EDIT LENGTH · sec"; value: Number(root.project.duration).toFixed(2); foreground: root.foreground; onEdited: function(value) { root.setting("duration", Number(value)) } }
      StudioButton { text: "+ Video"; foreground: root.foreground; onClicked: root.browse("video") }
      StudioButton { text: "+ Image"; foreground: root.foreground; onClicked: root.browse("image") }
      StudioButton { text: "+ Audio"; foreground: root.foreground; onClicked: root.browse("audio") }
    }
    Text { visible: !!root.project.base; text: "LAYERS & AUDIO"; color: root.foreground; font.pixelSize: Style.font.caption; font.letterSpacing: 1 }
    ColumnLayout {
      Layout.fillWidth: true
      spacing: Style.space(4)
      Repeater {
        model: root.project.base ? [root.project.base].concat(root.project.layers) : []
        Rectangle {
          required property var modelData
          required property int index
          Layout.fillWidth: true
          implicitHeight: Style.space(34)
          border.width: 1
          border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, root.selectedTrack === index - 1 ? 0.65 : 0.2)
          radius: Style.cornerRadius
          color: root.selectedTrack === index - 1 ? Style.selectedFillFor(root.foreground, Color.accent) : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
          Rectangle {
            x: parent.width * Math.max(0, Math.min(1, (modelData.at || 0) / root.project.duration))
            width: Math.max(0, Math.min(parent.width - x, parent.width * (index === 0 ? 1 : (modelData.length || root.project.duration) / root.project.duration)))
            height: parent.height
            radius: Style.cornerRadius
            color: root.foreground; opacity: 0.06
          }
          Text { anchors.fill: parent; anchors.margins: Style.space(8); text: (index === 0 ? "BASE" : String(index) + " · " + modelData.kind.toUpperCase()) + "   " + modelData.name + (modelData.hasAudio && modelData.volume === 0 ? " · muted" : ""); elide: Text.ElideMiddle; color: root.foreground; textFormat: Text.PlainText; font.pixelSize: Style.font.caption }
          MouseArea { anchors.fill: parent; enabled: !root.renderBusy; onClicked: root.selectedTrack = index - 1 }
        }
      }
    }
    ColumnLayout {
      Layout.fillWidth: true
      visible: !!root.track
      enabled: !root.renderBusy
      RowLayout {
        Layout.fillWidth: true
        EditorField { Layout.fillWidth: true; label: "SOURCE START · sec"; value: String(root.track ? root.track.mediaIn : 0); foreground: root.foreground; onEdited: function(value) { root.change("mediaIn", Number(value)) } }
        EditorField { Layout.fillWidth: true; visible: root.selectedTrack >= 0; label: "ON TIMELINE · sec"; value: String(root.track ? root.track.at : 0); foreground: root.foreground; onEdited: function(value) { root.change("at", Number(value)) } }
        EditorField { Layout.fillWidth: true; visible: root.selectedTrack >= 0; label: "LAYER LENGTH · sec"; value: String(root.track ? root.track.length : 0); foreground: root.foreground; onEdited: function(value) { root.change("length", Number(value)) } }
        EditorField { Layout.fillWidth: true; visible: !!root.track && root.track.hasAudio; label: "VOLUME · %"; value: String(root.track ? Math.round(root.track.volume * 100) : 100); foreground: root.foreground; onEdited: function(value) { root.change("volume", Number(value) / 100) } }
      }
      RowLayout {
        Layout.fillWidth: true
        visible: !!root.track && root.track.kind !== "audio"
        StudioButton { text: root.track && root.track.fit === "crop" ? "Crop to fill" : "Fit whole image"; foreground: root.foreground; onClicked: root.change("fit", root.track.fit === "crop" ? "fit" : "crop") }
        EditorField { Layout.fillWidth: true; label: "CROP X · %"; value: String(root.track ? Math.round(root.track.panX * 100) : 50); foreground: root.foreground; onEdited: function(value) { root.change("panX", Number(value) / 100) } }
        EditorField { Layout.fillWidth: true; label: "CROP Y · %"; value: String(root.track ? Math.round(root.track.panY * 100) : 50); foreground: root.foreground; onEdited: function(value) { root.change("panY", Number(value) / 100) } }
        EditorField { Layout.fillWidth: true; visible: root.selectedTrack >= 0; label: "WIDTH · %"; value: String(root.track ? Math.round(root.track.w * 100) : 30); foreground: root.foreground; onEdited: function(value) { root.change("w", Number(value) / 100) } }
        EditorField { Layout.fillWidth: true; visible: root.selectedTrack >= 0; label: "HEIGHT · %"; value: String(root.track ? Math.round(root.track.h * 100) : 30); foreground: root.foreground; onEdited: function(value) { root.change("h", Number(value) / 100) } }
      }
      RowLayout {
        Layout.fillWidth: true
        StudioButton { text: "Bring to front"; visible: root.selectedTrack >= 0 && !!root.track && root.track.kind !== "audio"; foreground: root.foreground; onClicked: root.raiseLayer() }
        StudioButton { text: "Remove layer"; visible: root.selectedTrack >= 0; foreground: root.foreground; onClicked: root.remove() }
        Item { Layout.fillWidth: true }
        StudioButton { text: "Save edit"; enabled: !saveProc.running; foreground: root.foreground; onClicked: { root.forceActiveFocus(); saveProc.command = [root.backend, "project-save", "--json", JSON.stringify(root.project)]; saveProc.running = true } }
      }
    }
    RowLayout {
      Layout.fillWidth: true
      StudioButton { Layout.fillWidth: true; text: root.renderBusy ? "Rendering…" : "Render preview"; enabled: !!root.project.base && !root.renderBusy; foreground: root.foreground; onClicked: root.render(true) }
      StudioButton { Layout.fillWidth: true; text: "Export composition · MP4"; enabled: !!root.project.base && !root.renderBusy; foreground: root.foreground; bordered: true; onClicked: root.render(false) }
    }
    Text { Layout.fillWidth: true; text: root.notice; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: root.foreground; font.pixelSize: Style.font.caption }
  }

  component Visual: Rectangle {
    id: visual
    property var media: null
    property int index: -1
    color: index === -1 ? "black" : "transparent"
    clip: true
    Image {
      id: picture
      readonly property real aspect: visual.media && visual.media.height ? visual.media.width / visual.media.height : 1
      width: visual.media && visual.media.fit === "crop" ? Math.max(visual.width, visual.height * aspect) : Math.min(visual.width, visual.height * aspect)
      height: width / aspect
      x: (visual.width - width) * (visual.media && visual.media.fit === "crop" ? visual.media.panX : 0.5)
      y: (visual.height - height) * (visual.media && visual.media.fit === "crop" ? visual.media.panY : 0.5)
      source: visual.media ? visual.media.thumbnail || "" : ""
      asynchronous: true
      fillMode: Image.Stretch
    }
    Rectangle { anchors.fill: parent; color: "transparent"; border.width: root.selectedTrack === visual.index && visual.media ? 1 : 0; border.color: root.foreground }
    MouseArea {
      anchors.fill: parent
      enabled: !!visual.media && !root.renderBusy
      cursorShape: Qt.SizeAllCursor
      property point origin
      property real fromX
      property real fromY
      onPressed: function(mouse) {
        root.selectedTrack = visual.index
        origin = mapToItem(canvas, mouse.x, mouse.y)
        fromX = visual.index < 0 ? visual.media.panX : visual.media.x
        fromY = visual.index < 0 ? visual.media.panY : visual.media.y
      }
      onPositionChanged: function(mouse) {
        if (!pressed) return
        var point = mapToItem(canvas, mouse.x, mouse.y)
        if (visual.index < 0) {
          root.change("panX", Math.max(0, Math.min(1, fromX - (point.x - origin.x) / Math.max(1, picture.width - visual.width))))
          root.change("panY", Math.max(0, Math.min(1, fromY - (point.y - origin.y) / Math.max(1, picture.height - visual.height))))
        } else {
          root.change("x", Math.max(0, Math.min(1 - visual.media.w, fromX + (point.x - origin.x) / canvas.width)))
          root.change("y", Math.max(0, Math.min(1 - visual.media.h, fromY + (point.y - origin.y) / canvas.height)))
        }
      }
    }
  }
}
