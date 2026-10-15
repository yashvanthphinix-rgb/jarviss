from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS guild_settings (
 guild_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
 PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS moderation_cases (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
 target_id INTEGER NOT NULL, actor_id INTEGER NOT NULL, action TEXT NOT NULL,
 reason TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_guild_target ON moderation_cases(guild_id, target_id);
CREATE TABLE IF NOT EXISTS security_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
 event_type TEXT NOT NULL, actor_id INTEGER, details TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_security_events_guild ON security_events(guild_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_security_actor_event_time ON security_events(guild_id, actor_id, event_type, created_at);
CREATE TABLE IF NOT EXISTS security_incidents (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 guild_id INTEGER NOT NULL,
 actor_id INTEGER,
 severity TEXT NOT NULL,
 summary TEXT NOT NULL,
 event_count INTEGER NOT NULL DEFAULT 0,
 action_taken TEXT NOT NULL DEFAULT 'none',
 status TEXT NOT NULL DEFAULT 'open',
 created_at TEXT NOT NULL,
 resolved_at TEXT,
 resolved_by INTEGER
);
CREATE INDEX IF NOT EXISTS idx_security_incidents_guild ON security_incidents(guild_id, id DESC);

CREATE TABLE IF NOT EXISTS notification_log (
 dedupe_key TEXT PRIMARY KEY, guild_id INTEGER NOT NULL, destination_id INTEGER,
 status TEXT NOT NULL, details TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jtc_channels (
 channel_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL,
 owner_id INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS xp (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, points INTEGER NOT NULL DEFAULT 0,
 last_award_at TEXT, PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS invite_snapshots (
 guild_id INTEGER NOT NULL, code TEXT NOT NULL, uses INTEGER NOT NULL,
 inviter_id INTEGER, PRIMARY KEY (guild_id, code)
);
CREATE TABLE IF NOT EXISTS backups (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
 name TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL
);
"""

class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None
        # Hot-path guild settings (e.g. Join-to-Create IDs) stay in memory so
        # frequent gateway events do not need a SQLite read every time.
        self._settings_cache: dict[tuple[int, str], Any] = {}

    async def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        # WAL + NORMAL improves concurrent read/write behaviour for this
        # single-process bot. busy_timeout avoids immediate failures on brief locks.
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.execute("PRAGMA journal_mode = WAL")
        await self.conn.execute("PRAGMA synchronous = NORMAL")
        await self.conn.execute("PRAGMA busy_timeout = 3000")
        await self.conn.execute("PRAGMA temp_store = MEMORY")
        await self.conn.executescript(SCHEMA)
        await self.conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES('version', '1') "
            "ON CONFLICT(key) DO NOTHING"
        )
        await self.conn.commit()

    def _db(self) -> aiosqlite.Connection:
        if self.conn is None:
            raise RuntimeError("Database has not been initialized")
        return self.conn

    async def get_setting(self, guild_id: int, key: str, default: Any = None) -> Any:
        cache_key = (guild_id, key)
        if cache_key in self._settings_cache:
            return self._settings_cache[cache_key]
        async with self._db().execute(
            "SELECT value FROM guild_settings WHERE guild_id=? AND key=?",
            (guild_id, key),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            value = default
        else:
            try:
                value = json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                value = row["value"]
        self._settings_cache[cache_key] = value
        return value

    async def set_setting(self, guild_id: int, key: str, value: Any) -> None:
        encoded = json.dumps(value, ensure_ascii=False)
        await self._db().execute(
            "INSERT INTO guild_settings(guild_id,key,value) VALUES(?,?,?) "
            "ON CONFLICT(guild_id,key) DO UPDATE SET value=excluded.value",
            (guild_id, key, encoded),
        )
        await self._db().commit()
        self._settings_cache[(guild_id, key)] = value

    async def record_case(self, guild_id: int, target_id: int, actor_id: int,
                          action: str, reason: str, created_at: str) -> int:
        cur = await self._db().execute(
            "INSERT INTO moderation_cases(guild_id,target_id,actor_id,action,reason,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (guild_id, target_id, actor_id, action, reason, created_at),
        )
        await self._db().commit()
        return int(cur.lastrowid)

    async def get_cases(self, guild_id: int, target_id: int, limit: int = 10):
        async with self._db().execute(
            "SELECT * FROM moderation_cases WHERE guild_id=? AND target_id=? "
            "ORDER BY id DESC LIMIT ?",
            (guild_id, target_id, limit),
        ) as cur:
            return await cur.fetchall()

    async def record_security_event(self, guild_id: int, event_type: str,
                                    actor_id: int | None, details: str, created_at: str) -> None:
        await self._db().execute(
            "INSERT INTO security_events(guild_id,event_type,actor_id,details,created_at) "
            "VALUES(?,?,?,?,?)",
            (guild_id, event_type, actor_id, details, created_at),
        )
        await self._db().commit()

    async def recent_security_events(self, guild_id: int, limit: int = 10):
        async with self._db().execute(
            "SELECT * FROM security_events WHERE guild_id=? ORDER BY id DESC LIMIT ?",
            (guild_id, limit),
        ) as cur:
            return await cur.fetchall()


    async def count_risky_events(self, guild_id: int, actor_id: int, since: str) -> int:
        async with self._db().execute(
            "SELECT COUNT(*) AS n FROM security_events "
            "WHERE guild_id=? AND actor_id=? AND event_type LIKE 'risky:%' AND created_at>=?",
            (guild_id, actor_id, since),
        ) as cur:
            row = await cur.fetchone()
        return int(row["n"] if row else 0)

    async def create_security_incident(
        self, guild_id: int, actor_id: int | None, severity: str, summary: str,
        event_count: int, action_taken: str, created_at: str, dedupe_seconds: int = 60,
    ) -> int | None:
        """Create one open incident per actor per dedupe window; None means deduplicated."""
        from datetime import datetime, timedelta, timezone
        try:
            now = datetime.fromisoformat(created_at)
        except ValueError:
            now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(seconds=max(1, dedupe_seconds))).isoformat()
        async with self._db().execute(
            "SELECT id FROM security_incidents WHERE guild_id=? AND actor_id IS ? "
            "AND status='open' AND created_at>=? ORDER BY id DESC LIMIT 1",
            (guild_id, actor_id, cutoff),
        ) as cur:
            existing = await cur.fetchone()
        if existing:
            return None
        cur = await self._db().execute(
            "INSERT INTO security_incidents(guild_id,actor_id,severity,summary,event_count,action_taken,status,created_at) "
            "VALUES(?,?,?,?,?,?, 'open', ?)",
            (guild_id, actor_id, severity, summary, event_count, action_taken, created_at),
        )
        await self._db().commit()
        return int(cur.lastrowid)

    async def update_incident_action(self, incident_id: int, action_taken: str) -> None:
        await self._db().execute(
            "UPDATE security_incidents SET action_taken=? WHERE id=?",
            (action_taken, incident_id),
        )
        await self._db().commit()

    async def recent_security_incidents(self, guild_id: int, limit: int = 10):
        async with self._db().execute(
            "SELECT * FROM security_incidents WHERE guild_id=? ORDER BY id DESC LIMIT ?",
            (guild_id, max(1, min(50, limit))),
        ) as cur:
            return await cur.fetchall()

    async def resolve_security_incident(self, guild_id: int, incident_id: int, user_id: int, resolved_at: str) -> bool:
        cur = await self._db().execute(
            "UPDATE security_incidents SET status='resolved', resolved_at=?, resolved_by=? "
            "WHERE guild_id=? AND id=? AND status='open'",
            (resolved_at, user_id, guild_id, incident_id),
        )
        await self._db().commit()
        return cur.rowcount > 0

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()
            self.conn = None
        self._settings_cache.clear()
