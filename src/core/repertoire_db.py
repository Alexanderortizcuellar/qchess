"""
Repertoire database repository.

Storage design:
    - repertoire_nodes: holds both folders and repertoire entries in a
      single adjacency-list tree.  node_type is either "folder" or
      "repertoire".
    - repertoires: the actual PGN payload for each repertoire node.

Source of truth: PGN text.  No move-tree tables, no JSON move storage.
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS repertoire_nodes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id  INTEGER REFERENCES repertoire_nodes(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    node_type  TEXT    NOT NULL CHECK (node_type IN ('folder', 'repertoire')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS repertoires (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id    INTEGER NOT NULL UNIQUE REFERENCES repertoire_nodes(id) ON DELETE CASCADE,
    pgn_text   TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_nodes_parent ON repertoire_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_repertoires_node ON repertoires(node_id);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Node value object
# ---------------------------------------------------------------------------

class RepertoireNode:
    """Lightweight value object returned by the repository."""

    __slots__ = ("id", "parent_id", "name", "node_type", "sort_order",
                 "created_at", "updated_at")

    def __init__(self, row: tuple):
        (self.id, self.parent_id, self.name, self.node_type,
         self.sort_order, self.created_at, self.updated_at) = row

    def is_folder(self) -> bool:
        return self.node_type == "folder"

    def is_repertoire(self) -> bool:
        return self.node_type == "repertoire"

    def __repr__(self) -> str:
        return f"<RepertoireNode id={self.id} type={self.node_type!r} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class RepertoireRepository:
    """
    SQLite-backed data-access layer for the Repertoire Manager.

    Usage::

        repo = RepertoireRepository("/path/to/repertoires.db")
        folder = repo.create_folder("White")
        rep = repo.create_repertoire("Italian", parent_id=folder.id)
        repo.save_pgn(rep.id, pgn_text)
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _node_from_row(self, row) -> Optional[RepertoireNode]:
        if row is None:
            return None
        return RepertoireNode((
            row["id"], row["parent_id"], row["name"], row["node_type"],
            row["sort_order"], row["created_at"], row["updated_at"],
        ))

    # ------------------------------------------------------------------
    # Node queries
    # ------------------------------------------------------------------

    def get_node(self, node_id: int) -> Optional[RepertoireNode]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM repertoire_nodes WHERE id = ?", (node_id,)
            ).fetchone()
            return self._node_from_row(row)

    def get_children(self, parent_id: Optional[int]) -> list:
        """Return direct children of *parent_id* (None = root level)."""
        with self._connect() as conn:
            if parent_id is None:
                rows = conn.execute(
                    "SELECT * FROM repertoire_nodes WHERE parent_id IS NULL "
                    "ORDER BY sort_order, name COLLATE NOCASE"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM repertoire_nodes WHERE parent_id = ? "
                    "ORDER BY sort_order, name COLLATE NOCASE",
                    (parent_id,),
                ).fetchall()
            return [self._node_from_row(r) for r in rows]

    def get_all_nodes(self) -> list:
        """Return all nodes ordered for tree reconstruction."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM repertoire_nodes "
                "ORDER BY sort_order, name COLLATE NOCASE"
            ).fetchall()
            return [self._node_from_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Folder CRUD
    # ------------------------------------------------------------------

    def create_folder(self, name: str,
                      parent_id: Optional[int] = None) -> RepertoireNode:
        now = _now_utc()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO repertoire_nodes "
                "(parent_id, name, node_type, created_at, updated_at) "
                "VALUES (?, ?, 'folder', ?, ?)",
                (parent_id, name, now, now),
            )
            new_id = cur.lastrowid
            conn.commit()
        return self.get_node(new_id)

    # ------------------------------------------------------------------
    # Repertoire CRUD
    # ------------------------------------------------------------------

    def create_repertoire(self, name: str,
                          parent_id: Optional[int] = None) -> RepertoireNode:
        now = _now_utc()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO repertoire_nodes "
                "(parent_id, name, node_type, created_at, updated_at) "
                "VALUES (?, ?, 'repertoire', ?, ?)",
                (parent_id, name, now, now),
            )
            node_id = cur.lastrowid
            conn.execute(
                "INSERT INTO repertoires (node_id, pgn_text, created_at, updated_at) "
                "VALUES (?, '', ?, ?)",
                (node_id, now, now),
            )
            conn.commit()
        return self.get_node(node_id)

    def get_pgn(self, node_id: int) -> str:
        """Return the PGN text for a repertoire node, or '' if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT pgn_text FROM repertoires WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            return row["pgn_text"] if row else ""

    def save_pgn(self, node_id: int, pgn_text: str):
        """Persist (update) the PGN text for a repertoire node."""
        now = _now_utc()
        with self._connect() as conn:
            conn.execute(
                "UPDATE repertoires SET pgn_text = ?, updated_at = ? "
                "WHERE node_id = ?",
                (pgn_text, now, node_id),
            )
            conn.execute(
                "UPDATE repertoire_nodes SET updated_at = ? WHERE id = ?",
                (now, node_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Shared CRUD
    # ------------------------------------------------------------------

    def rename_node(self, node_id: int, new_name: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE repertoire_nodes SET name = ?, updated_at = ? WHERE id = ?",
                (new_name, _now_utc(), node_id),
            )
            conn.commit()

    def move_node(self, node_id: int, new_parent_id: Optional[int]):
        """Move a node to a different parent (or to root if new_parent_id is None)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE repertoire_nodes SET parent_id = ?, updated_at = ? WHERE id = ?",
                (new_parent_id, _now_utc(), node_id),
            )
            conn.commit()

    def delete_node(self, node_id: int):
        """Delete a node and all its descendants (via ON DELETE CASCADE)."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM repertoire_nodes WHERE id = ?", (node_id,)
            )
            conn.commit()

    # ------------------------------------------------------------------
    # PGN import helper
    # ------------------------------------------------------------------

    def import_pgn_as_repertoire(self, name: str, pgn_text: str,
                                  parent_id: Optional[int] = None) -> RepertoireNode:
        """Create a new repertoire node and immediately populate its PGN."""
        node = self.create_repertoire(name, parent_id)
        self.save_pgn(node.id, pgn_text)
        return node

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> str:
        return self._db_path
