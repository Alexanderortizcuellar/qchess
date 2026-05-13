from PyQt5.QtWidgets import QAction, QPushButton
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QKeySequence, QIcon
import qtawesome as qta

ICON_SIZE = QSize(20, 20)

# Default colors for light/dark modes
DARK_ICON_COLOR = "#a9aea7"
LIGHT_ICON_COLOR = "#312e2b"

def _get_icon_color(is_dark: bool = True):
    return DARK_ICON_COLOR if is_dark else LIGHT_ICON_COLOR

def _qicon(name: str, color=None, is_dark=True):
    """Return a qtawesome icon safely; easy to swap/iconify in one place."""
    if color is None:
        color = _get_icon_color(is_dark)
    return qta.icon(name, color=color)


def _slot_or_noop(obj, method_name, *args, **kwargs):
    """Return a callable for QAction.triggered.connect. If missing, it's a no-op."""
    return getattr(obj, method_name, lambda *args, **kwargs: None)


def _create_action(
    parent,
    text,
    slot=None,
    shortcut=None,
    icon_name=None,
    checkable=False,
    checked=False,
    status_tip=None,
    tool_tip=None,
    is_dark=True
):
    """Consistency helper for QAction creation."""
    act = QAction(text, parent)
    if icon_name:
        # Store icon name for theme switching
        act.setProperty("icon_name", icon_name)
        act.setIcon(_qicon(icon_name, is_dark=is_dark))
    if shortcut:
        # Accept both QKeySequence and str
        act.setShortcut(
            shortcut if isinstance(shortcut, QKeySequence) else QKeySequence(shortcut)
        )
    if status_tip:
        act.setStatusTip(status_tip)
    if tool_tip:
        act.setToolTip(tool_tip)
    if checkable:
        act.setCheckable(True)
        act.setChecked(checked)
    if slot:
        act.triggered.connect(slot)
    return act


def _create_iconed_button(icon_name: str, shortcut=str, tooltip: str = "", is_dark=True) -> QPushButton:
    button = QPushButton()
    button.setObjectName("SmallIconButton")
    # Store icon name for theme switching
    button.setProperty("icon_name", icon_name)
    button.setIcon(_qicon(icon_name, is_dark=is_dark))
    button.setIconSize(ICON_SIZE)
    button.setToolTip(tooltip)
    button.setShortcut(shortcut)
    button.setCursor(Qt.PointingHandCursor)
    return button

def update_widget_icons(widget, is_dark: bool):
    """Recursively update icons of a widget and its children based on the theme."""
    from PyQt5 import QtWidgets
    
    # Update the widget itself if it has an icon_name property
    if hasattr(widget, "property") and widget.property("icon_name"):
        if isinstance(widget, (QPushButton, QAction)):
            widget.setIcon(_qicon(widget.property("icon_name"), is_dark=is_dark))
    
    # Update all PushButtons
    for btn in widget.findChildren(QPushButton):
        if btn.property("icon_name"):
            btn.setIcon(_qicon(btn.property("icon_name"), is_dark=is_dark))
    
    # Update all Actions found via findChildren (e.g. in toolbars, menus)
    for action in widget.findChildren(QAction):
        if action.property("icon_name"):
            action.setIcon(_qicon(action.property("icon_name"), is_dark=is_dark))
    
    # Special handling for MenuBar which might contain menus with actions
    if hasattr(widget, "menuBar") and widget.menuBar():
        for action in widget.menuBar().actions():
            if action.property("icon_name"):
                action.setIcon(_qicon(action.property("icon_name"), is_dark=is_dark))
            if action.menu():
                # For menus, we need to iterate their actions
                for menu_action in action.menu().actions():
                    if menu_action.property("icon_name"):
                        menu_action.setIcon(_qicon(menu_action.property("icon_name"), is_dark=is_dark))
                    # If there are submenus, this could continue, but usually 1 level is enough for this app
                    if menu_action.menu():
                         for sub_action in menu_action.menu().actions():
                             if sub_action.property("icon_name"):
                                 sub_action.setIcon(_qicon(sub_action.property("icon_name"), is_dark=is_dark))

    # Also handle toolbars explicitly just in case findChildren missed some actions
    for toolbar in widget.findChildren(QtWidgets.QToolBar):
        for action in toolbar.actions():
            if action.property("icon_name"):
                action.setIcon(_qicon(action.property("icon_name"), is_dark=is_dark))
