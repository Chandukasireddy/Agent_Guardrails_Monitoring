"""Built-in checks. Importing this package registers every one under its name."""

from . import (  # noqa: F401 - each import registers its checks
    injection,
    judge,
    keywords,
    length,
    pii,
    pressure,
    secret_scan,
    tool_limits,
    topic,
)
