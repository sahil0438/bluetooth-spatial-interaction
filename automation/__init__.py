"""
Action Execution Layer — Phase 6.

This module is responsible for translating action decisions from the Context Engine
into physical Windows OS commands (volume, lock, wake, slides, DND).
"""

from .action_executor import execute

__all__ = ["execute"]
