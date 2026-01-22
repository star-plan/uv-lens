from __future__ import annotations

import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from packaging.version import InvalidVersion, Version


_SCHEMA_VERSION = 1


def default_cache_path() -> Path:
    """
    返回默认缓存数据库路径（用户目录下全局共用）。
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "uv-lens" / "cache.sqlite3"
        home = Path.home()
        return home / "AppData" / "Local" / "uv-lens" / "cache.sqlite3"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "uv-lens" / "cache.sqlite3"

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / "uv-lens" / "cache.sqlite3"

    return Path.home() / ".cache" / "uv-lens" / "cache.sqlite3"


def index_scope_key(index_url: str, extra_index_urls: tuple[str, ...]) -> str:
    """
    将索引配置归一化为缓存的 scope key。
    """
    parts = [index_url.strip().rstrip("/")]
    parts.extend(u.strip().rstrip("/") for u in extra_index_urls)
    return "|".join(parts)


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """
    单个包在缓存中的记录。
    """

    latest: Version | None
    resolved_index_url: str | None
    not_found: bool
    error: str | None
    fetched_at: int


class CacheDB:
    """
    SQLite 缓存数据库（全局共用）。
    """

    def __init__(self, path: Path) -> None:
        """
        初始化缓存数据库连接（必要时创建表结构）。
        """
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        """
        关闭数据库连接。
        """
        self._conn.close()

    def _ensure_schema(self) -> None:
        """
        创建或升级缓存数据库表结构。
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS package_cache (
                scope TEXT NOT NULL,
                name TEXT NOT NULL,
                latest TEXT,
                resolved_index_url TEXT,
                not_found INTEGER NOT NULL,
                error TEXT,
                fetched_at INTEGER NOT NULL,
                PRIMARY KEY (scope, name)
            )
            """
        )
        cur.execute("SELECT value FROM meta WHERE key = 'schema_version'")
        row = cur.fetchone()
        if row is None:
            cur.execute("INSERT INTO meta(key, value) VALUES('schema_version', ?)", (str(_SCHEMA_VERSION),))
            self._conn.commit()
            return

        if int(row["value"]) != _SCHEMA_VERSION:
            cur.execute("DELETE FROM package_cache")
            cur.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (str(_SCHEMA_VERSION),))
            self._conn.commit()

    def get(self, *, scope: str, normalized_name: str, ttl_s: int) -> CacheEntry | None:
        """
        获取缓存记录；若过期或不存在则返回 None。
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT latest, resolved_index_url, not_found, error, fetched_at
            FROM package_cache
            WHERE scope = ? AND name = ?
            """,
            (scope, normalized_name),
        )
        row = cur.fetchone()
        if row is None:
            return None

        fetched_at = int(row["fetched_at"])
        if ttl_s > 0 and (time.time() - fetched_at) > ttl_s:
            return None

        latest_raw = row["latest"]
        latest: Version | None = None
        if latest_raw:
            try:
                latest = Version(str(latest_raw))
            except InvalidVersion:
                latest = None

        return CacheEntry(
            latest=latest,
            resolved_index_url=row["resolved_index_url"],
            not_found=bool(row["not_found"]),
            error=row["error"],
            fetched_at=fetched_at,
        )

    def set(
        self,
        *,
        scope: str,
        normalized_name: str,
        latest: Version | None,
        resolved_index_url: str | None,
        not_found: bool,
        error: str | None,
    ) -> None:
        """
        写入缓存记录。
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO package_cache(scope, name, latest, resolved_index_url, not_found, error, fetched_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope, name) DO UPDATE SET
                latest = excluded.latest,
                resolved_index_url = excluded.resolved_index_url,
                not_found = excluded.not_found,
                error = excluded.error,
                fetched_at = excluded.fetched_at
            """,
            (
                scope,
                normalized_name,
                str(latest) if latest else None,
                resolved_index_url,
                1 if not_found else 0,
                error,
                int(time.time()),
            ),
        )
        self._conn.commit()
