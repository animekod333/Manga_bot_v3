"""Subscription checking functions and decorators."""
from functools import wraps
from aiogram import types
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from data_manager import load_data
from config import CHANNELS_FILE


async def check_subscription(user_id: int, bot):
    """Check if user is subscribed to required channels."""
    channels = load_data(CHANNELS_FILE, {"channels": []})["channels"]
    if not channels: 
        return True
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']: 
                return False
        except TelegramBadRequest:
            print(f"Ошибка: Неверный ID канала '{channel}' или бот не админ в нем.")
            return False
        except Exception as e:
            print(f"Неожиданная ошибка при проверке подписки на {channel}: {e}")
            return False
    return True


async def get_subscribe_keyboard(bot):
    """Generate subscription keyboard."""
    channels = load_data(CHANNELS_FILE, {"channels": []})["channels"]
    keyboard = []
    for channel in channels:
        try:
            chat_info = await bot.get_chat(channel)
            invite_link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
            keyboard.append([InlineKeyboardButton(text=f"➡️ {chat_info.title}", url=invite_link)])
        except Exception as e:
            print(f"Не удалось получить информацию о канале {channel}: {e}")
    keyboard.append([InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription_again")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def subscription_wrapper(func):
    """Decorator to check subscription before executing handler."""
    @wraps(func)
    async def wrapper(event: types.Message | CallbackQuery, bot, **kwargs):
        user_id = event.from_user.id
        if not await check_subscription(user_id, bot):
            keyboard = await get_subscribe_keyboard(bot)
            text = "Для использования бота, пожалуйста, подпишитесь на наши каналы:"
            if isinstance(event, CallbackQuery):
                await event.message.answer(text, reply_markup=keyboard)
                await event.answer()
            else:
                await event.answer(text, reply_markup=keyboard)
            return
        return await func(event, bot=bot, **kwargs)
    return wrapper
