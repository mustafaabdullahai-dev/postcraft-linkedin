"""API route modules."""
from app.api.routes import auth, guidelines, health, linkedin, posts, uploads, voice

main_router_modules = [auth, posts, voice, health, linkedin, guidelines, uploads]

__all__ = [
    "auth",
    "posts",
    "voice",
    "health",
    "linkedin",
    "guidelines",
    "uploads",
    "main_router_modules",
]
