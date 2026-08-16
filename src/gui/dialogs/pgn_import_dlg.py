from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QDialogButtonBox,
    QLabel,
    QGroupBox,
    QGridLayout,
    QCheckBox,
)


class PGNImportDlg(QDialog):
    def __init__(self, parent=None, initial_text=""):
        super().__init__(parent)
        self.setWindowTitle("Import PGN")
        self.resize(650, 480)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Paste or edit your PGN here:"))
        
        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("1. e4 e5 ...")
        self.text_edit.setPlainText(initial_text)
        layout.addWidget(self.text_edit)
        
        # --- PGN Cleaning Options ---
        clean_group = QGroupBox("PGN Cleaning Options before Import")
        clean_layout = QGridLayout(clean_group)
        
        self.cb_delete_clk = QCheckBox("Delete clock [%clk]")
        self.cb_delete_eval = QCheckBox("Delete evaluations [%eval]")
        self.cb_remove_all_ann = QCheckBox("Remove all [%...] annotations")
        self.cb_delete_comments = QCheckBox("Delete comments")
        self.cb_remove_variations = QCheckBox("Remove variations")
        
        clean_layout.addWidget(self.cb_delete_clk, 0, 0)
        clean_layout.addWidget(self.cb_delete_eval, 0, 1)
        clean_layout.addWidget(self.cb_remove_all_ann, 0, 2)
        clean_layout.addWidget(self.cb_delete_comments, 1, 0)
        clean_layout.addWidget(self.cb_remove_variations, 1, 1)
        
        layout.addWidget(clean_group)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.button(QDialogButtonBox.Ok).setText("Import")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_pgn(self):
        pgn_text = self.text_edit.toPlainText().strip()
        
        del_clk = self.cb_delete_clk.isChecked()
        del_eval = self.cb_delete_eval.isChecked()
        del_comm = self.cb_delete_comments.isChecked()
        rem_var = self.cb_remove_variations.isChecked()
        rem_ann = self.cb_remove_all_ann.isChecked()
        
        if del_clk or del_eval or del_comm or rem_var or rem_ann:
            import io
            import re
            import chess.pgn
            
            try:
                game = chess.pgn.read_game(io.StringIO(pgn_text))
                if game:
                    def visit(node):
                        if rem_var:
                            if node.variations:
                                node.variations = [node.variations[0]]
                        if del_comm:
                            node.comment = ""
                        else:
                            comment = node.comment
                            if comment:
                                if rem_ann:
                                    comment = re.sub(r'\[%[^\]]+\]', '', comment)
                                else:
                                    if del_clk:
                                        comment = re.sub(r'\[%clk\s+[^\]]+\]', '', comment)
                                    if del_eval:
                                        comment = re.sub(r'\[%eval\s+[^\]]+\]', '', comment)
                                node.comment = comment.strip()
                                
                        for child in node.variations:
                            visit(child)
                            
                    visit(game)
                    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
                    pgn_text = game.accept(exporter)
            except Exception:
                pass
                
        return pgn_text.strip()
