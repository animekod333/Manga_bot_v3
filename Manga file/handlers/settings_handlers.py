"""Settings handlers."""
from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from models import MangaStates
from vip_manager import check_vip_access
from keyboards import create_settings_keyboard
import database


async def show_settings_menu(callback: CallbackQuery, state: FSMContext):
    """Show settings menu."""
    await state.set_state(MangaStates.settings_menu)
    await callback.message.edit_text(
        "⚙️ <b>Настройки VIP</b>\n\nЗдесь вы можете настроить дополнительные функции, доступные по подписке.",
        reply_markup=create_settings_keyboard(callback.from_user.id)
    )


async def handle_set_batch_size(callback: CallbackQuery, state: FSMContext):
    """Handle batch size setting."""
    if not check_vip_access(callback.from_user.id):
        await callback.answer("Эта функция доступна только для VIP-пользователей.", show_alert=True)
        return
    new_size = int(callback.data.split("_")[2])
    await database.save_user_settings(callback.from_user.id, {"batch_size": new_size})
    await callback.answer(f"✅ Установлено скачивание по {new_size} глав.", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=create_settings_keyboard(callback.from_user.id))


async def handle_set_output_format(callback: CallbackQuery, state: FSMContext):
    """Handle output format setting."""
    if not check_vip_access(callback.from_user.id):
        await callback.answer("Эта функция доступна только для VIP-пользователей.", show_alert=True)
        return
    new_format = callback.data.split("_")[2]
    await database.save_user_settings(callback.from_user.id, {"output_format": new_format})
    format_name = "PDF" if new_format == "pdf" else "Telegraph"
    await callback.answer(f"✅ Формат выдачи изменен на {format_name}.", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=create_settings_keyboard(callback.from_user.id))


def register_handlers(dp):
    """Register settings handlers."""
    dp.callback_query.register(handle_set_batch_size, MangaStates.settings_menu, F.data.startswith("set_batch_"))
    dp.callback_query.register(handle_set_output_format, MangaStates.settings_menu, F.data.startswith("set_format_"))
