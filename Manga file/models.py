"""FSM States for the manga bot."""
from aiogram.fsm.state import State, StatesGroup


class MangaStates(StatesGroup):
    main_menu = State()
    selecting_manga = State()
    viewing_manga_chapters = State()
    waiting_for_search_query = State()
    selecting_genres = State()
    selecting_kinds = State()
    settings_menu = State()
    premium_menu = State()


class AdminStates(StatesGroup):
    panel = State()
    adding_channel = State()
    removing_channel = State()
    mailing_get_content = State()
    mailing_get_buttons = State()
    mailing_confirm = State()
