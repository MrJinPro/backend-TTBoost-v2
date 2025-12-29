from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class AdminRuntimeState:
    maintenance_mode: bool = False
    disable_new_connections: bool = False
    updated_at: datetime | None = None


STATE = AdminRuntimeState()
