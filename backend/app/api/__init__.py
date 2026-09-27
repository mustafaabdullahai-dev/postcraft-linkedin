"""API route modules."""
from app.api.routes import auth, guidelines, health, linkedin, posts, voice

main_router_modules = [auth, posts, voice, health, linkedin, guidelines]

__all__ = [
    "auth",
    "posts",
    "voice",
    "health",
    "linkedin",
    "guidelines",
    "main_router_modules",
]
