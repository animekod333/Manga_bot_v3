"""Keyboard creation functions."""
import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from vip_manager import check_vip_access
from data_manager import get_user_settings, get_display_name
from config import (
    MANGAS_PER_PAGE, CHAPTERS_PER_PAGE, VIP_PLANS, 
    MANGA_GENRES, MANGA_KINDS
)


def create_main_inline_keyboard():
    """Create main menu keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск манги", callback_data="main_search"),
         InlineKeyboardButton(text="🌟 Premium", callback_data="main_premium")],
        [InlineKeyboardButton(text="💓 Избранное", callback_data="main_favorites"),
         InlineKeyboardButton(text="🚀 Топ рейтинга", callback_data="main_top")],
        [InlineKeyboardButton(text="📋 Поиск по жанрам", callback_data="main_genres"),
         InlineKeyboardButton(text="⚙️ Настройки", callback_data="main_settings")]
    ])


def create_admin_keyboard():
    """Create admin panel keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚡ Производительность", callback_data="admin_performance")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_mailing")],
        [InlineKeyboardButton(text="➕ Добавить канал", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="➖ Удалить канал", callback_data="admin_remove_channel")],
        [InlineKeyboardButton(text="📄 Список каналов", callback_data="admin_list_channels")],
        [InlineKeyboardButton(text="⬅️ Выйти", callback_data="admin_exit")]
    ])


def create_settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create settings menu keyboard."""
    is_vip = check_vip_access(user_id)
    keyboard = []

    if is_vip:
        settings = get_user_settings(user_id)
        current_batch_size = settings.get('batch_size', 5)
        current_format = settings.get('output_format', 'pdf')

        sizes = [3, 5, 10]
        batch_buttons = [InlineKeyboardButton(
            text=f"✅ {size} глав" if size == current_batch_size else f"{size} глав",
            callback_data=f"set_batch_{size}"
        ) for size in sizes]
        keyboard.append([InlineKeyboardButton(text="Кол-во глав в пакете:", callback_data="ignore")])
        keyboard.append(batch_buttons)

        format_buttons = [
            InlineKeyboardButton(
                text="✅ PDF" if current_format == 'pdf' else "PDF",
                callback_data="set_format_pdf"
            ),
            InlineKeyboardButton(
                text="✅ Telegraph" if current_format == 'telegraph' else "Telegraph",
                callback_data="set_format_telegraph"
            )
        ]
        keyboard.append([InlineKeyboardButton(text="Формат выдачи:", callback_data="ignore")])
        keyboard.append(format_buttons)
    else:
        keyboard.append(
            [InlineKeyboardButton(text="🌟 Купить Premium для доступа к настройкам", callback_data="main_premium")]
        )

    keyboard.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_document_navigation_keyboard(chapters: list, current_chapter_num: float,
                                        user_id: int) -> InlineKeyboardMarkup:
    """Create navigation keyboard for document viewing."""
    if not check_vip_access(user_id):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌟 Навигация доступна с Premium", callback_data="main_premium")],
            [InlineKeyboardButton(text="📖 К списку глав", callback_data="back_to_grid")]
        ])

    keyboard = []
    chapter_nums = [float(ch['ch']) for ch in chapters]
    try:
        current_index = chapter_nums.index(current_chapter_num)
    except ValueError:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Ошибка навигации", callback_data="ignore")]]
        )

    single_nav_row = []
    if current_index > 0:
        single_nav_row.append(
            InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"doc_nav_{chapter_nums[current_index - 1]}")
        )
    single_nav_row.append(InlineKeyboardButton(text=f"Гл. {current_chapter_num}", callback_data="ignore"))
    if current_index < len(chapter_nums) - 1:
        single_nav_row.append(
            InlineKeyboardButton(text="След. ➡️", callback_data=f"doc_nav_{chapter_nums[current_index + 1]}")
        )
    if single_nav_row: 
        keyboard.append(single_nav_row)

    settings = get_user_settings(user_id)
    batch_size = settings.get('batch_size', 5)
    batch_nav_row = []
    if current_index > 0:
        prev_batch_start_index = max(0, current_index - batch_size)
        batch_nav_row.append(
            InlineKeyboardButton(text=f"⬅️ Пред. {batch_size}", callback_data=f"batch_dl_{prev_batch_start_index}")
        )
    if current_index < len(chapter_nums) - 1:
        next_batch_start_index = current_index + 1
        batch_nav_row.append(
            InlineKeyboardButton(text=f"След. {batch_size} ➡️", callback_data=f"batch_dl_{next_batch_start_index}")
        )
    if batch_nav_row: 
        keyboard.append(batch_nav_row)

    keyboard.append([InlineKeyboardButton(text="📖 К списку глав", callback_data="back_to_grid")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_premium_keyboard() -> InlineKeyboardMarkup:
    """Create premium plans keyboard."""
    keyboard = [[InlineKeyboardButton(
        text=f"{plan_data['title']} - {plan_data['stars']} 🌟",
        callback_data=f"buy_{plan_key}"
    )] for plan_key, plan_data in VIP_PLANS.items()]
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_manga_list_keyboard(mangas: list, page: int, total_pages: int):
    """Create manga list keyboard with pagination."""
    keyboard = [[InlineKeyboardButton(text=get_display_name(manga), callback_data=f"manga_{manga['id']}")] 
                for manga in mangas[page * MANGAS_PER_PAGE:(page + 1) * MANGAS_PER_PAGE]]
    nav_row = []
    if page > 0: 
        nav_row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"list_page_{page - 1}"))
    if page < total_pages - 1: 
        nav_row.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"list_page_{page + 1}"))
    if nav_row: 
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_chapter_grid_keyboard(manga_id: str, chapters: list, is_fav: bool, page: int = 0):
    """Create chapter selection grid keyboard."""
    keyboard = []
    total_pages = math.ceil(len(chapters) / CHAPTERS_PER_PAGE)
    start_index = page * CHAPTERS_PER_PAGE
    end_index = start_index + CHAPTERS_PER_PAGE
    page_chapters = chapters[start_index:end_index]
    for i in range(0, len(page_chapters), 5):
        row = [InlineKeyboardButton(text=str(ch['ch']), callback_data=f"dl_{ch['ch']}") 
               for ch in page_chapters[i:i + 5]]
        keyboard.append(row)
    nav_row = []
    if page > 0: 
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"grid_page_{page - 1}"))
    if total_pages > 1: 
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))
    if page < total_pages - 1: 
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"grid_page_{page + 1}"))
    if nav_row: 
        keyboard.append(nav_row)
    fast_nav_row = []
    if page > 0: 
        fast_nav_row.append(InlineKeyboardButton(text="⏪ В начало", callback_data="grid_page_0"))
    if page < total_pages - 1: 
        fast_nav_row.append(
            InlineKeyboardButton(text="В конец ⏩", callback_data=f"grid_page_{total_pages - 1}")
        )
    if fast_nav_row: 
        keyboard.append(fast_nav_row)
    fav_text = "❌ Убрать из избранного" if is_fav else "⭐️ Добавить в избранное"
    keyboard.append([InlineKeyboardButton(text=fav_text, callback_data=f"toggle_fav_{manga_id}")])
    keyboard.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_manga_caption_for_grid(info: dict, chapters_count: int) -> str:
    """Create caption text for manga details."""
    title = f"<b>{get_display_name(info)}</b>"
    details = []
    if info.get('score'): 
        details.append(f"<b>📊 Рейтинг:</b> {info['score']}")
    if info.get('issue_year'): 
        details.append(f"<b>📅 Год выпуска:</b> {info['issue_year']}")
    if info.get('kind'):
        kind_rus = next((k['russian'] for k in MANGA_KINDS if k['id'] == info['kind']), info['kind'])
        details.append(f"<b>📘 Тип:</b> {kind_rus}")
    if info.get('status'):
        details.append(
            f"<b>⏳ Статус:</b> {info['status'].replace('ongoing', 'выпускается').replace('released', 'выпущен')}"
        )
    details.append(f"<b>📖 Глав:</b> {chapters_count}")
    genres = info.get('genres', [])
    if genres:
        genre_names = [g.get('russian', g.get('name', '')) for g in genres]
        details.append(f"<b>🎭 Жанры:</b> {', '.join(filter(None, genre_names))}")

    description = info.get('description', 'Нет описания').strip()
    details_text = "\n".join(details)
    base_text = f"{title}\n\n{details_text}\n\n"
    footer_text = "\n\n📚 <b>Выберите главу для скачивания:</b>"
    remaining_space = 1024 - len(base_text) - len(footer_text) - 20

    final_description = ""
    if remaining_space > 0 and description:
        if len(description) > remaining_space:
            description = description[:remaining_space] + '...'
        final_description = f"<i>{description}</i>"

    full_caption = base_text + final_description + footer_text
    if len(full_caption) > 1024:
        full_caption = full_caption[:1021] + '...'

    return full_caption


def create_genres_keyboard(selected_genres=None):
    """Create genre selection keyboard."""
    if selected_genres is None: 
        selected_genres = []
    keyboard = []
    row = []
    for genre in MANGA_GENRES:
        prefix = "✅ " if genre["id"] in selected_genres else ""
        btn = InlineKeyboardButton(text=f"{prefix}{genre['russian']}", callback_data=f"genre_{genre['id']}")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: 
        keyboard.append(row)
    action_row = []
    if selected_genres:
        action_row.append(InlineKeyboardButton(text="🔍 Найти мангу", callback_data="search_by_genres"))
        action_row.append(InlineKeyboardButton(text="❌ Очистить выбор", callback_data="clear_genres"))
    if action_row: 
        keyboard.append(action_row)
    keyboard.append([InlineKeyboardButton(text="📚 Выбрать тип манги", callback_data="select_kinds")])
    keyboard.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_kinds_keyboard(selected_kinds=None):
    """Create kind selection keyboard."""
    if selected_kinds is None: 
        selected_kinds = []
    keyboard = []
    for kind in MANGA_KINDS:
        prefix = "✅ " if kind["id"] in selected_kinds else ""
        keyboard.append([InlineKeyboardButton(text=f"{prefix}{kind['russian']}", callback_data=f"kind_{kind['id']}")])
    if selected_kinds: 
        keyboard.append([InlineKeyboardButton(text="❌ Очистить выбор", callback_data="clear_kinds")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад к жанрам", callback_data="back_to_genres")])
    keyboard.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
