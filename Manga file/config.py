"""Configuration and constants for the manga bot."""
import os
import json
import requests
from telegraph import Telegraph

# --- Конфигурация ---
TOKEN = ""
BASE_URL = 'https://desu.city/manga/api'
ADMIN_IDS = []

# --- Файлы данных ---
FAVORITES_FILE = "favorites.json"
CACHE_FILE = "cache_data.json"
CHANNELS_FILE = "channels.json"
USERS_FILE = "users.json"
STATS_FILE = "stats.json"
SETTINGS_FILE = "user_settings.json"
PREMIUM_USERS_FILE = "premium_users.json"
CHANNEL_ID = "@houuak"
STORAGE_CHANNEL_ID = "@houuak"  # Telegram channel for file storage

# --- Константы ---
MANGAS_PER_PAGE = 10
CHAPTERS_PER_PAGE = 25
API_LIMIT = 50

# --- ПЛАНЫ VIP-ПОДПИСКИ ---
VIP_PLANS = {
    "vip_1m": {"stars": 150, "days": 30, "title": "VIP на 1 месяц"},
    "vip_3m": {"stars": 400, "days": 90, "title": "VIP на 3 месяца"},
    "vip_6m": {"stars": 700, "days": 180, "title": "VIP на 6 месяцев"},
    "vip_12m": {"stars": 1100, "days": 365, "title": "VIP на 1 год"},
}

MANGA_GENRES = [
    {"id": 56, "text": "Action", "russian": "Экшен"}, {"id": 49, "text": "Comedy", "russian": "Комедия"},
    {"id": 51, "text": "Ecchi", "russian": "Этти"}, {"id": 57, "text": "Fantasy", "russian": "Фэнтези"},
    {"id": 62, "text": "Romance", "russian": "Романтика"}, {"id": 60, "text": "School", "russian": "Школа"},
    {"id": 48, "text": "Supernatural", "russian": "Сверхъестественное"},
    {"id": 69, "text": "Seinen", "russian": "Сэйнэн"}, {"id": 71, "text": "Shounen", "russian": "Сёнэн"},
    {"id": 73, "text": "Shoujo", "russian": "Сёдзё"}, {"id": 78, "text": "Drama", "russian": "Драма"},
    {"id": 82, "text": "Adventure", "russian": "Приключения"},
    {"id": 83, "text": "Sci-Fi", "russian": "Научная фантастика"}, {"id": 85, "text": "Horror", "russian": "Ужасы"},
    {"id": 88, "text": "Slice of Life", "russian": "Повседневность"},
    {"id": 74, "text": "yaoi", "russian": "Яой"}, {"id": 75, "text": "yuri", "russian": "Юри"},
    {"id": 70, "text": "shounen-ai", "russian": "Сёнен-ай"}, {"id": 72, "text": "shoujo-ai", "russian": "Сёдзё-ай"}
]

MANGA_KINDS = [
    {"id": "manga", "russian": "Манга"},
    {"id": "manhwa", "russian": "Манхва (Корейская)"},
    {"id": "manhua", "russian": "Маньхуа (Китайская)"}
]

# --- Инициализация сессии ---
session = requests.Session()
session.headers.update({
    'User-Agent': 'AniMangaBot/1.0 (contact: @Dao12g)',
    'Referer': 'https://desu.city/'
})

# --- Инициализация Telegraph ---
def init_telegraph() -> Telegraph:
    """Инициализация Telegraph клиента."""
    access_token = None
    try:
        with open("telegraph_token.json", "r") as f:
            acc_data = json.load(f)
            access_token = acc_data.get("access_token")
    except (FileNotFoundError, json.JSONDecodeError):
        print("Файл токена Telegraph не найден или поврежден. Будет создан новый.")

    telegraph = Telegraph(access_token=access_token)

    if not access_token:
        try:
            account = telegraph.create_account(short_name='AniMangaBot')
            access_token = account['access_token']
            with open("telegraph_token.json", "w") as f:
                json.dump({"access_token": access_token}, f)
            print(f"Создан новый аккаунт Telegraph и сохранен токен: {access_token}")
            telegraph = Telegraph(access_token=access_token)
        except Exception as e:
            print(f"Критическая ошибка: не удалось создать аккаунт Telegraph: {e}")

    return telegraph

telegraph = init_telegraph()
