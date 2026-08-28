"""Webhook event delivery service."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx

from ...shared.database import Store, identifier, now


def dispatch_event(store: Store, user_id: str, event: str, data: dict[str, Any]) -> None:
    delivery_id = identifier("evt")
    payload = {"id": delivery_id, "type": event, "created_at": now(), "data": data}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    for webhook in store.matching_webhooks(user_id, event):
        signature = hmac.new(webhook["secret"].encode(), encoded, hashlib.sha256).hexdigest()
        try:
            headers: dict[str, str] = {
                "Content-Type": "application/json",
                "X-Unifiles-Event": event,
                "X-Unifiles-Delivery": delivery_id,
                "X-Unifiles-Signature": f"sha256={signature}",
            }
            response = httpx.post(
                webhook["url"],
                content=encoded,
                headers=headers,
                timeout=10,
            )
            if response.is_success:
                store.mark_webhook_delivery(webhook["id"])
        except httpx.HTTPError:
            continue
