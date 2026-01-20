"""
Memory Module
=============
Persistent conversation context across all modalities.

Usage:
    from app.memory import context_manager

    # Get or create context
    ctx = await context_manager.get_context(user_id)

    # Add entry
    await context_manager.add_entry(user_id, ModalityEntry(...))

    # Get formatted context for LLM
    prompt_ctx = await context_manager.get_context_for_prompt(user_id)
"""

from app.memory.context_manager import (
    context_manager,
    configure_context_manager,
    ContextManager,
    ConversationContext,
    ModalityEntry,
    UserProfile,
    Modality,
    Role,
)

__all__ = [
    "context_manager",
    "configure_context_manager",
    "ContextManager",
    "ConversationContext",
    "ModalityEntry",
    "UserProfile",
    "Modality",
    "Role",
]
