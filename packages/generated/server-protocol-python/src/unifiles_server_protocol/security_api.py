# coding: utf-8

from collections.abc import Awaitable, Callable
from typing import TypeAlias

from unifiles_server_protocol.models.extra_models import TokenModel

SecurityProvider: TypeAlias = Callable[..., TokenModel | Awaitable[TokenModel]]

__all__ = ["SecurityProvider"]
