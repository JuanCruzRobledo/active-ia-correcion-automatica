"""
Integrations package for external services.

This package contains clients for integrating with external services:
- Gemini: Direct Google Gemini API for AI correction and rubric generation
- OpenRouter: OpenRouter proxy for model-agnostic AI correction
"""

from app.integrations.gemini_correction_client import GeminiCorrectionClient

__all__ = ["GeminiCorrectionClient"]
