"""Main menu and start handlers."""
from aiogram import types, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from models import MangaStates
from data_manager import add_user_to_db
from subscription import check_subscription, get_subscribe_keyboard
from keyboards import create_main_inline_keyboard


async def cmd_start(message: types.Message, state: FSMContext):
    """Handle /start command."""
    from aiogram import Bot
    bot = message.bot
    
    await state.clear()
    add_user_to_db(message.from_user.id)
    if not await check_subscription(message.from_user.id, bot):
        await message.answer(
            "Для использования бота, пожалуйста, подпишитесь на наши каналы:",
            reply_markup=await get_subscribe_keyboard(bot)
        )
        return
    await show_main_menu(message, state)


async def show_main_menu(message_or_callback: types.Message | CallbackQuery, state: FSMContext):
    """Show main menu."""
    text = (
        "<b>👋 Главное меню AniMangaBot!</b>\n\n"
        "Здесь ты можешь найти и читать свою любимую мангу 📚.\n\n"
        "▫️ /start — Перезапуск бота\n"
        "▫️ /premium — Узнать о преимуществах и купить VIP"
    )
    markup = create_main_inline_keyboard()
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=markup)
    else:
        try:
            await message_or_callback.message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:
            await message_or_callback.message.delete()
            await message_or_callback.message.answer(text, reply_markup=markup)
        finally:
            await message_or_callback.answer()
    await state.set_state(MangaStates.main_menu)


async def back_to_main_menu_handler(callback: CallbackQuery, state: FSMContext):
    """Handle back to main menu button."""
    await state.clear()
    await show_main_menu(callback, state)


async def check_subscription_again_handler(callback: CallbackQuery, state: FSMContext):
    """Handle subscription check again button."""
    from aiogram import Bot
    bot = callback.bot
    
    if await check_subscription(callback.from_user.id, bot):
        await callback.answer("✅ Спасибо за подписку!", show_alert=True)
        await callback.message.delete()
        await cmd_start(callback.message, state)
    else:
        await callback.answer("❌ Вы еще не подписались на все каналы.", show_alert=True)


def register_handlers(dp):
    """Register main menu handlers."""
    dp.message.register(cmd_start, CommandStart())
    dp.callback_query.register(back_to_main_menu_handler, F.data == "back_to_main_menu", StateFilter("*"))
    dp.callback_query.register(check_subscription_again_handler, F.data == "check_subscription_again")
