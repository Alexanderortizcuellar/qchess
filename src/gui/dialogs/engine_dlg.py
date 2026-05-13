import qtawesome as qta
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QCheckBox,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
)
from PyQt5.QtCore import QSettings


class EngineConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chess Engine Configuration")
        self.resize(520, 420)

        self.settings = QSettings("TestChessApp", "Engine")

        main = QVBoxLayout(self)

        # ───────────── Engine
        engine_group = QGroupBox(" Engine")
        engine_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        e_layout = QHBoxLayout(engine_group)

        self.engine_path = QLineEdit()
        self.engine_path.setPlaceholderText("Engine executable")

        browse_engine = QPushButton()
        browse_engine.setIcon(qta.icon("ei.folder-open"))
        browse_engine.clicked.connect(self.browse_engine)

        e_layout.addWidget(self.engine_path)
        e_layout.addWidget(browse_engine)

        # ───────────── Search
        search_group = QGroupBox(" Search")
        search_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        s_form = QFormLayout(search_group)

        self.threads = QSpinBox()
        self.threads.setRange(1, 128)

        self.depth = QSpinBox()
        self.depth.setRange(1, 99)

        self.multipv = QSpinBox()
        self.multipv.setRange(1, 50)

        self.hash = QSpinBox()
        self.hash.setRange(16, 65536)
        self.hash.setSuffix(" MB")

        s_form.addRow("Threads:", self.threads)
        s_form.addRow("Depth:", self.depth)
        s_form.addRow("Lines (MultiPV):", self.multipv)
        s_form.addRow("Hash:", self.hash)

        # ───────────── Advanced
        adv_group = QGroupBox(" Advanced")
        adv_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        a_form = QFormLayout(adv_group)

        self.skill = QSpinBox()
        self.skill.setRange(0, 20)

        self.syzygy_path = QLineEdit()

        browse_syzygy = QPushButton()
        browse_syzygy.setIcon(qta.icon("ei.folder"))
        browse_syzygy.clicked.connect(self.browse_syzygy)

        tb_layout = QHBoxLayout()
        tb_layout.addWidget(self.syzygy_path)
        tb_layout.addWidget(browse_syzygy)

        self.ponder = QCheckBox("Enable pondering")
        self.ponder.setIcon(qta.icon("fa5.clock"))

        a_form.addRow("Skill Level:", self.skill)
        a_form.addRow("Syzygy:", tb_layout)
        a_form.addRow(self.ponder)

        # ───────────── Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setIcon(qta.icon("ei.check"))
        buttons.button(QDialogButtonBox.Cancel).setIcon(qta.icon("fa5s.times"))

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        main.addWidget(engine_group)
        main.addWidget(search_group)
        main.addWidget(adv_group)
        main.addWidget(buttons)

        self.load()

    # ───────────── Helpers
    def browse_engine(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Engine")
        if path:
            self.engine_path.setText(path)

    def browse_syzygy(self):
        path = QFileDialog.getExistingDirectory(self, "Syzygy Path")
        if path:
            self.syzygy_path.setText(path)

    # ───────────── Settings
    def load(self):
        self.engine_path.setText(self.settings.value("path", ""))
        self.threads.setValue(int(self.settings.value("threads", 4)))
        self.depth.setValue(int(self.settings.value("depth", 20)))
        self.multipv.setValue(int(self.settings.value("multipv", 1)))
        self.hash.setValue(int(self.settings.value("hash", 1024)))
        self.skill.setValue(int(self.settings.value("skill", 20)))
        self.ponder.setChecked(self.settings.value("ponder", False, bool))
        self.syzygy_path.setText(self.settings.value("syzygy", ""))

    def accept(self):
        self.settings.setValue("path", self.engine_path.text())
        self.settings.setValue("threads", self.threads.value())
        self.settings.setValue("depth", self.depth.value())
        self.settings.setValue("multipv", self.multipv.value())
        self.settings.setValue("hash", self.hash.value())
        self.settings.setValue("skill", self.skill.value())
        self.settings.setValue("ponder", self.ponder.isChecked())
        self.settings.setValue("syzygy", self.syzygy_path.text())
        super().accept()

    def get_config(self):
        return {
            "path": self.engine_path.text(),
            "threads": self.threads.value(),
            "depth": self.depth.value(),
            "multipv": self.multipv.value(),
            "hash": self.hash.value(),
            "skill": self.skill.value(),
            "ponder": self.ponder.isChecked(),
            "syzygy": self.syzygy_path.text(),
        }
