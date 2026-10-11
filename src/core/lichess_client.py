import os
import json
from typing import Optional, Dict, Any, List, Callable
from PyQt5 import QtCore, QtNetwork


def find_env_file_path() -> Optional[str]:
    """Search for .env file in standard locations (CWD, project root)."""
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def load_lichess_token() -> str:
    """
    Load Lichess API personal access token.
    Precedence:
    1. QSettings stored token
    2. os.environ LICHESS_TOKEN or LICHESS_API_TOKEN
    3. .env file in project directory (supports key=value or raw token string)
    """
    settings = QtCore.QSettings("QChessApp", "Lichess")
    stored = settings.value("api_token", "")
    if stored and str(stored).strip():
        return str(stored).strip()

    env_val = os.environ.get("LICHESS_TOKEN") or os.environ.get("LICHESS_API_TOKEN")
    if env_val and env_val.strip():
        return env_val.strip()

    env_path = find_env_file_path()
    if env_path:
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip().upper()
                        v = v.strip().strip("'\"")
                        if k in ("LICHESS_TOKEN", "LICHESS_API_TOKEN", "TOKEN", "LICHESS_KEY"):
                            return v
                    elif line.startswith("lip_"):
                        return line
        except Exception:
            pass

    return ""


def save_lichess_token(token: str):
    """Save token to QSettings for persistent use."""
    settings = QtCore.QSettings("QChessApp", "Lichess")
    settings.setValue("api_token", token.strip())


class LichessClient(QtCore.QObject):
    """
    Asynchronous Lichess API client powered by Qt Network (QNetworkAccessManager).
    Provides methods for querying the Lichess Opening Explorer (Masters & Lichess online database)
    and fetching game PGNs.
    """
    treeReady = QtCore.pyqtSignal(dict, str)   # (response_data, fen)
    errorOccurred = QtCore.pyqtSignal(str)     # (error_message)
    gamePgnReady = QtCore.pyqtSignal(str, str) # (game_id, pgn_text)

    MASTERS_URL = "https://explorer.lichess.ovh/masters"
    LICHESS_URL = "https://explorer.lichess.ovh/lichess"
    GAME_EXPORT_URL = "https://lichess.org/game/export"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nam = QtNetwork.QNetworkAccessManager(self)
        self._active_tree_reply: Optional[QtNetwork.QNetworkReply] = None
        self._active_tree_fen: Optional[str] = None
        self._token: str = load_lichess_token()

    def get_token(self) -> str:
        if not self._token:
            self._token = load_lichess_token()
        return self._token

    def set_token(self, token: str, persist: bool = True):
        self._token = token.strip()
        if persist:
            save_lichess_token(self._token)

    def has_token(self) -> bool:
        return bool(self.get_token())

    def _create_request(self, url: QtCore.QUrl) -> QtNetwork.QNetworkRequest:
        req = QtNetwork.QNetworkRequest(url)
        req.setRawHeader(b"User-Agent", b"QChess-Desktop/1.0 (https://github.com/qchess)")
        token = self.get_token()
        if token:
            req.setRawHeader(b"Authorization", f"Bearer {token}".encode("utf-8"))
        return req

    def query_opening_tree(
        self,
        fen: str,
        source: str = "masters",
        speeds: Optional[List[str]] = None,
        ratings: Optional[List[int]] = None,
        moves_count: int = 15,
        top_games_count: int = 10,
        callback: Optional[Callable[[Optional[dict], Optional[str]], None]] = None,
    ):
        """
        Query Lichess Opening Explorer for the given FEN.
        source: 'masters' for FIDE masters database, 'lichess' for rated online games.
        """
        # Cancel any previous in-flight tree query to avoid race conditions
        if self._active_tree_reply is not None:
            try:
                self._active_tree_reply.abort()
                self._active_tree_reply.deleteLater()
            except Exception:
                pass
            self._active_tree_reply = None

        endpoint = self.MASTERS_URL if source == "masters" else self.LICHESS_URL
        url = QtCore.QUrl(endpoint)
        query = QtCore.QUrlQuery()
        query.addQueryItem("fen", fen)
        query.addQueryItem("moves", str(max(1, min(moves_count, 30))))
        query.addQueryItem("topGames", str(max(0, min(top_games_count, 20))))

        if source == "lichess":
            query.addQueryItem("recentGames", "5")
            if speeds:
                query.addQueryItem("speeds", ",".join(speeds))
            if ratings:
                query.addQueryItem("ratings", ",".join(str(r) for r in ratings))

        url.setQuery(query)
        req = self._create_request(url)

        reply = self.nam.get(req)
        self._active_tree_reply = reply
        self._active_tree_fen = fen

        def on_finished():
            if reply != self._active_tree_reply:
                reply.deleteLater()
                return

            self._active_tree_reply = None
            err = reply.error()
            http_status = reply.attribute(QtNetwork.QNetworkRequest.HttpStatusCodeAttribute)

            if err == QtNetwork.QNetworkReply.NoError:
                try:
                    raw_bytes = reply.readAll().data()
                    data = json.loads(raw_bytes.decode("utf-8"))
                    self.treeReady.emit(data, fen)
                    if callback:
                        callback(data, None)
                except Exception as ex:
                    msg = f"Failed to parse Lichess response: {ex}"
                    self.errorOccurred.emit(msg)
                    if callback:
                        callback(None, msg)
            else:
                if err == QtNetwork.QNetworkReply.OperationCanceledError:
                    reply.deleteLater()
                    return

                if http_status == 401:
                    msg = "Lichess API authentication failed (HTTP 401). Please check your token."
                elif http_status == 429:
                    msg = "Lichess rate limit reached (HTTP 429). Please wait a moment."
                elif http_status == 404:
                    msg = "Position not found in Lichess database."
                else:
                    msg = f"Lichess request error: {reply.errorString()} (HTTP {http_status or '?'})"

                self.errorOccurred.emit(msg)
                if callback:
                    callback(None, msg)

            reply.deleteLater()

        reply.finished.connect(on_finished)

    def fetch_game_pgn(
        self,
        game_id: str,
        callback: Optional[Callable[[Optional[str], Optional[str]], None]] = None,
    ):
        """Fetch the full PGN for a game by its Lichess ID."""
        url = QtCore.QUrl(f"{self.GAME_EXPORT_URL}/{game_id}")
        query = QtCore.QUrlQuery()
        query.addQueryItem("clocks", "false")
        query.addQueryItem("evals", "false")
        url.setQuery(query)

        req = self._create_request(url)
        reply = self.nam.get(req)

        def on_finished():
            err = reply.error()
            http_status = reply.attribute(QtNetwork.QNetworkRequest.HttpStatusCodeAttribute)
            if err == QtNetwork.QNetworkReply.NoError:
                raw_bytes = reply.readAll().data()
                pgn_text = raw_bytes.decode("utf-8", errors="replace")
                self.gamePgnReady.emit(game_id, pgn_text)
                if callback:
                    callback(pgn_text, None)
            else:
                msg = f"Failed to download PGN for game {game_id}: {reply.errorString()} (HTTP {http_status or '?'})"
                self.errorOccurred.emit(msg)
                if callback:
                    callback(None, msg)
            reply.deleteLater()

        reply.finished.connect(on_finished)
