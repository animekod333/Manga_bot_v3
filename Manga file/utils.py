"""Utility functions for the manga bot."""
from aiogram import Bot


def get_bot() -> Bot:
    """Get current bot instance for aiogram v3."""
    # Этот синтаксис единственно верный для aiogram 3.x
    return Bot.get_current()