"""Search and genre selection handlers."""
import math
import asyncio
from aiogram import types, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from models import MangaStates
from api_client_enhanced import get_mangas, get_mangas_by_genres_and_kinds
from keyboards import (
    create_genres_keyboard, create_kinds_keyboard, 
    create_manga_list_keyboard
)
from subscription import subscription_wrapper
from config import MANGA_GENRES, MANGA_KINDS, MANGAS_PER_PAGE
from vip_manager import check_vip_access
from rate_limiter import check_and_enforce_limit, increment_user_request


async def show_genres_menu(callback: CallbackQuery, state: FSMContext):
    """Show genre selection menu."""
    await callback.message.edit_text(
        "📋 Выберите жанры для поиска манги.\nМожно выбрать несколько жанров одновременно:",
        reply_markup=create_genres_keyboard()
    )
    await state.set_state(MangaStates.selecting_genres)
    await state.update_data(selected_genres=[], selected_kinds=[])


async def handle_genre_selection(callback: CallbackQuery, state: FSMContext):
    """Handle genre selection."""
    action = callback.data
    await callback.answer()
    if action == "clear_genres":
        await state.update_data(selected_genres=[])
        await callback.message.edit_reply_markup(reply_markup=create_genres_keyboard())
    elif action == "search_by_genres":
        await search_by_genres(callback, state)
    elif action == "select_kinds":
        data = await state.get_data()
        selected_kinds = data.get('selected_kinds', [])
        await callback.message.edit_text("📚 Выберите тип манги:", reply_markup=create_kinds_keyboard(selected_kinds))
        await state.set_state(MangaStates.selecting_kinds)
    elif action.startswith("genre_"):
        genre_id = int(action.split("_")[1])
        data = await state.get_data()
        selected_genres = data.get('selected_genres', [])
        if genre_id in selected_genres:
            selected_genres.remove(genre_id)
        else:
            selected_genres.append(genre_id)
        await state.update_data(selected_genres=selected_genres)
        await callback.message.edit_reply_markup(reply_markup=create_genres_keyboard(selected_genres))


async def handle_kind_selection(callback: CallbackQuery, state: FSMContext):
    """Handle kind selection."""
    action = callback.data
    await callback.answer()
    if action == "back_to_genres":
        data = await state.get_data()
        selected_genres = data.get('selected_genres', [])
        await callback.message.edit_text("📋 Выберите жанры...", reply_markup=create_genres_keyboard(selected_genres))
        await state.set_state(MangaStates.selecting_genres)
    elif action == "clear_kinds":
        await state.update_data(selected_kinds=[])
        await callback.message.edit_reply_markup(reply_markup=create_kinds_keyboard())
    elif action.startswith("kind_"):
        kind_id = action.split("_")[1]
        data = await state.get_data()
        selected_kinds = data.get('selected_kinds', [])
        if kind_id in selected_kinds:
            selected_kinds.remove(kind_id)
        else:
            selected_kinds.append(kind_id)
        await state.update_data(selected_kinds=selected_kinds)
        await callback.message.edit_reply_markup(reply_markup=create_kinds_keyboard(selected_kinds))


async def search_by_genres(callback: CallbackQuery, state: FSMContext):
    """Search mangas by selected genres and kinds."""
    data = await state.get_data()
    selected_genres = data.get('selected_genres', [])
    selected_kinds = data.get('selected_kinds', [])
    if not selected_genres and not selected_kinds:
        from aiogram import Bot
        bot = Bot.get_current()
        await bot.answer_callback_query(callback.id, "Пожалуйста, выберите хотя бы один жанр или тип", show_alert=True)
        return
    
    # Check rate limit
    user_id = callback.from_user.id
    is_premium = check_vip_access(user_id)
    can_proceed, error_msg = await check_and_enforce_limit(user_id, is_premium)
    
    if not can_proceed:
        from aiogram import Bot
        bot = Bot.get_current()
        await bot.answer_callback_query(callback.id, error_msg, show_alert=True)
        return
    
    selected_genre_names = [g['russian'] for g in MANGA_GENRES if g['id'] in selected_genres]
    selected_kind_names = [k['russian'] for k in MANGA_KINDS if k['id'] in selected_kinds]
    genres_text = ', '.join(selected_genre_names) if selected_genres else "любые"
    kinds_text = ', '.join(selected_kind_names) if selected_kinds else "любые"
    search_message = await callback.message.edit_text(f"🔍 Ищу мангу...\n\nЖанры: {genres_text}\nТипы: {kinds_text}")
    genres_param = ','.join([g['text'] for g in MANGA_GENRES if g['id'] in selected_genres])
    kinds_param = ','.join(selected_kinds)
    try:
        # Increment request count
        await increment_user_request(user_id)
        
        mangas, page_nav = await get_mangas_by_genres_and_kinds(genres_param, kinds_param, api_page=1)
        if not mangas:
            await search_message.edit_text(
                f"❌ Манга не найдена.", 
                reply_markup=create_genres_keyboard(selected_genres)
            )
            await state.set_state(MangaStates.selecting_genres)
            return
        await state.set_state(MangaStates.selecting_manga)
        await state.update_data(
            source="genres", 
            manga_list=mangas, 
            list_page=0, 
            selected_genres=selected_genres,
            selected_kinds=selected_kinds
        )
        total_pages = math.ceil(len(mangas) / MANGAS_PER_PAGE)
        await search_message.edit_text(
            f"🔍 Найдено манги: {page_nav.get('count', len(mangas))}",
            reply_markup=create_manga_list_keyboard(mangas, 0, total_pages)
        )
    except Exception as e:
        print(f"Ошибка при поиске по жанрам: {e}")
        await search_message.edit_text(
            f"❌ Произошла ошибка при поиске.",
            reply_markup=create_genres_keyboard(selected_genres)
        )
        await state.set_state(MangaStates.selecting_genres)


@subscription_wrapper
async def process_search_query(message: types.Message, state: FSMContext, bot):
    """Process search query."""
    from handlers.main_handlers import show_main_menu
    
    search_query = message.text.strip()
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    if not search_query:
        await message.answer("Пожалуйста, введите поисковый запрос.")
        return
    
    # Check rate limit
    user_id = message.from_user.id
    is_premium = check_vip_access(user_id)
    can_proceed, error_msg = await check_and_enforce_limit(user_id, is_premium)
    
    if not can_proceed:
        await message.answer(error_msg)
        await asyncio.sleep(3)
        await show_main_menu(message, state)
        return
    
    search_msg = await message.answer(f"🔍 Ищу '{search_query}'...")
    
    # Increment request count
    await increment_user_request(user_id)
    
    mangas, _ = await get_mangas(query=search_query, api_page=1, user_id=user_id)
    if not mangas:
        await search_msg.edit_text("❌ Ничего не найдено.")
        await asyncio.sleep(3)
        await search_msg.delete()
        await show_main_menu(message, state)
        return
    await state.set_state(MangaStates.selecting_manga)
    await state.update_data(source="search", manga_list=mangas, list_page=0)
    total_pages = math.ceil(len(mangas) / MANGAS_PER_PAGE)
    await search_msg.edit_text("🔍 Результаты поиска:", reply_markup=create_manga_list_keyboard(mangas, 0, total_pages))


def register_handlers(dp):
    """Register search handlers."""
    dp.callback_query.register(handle_genre_selection, MangaStates.selecting_genres)
    dp.callback_query.register(handle_kind_selection, MangaStates.selecting_kinds)
    dp.message.register(process_search_query, MangaStates.waiting_for_search_query)
