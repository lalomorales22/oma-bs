import QtQuick
import qs.Commons

Column {
  id: root
  property string label: ""
  property string value: ""
  property color foreground: Color.foreground
  signal edited(string value)
  spacing: Style.space(3)
  Text { width: parent.width; text: root.label; color: root.foreground; font.pixelSize: Style.font.caption; elide: Text.ElideRight }
  Rectangle {
    width: parent.width
    height: Style.space(32)
    radius: Style.cornerRadius
    color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.06)
    border.width: 1
    border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, input.activeFocus ? 0.9 : 0.3)
    TextInput {
      id: input
      anchors.fill: parent
      anchors.margins: Style.space(6)
      text: root.value
      color: root.foreground
      font.pixelSize: Style.font.bodySmall
      selectByMouse: true
      activeFocusOnTab: true
      clip: true
      onEditingFinished: { root.edited(text); text = Qt.binding(function() { return root.value }) }
    }
  }
}
