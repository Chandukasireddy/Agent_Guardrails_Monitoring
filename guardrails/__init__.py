"""Guardrails: the checks that decide what reaches the model, the tools, and the player.

Everything about guardrails lives in this folder:

- ``base.py``      the contract: ``Rail``, ``RailContext``, ``Verdict`` and the ``RAILS`` registry
- ``runner.py``    runs one stage of checks and records each step
- ``checks/``      the built-in checks, one file per check
- ``adapters/``    connections to outside frameworks (NVIDIA NeMo Guardrails)
- ``custom/``      your own checks, loaded automatically at startup
- ``text.py``      text helpers shared by the checks

Read ``README.md`` in this folder for the full guide.
"""

from . import adapters, checks  # noqa: F401 - importing registers every built-in check
from .base import RAILS, Rail, RailContext, Verdict
from .runner import StageResult, run_stage

__all__ = ["RAILS", "Rail", "RailContext", "Verdict", "StageResult", "run_stage"]
