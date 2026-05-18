"""LLM-powered semantic feedback module.

Uses a locally-running Ollama model to generate developer-facing
debugging feedback from root-cause analysis results.
"""

from .feedback_model import generate_developer_feedback  # noqa: F401
