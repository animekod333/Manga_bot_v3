"""Premium and payment handlers."""
from aiogram import types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from models import MangaStates
from vip_manager import grant_vip_access, check_vip_access, get_vip_expiry_date
from keyboards import create_premium_keyboard
from subscription import subscription_wrapper
from config import VIP_PLANS


@subscription_wrapper
async def cmd_premium(message: types.Message, state: FSMContext, bot):
    """Handle /premium command."""
    await show_premium_menu(message, state)


async def show_premium_menu(message: types.Message, state: FSMContext, is_callback: bool = False):
    """Show premium menu."""
    await state.set_state(MangaStates.premium_menu)
    user_id = message.chat.id
    text = (
        "🌟 <b>Premium доступ</b> 🌟\n\n"
        "Получите максимум от бота с VIP-подпиской!\n\n"
        "<b>Что вы получаете:</b>\n"
        "✅ <b>Пакетная загрузка</b> — скачивайте сразу по несколько глав.\n"
        "✅ <b>Быстрая навигация</b> — переключайтесь между главами прямо под файлом.\n"
        "✅ <b>Настройка скачивания</b> — выберите, сколько глав скачивать за раз.\n"
        "✅ <b>Формат Telegraph</b> — читайте мангу прямо в браузере без скачивания файлов.\n\n"
    )
    if check_vip_access(user_id):
        expiry_date = get_vip_expiry_date(user_id)
        text += (
            f"✅ <b>У вас уже есть активная подписка!</b>\n"
            f"     <i>Она действует до: {expiry_date}</i>\n\n"
            f"Вы можете продлить её, выбрав один из планов ниже:"
        )
    else:
        text += "Выберите подходящий план:"
    markup = create_premium_keyboard()
    if is_callback:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def handle_premium_from_settings(callback: CallbackQuery, state: FSMContext):
    """Handle premium button from settings."""
    await callback.answer()
    await show_premium_menu(callback.message, state, is_callback=True)


async def handle_premium_from_document(callback: CallbackQuery, state: FSMContext):
    """Handle premium button from document."""
    await callback.answer()
    await show_premium_menu(callback.message, state, is_callback=False)


async def handle_buy_premium(callback: CallbackQuery):
    """Handle buy premium button."""
    from utils import get_bot
    bot = get_bot()
    
    plan_key = callback.data.split("_", 1)[1]
    if plan_key not in VIP_PLANS:
        await callback.answer("Неизвестный тарифный план.", show_alert=True)
        return
    plan = VIP_PLANS[plan_key]

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=plan["title"],
        description=f"VIP-доступ к функциям бота на {plan['days']} дней.",
        payload=plan_key,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=plan["title"], amount=plan["stars"])]
    )
    await callback.answer()


async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    """Handle pre-checkout query."""
    from utils import get_bot
    bot = get_bot()
    
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


async def successful_payment_handler(message: types.Message):
    """Handle successful payment."""
    from utils import get_bot
    bot = get_bot()
    
    user_id = message.from_user.id
    payment_info = message.successful_payment
    plan_key = payment_info.invoice_payload
    grant_vip_access(user_id, plan_key)
    plan_title = VIP_PLANS.get(plan_key, {}).get("title", "услугу")
    expiry_date = get_vip_expiry_date(user_id)
    await bot.send_message(
        user_id, 
        f"🎉 <b>Спасибо за покупку!</b>\n\n"
        f"Вам предоставлен «{plan_title}».\n"
        f"Ваша подписка активна до: <b>{expiry_date}</b>.\n\n"
        "Все VIP-функции теперь доступны!"
    )


def register_handlers(dp):
    """Register premium handlers."""
    dp.message.register(cmd_premium, Command("premium"))
    dp.callback_query.register(handle_premium_from_settings, MangaStates.settings_menu, F.data == "main_premium")
    dp.callback_query.register(handle_premium_from_document, F.data == "main_premium", F.message.document)
    dp.callback_query.register(handle_buy_premium, MangaStates.premium_menu, F.data.startswith("buy_"))
    dp.pre_checkout_query.register(pre_checkout_query_handler)
    dp.message.register(successful_payment_handler, F.successful_payment)
