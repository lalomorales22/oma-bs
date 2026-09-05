import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.ScrollBar {
  id: control
  property color foreground: Color.foreground
  policy: Controls.ScrollBar.AsNeeded
  hoverEnabled: true
  padding: 0
  implicitWidth: Style.space(8)
  minimumSize: 0.06
  // Override both native-style surfaces; no permanent grey trough.
  background: Item {}
  opacity: size < 1 && (active || hovered || pressed) ? 1 : 0
  Behavior on opacity { NumberAnimation { duration: 180 } }
  contentItem: Rectangle {
    implicitWidth: Style.space(4)
    implicitHeight: Style.space(24)
    radius: width / 2
    color: Qt.rgba(control.foreground.r, control.foreground.g, control.foreground.b,
      control.pressed ? 0.65 : 0.35)
  }
}
