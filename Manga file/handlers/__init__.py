"""Handlers package for the manga bot."""
from . import main_handlers
from . import manga_handlers
from . import premium_handlers
from . import settings_handlers
from . import search_handlers
from . import admin_handlers


def register_all_handlers(dp):
    """Register all handlers with the dispatcher."""
    main_handlers.register_handlers(dp)
    manga_handlers.register_handlers(dp)
    premium_handlers.register_handlers(dp)
    settings_handlers.register_handlers(dp)
    search_handlers.register_handlers(dp)
    admin_handlers.register_handlers(dp)
