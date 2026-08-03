import os
import shutil
from PyQt5.QtCore import pyqtSignal, QProcess


class PGNIndexerProcess(QProcess):
    """Asynchronously runs the pgn-indexer Rust binary to index a PGN file into SQLite.

    Signals:
        finishedSuccessfully(str): Emitted with the SQLite DB path on success.
        indexingError(str): Emitted with error details on failure.
        progressMessage(str): Emitted with stdout/stderr lines during indexing.
    """

    finishedSuccessfully = pyqtSignal(str)  # Emits the SQLite DB path
    indexingError = pyqtSignal(str)
    progressMessage = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProcessChannelMode(QProcess.MergedChannels)
        self.readyReadStandardOutput.connect(self._read_output)
        self.finished.connect(self._on_finished)
        # Catch process start failures (e.g. executable not found)
        self.errorOccurred.connect(self._on_process_error)
        self.db_path = None
        self.output_buffer = ""

    def index_pgn(self, pgn_path: str):
        """Start indexing the given PGN file. The database is created at pgn_path + '.db'."""
        self.output_buffer = ""
        self.db_path = pgn_path + ".db"

        exe_path = self._find_executable()
        if exe_path is None:
            self.indexingError.emit(
                "pgn_indexer executable not found.\n"
                "Build it with: cd pgn-indexer && cargo build --release"
            )
            return

        self.setProgram(exe_path)
        self.setArguments([pgn_path, self.db_path])
        self.start()

    def _find_executable(self):
        """Resolve the pgn_indexer executable path.

        Search order:
          1. pgn-indexer submodule release build
          2. pgn-indexer submodule debug build
          3. System PATH (via shutil.which)
        """
        # Project root: src/core/indexer.py -> src/ -> qchess/
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(app_dir)

        candidates = [
            os.path.join(project_root, "pgn-indexer", "target", "release", "pgn_indexer.exe"),
            os.path.join(project_root, "pgn-indexer", "target", "debug", "pgn_indexer.exe"),
        ]

        for path in candidates:
            if os.path.isfile(path):
                return path

        # Fallback: system PATH
        which_result = shutil.which("pgn_indexer") or shutil.which("pgn_indexer.exe")
        if which_result:
            return which_result

        return None

    def _read_output(self):
        data = self.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self.output_buffer += data
        self.progressMessage.emit(data.strip())

    def _on_finished(self, exit_code, exit_status):
        if exit_code == 0:
            self.finishedSuccessfully.emit(self.db_path)
        else:
            self.indexingError.emit(
                f"Indexer failed with code {exit_code}:\n{self.output_buffer}"
            )

    def _on_process_error(self, error):
        """Handle QProcess errors like FailedToStart."""
        error_map = {
            QProcess.FailedToStart: "Failed to start pgn_indexer (executable not found or not executable)",
            QProcess.Crashed: "pgn_indexer process crashed",
            QProcess.Timedout: "pgn_indexer process timed out",
            QProcess.WriteError: "Write error communicating with pgn_indexer",
            QProcess.ReadError: "Read error communicating with pgn_indexer",
            QProcess.UnknownError: "Unknown error running pgn_indexer",
        }
        msg = error_map.get(error, f"QProcess error code: {error}")
        self.indexingError.emit(msg)
