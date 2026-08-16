"""
RepertoireTreeWidget — a QTreeWidget-based file-explorer-style panel
for browsing and managing chess repertoires.

Signals emitted (consumed by ApplicationController):
    repertoireOpenRequested(int)    — user double-clicked a repertoire node_id
    repertoireSaveRequested(int, str) — controller calls this after editor saves

Context-menu actions:
    New Folder / New Repertoire / Rename / Move / Delete / Import PGN / Export PGN / Open
"""

import os

import qtawesome as qta
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QAbstractItemView,
    QPushButton,
    QMenu,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QFormLayout,
)

from core.repertoire_db import RepertoireRepository, RepertoireNode


# ---------------------------------------------------------------------------
# Tree item roles
# ---------------------------------------------------------------------------
NODE_ID_ROLE   = Qt.UserRole
NODE_TYPE_ROLE = Qt.UserRole + 1

# Colors aligned with chess-memorization & app QSS palette
FOLDER_COLOR     = QColor("#fb923c")   # warm amber/orange matching chess-memorization
REPERTOIRE_COLOR = QColor("#e5e7eb")   # clean light text matching chess-memorization


# ---------------------------------------------------------------------------
# Custom draggable tree view with database persistence
# ---------------------------------------------------------------------------

class _RepertoireTreeView(QTreeWidget):
    """QTreeWidget subclass that intercepts drag-and-drop drops to persist them in DB."""

    nodeMoved = pyqtSignal(int, object)  # (dragged_node_id, new_parent_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dropEvent(self, event):
        dragged_items = self.selectedItems()
        if not dragged_items:
            event.ignore()
            return

        dragged_item = dragged_items[0]
        dragged_id = dragged_item.data(0, NODE_ID_ROLE)

        target_item = self.itemAt(event.pos())
        drop_pos = self.dropIndicatorPosition()

        if target_item is None or drop_pos == QAbstractItemView.OnViewport:
            new_parent_id = None
        elif drop_pos == QAbstractItemView.OnItem:
            if target_item.data(0, NODE_TYPE_ROLE) == "folder":
                new_parent_id = target_item.data(0, NODE_ID_ROLE)
            else:
                p = target_item.parent()
                new_parent_id = p.data(0, NODE_ID_ROLE) if p else None
        else:  # AboveItem or BelowItem
            p = target_item.parent()
            new_parent_id = p.data(0, NODE_ID_ROLE) if p else None

        if dragged_id == new_parent_id:
            event.ignore()
            return

        event.acceptProposedAction()
        self.nodeMoved.emit(dragged_id, new_parent_id)


# ---------------------------------------------------------------------------
# Small helpers / dialogs
# ---------------------------------------------------------------------------

def _ask_name(parent, title: str, label: str, default: str = "") -> str | None:
    text, ok = QInputDialog.getText(parent, title, label, text=default)
    return text.strip() if ok and text.strip() else None


class MoveFolderDialog(QDialog):
    """Let user pick a destination folder from a flat list."""

    def __init__(self, nodes: list, exclude_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Move To Folder")
        self.setMinimumWidth(360)

        self.setStyleSheet("""
            QDialog { background: #262421; color: #bababa; }
            QLabel  { color: #8b8987; font-weight: bold; }
            QComboBox {
                background: #312e2b; color: #ffffff;
                border: 1px solid #403d39; border-radius: 3px;
                padding: 5px; font-size: 13px;
            }
            QPushButton {
                background: #312e2b; color: #ffffff;
                border: 1px solid #403d39; border-radius: 3px; padding: 5px 14px;
            }
            QPushButton:hover { background: #383531; border-color: #504d48; }
            QPushButton:pressed { background: #21201d; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        self.combo = QComboBox()
        self.combo.addItem("— Root (top level) —", None)

        # Build path strings
        node_by_id = {n.id: n for n in nodes}
        folders = [n for n in nodes if n.is_folder() and n.id != exclude_id]

        def path_of(node) -> str:
            parts = []
            cur = node
            while cur:
                parts.insert(0, cur.name)
                cur = node_by_id.get(cur.parent_id) if cur.parent_id else None
            return " / ".join(parts)

        for f in folders:
            self.combo.addItem(path_of(f), f.id)

        form.addRow("Destination:", self.combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_parent_id(self):
        return self.combo.currentData()


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class RepertoireTreeWidget(QWidget):
    """
    Left-panel Repertoire Manager.

    The widget owns the RepertoireRepository and provides a full
    file-explorer-like UI.  It emits high-level signals so the
    ApplicationController can bridge to the Chess Analyzer.
    """

    # Emitted when the user wants to open a repertoire in the editor.
    # Carries the node_id (int) and the PGN text (str).
    repertoireOpenRequested = pyqtSignal(int, str)

    def __init__(self, repo: RepertoireRepository, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.setMinimumWidth(220)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header bar
        header = self._build_header()
        root_layout.addWidget(header)

        # Tree
        self.tree = _RepertoireTreeView(self)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        self.tree.nodeMoved.connect(self._on_node_dropped)
        self.tree.setStyleSheet(self._tree_style())
        self.tree.setFont(QFont("Segoe UI", 10))
        self.tree.setIndentation(20)
        self.tree.setIconSize(QSize(18, 18))
        root_layout.addWidget(self.tree, 1)

        # Bottom toolbar
        bottom = self._build_bottom_bar()
        root_layout.addWidget(bottom)

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(34)
        w.setStyleSheet("""
            QWidget { background: #21201d; border-bottom: 1px solid #312e2b; }
        """)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignVCenter)

        # Spacer so buttons sit at the right edge
        layout.addStretch()

        # New folder button
        btn_folder = QPushButton()
        btn_folder.setIcon(qta.icon("fa5s.folder-plus", color="#a9aea7"))
        btn_folder.setIconSize(QSize(14, 14))
        btn_folder.setToolTip("New Folder")
        btn_folder.setFixedSize(24, 24)
        btn_folder.setCursor(Qt.PointingHandCursor)
        btn_folder.setStyleSheet(self._icon_button_style())
        btn_folder.clicked.connect(self._new_folder_at_root)
        layout.addWidget(btn_folder, 0, Qt.AlignVCenter)

        # New repertoire button
        btn_rep = QPushButton()
        btn_rep.setIcon(qta.icon("fa5s.plus", color="#a9aea7"))
        btn_rep.setIconSize(QSize(14, 14))
        btn_rep.setToolTip("New Repertoire")
        btn_rep.setFixedSize(24, 24)
        btn_rep.setCursor(Qt.PointingHandCursor)
        btn_rep.setStyleSheet(self._icon_button_style())
        btn_rep.clicked.connect(self._new_repertoire_at_root)
        layout.addWidget(btn_rep, 0, Qt.AlignVCenter)

        return w

    def _build_bottom_bar(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(34)
        w.setStyleSheet("""
            QWidget { background: #21201d; border-top: 1px solid #312e2b; }
        """)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignVCenter)

        def _small_btn(icon_name, tooltip, slot):
            b = QPushButton()
            b.setIcon(qta.icon(icon_name, color="#a9aea7"))
            b.setIconSize(QSize(14, 14))
            b.setToolTip(tooltip)
            b.setFixedSize(24, 24)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(self._icon_button_style())
            b.clicked.connect(slot)
            return b

        layout.addWidget(_small_btn("fa5s.file-import",  "Import PGN",  self._import_pgn), 0, Qt.AlignVCenter)
        layout.addWidget(_small_btn("fa5s.file-export",  "Export PGN",  self._export_pgn), 0, Qt.AlignVCenter)
        layout.addStretch()
        layout.addWidget(_small_btn("fa5s.sync-alt",     "Refresh",     self.refresh), 0, Qt.AlignVCenter)

        return w

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload the whole tree from the database."""
        # Snapshot expanded state
        expanded_ids = set()
        self._collect_expanded(self.tree.invisibleRootItem(), expanded_ids)

        self.tree.clear()
        all_nodes = self._repo.get_all_nodes()
        node_by_id = {n.id: n for n in all_nodes}

        # Build QTreeWidgetItems top-down (parents first, which is guaranteed
        # by the ORDER BY sort_order, name)
        item_by_id: dict[int, QTreeWidgetItem] = {}

        def add_node(node: RepertoireNode, parent_item):
            item = QTreeWidgetItem(parent_item)
            item.setText(0, node.name)
            item.setData(0, NODE_ID_ROLE,   node.id)
            item.setData(0, NODE_TYPE_ROLE, node.node_type)

            if node.is_folder():
                item.setIcon(0, qta.icon("fa5s.folder", color="#fb923c"))
                item.setForeground(0, FOLDER_COLOR)
                item.setFlags(item.flags() | Qt.ItemIsDropEnabled)
            else:
                item.setIcon(0, qta.icon("fa5s.chess-knight", color="#cbd5e1"))
                item.setForeground(0, REPERTOIRE_COLOR)
                item.setFlags(item.flags() & ~Qt.ItemIsDropEnabled)

            item_by_id[node.id] = item
            return item

        # First pass: roots
        for n in all_nodes:
            if n.parent_id is None:
                add_node(n, self.tree)

        # Subsequent passes until all placed (handles arbitrary depth)
        remaining = [n for n in all_nodes if n.parent_id is not None]
        max_passes = 20
        passes = 0
        while remaining and passes < max_passes:
            still_remaining = []
            for n in remaining:
                if n.parent_id in item_by_id:
                    add_node(n, item_by_id[n.parent_id])
                else:
                    still_remaining.append(n)
            remaining = still_remaining
            passes += 1

        # Restore expanded state
        self._restore_expanded(self.tree.invisibleRootItem(), expanded_ids)

    def _collect_expanded(self, parent_item, result: set):
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.isExpanded():
                nid = child.data(0, NODE_ID_ROLE)
                if nid:
                    result.add(nid)
            self._collect_expanded(child, result)

    def _restore_expanded(self, parent_item, expanded_ids: set):
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            nid = child.data(0, NODE_ID_ROLE)
            if nid in expanded_ids:
                child.setExpanded(True)
                if child.data(0, NODE_TYPE_ROLE) == "folder":
                    child.setIcon(0, qta.icon("fa5s.folder-open", color="#fb923c"))
            self._restore_expanded(child, expanded_ids)

    def _on_item_expanded(self, item: QTreeWidgetItem):
        if item.data(0, NODE_TYPE_ROLE) == "folder":
            item.setIcon(0, qta.icon("fa5s.folder-open", color="#fb923c"))

    def _on_item_collapsed(self, item: QTreeWidgetItem):
        if item.data(0, NODE_TYPE_ROLE) == "folder":
            item.setIcon(0, qta.icon("fa5s.folder", color="#fb923c"))

    def _is_descendant(self, node_id: int, candidate_parent_id) -> bool:
        """Return True if candidate_parent_id is node_id or a descendant of node_id."""
        if candidate_parent_id is None:
            return False
        if node_id == candidate_parent_id:
            return True

        cur_id = candidate_parent_id
        visited = set()
        while cur_id is not None and cur_id not in visited:
            visited.add(cur_id)
            node = self._repo.get_node(cur_id)
            if not node:
                break
            if node.parent_id == node_id:
                return True
            cur_id = node.parent_id
        return False

    def _on_node_dropped(self, dragged_id: int, new_parent_id):
        """Persist drag-and-drop hierarchy changes to the database."""
        if self._is_descendant(dragged_id, new_parent_id):
            return
        self._repo.move_node(dragged_id, new_parent_id)
        self.refresh()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(self._menu_style())

        if item is None:
            # Clicked on empty space — only allow creation at root
            menu.addAction(qta.icon("fa5s.folder-plus", color="#fb923c"),
                           "New Folder",       self._new_folder_at_root)
            menu.addAction(qta.icon("fa5s.plus", color="#cbd5e1"),
                           "New Repertoire",   self._new_repertoire_at_root)
        else:
            node_type = item.data(0, NODE_TYPE_ROLE)

            if node_type == "folder":
                menu.addAction(qta.icon("fa5s.folder-plus", color="#fb923c"),
                               "New Subfolder",   lambda: self._new_folder(item))
                menu.addAction(qta.icon("fa5s.plus", color="#cbd5e1"),
                               "New Repertoire",  lambda: self._new_repertoire(item))
                menu.addSeparator()

            if node_type == "repertoire":
                menu.addAction(qta.icon("fa5s.chess-knight", color="#cbd5e1"),
                               "Open",            lambda: self._open_repertoire(item))
                menu.addSeparator()

            menu.addAction(qta.icon("fa5s.pen", color="#e6912c"),
                           "Rename",              lambda: self._rename(item))
            menu.addAction(qta.icon("fa5s.arrows-alt", color="#9ca3af"),
                           "Move…",               lambda: self._move(item))
            menu.addSeparator()

            if node_type == "repertoire":
                menu.addAction(qta.icon("fa5s.file-import", color="#a9aea7"),
                               "Import PGN…",     lambda: self._import_pgn_into(item))
                menu.addAction(qta.icon("fa5s.file-export", color="#a9aea7"),
                               "Export PGN…",     lambda: self._export_pgn_of(item))
                menu.addSeparator()

            act_del = menu.addAction(qta.icon("fa5s.trash-alt", color="#f87171"),
                                     "Delete")
            act_del.triggered.connect(lambda: self._delete(item))

        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Double-click
    # ------------------------------------------------------------------

    def _on_double_click(self, item: QTreeWidgetItem, col: int):
        node_type = item.data(0, NODE_TYPE_ROLE)
        if node_type == "repertoire":
            self._open_repertoire(item)
        elif node_type == "folder":
            item.setExpanded(not item.isExpanded())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _current_parent_id(self, item: QTreeWidgetItem | None) -> int | None:
        """Return node_id of *item* if it's a folder, or its parent if it's a repertoire."""
        if item is None:
            return None
        node_type = item.data(0, NODE_TYPE_ROLE)
        if node_type == "folder":
            return item.data(0, NODE_ID_ROLE)
        # repertoire → use its parent folder
        parent = item.parent()
        if parent is not None:
            pt = parent.data(0, NODE_TYPE_ROLE)
            if pt == "folder":
                return parent.data(0, NODE_ID_ROLE)
        return None

    def _new_folder_at_root(self):
        self._new_folder(None)

    def _new_folder(self, parent_item: QTreeWidgetItem | None):
        name = _ask_name(self, "New Folder", "Folder name:")
        if name is None:
            return
        parent_id = self._current_parent_id(parent_item) if parent_item else None
        self._repo.create_folder(name, parent_id)
        self.refresh()

    def _new_repertoire_at_root(self):
        self._new_repertoire(None)

    def _new_repertoire(self, parent_item: QTreeWidgetItem | None):
        name = _ask_name(self, "New Repertoire", "Repertoire name:")
        if name is None:
            return
        parent_id = self._current_parent_id(parent_item) if parent_item else None
        node = self._repo.create_repertoire(name, parent_id)
        self.refresh()
        # Auto-open for editing
        self.repertoireOpenRequested.emit(node.id, "")

    def _open_repertoire(self, item: QTreeWidgetItem):
        node_id = item.data(0, NODE_ID_ROLE)
        pgn = self._repo.get_pgn(node_id)
        self.repertoireOpenRequested.emit(node_id, pgn)

    def _rename(self, item: QTreeWidgetItem):
        node_id   = item.data(0, NODE_ID_ROLE)
        old_name  = item.text(0)
        new_name  = _ask_name(self, "Rename", "New name:", old_name)
        if new_name is None or new_name == old_name:
            return
        self._repo.rename_node(node_id, new_name)
        item.setText(0, new_name)

    def _move(self, item: QTreeWidgetItem):
        node_id   = item.data(0, NODE_ID_ROLE)
        all_nodes = self._repo.get_all_nodes()
        dlg = MoveFolderDialog(all_nodes, exclude_id=node_id, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_parent_id = dlg.selected_parent_id()
        if new_parent_id == node_id:
            return  # cannot move into self
        self._repo.move_node(node_id, new_parent_id)
        self.refresh()

    def _delete(self, item: QTreeWidgetItem):
        node_id   = item.data(0, NODE_ID_ROLE)
        node_type = item.data(0, NODE_TYPE_ROLE)
        name      = item.text(0)

        extra = " and all its contents" if node_type == "folder" else ""
        answer = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete '{name}'{extra}?  This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self._repo.delete_node(node_id)
        self.refresh()

    # -- PGN import / export -------------------------------------------

    def _import_pgn(self):
        """Import a PGN file as a new repertoire (asks for destination folder)."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import PGN", ".", "PGN Files (*.pgn);;All Files (*)"
        )
        if not path:
            return

        name = _ask_name(self, "Import PGN",
                         "Repertoire name:", os.path.splitext(os.path.basename(path))[0])
        if name is None:
            return

        # Pick parent folder
        all_nodes = self._repo.get_all_nodes()
        dlg = MoveFolderDialog(all_nodes, exclude_id=-1, parent=self)
        dlg.setWindowTitle("Import Into Folder")
        parent_id = None
        if dlg.exec_() == QDialog.Accepted:
            parent_id = dlg.selected_parent_id()

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                pgn_text = f.read()
        except Exception as e:
            QMessageBox.warning(self, "Import Error", str(e))
            return

        self._repo.import_pgn_as_repertoire(name, pgn_text, parent_id)
        self.refresh()

    def _import_pgn_into(self, item: QTreeWidgetItem):
        """Import a PGN file, replacing the content of an existing repertoire."""
        node_id = item.data(0, NODE_ID_ROLE)
        path, _ = QFileDialog.getOpenFileName(
            self, "Import PGN", ".", "PGN Files (*.pgn);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                pgn_text = f.read()
        except Exception as e:
            QMessageBox.warning(self, "Import Error", str(e))
            return
        self._repo.save_pgn(node_id, pgn_text)
        QMessageBox.information(self, "Import", "PGN imported successfully.")

    def _export_pgn(self):
        """Export the selected repertoire's PGN to a file."""
        item = self.tree.currentItem()
        if item is None or item.data(0, NODE_TYPE_ROLE) != "repertoire":
            QMessageBox.information(self, "Export PGN",
                                    "Select a repertoire first.")
            return
        self._export_pgn_of(item)

    def _export_pgn_of(self, item: QTreeWidgetItem):
        node_id  = item.data(0, NODE_ID_ROLE)
        pgn_text = self._repo.get_pgn(node_id)
        if not pgn_text.strip():
            QMessageBox.information(self, "Export PGN",
                                    "This repertoire is empty.")
            return

        default_name = item.text(0).replace(" ", "_") + ".pgn"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PGN", default_name, "PGN Files (*.pgn);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(pgn_text)
        except Exception as e:
            QMessageBox.warning(self, "Export Error", str(e))

    # ------------------------------------------------------------------
    # Public API (called by ApplicationController)
    # ------------------------------------------------------------------

    def on_repertoire_saved(self, node_id: int, pgn_text: str):
        """Called by the controller when the editor emits a save signal."""
        self._repo.save_pgn(node_id, pgn_text)
        self.refresh()

    # ------------------------------------------------------------------
    # Styling helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tree_style() -> str:
        return """
        QTreeWidget {
            background-color: #262421;
            border: none;
            color: #e5e7eb;
            outline: none;
        }
        QTreeWidget::item {
            padding: 6px 4px;
            border-bottom: 1px solid #21201d;
            border-radius: 4px;
        }
        QTreeWidget::item:hover {
            background-color: #312e2b;
            color: #ffffff;
        }
        QTreeWidget::item:selected {
            background-color: #403d39;
            color: #ffffff;
        }
        """

    @staticmethod
    def _icon_button_style() -> str:
        return """
        QPushButton {
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 3px;
            padding: 0px;
            margin: 0px;
            min-width: 0px;
            min-height: 0px;
        }
        QPushButton:hover {
            background-color: #312e2b;
            border: 1px solid #403d39;
        }
        QPushButton:pressed {
            background-color: #21201d;
        }
        """

    @staticmethod
    def _menu_style() -> str:
        return """
        QMenu {
            background: #262421;
            border: 1px solid #403d39;
            border-radius: 4px;
            padding: 4px;
            color: #bababa;
            font-size: 13px;
        }
        QMenu::item {
            padding: 6px 20px 6px 10px;
            border-radius: 3px;
            margin: 1px 2px;
        }
        QMenu::item:selected {
            background: #312e2b;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background: #403d39;
            margin: 4px 8px;
        }
        """
