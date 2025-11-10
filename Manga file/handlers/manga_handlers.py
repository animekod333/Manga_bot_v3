"""Manga viewing and chapter download handlers."""
import math
import asyncio
from io import BytesIO
from aiogram import types, F
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from models import MangaStates
from data_manager import (
    get_user_favorites, is_in_favorites, add_to_favorites, 
    remove_from_favorites, get_display_name
)
from vip_manager import check_vip_access
from api_client_enhanced import get_manga_info, upload_to_telegraph
from keyboards import (
    create_chapter_grid_keyboard, create_manga_caption_for_grid,
    create_document_navigation_keyboard, create_manga_list_keyboard
)
from subscription import subscription_wrapper
from config import CHANNEL_ID, BASE_URL, MANGAS_PER_PAGE
from storage_manager import get_chapter_from_channel, forward_chapter_to_user, download_and_cache_chapter
import database
from rate_limiter import check_and_enforce_limit, increment_user_request


async def show_manga_chapter_grid(manga_id: str, source: types.Message | CallbackQuery, state: FSMContext, 
                                  page: int = 0):
    """Show manga chapter selection grid."""
    from utils import get_bot
    bot = get_bot()
    
    message = source.message if isinstance(source, CallbackQuery) else source
    user_id = source.from_user.id
    try:
        if isinstance(source, CallbackQuery): 
            await source.answer("Загружаю информацию о манге...")
        info = await get_manga_info(manga_id, use_cache=True)
        if not info or not info.get('chapters', {}).get('list'):
            await message.edit_text("❌ Не удалось получить информацию об этой манге или у нее нет глав.")
            return
        all_chapters = info['chapters']['list']
        unique_chapters, seen_chapter_nums = [], set()
        for chapter in all_chapters:
            ch_num = chapter.get('ch')
            if ch_num and ch_num not in seen_chapter_nums:
                unique_chapters.append(chapter)
                seen_chapter_nums.add(ch_num)
        chapters_sorted = sorted(unique_chapters, key=lambda x: float(x['ch']))
        cover_url = info.get('image', {}).get('original', 'https://via.placeholder.com/200x300.png?text=No+Image')
        caption = create_manga_caption_for_grid(info, len(chapters_sorted))
        is_fav = is_in_favorites(user_id, manga_id)
        keyboard = create_chapter_grid_keyboard(manga_id, chapters_sorted, is_fav, page=page)
        current_message = message
        if isinstance(source, CallbackQuery) and source.message.photo:
            await current_message.edit_caption(caption=caption, reply_markup=keyboard)
        else:
            try:
                await current_message.delete()
            except TelegramBadRequest:
                pass
            current_message = await bot.send_photo(
                chat_id=message.chat.id, 
                photo=cover_url, 
                caption=caption,
                reply_markup=keyboard
            )
        await state.set_state(MangaStates.viewing_manga_chapters)
        await state.update_data(
            manga_id=manga_id, 
            info=info, 
            chapters=chapters_sorted, 
            grid_page=page,
            photo_msg_id=current_message.message_id
        )
    except Exception as e:
        print(f"Ошибка в show_manga_chapter_grid: {e}")
        await message.answer("Произошла ошибка при загрузке манги. Попробуйте позже.")


async def handle_manga_selection(callback: types.CallbackQuery, state: FSMContext):
    """Handle manga selection from list."""
    if callback.data.startswith("manga_"):
        manga_id = str(callback.data.split("_")[1])
        await show_manga_chapter_grid(manga_id, callback, state)
    elif callback.data.startswith("list_page_"):
        page = int(callback.data.split("_")[2])
        data = await state.get_data()
        manga_list = data.get('manga_list', [])
        total_pages = math.ceil(len(manga_list) / MANGAS_PER_PAGE)
        await callback.message.edit_text(
            "🔍 Результаты:",
            reply_markup=create_manga_list_keyboard(manga_list, page, total_pages)
        )
        await callback.answer()


async def send_chapter_or_telegraph(callback: types.CallbackQuery, state: FSMContext, chapter_num_to_dl: float,
                                    is_last_in_batch: bool = True):
    """Send chapter as PDF or Telegraph link with caching."""
    from utils import get_bot
    bot = get_bot()
    
    user_id = callback.from_user.id
    settings = await database.get_user_settings(user_id)
    output_format = settings.get('output_format', 'pdf')

    data = await state.get_data()
    manga_id = data.get('manga_id')
    if not manga_id or not data.get('chapters'):
        await bot.send_message(user_id, "❌ Ошибка сессии. Пожалуйста, выберите мангу заново из главного меню.")
        return
    chapter_to_dl = next((ch for ch in data['chapters'] if float(ch['ch']) == chapter_num_to_dl), None)
    if not chapter_to_dl:
        await bot.send_message(user_id, f"❌ Ошибка: Глава {chapter_num_to_dl} не найдена.")
        return

    last_doc_msg_id = data.get('last_doc_msg_id')
    if last_doc_msg_id:
        try:
            await bot.edit_message_reply_markup(chat_id=user_id, message_id=last_doc_msg_id, reply_markup=None)
        except TelegramBadRequest:
            pass

    keyboard = create_document_navigation_keyboard(
        data['chapters'], chapter_num_to_dl, user_id
    ) if is_last_in_batch else None

    # Handle Telegraph format for VIP users
    if output_format == 'telegraph' and check_vip_access(user_id):
        # Check cache
        cached_url = await database.get_chapter_telegraph_url(int(manga_id), chapter_num_to_dl)
        if cached_url:
            sent_msg = await bot.send_message(
                user_id,
                f"📖 <b>{get_display_name(data['info'])} - Глава {chapter_num_to_dl}</b>\n\n<a href='{cached_url}'>Читать в Telegraph</a> (из кэша)",
                reply_markup=keyboard, 
                disable_web_page_preview=False
            )
            if sent_msg and is_last_in_batch: 
                await state.update_data(last_doc_msg_id=sent_msg.message_id)
            return

        # Download and upload to Telegraph (using api_client_enhanced)
        from api_client_enhanced import safe_api_call
        url_api = f"{BASE_URL}/{manga_id}/chapter/{chapter_to_dl['id']}"
        resp = await safe_api_call(url_api)
        if resp:
            resp_data = resp.json()
            pages = resp_data.get('response', {}).get('pages', {}).get('list', [])

            if pages:
                telegraph_url = await upload_to_telegraph(get_display_name(data['info']), chapter_to_dl, pages, callback)
                if telegraph_url:
                    sent_msg = await bot.send_message(
                        user_id,
                        f"📖 <b>{get_display_name(data['info'])} - Глава {chapter_num_to_dl}</b>\n\n<a href='{telegraph_url}'>Читать в Telegraph</a>",
                        reply_markup=keyboard, 
                        disable_web_page_preview=False
                    )
                    if sent_msg and is_last_in_batch: 
                        await state.update_data(last_doc_msg_id=sent_msg.message_id)
                    return
        
        await bot.send_message(user_id, "❌ Не удалось создать Telegraph-страницу.")
        return

    # Handle PDF format - check cache first
    file_id = await get_chapter_from_channel(int(manga_id), chapter_num_to_dl)
    
    if file_id:
        # Try to send cached file
        try:
            sent_msg = await bot.send_document(
                chat_id=user_id, 
                document=file_id, 
                reply_markup=keyboard,
                caption="📖 Из кэша"
            )
            if sent_msg and is_last_in_batch: 
                await state.update_data(last_doc_msg_id=sent_msg.message_id)
            print(f"✅ Sent cached chapter {chapter_num_to_dl} to user {user_id}")
            return
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            print(f"⚠️ Cached file_id invalid for chapter {chapter_num_to_dl}: {e}")

    # Not cached or cache invalid - download and cache
    success = await download_and_cache_chapter(
        bot, user_id, int(manga_id), chapter_num_to_dl, chapter_to_dl
    )
    
    if success and is_last_in_batch:
        # Update keyboard on the last sent message
        # This is a bit tricky since download_and_cache_chapter sends the message
        # We'll need to update the state differently
        pass


async def run_batch_download(callback: CallbackQuery, state: FSMContext, start_index: int):
    """Run batch download of chapters."""
    from utils import get_bot
    bot = get_bot()
    
    user_id = callback.from_user.id
    settings = await database.get_user_settings(user_id)
    batch_size = settings.get('batch_size', 5)

    data = await state.get_data()
    all_chapters = data.get('chapters', [])
    end_index = min(start_index + batch_size, len(all_chapters))
    chapters_to_process = all_chapters[start_index:end_index]

    if not chapters_to_process:
        try:
            await callback.answer("Больше глав для скачивания нет.", show_alert=True)
        except TelegramBadRequest:
            await bot.send_message(user_id, "Больше глав для скачивания нет.")
        return

    try:
        await callback.answer(f"Начинаю VIP-загрузку {len(chapters_to_process)} глав...", show_alert=False)
    except TelegramBadRequest:
        print("Не удалось ответить на callback в начале batch_download.")

    for i, chapter in enumerate(chapters_to_process):
        is_last = (i == len(chapters_to_process) - 1)
        await send_chapter_or_telegraph(callback, state, float(chapter['ch']), is_last_in_batch=is_last)
        await asyncio.sleep(0.4)


async def handle_vip_navigation(callback: CallbackQuery, state: FSMContext):
    """Handle VIP navigation buttons."""
    if not check_vip_access(callback.from_user.id):
        await callback.answer("Эта функция доступна только для Premium-пользователей.", show_alert=True)
        return
    await callback.answer()
    await state.update_data(last_doc_msg_id=callback.message.message_id)
    action_full = callback.data
    if action_full.startswith("doc_nav_"):
        chapter_num_to_send = float(action_full.split("_")[2])
        await send_chapter_or_telegraph(callback, state, chapter_num_to_send)
    elif action_full.startswith("batch_dl_"):
        start_index = int(action_full.split("_")[2])
        asyncio.create_task(run_batch_download(callback, state, start_index))


async def handle_chapter_grid_actions(callback: types.CallbackQuery, state: FSMContext):
    """Handle chapter grid actions."""
    action_full = callback.data
    action = action_full.split("_")[0]
    data = await state.get_data()
    manga_id = data.get('manga_id')
    if not manga_id:
        await callback.answer("Ошибка сессии, выберите мангу заново.", show_alert=True)
        return
    if action == "grid":
        page = int(action_full.split("_")[2])
        await callback.answer()
        await show_manga_chapter_grid(manga_id, callback, state, page=page)
    elif action == "toggle":
        is_fav = is_in_favorites(callback.from_user.id, manga_id)
        if is_fav:
            remove_from_favorites(callback.from_user.id, manga_id)
            await callback.answer("🗑 Удалено из избранного.")
        else:
            add_to_favorites(callback.from_user.id, data['info'])
            await callback.answer("⭐️ Добавлено в избранное!")
        await show_manga_chapter_grid(manga_id, callback, state, page=data.get('grid_page', 0))
    elif action == "dl":
        await callback.answer("Начинаю загрузку...")
        chapter_num = float(action_full.split("_")[1])
        await state.update_data(last_doc_msg_id=None)
        await send_chapter_or_telegraph(callback, state, chapter_num)
    elif action_full == "back_to_grid":
        await callback.answer()
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await state.update_data(last_doc_msg_id=None)
        grid_page = data.get('grid_page', 0)
        await show_manga_chapter_grid(manga_id, callback.message, state, page=grid_page)


@subscription_wrapper
async def handle_main_menu_buttons(callback: types.CallbackQuery, state: FSMContext, bot):
    """Handle main menu button clicks."""
    from api_client import get_mangas
    from utils import get_bot
    bot_instance = get_bot()
    
    action = callback.data
    await callback.answer()
    if action == "main_search":
        await callback.message.edit_text("Введите название манги для поиска:")
        await state.set_state(MangaStates.waiting_for_search_query)
    elif action in ["main_favorites", "main_top"]:
        source = "favorites" if action == "main_favorites" else "top"
        if source == "favorites":
            manga_list = get_user_favorites(callback.from_user.id)
            if not manga_list:
                await bot_instance.answer_callback_query(callback.id, "📭 Ваше избранное пусто.", show_alert=True)
                return
            title = "⭐️ Ваше избранное:"
        else:
            await callback.message.edit_text("🏆 Загружаю топ манг...")
            manga_list, _ = get_mangas(order_by="popular")
            if not manga_list:
                await callback.message.edit_text("❌ Не удалось загрузить топ.")
                return
            title = "🏆 Топ манг по популярности:"
        await state.set_state(MangaStates.selecting_manga)
        await state.update_data(source=source, manga_list=manga_list, list_page=0)
        total_pages = math.ceil(len(manga_list) / MANGAS_PER_PAGE)
        await callback.message.edit_text(title, reply_markup=create_manga_list_keyboard(manga_list, 0, total_pages))
    elif action == "main_genres":
        from search_handlers import show_genres_menu
        await show_genres_menu(callback, state)
    elif action == "main_settings":
        from settings_handlers import show_settings_menu
        await show_settings_menu(callback, state)
    elif action == "main_premium":
        from premium_handlers import show_premium_menu
        await show_premium_menu(callback.message, state, is_callback=True)


def register_handlers(dp):
    """Register manga handlers."""
    dp.callback_query.register(handle_main_menu_buttons, MangaStates.main_menu)
    dp.callback_query.register(handle_manga_selection, MangaStates.selecting_manga)
    dp.callback_query.register(
        handle_vip_navigation, 
        StateFilter(MangaStates.viewing_manga_chapters, None), 
        F.data.startswith(("doc_nav_", "batch_dl_"))
    )
    dp.callback_query.register(handle_chapter_grid_actions, MangaStates.viewing_manga_chapters)
