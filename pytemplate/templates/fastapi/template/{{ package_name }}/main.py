"""ASGI entry point: `uvicorn <package>.main:app`."""

from .bootstrap.app import create_app

app = create_app()
