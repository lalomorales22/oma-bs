import QtQuick
import QtQuick.Layouts
import QtMultimedia
import qs.Ui
import qs.Commons

// Loaded dynamically: missing Qt Multimedia must never prevent the bar loading.
Item {
  id: root
  property url mediaUrl: ""
  property bool audioMode: false
  property url thumbnailUrl: ""
  property color foreground: Color.foreground
  readonly property real positionSeconds: player.position / 1000
  property string errorText: ""
  function pause() { player.pause() }
  function seek(seconds) { if (player.seekable) player.position = Math.round(seconds * 1000) }
  function stamp(ms) {
    var seconds = Math.floor(ms / 1000)
    return Math.floor(seconds / 60) + ":" + (seconds % 60 < 10 ? "0" : "") + seconds % 60
  }
  onMediaUrlChanged: errorText = ""
  Component.onDestruction: player.stop()
  MediaPlayer {
    id: player
    source: root.mediaUrl
    audioOutput: AudioOutput { id: audio; muted: !root.audioMode }
    videoOutput: video
    onErrorOccurred: function(error, errorString) { root.errorText = errorString }
  }
  ColumnLayout {
    anchors.fill: parent
    spacing: Style.space(5)
    Rectangle {
      Layout.fillWidth: true
      Layout.fillHeight: true
      color: "#101216"
      VideoOutput { id: video; anchors.fill: parent; fillMode: VideoOutput.PreserveAspectFit }
      Image { anchors.fill: parent; anchors.margins: Style.space(12); source: root.thumbnailUrl; visible: root.audioMode; fillMode: Image.PreserveAspectFit }
      Text {
        anchors.centerIn: parent
        width: parent.width - 20
        text: root.errorText
        visible: text !== ""
        color: "#e2e2e2"
        wrapMode: Text.Wrap
        font.pixelSize: Style.font.caption
      }
    }
    Rectangle {
      Layout.fillWidth: true
      height: Style.space(12)
      color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)
      radius: 3
      Rectangle {
        height: parent.height
        width: player.duration > 0 ? parent.width * player.position / player.duration : 0
        color: Color.accent
        radius: 3
      }
      MouseArea {
        anchors.fill: parent
        enabled: player.seekable
        cursorShape: Qt.PointingHandCursor
        onPressed: function(mouse) { player.position = Math.round(mouse.x / width * player.duration) }
        onPositionChanged: function(mouse) { if (pressed) player.position = Math.round(Math.max(0, Math.min(1, mouse.x / width)) * player.duration) }
      }
    }
    RowLayout {
      Layout.fillWidth: true
      StudioButton {
        text: player.playbackState === MediaPlayer.PlayingState ? "Pause" : "Play"
        foreground: root.foreground
        onClicked: player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play()
      }
      Text {
        text: root.stamp(player.position) + " / " + root.stamp(player.duration)
        Layout.fillWidth: true
        color: root.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }
      StudioButton { text: audio.muted ? "Sound off" : "Sound on"; foreground: root.foreground; onClicked: audio.muted = !audio.muted }
    }
  }
}
