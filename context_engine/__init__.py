"""
Context Awareness Engine — Phase 5.

Rule-based context detection and gesture-to-action mapping.
"""
from .contexts import CONTEXTS, GESTURE_ACTION_MAP, CONTEXT_NAMES
from .context_detector import get_current_context, get_context_info
from .action_resolver import resolve
from .session_tracker import get_session_summary
