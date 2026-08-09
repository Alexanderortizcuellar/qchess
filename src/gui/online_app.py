import re
import sys
import chess
from PyQt5.QtCore import Qt, QTimer, QUrl, QDateTime
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QMessageBox,
    QTableWidgetItem,
    QComboBox,
    QSpinBox,
)
from core.network_client import ChessClient
from gui.widgets.chessboard import ChessBoard
from gui.widgets.painter_pgn_browser import QPainterPGNBrowser
from core.move_manager import MoveManager


class OnlineChessApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QChess Online")
        self.resize(1000, 800)

        self.client = ChessClient(self)
        self.move_manager = MoveManager()
        self.current_game_id = None
        self.my_color = None  # 'white' or 'black' or None (spectator)
        self.my_game_roles = {}  # Track game_id -> color
        self.opponent_joined = False

        self.white_time_ms = 0
        self.black_time_ms = 0
        self.side_to_move = None
        self.last_update_ms = 0
        self.game_status = "ongoing"

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer_tick)
        self.timer.start(100)  # Update every 100ms

        self.init_ui()
        self.setup_signals()

    def init_ui(self):
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # 1. Connection Screen (Modernized)
        self.conn_widget = QWidget()
        self.conn_widget.setObjectName("conn_screen")
        conn_layout = QVBoxLayout(self.conn_widget)
        conn_layout.setContentsMargins(50, 50, 50, 50)
        conn_layout.addStretch()

        title = QLabel("Connect to QChess Server")
        title.setStyleSheet("font-size: 32px; font-weight: bold; margin-bottom: 20px;")
        conn_layout.addWidget(title, alignment=Qt.AlignCenter)

        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)

        self.url_input = QLineEdit("ws://localhost:8080/ws")
        self.url_input.setPlaceholderText("Server WebSocket URL")
        self.url_input.setFixedWidth(400)
        self.url_input.setStyleSheet("padding: 10px; font-size: 16px;")
        form_layout.addWidget(self.url_input, alignment=Qt.AlignCenter)

        self.connect_btn = QPushButton("Join Server")
        self.connect_btn.setFixedWidth(200)
        self.connect_btn.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; color: white; padding: 12px; 
                font-size: 18px; border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        form_layout.addWidget(self.connect_btn, alignment=Qt.AlignCenter)

        conn_layout.addWidget(form_widget, alignment=Qt.AlignCenter)
        conn_layout.addStretch()
        self.stacked_widget.addWidget(self.conn_widget)

        # 2. Lobby Screen (Modernized with Tabs and Tables)
        self.lobby_widget = QWidget()
        lobby_layout = QVBoxLayout(self.lobby_widget)
        lobby_layout.setContentsMargins(20, 20, 20, 20)

        lobby_header = QHBoxLayout()
        header_text = QLabel("Game Lobby")
        header_text.setStyleSheet("font-size: 28px; font-weight: bold;")
        lobby_header.addWidget(header_text)
        lobby_header.addStretch()

        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.client.list_games)
        lobby_header.addWidget(self.refresh_btn)
        lobby_layout.addLayout(lobby_header)

        # Create Game Area
        create_box = QWidget()
        create_box.setStyleSheet("""
            QWidget { 
                background: #312e2b; 
                border: 1px solid #403d39; 
                border-radius: 8px; 
            }
            QLabel { background: transparent; color: #bababa; }
            QSpinBox { 
                background: #262421; 
                color: white; 
                border: 1px solid #403d39; 
                padding: 4px; 
                border-radius: 4px;
                min-width: 60px;
            }
        """)
        create_layout = QHBoxLayout(create_box)
        create_layout.setSpacing(15)

        lbl = QLabel("Create Game:")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        create_layout.addWidget(lbl)

        # Game Type
        create_layout.addWidget(QLabel("Type:"))
        self.game_type_combo = QComboBox()
        self.game_type_combo.addItems(["Sudden Death", "Increment"])
        self.game_type_combo.setStyleSheet("""
            QComboBox {
                background: #262421;
                color: white;
                border: 1px solid #403d39;
                padding: 4px;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView {
                background: #262421;
                color: white;
                selection-background-color: #e6912c;
            }
        """)
        self.game_type_combo.currentIndexChanged.connect(self.on_game_type_changed)
        create_layout.addWidget(self.game_type_combo)

        # Base Time
        self.base_time_lbl = QLabel("Time (min):")
        create_layout.addWidget(self.base_time_lbl)
        self.base_time_spin = QSpinBox()
        self.base_time_spin.setRange(1, 180)
        self.base_time_spin.setValue(10)
        create_layout.addWidget(self.base_time_spin)

        # Increment (Initially Hidden)
        self.inc_time_lbl = QLabel("Inc (sec):")
        self.inc_time_lbl.hide()
        create_layout.addWidget(self.inc_time_lbl)
        self.inc_time_spin = QSpinBox()
        self.inc_time_spin.setRange(0, 60)
        self.inc_time_spin.setValue(2)
        self.inc_time_spin.hide()
        create_layout.addWidget(self.inc_time_spin)

        self.create_custom_btn = QPushButton("Create Game")
        self.create_custom_btn.setStyleSheet("""
            QPushButton { 
                background-color: #27ae60; 
                color: white; 
                padding: 8px 15px; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        self.create_custom_btn.clicked.connect(self.on_create_custom_clicked)
        create_layout.addWidget(self.create_custom_btn)

        create_layout.addStretch()
        lobby_layout.addWidget(create_box)

        # Tabs for Challenges vs Ongoing
        from PyQt5.QtWidgets import QTabWidget, QTableWidget, QHeaderView

        self.tabs = QTabWidget()

        # Challenges Tab
        self.challenges_table = QTableWidget(0, 3)
        self.challenges_table.setHorizontalHeaderLabels(
            ["Game ID", "Time Control", "Action"]
        )
        self.challenges_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.challenges_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.challenges_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.challenges_table.cellDoubleClicked.connect(self.on_challenge_cell_clicked)

        # Ongoing Tab
        self.ongoing_table = QTableWidget(0, 4)
        self.ongoing_table.setHorizontalHeaderLabels(
            ["Game ID", "White", "Black", "Time"]
        )
        self.ongoing_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ongoing_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ongoing_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ongoing_table.cellDoubleClicked.connect(self.on_ongoing_cell_clicked)

        # Apply dark theme to tables for better contrast
        table_style = """
            QTableWidget {
                background-color: #262421;
                color: #bababa;
                gridline-color: #403d39;
                border: 1px solid #403d39;
                selection-background-color: #e6912c;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #21201d;
                color: #ffffff;
                padding: 6px;
                border: 1px solid #403d39;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 10px;
            }
        """
        self.challenges_table.setStyleSheet(table_style)
        self.ongoing_table.setStyleSheet(table_style)

        self.tabs.addTab(self.challenges_table, "Available Challenges")
        self.tabs.addTab(self.ongoing_table, "Active Games")

        lobby_layout.addWidget(self.tabs)
        self.stacked_widget.addWidget(self.lobby_widget)

        # 3. Game Screen
        self.game_widget = QWidget()
        game_layout = QHBoxLayout(self.game_widget)

        # Left side: Board and Clocks
        board_area = QWidget()
        board_area_layout = QVBoxLayout(board_area)

        self.opponent_info = QLabel("Opponent: -")
        self.opponent_clock = QLabel("00:00")
        self.opponent_clock.setStyleSheet(
            "font-size: 20px; font-weight: bold; font-family: monospace;"
        )

        self.chessboard = ChessBoard(self, chess.Board().fen(), size=600)

        self.my_info = QLabel("You: -")
        self.my_clock = QLabel("00:00")
        self.my_clock.setStyleSheet(
            "font-size: 20px; font-weight: bold; font-family: monospace;"
        )

        board_area_layout.addWidget(self.opponent_info)
        board_area_layout.addWidget(self.opponent_clock)
        board_area_layout.addWidget(self.chessboard, alignment=Qt.AlignCenter)
        board_area_layout.addWidget(self.my_clock)
        board_area_layout.addWidget(self.my_info)

        # Right side: History and Status
        info_area = QWidget()
        info_layout = QVBoxLayout(info_area)

        self.game_status_label = QLabel("Status: Waiting...")
        self.game_status_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.game_status_label)

        self.waiting_indicator = QLabel("Waiting for opponent to join...")
        self.waiting_indicator.setStyleSheet(
            "color: #e67e22; font-weight: bold; font-size: 16px;"
        )
        self.waiting_indicator.setAlignment(Qt.AlignCenter)
        self.waiting_indicator.hide()
        info_layout.addWidget(self.waiting_indicator)

        self.pgn_browser = QPainterPGNBrowser(self, self.move_manager)
        info_layout.addWidget(self.pgn_browser)

        self.resign_btn = QPushButton("Resign")
        self.resign_btn.clicked.connect(self.on_resign_clicked)
        info_layout.addWidget(self.resign_btn)

        self.abort_btn = QPushButton("Abort")
        self.abort_btn.clicked.connect(self.on_abort_clicked)
        info_layout.addWidget(self.abort_btn)

        self.back_to_lobby_btn = QPushButton("Back to Lobby")
        self.back_to_lobby_btn.clicked.connect(self.go_to_lobby)
        info_layout.addWidget(self.back_to_lobby_btn)

        game_layout.addWidget(board_area, stretch=3)
        game_layout.addWidget(info_area, stretch=1)

        self.stacked_widget.addWidget(self.game_widget)

    def setup_signals(self):
        self.client.connected.connect(self.on_connected)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.errorOccurred.connect(self.on_error)
        self.client.gameListReceived.connect(self.on_game_list)
        self.client.stateReceived.connect(self.on_state_received)
        self.chessboard.moveMade.connect(self.on_move_made)
        self.pgn_browser.anchorClicked.connect(self.on_anchor_clicked)

    def on_anchor_clicked(self, url: QUrl):
        match = re.match(r"move\((\d+)\)", url.toString())
        if match:
            idx = int(match.group(1))
            self.move_manager.jump_to(idx)
            fen = self.move_manager.current_node.board().fen()
            self.chessboard.update_board(fen, self.move_manager.current_node.move)
            # Disable board if not at the latest move
            self.chessboard.interactive = self.move_manager.current_node.is_end() and (
                self.my_color == self.move_manager.get_board().turn
            )

    def on_connect_clicked(self):
        url = self.url_input.text()
        self.client.connect_to_server(url)
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")

    def on_connected(self):
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.stacked_widget.setCurrentWidget(self.lobby_widget)
        self.client.list_games()

    def on_disconnected(self):
        QMessageBox.warning(self, "Disconnected", "Lost connection to server")
        self.stacked_widget.setCurrentWidget(self.conn_widget)

    def on_error(self, message):
        QMessageBox.critical(self, "Error", message)
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")

    def on_game_list(self, data):
        if self.current_game_id:
            # Check if our current game is in the ongoing list (meaning both players joined)
            for game in data.get("ongoing", []):
                if game["game_id"] == self.current_game_id:
                    self.opponent_joined = True
                    self.update_game_active_state()
                    break
            else:
                # Check challenges
                for game in data.get("challenges", []):
                    if game["game_id"] == self.current_game_id:
                        if game.get("black"):
                            self.opponent_joined = True
                            self.update_game_active_state()
                        break

        def format_clock(config):
            if not config:
                return "-"
            time_m = config.get("time_ms", 0) // 60000
            inc_s = config.get("increment_ms", 0) // 1000
            if config.get("type") == "increment":
                return f"{time_m}m + {inc_s}s"
            return f"{time_m} min"

        # Update Challenges Table
        challenges = data.get("challenges", [])
        self.challenges_table.setRowCount(len(challenges))
        for i, game in enumerate(challenges):
            self.challenges_table.setItem(i, 0, QTableWidgetItem(game["game_id"]))
            self.challenges_table.setItem(
                i, 1, QTableWidgetItem(format_clock(game.get("clock_config")))
            )
            self.challenges_table.setItem(i, 2, QTableWidgetItem("Click to Join"))

        # Update Ongoing Table
        ongoing = data.get("ongoing", [])
        self.ongoing_table.setRowCount(len(ongoing))
        for i, game in enumerate(ongoing):
            self.ongoing_table.setItem(i, 0, QTableWidgetItem(game["game_id"]))
            self.ongoing_table.setItem(i, 1, QTableWidgetItem(game["white"] or "-"))
            self.ongoing_table.setItem(i, 2, QTableWidgetItem(game["black"] or "-"))
            self.ongoing_table.setItem(
                i, 3, QTableWidgetItem(format_clock(game.get("clock_config")))
            )

    def on_challenge_cell_clicked(self, row, column):
        game_id = self.challenges_table.item(row, 0).text()
        self.my_color = "black"
        self.my_game_roles[game_id] = "black"
        self.client.join_game(game_id)

    def on_ongoing_cell_clicked(self, row, column):
        game_id = self.ongoing_table.item(row, 0).text()
        # Check if we were already a player in this game
        if game_id in self.my_game_roles:
            self.my_color = self.my_game_roles[game_id]
        else:
            # Joining an ongoing game as a spectator
            self.my_color = None
        self.client.join_game(game_id)

    def on_game_selected(self, item):
        # This was for the old QListWidget, can be removed if not used
        pass

    def on_game_type_changed(self, index):
        is_increment = self.game_type_combo.currentText() == "Increment"
        self.inc_time_lbl.setVisible(is_increment)
        self.inc_time_spin.setVisible(is_increment)

    def on_create_custom_clicked(self):
        base_ms = self.base_time_spin.value() * 60000
        inc_ms = self.inc_time_spin.value() * 1000
        game_type = (
            "increment"
            if self.game_type_combo.currentText() == "Increment"
            else "sudden_death"
        )
        self.my_color = "white"
        # Role will be stored in on_state_received once we have the game_id
        self.client.create_game(base_ms, inc_ms, game_type)

    def on_create_game_clicked(
        self, time_ms=600000, increment_ms=0, game_type="sudden_death"
    ):
        self.my_color = "white"
        self.client.create_game(time_ms, increment_ms, game_type)

    def on_state_received(self, state):
        if not state:
            return

        self.current_game_id = state.get("game_id")

        # Persist role if we just created/joined or if we are rejoining
        if self.current_game_id and self.my_color:
            self.my_game_roles[self.current_game_id] = self.my_color
        elif self.current_game_id in self.my_game_roles:
            self.my_color = self.my_game_roles[self.current_game_id]

        self.stacked_widget.setCurrentWidget(self.game_widget)

        fen = state.get("fen")
        self.side_to_move = state.get("side_to_move")
        new_status = state.get("status", "ongoing")

        # Set user color for premoves support
        if self.my_color == "white":
            self.chessboard.user_color = chess.WHITE
        elif self.my_color == "black":
            self.chessboard.user_color = chess.BLACK
        else:
            self.chessboard.user_color = None

        self.chessboard.set_premoves_enabled(True)

        # If it's my first time in this game and I'm black, flip the board
        if self.my_color == "black" and self.chessboard.side == chess.WHITE:
            self.chessboard.flip()
        elif self.my_color == "white" and self.chessboard.side == chess.BLACK:
            self.chessboard.flip()

        self.chessboard.update_board(fen)

        # Sync time with server
        self.white_time_ms = state.get("white_time_ms", 0)
        self.black_time_ms = state.get("black_time_ms", 0)
        self.last_update_ms = QDateTime.currentMSecsSinceEpoch()

        # Determine move history
        history = state.get("move_history", [])

        if len(history) > 0 or self.my_color == "black":
            self.opponent_joined = True

        if self.my_color == "white" and len(history) == 0 and not self.opponent_joined:
            # We don't know if Black is here from the state payload alone.
            # Ask the server for the game list to verify.
            self.client.list_games()

        # Check if game status changed to terminal
        is_terminal = new_status != "ongoing" and new_status != "check"
        old_terminal = self.game_status != "ongoing" and self.game_status != "check"

        self.game_status = new_status
        self.update_game_active_state()

        # If game just ended, show dialog
        if is_terminal and not old_terminal:
            self.show_game_end_dialog(self.game_status)

        # Update buttons
        self.resign_btn.setEnabled(
            self.game_status == "ongoing" or self.game_status == "check"
        )
        self.abort_btn.setVisible(
            self.game_status == "ongoing"
            and len(history) == 0
            and self.my_color is not None
        )

        self.refresh_clocks_display()

        if self.game_status == "aborted":
            status_text = "Status: ABORTED"
        elif isinstance(self.game_status, dict):
            # Status can be {"checkmate": {"winner": "white"}}, etc.
            key = list(self.game_status.keys())[0]
            val = self.game_status[key]
            if isinstance(val, dict) and "winner" in val:
                status_text = f"Status: {key.upper()} - {val['winner'].upper()} WON"
            elif isinstance(val, dict) and "reason" in val:
                status_text = f"Status: {key.upper()} ({val['reason']})"
            else:
                status_text = f"Status: {key.upper()}"
        else:
            is_my_turn = self.my_color == self.side_to_move
            status_text = f"Status: {self.game_status.upper()} | Turn: {self.side_to_move.upper()} {'(YOUR TURN)' if is_my_turn else ''}"

        self.game_status_label.setText(status_text)

        # Update move history
        self.rebuild_history(history)

    def show_game_end_dialog(self, status):
        title = "Game Over"
        message = ""

        if status == "aborted":
            message = "The game was aborted."
        elif isinstance(status, dict):
            if "checkmate" in status:
                winner = status["checkmate"]["winner"]
                message = f"Checkmate! {winner.capitalize()} wins."
            elif "resigned" in status:
                winner = status["resigned"]["winner"]
                message = f"Opponent resigned. {winner.capitalize()} wins."
            elif "draw" in status:
                reason = status["draw"].get("reason", "unknown")
                message = f"Game ended in a draw: {reason}."
            elif "time_expired" in status:
                winner = status["time_expired"]["winner"]
                message = f"Time expired. {winner.capitalize()} wins."
            else:
                message = f"Game ended: {status}"
        else:
            message = f"Game status: {status}"

        QMessageBox.information(self, title, message)

    def update_game_active_state(self):
        if not self.current_game_id:
            return

        # Game is active if ongoing/check and opponent joined (or I'm Black)
        is_ongoing = self.game_status == "ongoing" or self.game_status == "check"
        is_waiting = self.my_color == "white" and not self.opponent_joined

        if is_waiting:
            self.waiting_indicator.show()
            self.is_game_active = False
        else:
            self.waiting_indicator.hide()
            self.is_game_active = is_ongoing

        if not is_ongoing:
            self.chessboard.interactive = False
        else:
            is_my_turn = self.my_color == self.side_to_move
            self.chessboard.interactive = is_my_turn and self.is_game_active

    def on_timer_tick(self):
        if (
            not self.current_game_id
            or self.game_status != "ongoing"
            or not getattr(self, "is_game_active", True)
        ):
            return
        self.refresh_clocks_display()

    def refresh_clocks_display(self):
        now = QDateTime.currentMSecsSinceEpoch()
        elapsed = now - self.last_update_ms if self.last_update_ms > 0 else 0

        w_display = self.white_time_ms
        b_display = self.black_time_ms

        if self.game_status == "ongoing" and getattr(self, "is_game_active", True):
            if self.side_to_move == "white":
                w_display = max(0, self.white_time_ms - elapsed)
            elif self.side_to_move == "black":
                b_display = max(0, self.black_time_ms - elapsed)

        def format_time(ms):
            s = int(ms // 1000)
            m = s // 60
            s = s % 60
            return f"{m:02d}:{s:02d}"

        # Adjust display labels based on color
        if self.my_color == "black":
            self.my_clock.setText(f"You (Black): {format_time(b_display)}")
            self.opponent_clock.setText(f"Opponent (White): {format_time(w_display)}")
            self.my_info.setText("You: Black")
            self.opponent_info.setText("Opponent: White")
        elif self.my_color == "white":
            self.my_clock.setText(f"You (White): {format_time(w_display)}")
            self.opponent_clock.setText(f"Opponent (Black): {format_time(b_display)}")
            self.my_info.setText("You: White")
            self.opponent_info.setText("Opponent: Black")
        else:
            self.my_clock.setText(f"White: {format_time(w_display)}")
            self.opponent_clock.setText(f"Black: {format_time(b_display)}")
            self.my_info.setText("Spectating")
            self.opponent_info.setText("")

    def rebuild_history(self, history):
        # MoveManager usually tracks its own game. We can manually reset it.
        self.move_manager.clear()
        for move_uci in history:
            self.move_manager.make_move(move_uci)
        self.pgn_browser.setHtml(self.move_manager.html)

    def on_move_made(self, uci):
        if self.current_game_id:
            self.client.make_move(self.current_game_id, uci)

    def on_resign_clicked(self):
        if self.current_game_id:
            self.client.resign(self.current_game_id)

    def on_abort_clicked(self):
        if self.current_game_id:
            self.client.abort(self.current_game_id)

    def go_to_lobby(self):
        self.current_game_id = None
        self.opponent_joined = False
        self.stacked_widget.setCurrentWidget(self.lobby_widget)
        self.client.list_games()


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = OnlineChessApp()
    window.show()
    sys.exit(app.exec_())
