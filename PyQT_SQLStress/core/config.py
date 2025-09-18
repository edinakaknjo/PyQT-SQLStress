from dataclasses import dataclass
from typing import Optional

@dataclass
class ExecResult:
    ok: bool
    duration_ms: float
    error: Optional[str] = None

@dataclass
class RunConfig:
    dsn: Optional[str]
    server: str
    database: str
    username: Optional[str]
    password: Optional[str]
    trusted: bool
    query: str
    threads: int
    iterations_per_thread: int
    delay_ms: int
    autocommit: bool
