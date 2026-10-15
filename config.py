from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    discord_token: str
    database_path: str
    creator_name: str
    message_content_intent: bool
    sync_commands_on_start: bool
    default_security_threshold: int
    default_security_window_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        db_path = os.getenv("DATABASE_PATH", "data/jarvis.sqlite3")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return cls(
            discord_token=os.getenv("DISCORD_TOKEN", "").strip(),
            database_path=db_path,
            creator_name=os.getenv("JARVIS_CREATOR", "JARVIS Development Team"),
            message_content_intent=env_bool("MESSAGE_CONTENT_INTENT", False),
            sync_commands_on_start=env_bool("SYNC_COMMANDS_ON_START", True),
            default_security_threshold=max(2, int(os.getenv("SECURITY_THRESHOLD", "5"))),
            default_security_window_seconds=min(50000, max(1, int(os.getenv("SECURITY_WINDOW_SECONDS", "12")))),
        )
