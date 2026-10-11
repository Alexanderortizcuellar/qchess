import os
import sys
from typing import Optional, List, Dict, Any
from PyQt5 import QtCore, QtGui, QtWidgets


class PercentageBar(QtWidgets.QWidget):
    def __init__(self, white_win: int, draw: int, black_win: int, avg_white_elo=None, avg_black_elo=None, parent=None):
        super().__init__(parent)
        self.white_win = int(white_win)
        self.draw = int(draw)
        self.black_win = int(black_win)
        self.avg_white_elo = avg_white_elo
        self.avg_black_elo = avg_black_elo
        self.setFixedHeight(22)
        self.is_dark = True

        # Calculate percentages and set tooltip
        total = self.white_win + self.draw + self.black_win
        if total > 0:
            white_pct = (self.white_win / total) * 100
            draw_pct = (self.draw / total) * 100
            black_pct = (self.black_win / total) * 100
            tooltip = (
                f"Total games: {total:,}\n"
                f"White wins: {self.white_win:,} ({white_pct:.1f}%)\n"
                f"Draws: {self.draw:,} ({draw_pct:.1f}%)\n"
                f"Black wins: {self.black_win:,} ({black_pct:.1f}%)"
            )
            if self.avg_white_elo or self.avg_black_elo:
                w_elo = self.avg_white_elo or "?"
                b_elo = self.avg_black_elo or "?"
                tooltip += f"\nAvg Elo: ♔ {w_elo} / ♚ {b_elo}"
            self.setToolTip(tooltip)
        else:
            self.setToolTip("No games played")

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        total_w = self.width()
        h = self.height()

        total = self.white_win + self.draw + self.black_win
        if total == 0:
            return

        pw = (self.white_win / total) * total_w
        pd = (self.draw / total) * total_w
        pb = total_w - pw - pd

        color_white = QtGui.QColor("#ffffff")
        color_draw = QtGui.QColor("#94a3b8")
        color_black = QtGui.QColor("#1e293b" if not self.is_dark else "#312e2b")

        painter.setPen(QtCore.Qt.NoPen)

        # White
        if pw > 0:
            painter.setBrush(color_white)
            painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if not self.is_dark:
                painter.setPen(QtGui.QPen(QtGui.QColor("#cbd5e1"), 1))
                painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if pw > 22:
                painter.setPen(QtGui.QColor("#0f172a"))
                painter.setFont(QtGui.QFont("Segoe UI", 8, QtGui.QFont.Bold))
                painter.drawText(
                    QtCore.QRectF(0, 0, pw, h),
                    QtCore.Qt.AlignCenter,
                    f"{self.white_win}",
                )

        # Draw
        if pd > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_draw)
            painter.drawRect(QtCore.QRectF(pw, 0, pd, h))
            if pd > 22:
                painter.setPen(QtGui.QColor("#ffffff"))
                painter.setFont(QtGui.QFont("Segoe UI", 8, QtGui.QFont.Bold))
                painter.drawText(
                    QtCore.QRectF(pw, 0, pd, h),
                    QtCore.Qt.AlignCenter,
                    f"{self.draw}",
                )

        # Black
        if pb > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_black)
            painter.drawRect(QtCore.QRectF(pw + pd, 0, pb, h))
            if pb > 22:
                painter.setPen(QtGui.QColor("#ffffff"))
                painter.setFont(QtGui.QFont("Segoe UI", 8, QtGui.QFont.Bold))
                painter.drawText(
                    QtCore.QRectF(pw + pd, 0, pb, h),
                    QtCore.Qt.AlignCenter,
                    f"{self.black_win}",
                )


class TwoBarWidget(QtWidgets.QWidget):
    """
    Compact 2-color outcome bar showing White win % (left) and Black win % (right).
    Draw % is displayed separately in a dedicated table column.
    """
    def __init__(self, white_wins: int, black_wins: int, total_games: int = 0, parent=None):
        super().__init__(parent)
        self.white_wins = int(white_wins)
        self.black_wins = int(black_wins)
        self.total_games = int(total_games) if total_games > 0 else (self.white_wins + self.black_wins)
        self.setFixedHeight(18)
        self.setMinimumWidth(60)
        self.is_dark = True
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        if self.total_games > 0:
            w_pct = (self.white_wins / self.total_games) * 100
            b_pct = (self.black_wins / self.total_games) * 100
            self.setToolTip(
                f"White wins: {self.white_wins:,} ({w_pct:.1f}%)\n"
                f"Black wins: {self.black_wins:,} ({b_pct:.1f}%)"
            )
        else:
            self.setToolTip("")

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        decisive = self.white_wins + self.black_wins
        if decisive == 0:
            return

        pw = (self.white_wins / decisive) * w
        pb = w - pw

        color_white = QtGui.QColor("#ffffff")
        color_black = QtGui.QColor("#1e293b" if not self.is_dark else "#312e2b")

        # White bar (left)
        if pw > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_white)
            painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if not self.is_dark:
                painter.setPen(QtGui.QPen(QtGui.QColor("#cbd5e1"), 1))
                painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if pw > 20:
                w_pct = int(round((self.white_wins / self.total_games) * 100)) if self.total_games > 0 else 0
                painter.setPen(QtGui.QColor("#0f172a"))
                painter.setFont(QtGui.QFont("Segoe UI", 8, QtGui.QFont.Bold))
                painter.drawText(QtCore.QRectF(0, 0, pw, h), QtCore.Qt.AlignCenter, f"{w_pct}%")

        # Black bar (right)
        if pb > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_black)
            painter.drawRect(QtCore.QRectF(pw, 0, pb, h))
            if pb > 20:
                b_pct = int(round((self.black_wins / self.total_games) * 100)) if self.total_games > 0 else 0
                painter.setPen(QtGui.QColor("#ffffff"))
                painter.setFont(QtGui.QFont("Segoe UI", 8, QtGui.QFont.Bold))
                painter.drawText(QtCore.QRectF(pw, 0, pb, h), QtCore.Qt.AlignCenter, f"{b_pct}%")


class MoveItem(QtWidgets.QWidget):
    moveClicked = QtCore.pyqtSignal(str)

    def __init__(self, move_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.move_data = move_data
        self.move_text = move_data.get("san") or move_data.get("move") or move_data.get("uci") or ""
        self.move_uci = move_data.get("uci") or self.move_text

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)

        self.move_lbl = QtWidgets.QLabel(self.move_text)
        self.move_lbl.setFixedWidth(50)

        white_wins = move_data.get("white_wins", 0)
        draws = move_data.get("draws", 0)
        black_wins = move_data.get("black_wins", 0)
        avg_w = move_data.get("avg_white_elo")
        avg_b = move_data.get("avg_black_elo")

        self.bar = PercentageBar(
            white_wins, draws, black_wins, avg_white_elo=avg_w, avg_black_elo=avg_b, parent=self
        )

        layout.addWidget(self.move_lbl)
        layout.addWidget(self.bar)

        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        color = "#f8fafc" if is_dark else "#0f172a"
        self.move_lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 12px;"
        )
        self.bar.set_theme(is_dark)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.moveClicked.emit(self.move_uci)
        super().mousePressEvent(event)


class NoFocusDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate that suppresses the dotted cell focus rectangle on selection."""
    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        opt.state &= ~QtWidgets.QStyle.State_HasFocus
        super().paint(painter, opt, index)


class OpeningTreeTable(QtWidgets.QTableWidget):
    moveSelected = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["Move", "Games", "Score", "Draw %", "Years"])
        self.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(0, 70)
        self.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)

        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.setItemDelegate(NoFocusDelegate(self))
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.is_dark = True
        self.positions_data = []

        self.cellClicked.connect(self._on_cell_clicked)
        self.cellDoubleClicked.connect(self._on_cell_clicked)
        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        text_color = "#f8fafc" if is_dark else "#0f172a"
        header_bg = "#141312" if is_dark else "#e2e8f0"
        header_text = "#f8fafc" if is_dark else "#0f172a"
        border_r = "#383531" if is_dark else "#cbd5e1"
        sel_bg = "#1e3a5f" if is_dark else "#2563eb"
        sel_color = "#ffffff"

        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg};
                color: {text_color};
                border: none;
                font-size: 11px;
                selection-background-color: {sel_bg};
                selection-color: {sel_color};
                outline: none;
            }}
            QTableWidget::item {{
                outline: none;
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: {sel_bg};
                color: {sel_color};
                outline: none;
                border: none;
            }}
            QTableWidget::item:focus {{
                outline: none;
                border: none;
            }}
            QTableWidget::item:selected:focus {{
                background-color: {sel_bg};
                color: {sel_color};
                outline: none;
                border: none;
            }}
            QHeaderView::section {{
                background-color: {header_bg};
                color: {header_text};
                border: none;
                border-right: 1px solid {border_r};
                border-bottom: 1px solid {border_r};
                padding: 3px 4px;
                font-weight: bold;
                font-size: 10px;
            }}
        """)

        for row in range(self.rowCount()):
            bar_w = self.cellWidget(row, 2)
            if isinstance(bar_w, TwoBarWidget):
                bar_w.set_theme(is_dark)

    def update_positions(self, positions: List[Dict[str, Any]]):
        self.positions_data = positions
        self.setRowCount(len(positions))

        font_bold = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold)
        font_regular = QtGui.QFont("Segoe UI", 9)

        for row, move_data in enumerate(positions):
            move_text = move_data.get("san") or move_data.get("move") or move_data.get("uci") or ""
            move_uci = move_data.get("uci") or move_text
            white_wins = move_data.get("white_wins", 0)
            draws = move_data.get("draws", 0)
            black_wins = move_data.get("black_wins", 0)
            total = move_data.get("total_games", white_wins + draws + black_wins)

            # Draw % (with decimal precision)
            draw_pct_str = f"{(draws / total) * 100:.1f}%" if total > 0 else "-"

            # Item 0: Move
            item_move = QtWidgets.QTableWidgetItem(move_text)
            item_move.setFont(font_bold)
            item_move.setData(QtCore.Qt.UserRole, move_uci)

            # Item 1: Total games
            item_games = QtWidgets.QTableWidgetItem(f"{total:,}" if total > 0 else "0")
            item_games.setFont(font_regular)
            item_games.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

            # Item 2: Score 2-Bar Widget
            bar_widget = TwoBarWidget(white_wins, black_wins, total_games=total, parent=self)
            bar_widget.set_theme(self.is_dark)

            # Item 3: Draw %
            item_draw = QtWidgets.QTableWidgetItem(draw_pct_str)
            item_draw.setFont(font_regular)
            item_draw.setTextAlignment(QtCore.Qt.AlignCenter)

            # Item 4: Years (first_year - last_year)
            first_year = move_data.get("first_year")
            last_year = move_data.get("last_year") or move_data.get("last_played")
            if first_year and last_year:
                years_str = str(first_year) if str(first_year) == str(last_year) else f"{first_year}-{last_year}"
            elif last_year:
                years_str = str(last_year)
            elif first_year:
                years_str = str(first_year)
            else:
                years_str = "-"

            item_years = QtWidgets.QTableWidgetItem(years_str)
            item_years.setFont(font_regular)
            item_years.setTextAlignment(QtCore.Qt.AlignCenter)

            tooltip = (
                f"Move: {move_text}\n"
                f"Total games: {total:,}\n"
                f"White wins: {white_wins:,} ({(white_wins / total) * 100:.1f}%)\n"
                f"Draws: {draws:,} ({(draws / total) * 100:.1f}%)\n"
                f"Black wins: {black_wins:,} ({(black_wins / total) * 100:.1f}%)\n"
                f"Years: {years_str}"
            )
            item_move.setToolTip(tooltip)
            item_games.setToolTip(tooltip)
            item_draw.setToolTip(tooltip)
            item_years.setToolTip(tooltip)

            self.setItem(row, 0, item_move)
            self.setItem(row, 1, item_games)
            self.setCellWidget(row, 2, bar_widget)
            self.setItem(row, 3, item_draw)
            self.setItem(row, 4, item_years)
            self.setRowHeight(row, 22)

    def _on_cell_clicked(self, row: int, column: int):
        item = self.item(row, 0)
        if item:
            uci = item.data(QtCore.Qt.UserRole)
            if uci:
                self.moveSelected.emit(str(uci))
                return
        if 0 <= row < len(self.positions_data):
            m = self.positions_data[row]
            uci = m.get("uci") or m.get("san") or m.get("move")
            if uci:
                self.moveSelected.emit(str(uci))


class SampleGamesTable(QtWidgets.QTableWidget):
    gameSelected = QtCore.pyqtSignal(int, dict)  # (game_id, game_summary)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(["White", "Elo W", "Black", "Elo B", "Res", "Date", "ECO"])
        self.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(1, 55)
        self.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(3, 55)
        self.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(4, 50)
        self.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(5, 75)
        self.horizontalHeader().setSectionResizeMode(6, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(6, 45)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.setSortingEnabled(True)
        self.setItemDelegate(NoFocusDelegate(self))
        self.is_dark = True
        self.games_data = []

        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        text_color = "#bababa" if is_dark else "#0f172a"
        header_bg = "#141312" if is_dark else "#e2e8f0"
        header_text = "#f8fafc" if is_dark else "#0f172a"
        border_r = "#383531" if is_dark else "#cbd5e1"
        sel_bg = "#1e3a5f" if is_dark else "#2563eb"
        sel_color = "#ffffff"

        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg};
                color: {text_color};
                border: none;
                font-size: 11px;
                selection-background-color: {sel_bg};
                selection-color: {sel_color};
                outline: none;
            }}
            QTableWidget::item {{
                outline: none;
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: {sel_bg};
                color: {sel_color};
                outline: none;
                border: none;
            }}
            QTableWidget::item:focus {{
                outline: none;
                border: none;
            }}
            QTableWidget::item:selected:focus {{
                background-color: {sel_bg};
                color: {sel_color};
                outline: none;
                border: none;
            }}
            QHeaderView::section {{
                background-color: {header_bg};
                color: {header_text};
                border: none;
                border-right: 1px solid {border_r};
                border-bottom: 1px solid {border_r};
                padding: 4px 6px;
                font-weight: bold;
                font-size: 10px;
            }}
        """)

    def update_games(self, games: List[Dict[str, Any]]):
        self.setSortingEnabled(False)
        self.games_data = games
        self.setRowCount(len(games))

        font_demibold = QtGui.QFont("Segoe UI", 9, QtGui.QFont.DemiBold)
        font_regular = QtGui.QFont("Segoe UI", 9)

        for row, g in enumerate(games):
            w_name = g.get("white", "?")
            w_elo = g.get("white_elo", 0)
            w_elo_str = str(w_elo) if w_elo and int(w_elo) > 0 else ""

            b_name = g.get("black", "?")
            b_elo = g.get("black_elo", 0)
            b_elo_str = str(b_elo) if b_elo and int(b_elo) > 0 else ""

            res_str = g.get("result", "*")

            date_str = str(g.get("date") or "").strip()
            if not date_str or date_str == "?":
                year_val = g.get("year")
                date_str = str(year_val) if year_val else ""

            eco_str = g.get("eco", "")

            item_w = QtWidgets.QTableWidgetItem(w_name)
            item_w.setFont(font_demibold)
            item_w.setData(QtCore.Qt.UserRole, g)

            item_w_elo = QtWidgets.QTableWidgetItem(w_elo_str)
            item_w_elo.setFont(font_regular)
            item_w_elo.setTextAlignment(QtCore.Qt.AlignCenter)

            item_r = QtWidgets.QTableWidgetItem(res_str)
            item_r.setFont(font_demibold)
            item_r.setTextAlignment(QtCore.Qt.AlignCenter)

            item_b = QtWidgets.QTableWidgetItem(b_name)
            item_b.setFont(font_demibold)

            item_b_elo = QtWidgets.QTableWidgetItem(b_elo_str)
            item_b_elo.setFont(font_regular)
            item_b_elo.setTextAlignment(QtCore.Qt.AlignCenter)

            item_d = QtWidgets.QTableWidgetItem(date_str)
            item_d.setFont(font_regular)
            item_d.setTextAlignment(QtCore.Qt.AlignCenter)

            item_e = QtWidgets.QTableWidgetItem(eco_str)
            item_e.setFont(font_regular)
            item_e.setTextAlignment(QtCore.Qt.AlignCenter)

            tooltip = (
                f"{w_name} ({w_elo_str or 'unrated'}) vs {b_name} ({b_elo_str or 'unrated'})\n"
                f"Result: {res_str} | Date: {date_str or 'Unknown'} | ECO: {eco_str}\n"
                f"Event: {g.get('event', '')}\nSite: {g.get('site', '')}"
            )
            item_w.setToolTip(tooltip)
            item_w_elo.setToolTip(tooltip)
            item_r.setToolTip(tooltip)
            item_b.setToolTip(tooltip)
            item_b_elo.setToolTip(tooltip)
            item_d.setToolTip(tooltip)
            item_e.setToolTip(tooltip)

            self.setItem(row, 0, item_w)
            self.setItem(row, 1, item_w_elo)
            self.setItem(row, 2, item_b)
            self.setItem(row, 3, item_b_elo)
            self.setItem(row, 4, item_r)
            self.setItem(row, 5, item_d)
            self.setItem(row, 6, item_e)
            self.setRowHeight(row, 24)

        self.setSortingEnabled(True)

    def _on_cell_double_clicked(self, row: int, column: int):
        item = self.item(row, 0)
        if item:
            g = item.data(QtCore.Qt.UserRole)
            if isinstance(g, dict):
                game_id = g.get("id")
                if game_id is not None:
                    self.gameSelected.emit(int(game_id), g)
                    return
        if 0 <= row < len(self.games_data):
            g = self.games_data[row]
            game_id = g.get("id")
            if game_id is not None:
                self.gameSelected.emit(int(game_id), g)


class OpeningExplorer(QtWidgets.QWidget):
    moveSelected = QtCore.pyqtSignal(str)
    sampleGameSelected = QtCore.pyqtSignal(int, dict)

    def __init__(self, parent=None, positions=None):
        super().__init__(parent)
        self.is_dark = True
        self.mode = "table"
        self.cached_positions = []

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Stack to hold Bars view and Table view (no bulky redundant header label on top)
        self.stack = QtWidgets.QStackedWidget(self)

        # 1. Bars View (Scroll Area)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self.container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(1)
        self.container_layout.addStretch()

        self.scroll.setWidget(self.container)
        self.stack.addWidget(self.scroll)

        # 2. Table View
        self.table_view = OpeningTreeTable(self)
        self.table_view.moveSelected.connect(self.moveSelected.emit)
        self.stack.addWidget(self.table_view)

        self.main_layout.addWidget(self.stack, 1)

        self.status_lbl = QtWidgets.QLabel(self.container)
        self.status_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.status_lbl.setStyleSheet("color: #8b8987; font-style: italic; font-size: 11px; padding: 12px;")
        self.status_lbl.setText("Open a database to explore positions.")
        self.status_lbl.show()
        self.container_layout.insertWidget(0, self.status_lbl)

        # Load saved view mode from settings (default "table")
        saved_mode = QtCore.QSettings("TestChessApp", "Config").value("explorer_view_mode", "table")
        self.set_mode(saved_mode)
        self.set_theme(True)

        if positions:
            self.update_positions(positions)

    def toggle_view_mode(self):
        new_mode = "table" if self.mode == "bars" else "bars"
        self.set_mode(new_mode)

    def set_mode(self, mode: str):
        self.mode = mode if mode in ("bars", "table") else "table"
        if self.mode == "table":
            self.stack.setCurrentWidget(self.table_view)
        else:
            self.stack.setCurrentWidget(self.scroll)
        QtCore.QSettings("TestChessApp", "Config").setValue("explorer_view_mode", self.mode)

    def show_loading(self, message: str = "Querying opening tree..."):
        self._clear_move_items()
        self.status_lbl.setText(message)
        self.status_lbl.show()
        self.table_view.setRowCount(0)

    def show_status(self, message: str):
        self._clear_move_items()
        self.status_lbl.setText(message)
        self.status_lbl.show()
        self.table_view.setRowCount(0)

    def _clear_move_items(self):
        while self.container_layout.count() > 2:
            item = self.container_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        color = "#94a3b8" if is_dark else "#64748b"

        self.setStyleSheet(f"background-color: {bg};")
        self.status_lbl.setStyleSheet(f"color: {color}; font-style: italic; font-size: 11px; padding: 12px;")
        self.table_view.set_theme(is_dark)

        for i in range(self.container_layout.count()):
            w = self.container_layout.itemAt(i).widget()
            if isinstance(w, MoveItem):
                w.set_theme(is_dark)

    def update_positions(self, positions: List[Dict[str, Any]]):
        self._clear_move_items()
        self.cached_positions = positions or []

        # Update Table view
        self.table_view.update_positions(self.cached_positions)

        # Update Bars view
        if not positions:
            self.status_lbl.setText("No games found in this position.")
            self.status_lbl.show()
            return

        self.status_lbl.hide()
        for move_data in positions:
            item = MoveItem(move_data, self)
            item.set_theme(self.is_dark)
            item.moveClicked.connect(self.moveSelected.emit)
            self.container_layout.insertWidget(self.container_layout.count() - 1, item)

    def update_sample_games(self, sample_games: List[Dict[str, Any]]):
        pass


class OpeningExplorerHeader(QtWidgets.QWidget):
    """Compatibility shim for any legacy references."""
    modeToggleRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(0)
        self.hide()

    def set_mode(self, mode: str):
        pass

    def set_theme(self, is_dark: bool):
        pass


class OpeningExplorerLogic(QtWidgets.QWidget):
    """
    Pure UI Widget for Opening Explorer.
    Completely decoupled from databases, SQLite, or backend processes.
    Emits queryRequested(fen, filters) to let the controller fetch statistics.
    Filters are sourced exclusively from the global ReferenceFilterManager / ReferenceFiltersDialog.
    """
    queryRequested = QtCore.pyqtSignal(str, dict)  # (fen, filters)
    moveSelected = QtCore.pyqtSignal(str)          # (move_uci)
    sampleGameSelected = QtCore.pyqtSignal(int, dict)  # (game_id, game_summary)
    errorOcurred = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.explorer = OpeningExplorer(self)
        self.explorer.moveSelected.connect(self.moveSelected.emit)
        self.explorer.sampleGameSelected.connect(self.sampleGameSelected.emit)
        self.last_fen = None
        self.is_dark = QtCore.QSettings("QChessApp", "Theme").value("theme", "dark") == "dark"

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.explorer)

        # Wire global reference filter manager
        from core.reference_filters import get_reference_filter_manager
        self.ref_filter_mgr = get_reference_filter_manager()
        self.ref_filter_mgr.filtersChanged.connect(self._on_global_filters_changed)
        self.set_theme(self.is_dark)

    def _on_global_filters_changed(self, _=None):
        if self.last_fen:
            self.send_fen(self.last_fen, force=True)

    def get_filters(self) -> Dict[str, Any]:
        return self.ref_filter_mgr.get_filter_dict()

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.explorer.set_theme(is_dark)

    def toggle_view_mode(self):
        self.explorer.toggle_view_mode()

    def set_view_mode(self, mode: str):
        self.explorer.set_mode(mode)

    def set_tree_data(self, data: Any):
        """
        Accepts OpeningTreeReport dictionary returned by scid-mgr or list of moves.
        """
        if isinstance(data, dict):
            moves = data.get("moves", [])
            sample_games = data.get("sample_games", [])
        elif isinstance(data, list):
            moves = data
            sample_games = []
        else:
            moves = []
            sample_games = []

        if moves:
            # Sort by total games played descending and limit to top 10 moves for smooth rendering
            moves = sorted(
                moves,
                key=lambda x: x.get("total_games", x.get("white_wins", 0) + x.get("draws", 0) + x.get("black_wins", 0)),
                reverse=True,
            )
            self.explorer.update_positions(moves[:10])
        else:
            self.explorer.update_positions([])

        self.explorer.update_sample_games(sample_games[:5])

    def show_loading(self, message: str = "Querying opening tree..."):
        self.explorer.show_loading(message)

    def show_status(self, message: str):
        self.explorer.show_status(message)

    def set_progress(self, scanned: int, total: int, percent: float):
        msg = f"Scanning database... {scanned:,} / {total:,} ({percent:.1f}%)"
        self.explorer.status_lbl.setText(msg)
        self.explorer.status_lbl.show()

    def send_fen(self, fen: str, force: bool = False):
        current_filters = self.get_filters()
        if not force and self.last_fen == fen and getattr(self, "last_filters", None) == current_filters:
            return

        self.last_fen = fen
        self.last_filters = current_filters
        self.show_loading("Querying opening tree...")
        self.queryRequested.emit(fen, current_filters)

    def showEvent(self, event):
        super().showEvent(event)
        if self.last_fen:
            self.send_fen(self.last_fen, force=False)
