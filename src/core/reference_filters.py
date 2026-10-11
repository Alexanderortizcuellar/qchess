from typing import Dict, Any, Optional
from PyQt5 import QtCore
from PyQt5.QtCore import QSettings


class ReferenceFilterManager(QtCore.QObject):
    """
    Singleton / shared manager for reference database filters.
    These filters apply globally across:
      1. Opening Explorer (Tree widget)
      2. Common Continuations (Continuations widget)
      3. Endgame Statistics (Endgames widget)
    """
    filtersChanged = QtCore.pyqtSignal(dict)

    _instance: Optional["ReferenceFilterManager"] = None

    @classmethod
    def get_instance(cls) -> "ReferenceFilterManager":
        if cls._instance is None:
            cls._instance = ReferenceFilterManager()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings("TestChessApp", "ReferenceFilters")
        self._current_filters: Dict[str, Any] = self._load_from_settings()

    def _load_from_settings(self) -> Dict[str, Any]:
        """Load stored reference filters from persistent settings."""
        filters = {}
        player = self._settings.value("player", "", type=str).strip()
        color = self._settings.value("color", "Either Color", type=str)
        min_rating = int(self._settings.value("min_rating", 0))
        max_rating = int(self._settings.value("max_rating", 0))
        eco = self._settings.value("eco", "", type=str).strip().upper()
        result = self._settings.value("result", "Any", type=str)
        event = self._settings.value("event", "", type=str).strip()
        site = self._settings.value("site", "", type=str).strip()
        min_year = int(self._settings.value("min_year", 0))
        max_year = int(self._settings.value("max_year", 0))

        if player:
            filters["player_name"] = player
            filters["player_color"] = color
        if min_rating > 0:
            filters["min_rating"] = min_rating
        if max_rating > 0:
            filters["max_rating"] = max_rating
        if eco:
            filters["eco"] = eco
        if result and result != "Any":
            filters["result"] = result
        if event:
            filters["event"] = event
        if site:
            filters["site"] = site
        if min_year > 0:
            filters["min_year"] = min_year
        if max_year > 0:
            filters["max_year"] = max_year

        return filters

    def get_raw_settings(self) -> Dict[str, Any]:
        """Returns full raw settings dictionary including default/empty fields for UI inputs."""
        return {
            "player": self._settings.value("player", "", type=str),
            "color": self._settings.value("color", "Either Color", type=str),
            "min_rating": int(self._settings.value("min_rating", 0)),
            "max_rating": int(self._settings.value("max_rating", 0)),
            "eco": self._settings.value("eco", "", type=str),
            "result": self._settings.value("result", "Any", type=str),
            "event": self._settings.value("event", "", type=str),
            "site": self._settings.value("site", "", type=str),
            "min_year": int(self._settings.value("min_year", 0)),
            "max_year": int(self._settings.value("max_year", 0)),
        }

    def get_filter_dict(self) -> Dict[str, Any]:
        """
        Returns the formatted filter dictionary ready to be sent to the backend (scid-mgr).
        Maps player/color to 'player', 'white', or 'black'.
        """
        raw = self.get_raw_settings()
        filter_dict: Dict[str, Any] = {}

        player = raw.get("player", "").strip()
        color = raw.get("color", "Either Color")
        if player:
            if color == "As White" or color == "White":
                filter_dict["white"] = player
            elif color == "As Black" or color == "Black":
                filter_dict["black"] = player
            else:
                filter_dict["player"] = player

        min_r = int(raw.get("min_rating", 0))
        if min_r > 0:
            filter_dict["min_rating"] = min_r

        max_r = int(raw.get("max_rating", 0))
        if max_r > 0:
            filter_dict["max_rating"] = max_r

        eco = raw.get("eco", "").strip().upper()
        if eco:
            filter_dict["eco"] = eco

        result = raw.get("result", "Any")
        if result and result != "Any":
            filter_dict["result"] = result

        event = raw.get("event", "").strip()
        if event:
            filter_dict["event"] = event

        site = raw.get("site", "").strip()
        if site:
            filter_dict["site"] = site

        min_y = int(raw.get("min_year", 0))
        if min_y > 0:
            filter_dict["date_from"] = f"{min_y}.01.01"

        max_y = int(raw.get("max_year", 0))
        if max_y > 0:
            filter_dict["date_to"] = f"{max_y}.12.31"

        return filter_dict

    def has_active_filter(self) -> bool:
        """Return True if any reference filter is currently active."""
        return len(self.get_filter_dict()) > 0

    def get_summary_text(self) -> str:
        """Returns a human-readable 1-line summary of active filters."""
        parts = []
        raw = self.get_raw_settings()

        player = raw.get("player", "").strip()
        color = raw.get("color", "Either Color")
        if player:
            if color == "As White" or color == "White":
                parts.append(f"White: {player}")
            elif color == "As Black" or color == "Black":
                parts.append(f"Black: {player}")
            else:
                parts.append(f"Player: {player}")

        min_r = int(raw.get("min_rating", 0))
        max_r = int(raw.get("max_rating", 0))
        if min_r > 0 and max_r > 0:
            parts.append(f"Elo: {min_r}-{max_r}")
        elif min_r > 0:
            parts.append(f"Elo ≥ {min_r}")
        elif max_r > 0:
            parts.append(f"Elo ≤ {max_r}")

        eco = raw.get("eco", "").strip()
        if eco:
            parts.append(f"ECO: {eco}")

        result = raw.get("result", "Any")
        if result and result != "Any":
            parts.append(f"Result: {result}")

        event = raw.get("event", "").strip()
        if event:
            parts.append(f"Event: {event}")

        if not parts:
            return "No reference filters active (Entire Database)"
        return " | ".join(parts)

    def set_filters(
        self,
        player: str = "",
        color: str = "Either Color",
        min_rating: int = 0,
        max_rating: int = 0,
        eco: str = "",
        result: str = "Any",
        event: str = "",
        site: str = "",
        min_year: int = 0,
        max_year: int = 0,
    ):
        """Save new filter values and emit filtersChanged."""
        self._settings.setValue("player", player.strip())
        self._settings.setValue("color", color)
        self._settings.setValue("min_rating", int(min_rating))
        self._settings.setValue("max_rating", int(max_rating))
        self._settings.setValue("eco", eco.strip().upper())
        self._settings.setValue("result", result)
        self._settings.setValue("event", event.strip())
        self._settings.setValue("site", site.strip())
        self._settings.setValue("min_year", int(min_year))
        self._settings.setValue("max_year", int(max_year))
        self._settings.sync()

        formatted = self.get_filter_dict()
        self.filtersChanged.emit(formatted)

    def clear_filters(self):
        """Reset all reference filters to default (unfiltered)."""
        self.set_filters()


def get_reference_filter_manager() -> ReferenceFilterManager:
    """Convenience helper to access the global ReferenceFilterManager instance."""
    return ReferenceFilterManager.get_instance()
