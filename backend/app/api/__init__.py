"""API route modules."""
from app.api.routes import auth, health, linkedin, posts, voice

main_router_modules = [auth, posts, voice, health, linkedin]

__all__ = ["auth", "posts", "voice", "health", "linkedin", "main_router_modules"]