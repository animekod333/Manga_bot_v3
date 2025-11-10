"""Cache management functions."""
from datetime import datetime
from data_manager import load_data, save_data
from config import CACHE_FILE


def get_cache_key(manga_id, chapter_num, format_type='pdf'):
    """Generate cache key."""
    return f"{manga_id}_{chapter_num}_{format_type}"


def get_file_id_from_cache(manga_id, chapter_num, cache_data, format_type='pdf'):
    """Get file ID from cache."""
    key = get_cache_key(manga_id, chapter_num, format_type)
    return cache_data["files"].get(key)


def save_file_id_to_cache(manga_id, chapter_num, file_id_or_url, cache_data, format_type='pdf'):
    """Save file ID to cache."""
    key = get_cache_key(manga_id, chapter_num, format_type)
    data_to_save = {"data": file_id_or_url, "timestamp": datetime.now().isoformat()}
    cache_data["files"][key] = data_to_save
    save_data(CACHE_FILE, cache_data)
