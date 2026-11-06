"""A tiny plugin registry used by guardrails, tools, and LLM providers.

Anything decorated with ``@REGISTRY.register("name")`` becomes available by
name in challenge YAML files. Python files in ``guardrails/custom/`` and
``vault_heist/tools/custom/`` are imported at startup, so new plugins need
no changes to core code.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Callable, Generic, TypeVar

log = logging.getLogger(__name__)
T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[str, type[T]] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            old = self._items.get(name)
            if old is not None and old.__module__ != cls.__module__:
                log.warning("%s '%s' is being replaced by %s", self.kind, name, cls.__name__)
            cls.name = name  # type: ignore[attr-defined]
            self._items[name] = cls
            return cls

        return decorator

    def get(self, name: str) -> type[T]:
        try:
            return self._items[name]
        except KeyError:
            known = ", ".join(sorted(self._items)) or "(none)"
            raise KeyError(f"Unknown {self.kind} '{name}'. Known {self.kind}s: {known}") from None

    def names(self) -> list[str]:
        return sorted(self._items)

    def __contains__(self, name: str) -> bool:
        return name in self._items


def load_extension_modules(folder: Path) -> list[str]:
    """Import every ``*.py`` file in ``folder``. Broken files are logged, not fatal."""
    loaded: list[str] = []
    if not folder.is_dir():
        return loaded
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"vault_heist_ext_{folder.name}_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            loaded.append(path.name)
        except Exception:  # noqa: BLE001 - an extension must never crash the game
            log.exception("Could not load extension %s; skipping it", path)
    return loaded
