"""Functions for data loading and saving."""
import os
import json
from config import FAVORITES_FILE, USERS_FILE, STATS_FILE, SETTINGS_FILE


def load_data(file_path, default_data):
    """Load data from JSON file."""
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, indent=2)
        return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default_data


def save_data(file_path, data):
    """Save data to JSON file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Ошибка сохранения файла {file_path}: {e}")


def add_user_to_db(user_id):
    """Add user to database."""
    users = load_data(USERS_FILE, {"users": []})
    if user_id not in users["users"]:
        users["users"].append(user_id)
        save_data(USERS_FILE, users)


def get_display_name(manga_data: dict) -> str:
    """Get display name for manga."""
    return manga_data.get('russian') or manga_data.get('name', 'Неизвестно')


def increment_download_count():
    """Increment download statistics."""
    stats = load_data(STATS_FILE, {"downloads": 0})
    stats["downloads"] += 1
    save_data(STATS_FILE, stats)


# --- Функции для избранного ---
def add_to_favorites(user_id, manga_info):
    """Add manga to user's favorites."""
    favorites = load_data(FAVORITES_FILE, {})
    user_id_str = str(user_id)
    if user_id_str not in favorites: 
        favorites[user_id_str] = []
    if not any(str(m['id']) == str(manga_info['id']) for m in favorites[user_id_str]):
        simplified_manga = {
            'id': manga_info['id'], 
            'name': manga_info.get('name'),
            'russian': manga_info.get('russian')
        }
        favorites[user_id_str].append(simplified_manga)
        save_data(FAVORITES_FILE, favorites)
        return True
    return False


def remove_from_favorites(user_id, manga_id):
    """Remove manga from user's favorites."""
    favorites = load_data(FAVORITES_FILE, {})
    user_id_str = str(user_id)
    if user_id_str in favorites:
        initial_len = len(favorites[user_id_str])
        favorites[user_id_str] = [m for m in favorites[user_id_str] if str(m['id']) != str(manga_id)]
        if len(favorites[user_id_str]) < initial_len:
            save_data(FAVORITES_FILE, favorites)
            return True
    return False


def get_user_favorites(user_id):
    """Get user's favorites list."""
    return load_data(FAVORITES_FILE, {}).get(str(user_id), [])


def is_in_favorites(user_id, manga_id):
    """Check if manga is in user's favorites."""
    return any(str(m['id']) == str(manga_id) for m in get_user_favorites(user_id))


# --- Настройки пользователя ---
def get_user_settings(user_id: int) -> dict:
    """Get user settings with defaults."""
    all_settings = load_data(SETTINGS_FILE, {})
    default_settings = {"batch_size": 5, "output_format": "pdf"}
    user_settings = all_settings.get(str(user_id), {})
    default_settings.update(user_settings)
    return default_settings


def save_user_settings(user_id: int, new_settings: dict):
    """Save user settings."""
    all_settings = load_data(SETTINGS_FILE, {})
    user_id_str = str(user_id)
    if user_id_str not in all_settings:
        all_settings[user_id_str] = {}
    all_settings[user_id_str].update(new_settings)
    save_data(SETTINGS_FILE, all_settings)
