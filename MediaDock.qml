import QtQuick
import QtQuick.Layouts
import qs.Commons

Rectangle {
  id: root
  property string section: "video"
  property color foreground: Color.foreground
  signal chosen(string section)
  implicitHeight: Style.space(58)
  border.width: 1
  border.color: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.2)
  radius: Style.cornerRadius
  color: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.04)
  RowLayout {
    anchors.fill: parent
    anchors.margins: Style.space(4)
    spacing: Style.space(3)
    Repeater {
      model: [{key:"video", label:"Video", icon:"󰈫"}, {key:"image", label:"Images", icon:"󰋩"}, {key:"audio", label:"Audio", icon:"󰎈"}, {key:"editor", label:"Editor", icon:"󰕧"}, {key:"stream", label:"Stream", icon:"󰑋"}]
      Rectangle {
        required property var modelData
        Layout.fillWidth: true
        Layout.fillHeight: true
        radius: Style.cornerRadius
        color: root.section === modelData.key ? Style.selectedFillFor(root.foreground, Color.accent) : hit.containsMouse ? Style.hoverFillFor(root.foreground, Color.accent) : "transparent"
        activeFocusOnTab: true
        border.width: 1
        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, activeFocus ? 0.95 : root.section === modelData.key ? 0.65 : 0.14)
        Accessible.role: Accessible.Button
        Accessible.name: modelData.label
        Keys.onSpacePressed: root.chosen(modelData.key)
        Keys.onReturnPressed: root.chosen(modelData.key)
        Column {
          anchors.centerIn: parent
          spacing: Style.space(2)
          Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.icon; color: root.foreground; font.family: Style.font.family; font.pixelSize: Style.font.icon }
          Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.label; color: root.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption }
        }
        MouseArea { id: hit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.chosen(modelData.key) }
      }
    }
  }
}
