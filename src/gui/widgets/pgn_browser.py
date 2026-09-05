import re

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QMenu,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
)

from core.move_manager import MoveManager


class CommentDialog(QDialog):
    def __init__(self, parent, comment: str = ""):
        super().__init__(parent)
        self.comment = comment
        self.setWindowTitle("Comments")
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.textedit = QTextEdit()
        self.textedit.setPlainText(comment)
        layout.addWidget(self.textedit)
        buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttonbox)
        buttonbox.accepted.connect(self.on_accepted)
        buttonbox.rejected.connect(self.close)

    def on_accepted(self):
        self.comment = self.textedit.toPlainText()
        self.accept()


class PGNBrowser(QTextBrowser):
    def __init__(self, parent, movemanager: MoveManager):
        super().__init__(parent)
        self.movemanager = movemanager
        self.setOpenLinks(False)
        self.setStyleSheet("QTextBrowser {font-size:20px;font-family: Noto Sans;}")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_custom_context)
        # self.anchorClicked.connect(self.on_anchor_clicked)

    def setHtml(self, html: str):
        super().setHtml(html)
        self.scroll_to_current()

    def scroll_to_current(self):
        node = self.movemanager.current_node
        if node and hasattr(node, "flat_index"):
            idx = node.flat_index
            self.scrollToAnchor(f"m{idx}")

    def on_custom_context(self, point):
        anchor = self.anchorAt(point)
        if not anchor:
            return

        import qtawesome as qta

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: palette(window);
                color: palette(text);
                border: 1px solid palette(mid);
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px 6px 12px;
                margin: 2px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            QMenu::separator {
                height: 1px;
                background-color: palette(mid);
                margin: 4px 8px;
            }
        """)

        import qtawesome as qta

        node_index = self.match_node(anchor)
        current_nags = set()
        if node_index is not None:
            node = self.movemanager.get_node_by_index(node_index)
            current_nags = getattr(node, "nags", set())

        # --- Move Evaluation Submenu ---
        if node_index is not None:
            move_eval_menu = menu.addMenu("Move Evaluation")
            move_eval_options = [
                (1, "Good move (!)"),
                (2, "Poor or mistake move (?)"),
                (3, "Excellent or brilliant move (!!)"),
                (4, "Blunder (??)"),
                (5, "Interesting move (!?)"),
                (6, "Dubious move (?!)"),
                (9, "Miss"),
            ]
            for nag_id, label in move_eval_options:
                act = QAction(label, self)
                act.setCheckable(True)
                act.setChecked(nag_id in current_nags)
                act.triggered.connect(lambda checked, idx=node_index, n=nag_id: self.movemanager.set_move_nag(idx, n))
                move_eval_menu.addAction(act)

            # --- Position Evaluation Submenu ---
            pos_eval_menu = menu.addMenu("Position Evaluation")
            pos_eval_options = [
                (10, "Equal position (=)"),
                (14, "White has a slight advantage (+=)"),
                (15, "Black has a slight advantage (=+)"),
                (16, "White has a moderate advantage (+/-)"),
                (17, "Black has a moderate advantage (-/+)"),
                (18, "White has a decisive advantage (+-)"),
                (19, "Black has a decisive advantage (-+)"),
            ]
            for nag_id, label in pos_eval_options:
                act = QAction(label, self)
                act.setCheckable(True)
                act.setChecked(nag_id in current_nags)
                act.triggered.connect(lambda checked, idx=node_index, n=nag_id: self.movemanager.set_pos_nag(idx, n))
                pos_eval_menu.addAction(act)

            clear_eval_act = QAction("Clear Evaluation", self)
            clear_eval_act.triggered.connect(lambda checked, idx=node_index: self.movemanager.clear_nags(idx))
            menu.addAction(clear_eval_act)

            # --- Add Engine Evaluation (only when engine is enabled) ---
            if self.is_engine_enabled():
                eval_score = self.get_current_engine_eval()
                eval_label = f"Add Eval ({eval_score})" if eval_score else "Add Eval"
                add_eval_act = QAction(qta.icon("fa5s.chart-line", color="#a9aea7"), eval_label, self)
                add_eval_act.triggered.connect(lambda checked, idx=node_index: self.on_add_eval(idx))
                menu.addAction(add_eval_act)

            menu.addSeparator()

        actions = [
            ("Edit Comment...", self.on_add_comment, "fa5s.comment-alt"),
            (None, None, None),  # Separator
            ("Promote to Main Line", self.on_promote_to_main, "fa5s.arrow-up"),
            ("Promote Move", self.on_promote, "fa5s.chevron-up"),
            ("Demote Move", self.on_demote, "fa5s.chevron-down"),
            ("Delete from Here", self.on_delete, "fa5s.trash-alt"),
        ]

        for name, func, icon_name in actions:
            if name is None:
                menu.addSeparator()
            else:
                icon = qta.icon(icon_name) if icon_name else None
                act = QAction(icon, name, self) if icon else QAction(name, self)
                act.triggered.connect(lambda checked, f=func: f(anchor))
                menu.addAction(act)

        menu.exec_(self.mapToGlobal(point))

    def on_add_comment(self, anchor):
        node_index = self.match_node(anchor)
        if node_index is not None:
            node = self.movemanager.get_node_by_index(node_index)
            dlg = CommentDialog(self, node.comment)
            if dlg.exec_() != QDialog.Accepted:
                return
            self.movemanager.add_comment(node_index, dlg.comment)

    def on_promote_to_main(self, anchor):
        node_index = self.match_node(anchor)
        if node_index is not None:
            self.movemanager.promote_to_main(node_index)

    def on_promote(self, anchor):
        node_index = self.match_node(anchor)
        if node_index is not None:
            self.movemanager.promote(node_index)

    def on_demote(self, anchor):
        node_index = self.match_node(anchor)
        if node_index is not None:
            self.movemanager.demote(node_index)

    def on_delete(self, anchor):
        node_index = self.match_node(anchor)
        if node_index is not None:
            self.movemanager.delete_from_here(node_index)

    def match_node(self, anchor: str) -> int | None:
        match = re.match(r"move\((\d+)\)", anchor)
        if match:
            try:
                index = int(match.group(1))
                return index
            except ValueError:
                return None
        return None

    def is_engine_enabled(self) -> bool:
        app = self.window()
        if hasattr(app, "analysis_widget") and hasattr(app.analysis_widget, "check_analysis"):
            return app.analysis_widget.check_analysis.isChecked()
        return False

    def get_current_engine_eval(self) -> str | None:
        app = self.window()
        if hasattr(app, "get_current_engine_eval"):
            return app.get_current_engine_eval()
        return None

    def on_add_eval(self, node_index: int):
        eval_score = self.get_current_engine_eval()
        if eval_score:
            self.movemanager.set_eval_annotation(node_index, eval_score)

    def on_anchor_clicked(self, url: QUrl):
        match = re.match(r"move\((\d+)\)", url.toString())
        if match:
            print("Clicked move:", match.group(1))


if __name__ == "__main__":
    app = QApplication([])
    browser = PGNBrowser(None, MoveManager())
    browser.show()
    app.exec_()
