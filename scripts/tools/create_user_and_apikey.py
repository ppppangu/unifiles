import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import asyncpg

from unifiles.core.config.env_config import read_pg_config


async def _connect() -> asyncpg.Connection:
    cfg = read_pg_config()
    return await asyncpg.connect(
        host=cfg.get("host", "localhost"),
        port=int(cfg.get("port", 5432)),
        user=cfg.get("user", "postgres"),
        password=cfg.get("password", "postgres"),
        database=cfg.get("database", "postgres"),
    )


async def ensure_user(
    conn: asyncpg.Connection,
    user_id: str,
    username: Optional[str],
    display_name: Optional[str],
    role: str,
    status: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO unifiles.users (id, username, display_name, user_role, user_status)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO NOTHING
        """,
        user_id,
        username,
        display_name,
        role,
        status,
    )


async def create_key_via_function(
    conn: asyncpg.Connection,
    user_id: str,
    name: str,
    description: Optional[str],
    scopes: List[str],
    expires_at: Optional[datetime],
    max_hour: Optional[int],
    max_day: Optional[int],
    max_file_mb: Optional[int],
    max_kb: Optional[int],
    can_create_kb: bool,
    can_delete_files: bool,
    can_share_files: bool,
    can_export_data: bool,
    allowed_ips: Optional[List[str]],
) -> dict:
    row = await conn.fetchrow(
        """
        SELECT create_access_key(
            p_user_id := $1,
            p_name := $2,
            p_description := $3,
            p_scopes := $4::text[],
            p_expires_at := $5,
            p_max_requests_per_hour := $6,
            p_max_requests_per_day := $7,
            p_max_file_size_mb := $8,
            p_max_knowledge_bases := $9,
            p_can_create_kb := $10,
            p_can_delete_files := $11,
            p_can_share_files := $12,
            p_can_export_data := $13,
            p_allowed_ips := $14::text[]
        )::text AS result
        """,
        user_id,
        name,
        description,
        scopes,
        expires_at,
        max_hour,
        max_day,
        max_file_mb,
        max_kb,
        can_create_kb,
        can_delete_files,
        can_share_files,
        can_export_data,
        allowed_ips,
    )
    return json.loads(row["result"]) if row and row["result"] else {}


async def create_key_via_insert(
    conn: asyncpg.Connection,
    user_id: str,
    name: str,
    description: Optional[str],
    scopes: List[str],
    expires_at: Optional[datetime],
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO unifiles.access_keys (
            user_id, name, description, scopes, expires_at
        ) VALUES ($1, $2, $3, $4::text[], $5)
        RETURNING id, access_key, created_at, expires_at
        """,
        user_id,
        name,
        description,
        scopes,
        expires_at,
    )
    return {
        "success": True,
        "key_id": row["id"],
        "access_key": row["access_key"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
        "message": "Access key created via insert",
    }


async def run(args: argparse.Namespace) -> None:
    conn = await _connect()
    try:
        await ensure_user(
            conn,
            user_id=args.user_id,
            username=args.username,
            display_name=args.display_name,
            role=args.role,
            status=args.status,
        )

        scopes = [
            s.strip() for s in (args.scopes or "read,write").split(",") if s.strip()
        ]
        allowed_ips = (
            [ip.strip() for ip in args.allowed_ips.split(",")]
            if args.allowed_ips
            else None
        )

        expires_at: Optional[datetime]
        if args.never_expires:
            expires_at = None
        elif args.expires_days is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=args.expires_days)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        try:
            result = await create_key_via_function(
                conn,
                user_id=args.user_id,
                name=args.key_name,
                description=args.key_description,
                scopes=scopes,
                expires_at=expires_at,
                max_hour=args.max_requests_per_hour,
                max_day=args.max_requests_per_day,
                max_file_mb=args.max_file_size_mb,
                max_kb=args.max_knowledge_bases,
                can_create_kb=not args.disable_create_kb,
                can_delete_files=not args.disable_delete_files,
                can_share_files=not args.disable_share_files,
                can_export_data=not args.disable_export_data,
                allowed_ips=allowed_ips,
            )
            if not result.get("success"):
                raise RuntimeError(
                    result.get("message") or "create_access_key returned failure"
                )
        except Exception:
            result = await create_key_via_insert(
                conn,
                user_id=args.user_id,
                name=args.key_name,
                description=args.key_description,
                scopes=scopes,
                expires_at=expires_at,
            )

        print(
            json.dumps(
                {
                    "success": True,
                    "user_id": args.user_id,
                    "key_id": result.get("key_id"),
                    "access_key": result.get("access_key"),
                    "expires_at": result.get("expires_at"),
                    "message": result.get("message", "Access key created successfully"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        await conn.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Create a user and generate an API key in the configured PostgreSQL database",
    )
    p.add_argument("--user-id", required=True, help="User ID (TEXT primary key)")
    p.add_argument("--username", default=None, help="Optional username")
    p.add_argument("--display-name", default=None, help="Optional display name")
    p.add_argument(
        "--role",
        default="user",
        choices=["admin", "user", "readonly"],
        help="User role",
    )
    p.add_argument(
        "--status",
        default="active",
        choices=["active", "inactive", "suspended", "deleted"],
        help="User status",
    )

    p.add_argument("--key-name", default="default-key", help="API key name/label")
    p.add_argument(
        "--key-description", default="CLI created key", help="API key description"
    )
    p.add_argument(
        "--scopes",
        default="read,write",
        help="Comma-separated scopes, e.g. 'read,write'",
    )
    p.add_argument(
        "--expires-days",
        type=int,
        default=None,
        help="Days until expiry (default 30). Use --never-expires to disable",
    )
    p.add_argument(
        "--never-expires", action="store_true", help="Create a non-expiring key"
    )

    p.add_argument("--max-requests-per-hour", type=int, default=1000)
    p.add_argument("--max-requests-per-day", type=int, default=10000)
    p.add_argument("--max-file-size-mb", type=int, default=200)
    p.add_argument("--max-knowledge-bases", type=int, default=10)

    p.add_argument("--disable-create-kb", action="store_true")
    p.add_argument("--disable-delete-files", action="store_true")
    p.add_argument("--disable-share-files", action="store_true")
    p.add_argument("--disable-export-data", action="store_true")

    p.add_argument(
        "--allowed-ips", default=None, help="Comma-separated IP allowlist (optional)"
    )
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
