"""Admin panel handlers."""
import time
import asyncio
from aiogram import types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from models import AdminStates
from data_manager import load_data, save_data
from keyboards import create_admin_keyboard
from config import ADMIN_IDS, USERS_FILE, STATS_FILE, CHANNELS_FILE


async def cmd_admin(message: types.Message, state: FSMContext):
    """Handle /admin command."""
    if message.from_user.id not in ADMIN_IDS: 
        return
    await state.clear()
    await state.set_state(AdminStates.panel)
    await message.answer("Добро пожаловать в админ-панель!", reply_markup=create_admin_keyboard())


async def handle_admin_panel(callback: CallbackQuery, state: FSMContext):
    """Handle admin panel actions."""
    action = callback.data
    await callback.answer()

    if action == "admin_performance":
        from performance_monitor import performance_report
        report = await performance_report()
        await callback.message.edit_text(report, reply_markup=create_admin_keyboard())
    elif action == "admin_stats":
        import database
        
        users_count = len(load_data(USERS_FILE, {"users": []})["users"])
        downloads_count = load_data(STATS_FILE, {"downloads": 0})["downloads"]
        
        # Get cache statistics
        cache_stats = await database.get_cache_stats()
        
        # Calculate cache hit rate
        cache_hit_rate = 0
        if cache_stats['search_cache_entries'] > 0:
            cache_hit_rate = (cache_stats['search_cache_hits'] / 
                            (cache_stats['search_cache_entries'] + cache_stats['search_cache_hits']) * 100)
        
        text = (
            f"<b>📊 Статистика бота:</b>\n\n"
            f"👤 Уникальных пользователей: {users_count}\n"
            f"📥 Всего скачано глав: {downloads_count}\n\n"
            f"<b>💾 Кэширование:</b>\n"
            f"📚 Манга в кэше: {cache_stats['manga_count']}\n"
            f"📖 Глав в кэше: {cache_stats['chapters_count']}\n"
            f"📄 Файлов с file_id: {cache_stats['cached_files']}\n"
            f"🔍 Поисковых запросов: {cache_stats['search_cache_entries']}\n"
            f"✅ Попаданий в кэш: {cache_stats['search_cache_hits']}\n"
            f"📈 Hit Rate: {cache_hit_rate:.1f}%"
        )
        await callback.message.edit_text(text, reply_markup=create_admin_keyboard())
    elif action == "admin_mailing":
        await state.set_state(AdminStates.mailing_get_content)
        await callback.message.edit_text("Пришлите сообщение, которое хотите разослать.")
    elif action == "admin_add_channel":
        await state.set_state(AdminStates.adding_channel)
        await callback.message.edit_text("Отправьте ID канала (например, @channelname или -100123456789).")
    elif action == "admin_remove_channel":
        await state.set_state(AdminStates.removing_channel)
        await callback.message.edit_text("Отправьте ID канала для удаления.")
    elif action == "admin_list_channels":
        channels = load_data(CHANNELS_FILE, {"channels": []})["channels"]
        text = "<b>Каналы для обязательной подписки:</b>\n\n" + "\n".join(
            f"<code>{ch}</code>" for ch in channels) if channels else "Список каналов пуст."
        await callback.message.edit_text(text, reply_markup=create_admin_keyboard())
    elif action == "admin_exit":
        await callback.message.delete()
        await state.clear()


async def process_adding_channel(message: types.Message, state: FSMContext):
    """Process adding a channel."""
    channel_id = message.text.strip()
    channels_data = load_data(CHANNELS_FILE, {"channels": []})
    if channel_id not in channels_data["channels"]:
        channels_data["channels"].append(channel_id)
        save_data(CHANNELS_FILE, channels_data)
        await message.answer(f"✅ Канал <code>{channel_id}</code> успешно добавлен.")
    else:
        await message.answer(f"⚠️ Канал <code>{channel_id}</code> уже есть в списке.")
    await state.set_state(AdminStates.panel)
    await message.answer("Админ-панель:", reply_markup=create_admin_keyboard())


async def process_removing_channel(message: types.Message, state: FSMContext):
    """Process removing a channel."""
    channel_id = message.text.strip()
    channels_data = load_data(CHANNELS_FILE, {"channels": []})
    if channel_id in channels_data["channels"]:
        channels_data["channels"].remove(channel_id)
        save_data(CHANNELS_FILE, channels_data)
        await message.answer(f"🗑 Канал <code>{channel_id}</code> удален.")
    else:
        await message.answer(f"❌ Канал <code>{channel_id}</code> не найден в списке.")
    await state.set_state(AdminStates.panel)
    await message.answer("Админ-панель:", reply_markup=create_admin_keyboard())


# --- ЛОГИКА РАССЫЛКИ ---
async def handle_mailing_content(message: types.Message, state: FSMContext):
    """Handle mailing content."""
    mailing_data = {}
    if message.text:
        mailing_data = {"type": "text", "text": message.html_text}
    elif message.photo:
        mailing_data = {"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.html_text}
    elif message.video:
        mailing_data = {"type": "video", "file_id": message.video.file_id, "caption": message.html_text}
    elif message.document:
        mailing_data = {"type": "document", "file_id": message.document.file_id, "caption": message.html_text}
    elif message.audio:
        mailing_data = {"type": "audio", "file_id": message.audio.file_id, "caption": message.html_text}
    else:
        await message.answer("❌ Неподдерживаемый тип сообщения.")
        return

    await state.update_data(mailing_data=mailing_data)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить кнопки", callback_data="mailing_skip_buttons")]]
    )
    await message.answer(
        "📎 Контент сохранен! Теперь отправьте кнопки в формате:\n\n<code>Текст - https://ссылка</code>\n\nИли нажмите 'Пропустить'",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.mailing_get_buttons)


async def handle_mailing_buttons(message: types.Message, state: FSMContext):
    """Handle mailing buttons."""
    try:
        buttons = []
        for line in message.text.strip().split('\n'):
            if ' - ' in line:
                text, url = line.split(' - ', 1)
                buttons.append([InlineKeyboardButton(text=text.strip(), url=url.strip())])
        await state.update_data(mailing_buttons=buttons)
        await show_mailing_preview(message.from_user.id, state)
    except Exception as e:
        await message.answer(f"❌ Ошибка в формате кнопок: {e}\nПопробуйте еще раз:")


async def skip_mailing_buttons(callback: CallbackQuery, state: FSMContext):
    """Skip mailing buttons."""
    await state.update_data(mailing_buttons=[])
    await callback.message.delete()
    await show_mailing_preview(callback.from_user.id, state)
    await callback.answer()


async def send_broadcast_message(chat_id: int, data: dict, bot):
    """Send broadcast message to user."""
    mailing_data = data.get('mailing_data', {})
    buttons = data.get('mailing_buttons', [])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    message_type = mailing_data.get('type')
    try:
        if message_type == 'text':
            await bot.send_message(
                chat_id=chat_id, 
                text=mailing_data['text'], 
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        elif message_type == 'photo':
            await bot.send_photo(
                chat_id=chat_id, 
                photo=mailing_data['file_id'], 
                caption=mailing_data.get('caption'),
                reply_markup=reply_markup
            )
        elif message_type == 'video':
            await bot.send_video(
                chat_id=chat_id, 
                video=mailing_data['file_id'], 
                caption=mailing_data.get('caption'),
                reply_markup=reply_markup
            )
        elif message_type == 'document':
            await bot.send_document(
                chat_id=chat_id, 
                document=mailing_data['file_id'],
                caption=mailing_data.get('caption'), 
                reply_markup=reply_markup
            )
        elif message_type == 'audio':
            await bot.send_audio(
                chat_id=chat_id, 
                audio=mailing_data['file_id'], 
                caption=mailing_data.get('caption'),
                reply_markup=reply_markup
            )
        return True
    except Exception as e:
        if "bot was blocked by the user" in str(e):
            print(f"Пользователь {chat_id} заблокировал бота.")
        elif "chat not found" in str(e):
            print(f"Чат с пользователем {chat_id} не найден.")
        else:
            print(f"Ошибка отправки пользователю {chat_id}: {e}")
        return False


async def show_mailing_preview(admin_id: int, state: FSMContext):
    """Show mailing preview."""
    from aiogram import Bot
    bot = Bot.get_current()
    
    data = await state.get_data()
    await bot.send_message(admin_id, "👀 Предпросмотр сообщения:")
    await send_broadcast_message(admin_id, data, bot)
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Начать рассылку", callback_data="mailing_confirm_send")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="mailing_confirm_cancel")]
    ])
    await bot.send_message(admin_id, "Начать рассылку?", reply_markup=confirm_keyboard)
    await state.set_state(AdminStates.mailing_confirm)


async def handle_mailing_confirmation(callback: CallbackQuery, state: FSMContext):
    """Handle mailing confirmation."""
    await callback.answer()
    if callback.data == "mailing_confirm_send":
        await callback.message.edit_text("🔄 Начинаю рассылку...")
        asyncio.create_task(start_broadcast(callback.from_user.id, state))
    else:
        await callback.message.edit_text("❌ Рассылка отменена.")
        await state.set_state(AdminStates.panel)
        await callback.message.answer("Админ-панель:", reply_markup=create_admin_keyboard())


async def start_broadcast(admin_id: int, state: FSMContext):
    """Start broadcasting to all users."""
    from aiogram import Bot
    bot = Bot.get_current()
    
    data = await state.get_data()
    users = load_data(USERS_FILE, {"users": []})["users"]
    total_users = len(users)
    successful, failed = 0, 0
    start_time = time.time()

    progress_msg = await bot.send_message(admin_id, f"📤 Рассылка начата... 0/{total_users}")

    for i, user_id in enumerate(users):
        if await send_broadcast_message(user_id, data, bot):
            successful += 1
        else:
            failed += 1

        if (i + 1) % 25 == 0 or (i + 1) == total_users:
            try:
                await bot.edit_message_text(
                    chat_id=admin_id,
                    message_id=progress_msg.message_id,
                    text=f"📤 Рассылка... {i + 1}/{total_users}\n✅ Успешно: {successful}\n❌ Ошибок: {failed}"
                )
            except TelegramBadRequest:
                pass
        await asyncio.sleep(0.04)

    end_time = time.time()
    duration = round(end_time - start_time)

    await bot.send_message(
        admin_id, 
        f"✅ Рассылка завершена за {duration} сек.!\n\n"
        f"👥 Всего: {total_users}\n"
        f"✅ Успешно: {successful}\n"
        f"❌ Ошибок: {failed}"
    )
    await state.set_state(AdminStates.panel)
    await bot.send_message(admin_id, "Админ-панель:", reply_markup=create_admin_keyboard())


def register_handlers(dp):
    """Register admin handlers."""
    dp.message.register(cmd_admin, Command("admin"))
    dp.callback_query.register(handle_admin_panel, AdminStates.panel)
    dp.message.register(process_adding_channel, AdminStates.adding_channel)
    dp.message.register(process_removing_channel, AdminStates.removing_channel)
    dp.message.register(handle_mailing_content, AdminStates.mailing_get_content, F.media_group_id)
    dp.message.register(handle_mailing_content, AdminStates.mailing_get_content)
    dp.message.register(handle_mailing_buttons, AdminStates.mailing_get_buttons)
    dp.callback_query.register(skip_mailing_buttons, AdminStates.mailing_get_buttons, F.data == "mailing_skip_buttons")
    dp.callback_query.register(handle_mailing_confirmation, AdminStates.mailing_confirm)
