import QtQuick
import qs.Ui as Ui
import qs.Commons

// A visible outline even when the shell theme uses borderless controls.
Ui.Button {
  id: control
  bordered: true
  focusable: true
  fontSize: Style.font.bodySmall
  horizontalPadding: Style.space(10)
  verticalPadding: Style.space(8)
  radius: Style.space(9)
  background: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.035)
  borderSpec: Border.flat(Qt.rgba(foreground.r, foreground.g, foreground.b,
    activeFocus ? 0.95 : selected || active ? 0.65 : hot ? 0.5 : 0.26), 1)
  opacity: enabled ? 1 : 0.4
  Accessible.role: Accessible.Button
  Accessible.name: text || tooltipText
}
