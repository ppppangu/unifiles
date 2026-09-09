from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from .errors import APIError
from .settings import Settings


def now() -> str:
    return datetime.now(UTC).isoformat()


def identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def decode(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def key_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def derived_api_key(bootstrap_key: str, key_id: str) -> str:
    material = hmac.new(
        bootstrap_key.encode(),
        f"unifiles/api-key/v1/{key_id}".encode(),
        hashlib.sha256,
    ).digest()
    return f"sk_live_{material.hex()}"


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    scopes TEXT NOT NULL,
    expires_at TEXT,
    last_used_at TEXT,
    created_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size INTEGER NOT NULL,
    metadata TEXT NOT NULL,
    tags TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_user_created ON files(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS extractions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    file_id TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    options TEXT NOT NULL,
    progress INTEGER,
    markdown TEXT,
    total_pages INTEGER,
    metadata TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_extractions_file_created ON extractions(file_id, created_at DESC);

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    chunking_strategy TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_kb_user_created ON knowledge_bases(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    kb_id TEXT NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    extraction_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
    title TEXT,
    status TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    metadata TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    indexed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_documents_kb_created ON documents(kb_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    kb_id TEXT NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    content TEXT NOT NULL,
    vector TEXT NOT NULL,
    metadata TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_kb ON chunks(kb_id, position);

CREATE TABLE IF NOT EXISTS webhooks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    url TEXT NOT NULL,
    events TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    secret TEXT NOT NULL,
    last_delivery_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS idempotency (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    operation TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, key, operation)
);
"""


class Store:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.files_dir.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(settings.database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self.connection.executescript(SCHEMA)
            self.connection.commit()
        self._scrub_sensitive_idempotency()
        self._ensure_bootstrap_key()

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def _ensure_bootstrap_key(self) -> None:
        bootstrap_key = self.settings.bootstrap_api_key
        if bootstrap_key is None or not bootstrap_key.get_secret_value().strip():
            raise RuntimeError(
                "UNIFILES_BOOTSTRAP_API_KEY must be set before starting the server"
            )
        value = bootstrap_key.get_secret_value()
        if value in {"<bootstrap-key>", "replace-me", "change-me"}:
            raise RuntimeError("UNIFILES_BOOTSTRAP_API_KEY must not use a public default value")
        digest = key_hash(value)
        with self._lock:
            self.connection.execute(
                "DELETE FROM api_keys WHERE user_id = 'local' AND name = 'bootstrap' AND key_hash != ?",
                (digest,),
            )
            existing = self.connection.execute(
                "SELECT id FROM api_keys WHERE key_hash = ?", (digest,)
            ).fetchone()
            if existing:
                self.connection.commit()
                return
            self.connection.execute(
                """
                INSERT INTO api_keys
                    (id, user_id, name, key_hash, key_prefix, scopes, created_at)
                VALUES (?, 'local', 'bootstrap', ?, ?, '["*"]', ?)
                """,
                (identifier("key"), digest, value[:12], now()),
            )
            self.connection.commit()

    def _scrub_sensitive_idempotency(self) -> None:
        """Remove raw API keys left by versions before encrypted replay metadata."""

        with self._lock:
            rows = self.connection.execute(
                "SELECT user_id, key, operation, data FROM idempotency "
                "WHERE operation = 'api-keys.create'"
            ).fetchall()
            for row in rows:
                data = decode(row["data"], None)
                if not isinstance(data, dict) or "key" not in data:
                    continue
                data["key"] = None
                data["_key_id"] = data.get("_key_id") or data.get("id")
                self.connection.execute(
                    "UPDATE idempotency SET data = ? WHERE user_id = ? AND key = ? AND operation = ?",
                    (encode(data), row["user_id"], row["key"], row["operation"]),
                )
            self.connection.commit()

    def execute(self, sql: str, values: Iterable[Any] = ()) -> None:
        with self._lock:
            self.connection.execute(sql, tuple(values))
            self.connection.commit()

    def one(self, sql: str, values: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self.connection.execute(sql, tuple(values)).fetchone()

    def all(self, sql: str, values: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self.connection.execute(sql, tuple(values)).fetchall())

    def authenticate(self, token: str) -> dict[str, Any]:
        row = self.one(
            "SELECT * FROM api_keys WHERE key_hash = ? AND revoked = 0", (key_hash(token),)
        )
        if not row:
            raise APIError(401, "INVALID_API_KEY", "API key is invalid or revoked")
        if row["expires_at"]:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= datetime.now(UTC):
                raise APIError(401, "EXPIRED_API_KEY", "API key has expired")
        self.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (now(), row["id"]))
        return {"user_id": row["user_id"], "key_id": row["id"], "scopes": decode(row["scopes"], [])}

    def idempotent_get(
        self, user_id: str, key: str | None, operation: str
    ) -> dict[str, Any] | None:
        if not key:
            return None
        row = self.one(
            "SELECT data FROM idempotency WHERE user_id = ? AND key = ? AND operation = ?",
            (user_id, key, operation),
        )
        data = decode(row["data"], None) if row else None
        if operation == "api-keys.create" and isinstance(data, dict):
            data.pop("key", None)
            data["_key_id"] = data.get("_key_id") or data.get("id")
        return data

    def idempotent_put(
        self, user_id: str, key: str | None, operation: str, data: dict[str, Any]
    ) -> None:
        if not key:
            return
        if operation == "api-keys.create":
            data = {**data, "key": None, "_key_id": data.get("id")}
        self.execute(
            "INSERT OR REPLACE INTO idempotency (user_id, key, operation, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, key, operation, encode(data), now()),
        )

    def insert_file(
        self,
        *,
        file_id: str,
        user_id: str,
        filename: str,
        content_type: str,
        size: int,
        metadata: dict[str, Any],
        tags: list[str],
        storage_path: str,
    ) -> dict[str, Any]:
        created_at = now()
        self.execute(
            "INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                file_id,
                user_id,
                filename,
                content_type,
                size,
                encode(metadata),
                encode(tags),
                storage_path,
                created_at,
            ),
        )
        return self.file(user_id, file_id)

    def file(self, user_id: str, file_id: str, *, internal: bool = False) -> dict[str, Any]:
        row = self.one("SELECT * FROM files WHERE user_id = ? AND id = ?", (user_id, file_id))
        if not row:
            raise APIError(404, "FILE_NOT_FOUND", "File not found", details={"file_id": file_id})
        data = self._file(row)
        if internal:
            data["storage_path"] = row["storage_path"]
        return data

    def list_files(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
        tags: list[str] | None,
        content_type: str | None,
        sort_by: str,
        order: str,
    ) -> dict[str, Any]:
        clauses = ["user_id = ?"]
        values: list[Any] = [user_id]
        if content_type:
            clauses.append("content_type = ?")
            values.append(content_type)
        allowed_sort = {"created_at", "filename", "size"}
        sort = sort_by if sort_by in allowed_sort else "created_at"
        direction = "ASC" if order.lower() == "asc" else "DESC"
        where = " AND ".join(clauses)
        rows = self.all(
            f"SELECT * FROM files WHERE {where} ORDER BY {sort} {direction}",
            values,
        )
        items = [self._file(row) for row in rows]
        if tags:
            required = set(tags)
            items = [item for item in items if required.issubset(set(item["tags"]))]
        total = len(items)
        page = items[offset : offset + limit]
        return {
            "items": page,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(page) < total,
        }

    def delete_file(self, user_id: str, file_id: str) -> str:
        record = self.file(user_id, file_id, internal=True)
        self.execute("DELETE FROM files WHERE user_id = ? AND id = ?", (user_id, file_id))
        return str(record["storage_path"])

    @staticmethod
    def _file(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "filename": row["filename"],
            "content_type": row["content_type"],
            "size": row["size"],
            "metadata": decode(row["metadata"], {}),
            "tags": decode(row["tags"], []),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_extraction(
        self, user_id: str, file_id: str, mode: str, options: dict[str, Any]
    ) -> dict[str, Any]:
        self.file(user_id, file_id)
        extraction_id = identifier("ext")
        self.execute(
            """
            INSERT INTO extractions
                (id, user_id, file_id, status, mode, options, progress, created_at)
            VALUES (?, ?, ?, 'pending', ?, ?, 0, ?)
            """,
            (extraction_id, user_id, file_id, mode, encode(options), now()),
        )
        return self.extraction(user_id, extraction_id)

    def extraction(
        self, user_id: str, extraction_id: str, *, internal: bool = False
    ) -> dict[str, Any]:
        row = self.one(
            "SELECT * FROM extractions WHERE user_id = ? AND id = ?", (user_id, extraction_id)
        )
        if not row:
            raise APIError(
                404,
                "EXTRACTION_NOT_FOUND",
                "Extraction not found",
                details={"extraction_id": extraction_id},
            )
        result = self._extraction(row)
        if internal:
            result["options"] = decode(row["options"], {})
        return result

    def list_extractions(
        self, user_id: str, file_id: str, limit: int, offset: int
    ) -> dict[str, Any]:
        self.file(user_id, file_id)
        rows = self.all(
            "SELECT * FROM extractions WHERE user_id = ? AND file_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, file_id, limit, offset),
        )
        count = self.one(
            "SELECT COUNT(*) AS count FROM extractions WHERE user_id = ? AND file_id = ?",
            (user_id, file_id),
        )
        total = int(count["count"] if count else 0)
        return {
            "items": [self._extraction(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
        }

    def latest_completed_extraction(self, user_id: str, file_id: str) -> dict[str, Any]:
        row = self.one(
            """
            SELECT * FROM extractions
            WHERE user_id = ? AND file_id = ? AND status = 'completed'
            ORDER BY completed_at DESC LIMIT 1
            """,
            (user_id, file_id),
        )
        if not row:
            raise APIError(
                409,
                "EXTRACTION_REQUIRED",
                "The file must have a completed extraction before indexing",
                details={"file_id": file_id},
            )
        return self._extraction(row)

    def update_extraction(self, extraction_id: str, **changes: Any) -> None:
        allowed = {
            "status",
            "progress",
            "markdown",
            "total_pages",
            "metadata",
            "error",
            "completed_at",
        }
        values = {key: value for key, value in changes.items() if key in allowed}
        for key in ("metadata", "error"):
            if key in values and values[key] is not None:
                values[key] = encode(values[key])
        if not values:
            return
        assignments = ", ".join(f"{key} = ?" for key in values)
        self.execute(
            f"UPDATE extractions SET {assignments} WHERE id = ?",
            (*values.values(), extraction_id),
        )

    def pending_extractions(self) -> list[dict[str, str]]:
        rows = self.all(
            "SELECT id, user_id FROM extractions WHERE status IN ('pending', 'processing')"
        )
        return [{"id": row["id"], "user_id": row["user_id"]} for row in rows]

    @staticmethod
    def _extraction(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "file_id": row["file_id"],
            "status": row["status"],
            "mode": row["mode"],
            "progress": row["progress"],
            "markdown": row["markdown"],
            "total_pages": row["total_pages"],
            "metadata": decode(row["metadata"], None),
            "error": decode(row["error"], None),
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }

    def create_kb(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        kb_id = identifier("kb")
        created_at = now()
        self.execute(
            "INSERT INTO knowledge_bases VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                kb_id,
                user_id,
                payload["name"],
                payload.get("description"),
                encode(payload.get("chunking_strategy", {})),
                encode(payload.get("metadata", {})),
                created_at,
            ),
        )
        return self.kb(user_id, kb_id)

    def kb(self, user_id: str, kb_id: str) -> dict[str, Any]:
        row = self.one(
            "SELECT * FROM knowledge_bases WHERE user_id = ? AND id = ?", (user_id, kb_id)
        )
        if not row:
            raise APIError(
                404, "KB_NOT_FOUND", "Knowledge base not found", details={"kb_id": kb_id}
            )
        return self._kb(row)

    def list_kbs(self, user_id: str, limit: int, offset: int) -> dict[str, Any]:
        rows = self.all(
            "SELECT * FROM knowledge_bases WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
        count = self.one(
            "SELECT COUNT(*) AS count FROM knowledge_bases WHERE user_id = ?", (user_id,)
        )
        total = int(count["count"] if count else 0)
        return {
            "items": [self._kb(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
        }

    def update_kb(self, user_id: str, kb_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        self.kb(user_id, kb_id)
        allowed = {"name", "description", "chunking_strategy", "metadata"}
        values = {key: value for key, value in changes.items() if key in allowed}
        for key in ("chunking_strategy", "metadata"):
            if key in values:
                values[key] = encode(values[key])
        values["updated_at"] = now()
        assignments = ", ".join(f"{key} = ?" for key in values)
        self.execute(
            f"UPDATE knowledge_bases SET {assignments} WHERE user_id = ? AND id = ?",
            (*values.values(), user_id, kb_id),
        )
        return self.kb(user_id, kb_id)

    def delete_kb(self, user_id: str, kb_id: str) -> None:
        self.kb(user_id, kb_id)
        self.execute("DELETE FROM knowledge_bases WHERE user_id = ? AND id = ?", (user_id, kb_id))

    def _kb(self, row: sqlite3.Row) -> dict[str, Any]:
        document_count = self.one(
            "SELECT COUNT(*) AS count FROM documents WHERE kb_id = ?", (row["id"],)
        )
        chunk_count = self.one("SELECT COUNT(*) AS count FROM chunks WHERE kb_id = ?", (row["id"],))
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "chunking_strategy": decode(row["chunking_strategy"], {}),
            "document_count": int(document_count["count"] if document_count else 0),
            "chunk_count": int(chunk_count["count"] if chunk_count else 0),
            "metadata": decode(row["metadata"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_document(
        self, user_id: str, kb_id: str, file_id: str, title: str | None, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        self.kb(user_id, kb_id)
        file = self.file(user_id, file_id)
        extraction = self.latest_completed_extraction(user_id, file_id)
        document_id = identifier("doc")
        self.execute(
            """
            INSERT INTO documents
                (id, user_id, kb_id, file_id, extraction_id, title, status, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                document_id,
                user_id,
                kb_id,
                file_id,
                extraction["id"],
                title or file["filename"],
                encode(metadata),
                now(),
            ),
        )
        return self.document(user_id, kb_id, document_id, internal=True)

    def document(
        self, user_id: str, kb_id: str, document_id: str, *, internal: bool = False
    ) -> dict[str, Any]:
        row = self.one(
            "SELECT * FROM documents WHERE user_id = ? AND kb_id = ? AND id = ?",
            (user_id, kb_id, document_id),
        )
        if not row:
            raise APIError(
                404,
                "DOCUMENT_NOT_FOUND",
                "Document not found",
                details={"document_id": document_id},
            )
        result = self._document(row)
        if internal:
            result["extraction_id"] = row["extraction_id"]
            result["user_id"] = row["user_id"]
        return result

    def list_documents(self, user_id: str, kb_id: str, limit: int, offset: int) -> dict[str, Any]:
        self.kb(user_id, kb_id)
        rows = self.all(
            "SELECT * FROM documents WHERE user_id = ? AND kb_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, kb_id, limit, offset),
        )
        count = self.one(
            "SELECT COUNT(*) AS count FROM documents WHERE user_id = ? AND kb_id = ?",
            (user_id, kb_id),
        )
        total = int(count["count"] if count else 0)
        return {
            "items": [self._document(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
        }

    def update_document(self, document_id: str, **changes: Any) -> None:
        allowed = {"status", "chunk_count", "error", "indexed_at"}
        values = {key: value for key, value in changes.items() if key in allowed}
        if "error" in values and values["error"] is not None:
            values["error"] = encode(values["error"])
        assignments = ", ".join(f"{key} = ?" for key in values)
        self.execute(
            f"UPDATE documents SET {assignments} WHERE id = ?", (*values.values(), document_id)
        )

    def pending_documents(self) -> list[dict[str, str]]:
        rows = self.all(
            "SELECT id, user_id, kb_id FROM documents WHERE status IN ('pending', 'indexing')"
        )
        return [{"id": row["id"], "user_id": row["user_id"], "kb_id": row["kb_id"]} for row in rows]

    def delete_document(self, user_id: str, kb_id: str, document_id: str) -> None:
        self.document(user_id, kb_id, document_id)
        self.execute(
            "DELETE FROM documents WHERE user_id = ? AND kb_id = ? AND id = ?",
            (user_id, kb_id, document_id),
        )

    @staticmethod
    def _document(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "kb_id": row["kb_id"],
            "file_id": row["file_id"],
            "title": row["title"],
            "status": row["status"],
            "chunk_count": row["chunk_count"],
            "metadata": decode(row["metadata"], {}),
            "error": decode(row["error"], None),
            "created_at": row["created_at"],
            "indexed_at": row["indexed_at"],
        }

    def replace_chunks(self, document: dict[str, Any], chunks: list[dict[str, Any]]) -> None:
        with self._lock:
            self.connection.execute("DELETE FROM chunks WHERE document_id = ?", (document["id"],))
            self.connection.executemany(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        chunk["id"],
                        document["user_id"],
                        document["kb_id"],
                        document["id"],
                        chunk["position"],
                        chunk["content"],
                        encode(chunk["vector"]),
                        encode(chunk["metadata"]),
                    )
                    for chunk in chunks
                ],
            )
            self.connection.commit()

    def chunks(self, user_id: str, kb_id: str) -> list[dict[str, Any]]:
        self.kb(user_id, kb_id)
        rows = self.all(
            """
            SELECT c.*, d.title AS document_title
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE c.user_id = ? AND c.kb_id = ?
            """,
            (user_id, kb_id),
        )
        return [
            {
                "id": row["id"],
                "document_id": row["document_id"],
                "document_title": row["document_title"],
                "content": row["content"],
                "vector": decode(row["vector"], []),
                "metadata": decode(row["metadata"], {}),
            }
            for row in rows
        ]

    def create_webhook(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        webhook_id = identifier("wh")
        self.execute(
            "INSERT INTO webhooks VALUES (?, ?, ?, ?, 1, ?, ?, NULL, ?, NULL)",
            (
                webhook_id,
                user_id,
                payload["url"],
                encode(payload["events"]),
                payload.get("description"),
                secrets.token_hex(32),
                now(),
            ),
        )
        return self.webhook(user_id, webhook_id)

    def webhook(self, user_id: str, webhook_id: str, *, internal: bool = False) -> dict[str, Any]:
        row = self.one("SELECT * FROM webhooks WHERE user_id = ? AND id = ?", (user_id, webhook_id))
        if not row:
            raise APIError(404, "WEBHOOK_NOT_FOUND", "Webhook not found")
        result = self._webhook(row)
        if internal:
            result["secret"] = row["secret"]
        return result

    def list_webhooks(self, user_id: str, limit: int, offset: int) -> dict[str, Any]:
        rows = self.all(
            "SELECT * FROM webhooks WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
        count = self.one("SELECT COUNT(*) AS count FROM webhooks WHERE user_id = ?", (user_id,))
        total = int(count["count"] if count else 0)
        return {
            "items": [self._webhook(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
        }

    def update_webhook(
        self, user_id: str, webhook_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        self.webhook(user_id, webhook_id)
        allowed = {"url", "events", "enabled", "description"}
        values = {key: value for key, value in changes.items() if key in allowed}
        if "events" in values:
            values["events"] = encode(values["events"])
        if "enabled" in values:
            values["enabled"] = int(values["enabled"])
        values["updated_at"] = now()
        assignments = ", ".join(f"{key} = ?" for key in values)
        self.execute(
            f"UPDATE webhooks SET {assignments} WHERE user_id = ? AND id = ?",
            (*values.values(), user_id, webhook_id),
        )
        return self.webhook(user_id, webhook_id)

    def delete_webhook(self, user_id: str, webhook_id: str) -> None:
        self.webhook(user_id, webhook_id)
        self.execute("DELETE FROM webhooks WHERE user_id = ? AND id = ?", (user_id, webhook_id))

    def matching_webhooks(self, user_id: str, event: str) -> list[dict[str, Any]]:
        rows = self.all("SELECT * FROM webhooks WHERE user_id = ? AND enabled = 1", (user_id,))
        return [
            self.webhook(user_id, row["id"], internal=True)
            for row in rows
            if event in decode(row["events"], [])
        ]

    def mark_webhook_delivery(self, webhook_id: str) -> None:
        self.execute("UPDATE webhooks SET last_delivery_at = ? WHERE id = ?", (now(), webhook_id))

    @staticmethod
    def _webhook(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "url": row["url"],
            "events": decode(row["events"], []),
            "enabled": bool(row["enabled"]),
            "description": row["description"],
            "last_delivery_at": row["last_delivery_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_api_key(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        key_id = identifier("key")
        bootstrap_key = self.settings.bootstrap_api_key
        if bootstrap_key is None:
            raise RuntimeError("UNIFILES_BOOTSTRAP_API_KEY must be set")
        raw_key = derived_api_key(bootstrap_key.get_secret_value(), key_id)
        created_at = now()
        self.execute(
            """
            INSERT INTO api_keys
                (id, user_id, name, key_hash, key_prefix, scopes, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key_id,
                user_id,
                payload["name"],
                key_hash(raw_key),
                raw_key[:12],
                encode(payload.get("scopes", ["*"])),
                payload.get("expires_at"),
                created_at,
            ),
        )
        result = self.api_key(user_id, key_id)
        result["key"] = raw_key
        return result

    def restore_idempotent_api_key(self, cached: dict[str, Any]) -> dict[str, Any]:
        key_id = cached.get("_key_id")
        bootstrap_key = self.settings.bootstrap_api_key
        if not isinstance(key_id, str) or bootstrap_key is None:
            raise APIError(
                409,
                "IDEMPOTENCY_REPLAY_UNAVAILABLE",
                "The idempotency record cannot be replayed after credential rotation",
            )
        raw_key = derived_api_key(bootstrap_key.get_secret_value(), key_id)
        row = self.one(
            "SELECT key_hash FROM api_keys WHERE user_id = 'local' AND id = ? AND revoked = 0",
            (key_id,),
        )
        if not row or not hmac.compare_digest(row["key_hash"], key_hash(raw_key)):
            raise APIError(
                409,
                "IDEMPOTENCY_REPLAY_UNAVAILABLE",
                "The idempotency record cannot be replayed after credential rotation",
            )
        result = {key: value for key, value in cached.items() if key not in {"_key_id", "key"}}
        result["key"] = raw_key
        return result

    def api_key(self, user_id: str, key_id: str) -> dict[str, Any]:
        row = self.one(
            "SELECT * FROM api_keys WHERE user_id = ? AND id = ? AND revoked = 0",
            (user_id, key_id),
        )
        if not row:
            raise APIError(404, "API_KEY_NOT_FOUND", "API key not found")
        return self._api_key(row)

    def list_api_keys(self, user_id: str, limit: int, offset: int) -> dict[str, Any]:
        rows = self.all(
            "SELECT * FROM api_keys WHERE user_id = ? AND revoked = 0 ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
        count = self.one(
            "SELECT COUNT(*) AS count FROM api_keys WHERE user_id = ? AND revoked = 0", (user_id,)
        )
        total = int(count["count"] if count else 0)
        return {
            "items": [self._api_key(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
        }

    def revoke_api_key(self, user_id: str, key_id: str) -> None:
        self.api_key(user_id, key_id)
        self.execute(
            "UPDATE api_keys SET revoked = 1 WHERE user_id = ? AND id = ?", (user_id, key_id)
        )

    @staticmethod
    def _api_key(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "key": None,
            "key_prefix": row["key_prefix"],
            "scopes": decode(row["scopes"], []),
            "last_used_at": row["last_used_at"],
            "expires_at": row["expires_at"],
            "created_at": row["created_at"],
        }

    def usage(self, user_id: str) -> dict[str, Any]:
        storage = self.one(
            "SELECT COALESCE(SUM(size), 0) AS used FROM files WHERE user_id = ?", (user_id,)
        )
        pages = self.one(
            "SELECT COALESCE(SUM(total_pages), 0) AS used FROM extractions WHERE user_id = ? AND status = 'completed'",
            (user_id,),
        )
        kbs = self.one("SELECT COUNT(*) AS used FROM knowledge_bases WHERE user_id = ?", (user_id,))
        used_bytes = int(storage["used"] if storage else 0)
        return {
            "storage": {
                "used_bytes": used_bytes,
                "limit_bytes": self.settings.storage_limit_bytes,
                "used_percentage": round(100 * used_bytes / self.settings.storage_limit_bytes, 3),
            },
            "extraction": {
                "pages_used": int(pages["used"] if pages else 0),
                "pages_limit": self.settings.extraction_pages_limit,
                "reset_at": None,
            },
            "knowledge_bases": {
                "used": int(kbs["used"] if kbs else 0),
                "limit": self.settings.knowledge_base_limit,
            },
        }
