from PyQt5.QtWidgets import QAction, QPushButton
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QKeySequence
import qtawesome as qta

ICON_SIZE = QSize(32, 32)


def _qicon(name: str, color="#a9aea7"):
    """Return a qtawesome icon safely; easy to swap/iconify in one place."""
    # Examples of names:
    # 'fa5s.file-pdf', 'fa5s.search', 'fa5s.broom', 'fa5s.list', 'fa5s.font', 'fa5s.image',
    # 'fa5s.chess-board' (fallbacks available), 'mdi.select-drag', 'fa5s.info-circle'
    return qta.icon(name, color=color)


def _slot_or_noop(obj, method_name):
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
):
    """Consistency helper for QAction creation."""
    act = QAction(text, parent)
    if icon_name:
        act.setIcon(_qicon(icon_name))
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


def _create_iconed_button(icon: str, shortcut=str, tooltip: str = "") -> QPushButton:
    button = QPushButton()
    button.setIcon(qta.icon(icon, size=ICON_SIZE, color="#a9aea7"))
    button.setIconSize(ICON_SIZE)
    button.setToolTip(tooltip)
    button.setShortcut(shortcut)
    button.setCursor(Qt.PointingHandCursor)
    # button.clicked.connect(callback)
    return button
