"""VIP access management functions."""
from datetime import datetime, timedelta, timezone
from data_manager import load_data, save_data
from config import PREMIUM_USERS_FILE, VIP_PLANS


def grant_vip_access(user_id: int, plan_key: str):
    """Grant VIP access to user."""
    if plan_key not in VIP_PLANS:
        print(f"Ошибка: Неизвестный план '{plan_key}'")
        return
    users_data = load_data(PREMIUM_USERS_FILE, {})
    user_id_str = str(user_id)
    duration_days = VIP_PLANS[plan_key]["days"]
    start_date = datetime.now(timezone.utc)
    current_expiry_str = users_data.get(user_id_str, {}).get("vip_expires_at")
    if current_expiry_str:
        try:
            current_expiry_date = datetime.fromisoformat(current_expiry_str)
            if current_expiry_date.tzinfo is None:
                current_expiry_date = current_expiry_date.replace(tzinfo=timezone.utc)
            if current_expiry_date > start_date:
                start_date = current_expiry_date
        except (ValueError, TypeError):
            pass
    new_expiry_date = start_date + timedelta(days=duration_days)
    if user_id_str not in users_data:
        users_data[user_id_str] = {}
    users_data[user_id_str]["vip_expires_at"] = new_expiry_date.isoformat()
    save_data(PREMIUM_USERS_FILE, users_data)
    print(f"Пользователю {user_id} предоставлен/продлен VIP до {new_expiry_date.strftime('%Y-%m-%d %H:%M %Z')}.")


def check_vip_access(user_id: int) -> bool:
    """Check if user has active VIP access."""
    users_data = load_data(PREMIUM_USERS_FILE, {})
    user_info = users_data.get(str(user_id))
    if not user_info or "vip_expires_at" not in user_info:
        return False
    try:
        expiry_date = datetime.fromisoformat(user_info["vip_expires_at"])
        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < expiry_date
    except (ValueError, TypeError):
        return False


def get_vip_expiry_date(user_id: int) -> str | None:
    """Get VIP expiry date for user."""
    users_data = load_data(PREMIUM_USERS_FILE, {})
    user_info = users_data.get(str(user_id))
    if not user_info or "vip_expires_at" not in user_info:
        return None
    try:
        expiry_date = datetime.fromisoformat(user_info["vip_expires_at"])
        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expiry_date:
            return None
        return expiry_date.strftime("%d.%m.%Y в %H:%M UTC")
    except (ValueError, TypeError):
        return None
