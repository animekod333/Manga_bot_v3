"""Database module for multi-level caching architecture."""
import aiosqlite
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path


DB_PATH = Path("manga_bot.db")


async def init_database():
    """Initialize database with required tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Основная информация о манге
        await db.execute("""
            CREATE TABLE IF NOT EXISTS manga (
                id INTEGER PRIMARY KEY,
                title_ru TEXT,
                title_en TEXT,
                description TEXT,
                cover_url TEXT,
                genres TEXT,
                status TEXT,
                rating REAL,
                year INTEGER,
                kind TEXT,
                chapters_count INTEGER,
                last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Главы манги
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manga_id INTEGER NOT NULL,
                chapter_number REAL NOT NULL,
                chapter_id TEXT NOT NULL,
                title TEXT,
                file_id TEXT,
                telegraph_url TEXT,
                pages_count INTEGER,
                size_mb REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (manga_id) REFERENCES manga(id),
                UNIQUE(manga_id, chapter_number)
            )
        """)
        
        # Кэш поисковых запросов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS search_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_hash TEXT UNIQUE NOT NULL,
                query_text TEXT,
                filters TEXT,
                results TEXT,
                hit_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        """)
        
        # Пользователи и лимиты
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                is_premium BOOLEAN DEFAULT FALSE,
                daily_requests INTEGER DEFAULT 0,
                monthly_requests INTEGER DEFAULT 0,
                settings TEXT,
                last_request_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для оптимизации
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chapters_manga_id ON chapters(manga_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_hash ON search_cache(query_hash)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON search_cache(expires_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_premium ON users(is_premium)")
        
        await db.commit()
        print("✅ База данных инициализирована успешно")


# === Manga Functions ===

async def save_manga_to_db(manga_data: Dict[str, Any]) -> None:
    """Save or update manga metadata in database."""
    async with aiosqlite.connect(DB_PATH) as db:
        genres_json = json.dumps(manga_data.get('genres', []), ensure_ascii=False)
        
        await db.execute("""
            INSERT OR REPLACE INTO manga 
            (id, title_ru, title_en, description, cover_url, genres, status, rating, year, kind, chapters_count, last_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            manga_data.get('id'),
            manga_data.get('russian'),
            manga_data.get('name'),
            manga_data.get('description'),
            manga_data.get('image', {}).get('original') if isinstance(manga_data.get('image'), dict) else None,
            genres_json,
            manga_data.get('status'),
            manga_data.get('score'),
            manga_data.get('aired_on', {}).get('year') if isinstance(manga_data.get('aired_on'), dict) else None,
            manga_data.get('kind'),
            manga_data.get('chapters', 0),
            datetime.now().isoformat()
        ))
        
        await db.commit()


async def get_manga_from_db(manga_id: int) -> Optional[Dict[str, Any]]:
    """Get manga metadata from database."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM manga WHERE id = ?", (manga_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None


async def is_manga_cached(manga_id: int, max_age_hours: int = 24) -> bool:
    """Check if manga is cached and fresh."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT last_synced FROM manga WHERE id = ?", (manga_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                last_synced = datetime.fromisoformat(row[0])
                age = datetime.now() - last_synced
                return age < timedelta(hours=max_age_hours)
    return False


# === Chapter Functions ===

async def save_chapter_to_db(manga_id: int, chapter_data: Dict[str, Any], 
                             file_id: Optional[str] = None, 
                             telegraph_url: Optional[str] = None) -> None:
    """Save chapter metadata to database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO chapters 
            (manga_id, chapter_number, chapter_id, title, file_id, telegraph_url, pages_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            manga_id,
            float(chapter_data.get('ch', 0)),
            str(chapter_data.get('id', '')),
            chapter_data.get('title'),
            file_id,
            telegraph_url,
            chapter_data.get('pages_count'),
            datetime.now().isoformat()
        ))
        await db.commit()


async def get_chapter_file_id(manga_id: int, chapter_number: float) -> Optional[str]:
    """Get cached file_id for chapter."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT file_id FROM chapters WHERE manga_id = ? AND chapter_number = ?",
            (manga_id, chapter_number)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
    return None


async def get_chapter_telegraph_url(manga_id: int, chapter_number: float) -> Optional[str]:
    """Get cached telegraph URL for chapter."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT telegraph_url FROM chapters WHERE manga_id = ? AND chapter_number = ?",
            (manga_id, chapter_number)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
    return None


async def update_chapter_file_id(manga_id: int, chapter_number: float, file_id: str) -> None:
    """Update file_id for cached chapter."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE chapters SET file_id = ? 
            WHERE manga_id = ? AND chapter_number = ?
        """, (file_id, manga_id, chapter_number))
        await db.commit()


async def update_chapter_telegraph_url(manga_id: int, chapter_number: float, telegraph_url: str) -> None:
    """Update telegraph URL for cached chapter."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE chapters SET telegraph_url = ? 
            WHERE manga_id = ? AND chapter_number = ?
        """, (telegraph_url, manga_id, chapter_number))
        await db.commit()


# === Search Cache Functions ===

def create_query_hash(query: str, filters: Optional[Dict[str, Any]] = None) -> str:
    """Create hash for search query and filters."""
    query_str = query.lower().strip()
    if filters:
        filter_str = json.dumps(filters, sort_keys=True)
        query_str += filter_str
    return hashlib.md5(query_str.encode()).hexdigest()


async def get_search_cache(query: str, filters: Optional[Dict[str, Any]] = None, 
                           cache_hours: int = 24) -> Optional[List[int]]:
    """Get cached search results."""
    query_hash = create_query_hash(query, filters)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT results, expires_at FROM search_cache 
            WHERE query_hash = ? AND expires_at > ?
        """, (query_hash, datetime.now().isoformat())) as cursor:
            row = await cursor.fetchone()
            
            if row:
                # Увеличить счетчик попаданий
                await db.execute(
                    "UPDATE search_cache SET hit_count = hit_count + 1 WHERE query_hash = ?",
                    (query_hash,)
                )
                await db.commit()
                
                return json.loads(row[0])
    
    return None


async def save_search_cache(query: str, filters: Optional[Dict[str, Any]], 
                            manga_ids: List[int], cache_hours: int = 24) -> None:
    """Save search results to cache."""
    query_hash = create_query_hash(query, filters)
    expires_at = datetime.now() + timedelta(hours=cache_hours)
    
    filters_json = json.dumps(filters, ensure_ascii=False) if filters else None
    results_json = json.dumps(manga_ids)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO search_cache 
            (query_hash, query_text, filters, results, hit_count, created_at, expires_at)
            VALUES (?, ?, ?, ?, 0, ?, ?)
        """, (query_hash, query, filters_json, results_json, datetime.now().isoformat(), expires_at.isoformat()))
        await db.commit()


async def cleanup_expired_cache() -> None:
    """Remove expired cache entries."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM search_cache WHERE expires_at < ?", (datetime.now().isoformat(),))
        await db.commit()


# === User & Rate Limit Functions ===

async def get_or_create_user(user_id: int, is_premium: bool = False) -> Dict[str, Any]:
    """Get or create user record."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Try to get existing user
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        
        # Create new user
        today = datetime.now().date().isoformat()
        await db.execute("""
            INSERT INTO users (user_id, is_premium, daily_requests, monthly_requests, last_request_date, created_at)
            VALUES (?, ?, 0, 0, ?, ?)
        """, (user_id, is_premium, today, datetime.now().isoformat()))
        await db.commit()
        
        # Return new user
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row)


async def check_rate_limit(user_id: int, is_premium: bool = False) -> tuple[bool, str]:
    """Check if user has exceeded rate limits.
    
    Returns:
        (can_proceed, message) - True if user can make request, False otherwise
    """
    user = await get_or_create_user(user_id, is_premium)
    today = datetime.now().date().isoformat()
    
    # Reset daily counter if new day
    if user['last_request_date'] != today:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE users SET daily_requests = 0, last_request_date = ?
                WHERE user_id = ?
            """, (today, user_id))
            await db.commit()
        user['daily_requests'] = 0
    
    # Check limits
    daily_limit = 100 if is_premium else 10
    monthly_limit = 3000 if is_premium else 300
    
    if user['daily_requests'] >= daily_limit:
        return False, f"❌ Превышен дневной лимит запросов ({daily_limit}). Попробуйте завтра."
    
    if user['monthly_requests'] >= monthly_limit:
        return False, f"❌ Превышен месячный лимит запросов ({monthly_limit})."
    
    return True, ""


async def increment_request_count(user_id: int) -> None:
    """Increment user's request counters."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users 
            SET daily_requests = daily_requests + 1,
                monthly_requests = monthly_requests + 1
            WHERE user_id = ?
        """, (user_id,))
        await db.commit()


async def update_user_premium_status(user_id: int, is_premium: bool) -> None:
    """Update user's premium status."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_premium = ? WHERE user_id = ?",
            (is_premium, user_id)
        )
        await db.commit()


async def get_user_settings(user_id: int) -> Dict[str, Any]:
    """Get user settings from database."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT settings FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
    return {"batch_size": 5, "output_format": "pdf"}


async def save_user_settings(user_id: int, settings: Dict[str, Any]) -> None:
    """Save user settings to database."""
    await get_or_create_user(user_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        settings_json = json.dumps(settings, ensure_ascii=False)
        await db.execute(
            "UPDATE users SET settings = ? WHERE user_id = ?",
            (settings_json, user_id)
        )
        await db.commit()


# === Statistics Functions ===

async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Total cached manga
        async with db.execute("SELECT COUNT(*) FROM manga") as cursor:
            manga_count = (await cursor.fetchone())[0]
        
        # Total cached chapters
        async with db.execute("SELECT COUNT(*) FROM chapters") as cursor:
            chapters_count = (await cursor.fetchone())[0]
        
        # Chapters with file_id
        async with db.execute("SELECT COUNT(*) FROM chapters WHERE file_id IS NOT NULL") as cursor:
            cached_files = (await cursor.fetchone())[0]
        
        # Search cache stats
        async with db.execute("SELECT COUNT(*), SUM(hit_count) FROM search_cache") as cursor:
            row = await cursor.fetchone()
            search_entries = row[0]
            total_hits = row[1] or 0
        
        return {
            "manga_count": manga_count,
            "chapters_count": chapters_count,
            "cached_files": cached_files,
            "search_cache_entries": search_entries,
            "search_cache_hits": total_hits
        }
