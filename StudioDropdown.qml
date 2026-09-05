import QtQuick
import qs.Ui as Ui
import qs.Commons

Item {
  id: root
  property alias label: control.label
  property alias value: control.value
  property alias options: control.options
  property alias foreground: control.foreground
  signal changed(string value)
  implicitWidth: control.implicitWidth + Style.space(16)
  implicitHeight: control.implicitHeight + Style.space(16)
  Rectangle {
    anchors.fill: parent
    radius: Style.space(9)
    color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.025)
    border.width: 1
    border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, control.popupOpen ? 0.65 : 0.26)
  }
  Ui.Dropdown {
    id: control
    anchors.top: parent.top
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.margins: Style.space(8)
    onChanged: function(value) { root.changed(value) }
  }
}
