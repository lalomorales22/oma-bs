import QtQuick
import qs.Commons

Rectangle {
  id: section
  property color foreground: Color.foreground
  property real padding: Style.space(12)
  property alias spacing: body.spacing
  default property alias contents: body.data
  implicitHeight: body.implicitHeight + padding * 2
  color: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.025)
  border.width: 1
  border.color: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.18)
  radius: Style.space(12)
  Column {
    id: body
    anchors.top: parent.top
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.margins: section.padding
    spacing: Style.space(10)
  }
}
