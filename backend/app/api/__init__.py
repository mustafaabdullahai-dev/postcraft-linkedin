"""API route modules."""
from app.api.routes import auth, health, linkedin, posts

main_router_modules = [auth, posts, health, linkedin]

__all__ = ["auth", "posts", "health", "linkedin", "main_router_modules"]