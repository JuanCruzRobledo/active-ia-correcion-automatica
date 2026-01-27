"""
Integrations package for external services.

This package contains clients for integrating with external services:
- N8N: Workflow automation and AI orchestration
"""

from app.integrations.n8n_client import N8NClient

__all__ = ["N8NClient"]
