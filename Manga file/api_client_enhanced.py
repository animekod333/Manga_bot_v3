"""Enhanced API client with protection mechanisms and caching."""
import asyncio
import time
import random
from io import BytesIO
from typing import Optional, Tuple, List, Dict, Any
from PIL import Image
import img2pdf
import requests
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from http.client import IncompleteRead
from requests.exceptions import RequestException
from telegraph.exceptions import TelegraphException
from config import BASE_URL, telegraph, API_LIMIT
import database
from performance_monitor import monitor


# User-Agent rotation for protection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


def get_random_user_agent() -> str:
    """Get random User-Agent for requests."""
    return random.choice(USER_AGENTS)


def create_session() -> requests.Session:
    """Create session with rotating User-Agent."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': get_random_user_agent(),
        'Referer': 'https://desu.city/'
    })
    return session


# Global session
_session = create_session()


async def safe_api_call(url: str, timeout: int = 15, max_retries: int = 3) -> Optional[requests.Response]:
    """Safe API call with error handling and retries.
    
    Args:
        url: URL to request
        timeout: Request timeout in seconds
        max_retries: Maximum number of retries
        
    Returns:
        Response object or None if failed
    """
    global _session
    
    for attempt in range(max_retries):
        try:
            # Rotate User-Agent for each retry
            if attempt > 0:
                _session.headers.update({'User-Agent': get_random_user_agent()})
            
            response = _session.get(url, timeout=timeout)
            
            # Handle rate limiting
            if response.status_code == 429:
                wait_time = 300  # 5 minutes
                print(f"⚠️ Rate limit hit (429). Waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                continue
            
            # Handle forbidden
            if response.status_code == 403:
                print(f"🚫 Access forbidden (403). Possible ban detected!")
                # Log ban alert
                with open("ban_alerts.log", "a") as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - 403 Forbidden on {url}\n")
                
                # Wait longer and retry with new User-Agent
                if attempt < max_retries - 1:
                    wait_time = 60 * (attempt + 1)
                    print(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                    _session = create_session()  # Create new session
                    continue
                return None
            
            response.raise_for_status()
            monitor.log_api_call()
            return response
            
        except RequestException as e:
            print(f"⚠️ API call error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            return None
        
        except Exception as e:
            print(f"❌ Unexpected error in API call: {e}")
            return None
    
    return None


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2),
       retry=retry_if_exception_type((IncompleteRead, RequestException)))
def download_image(img_url: str) -> bytes:
    """Download image with retry logic."""
    global _session
    r = _session.get(img_url, timeout=15)
    r.raise_for_status()
    return r.content


async def get_mangas(query: str = "", api_page: int = 1, order_by: str = "popular", 
                     user_id: Optional[int] = None) -> Tuple[List[Dict], Dict]:
    """Get list of mangas with caching support.
    
    Args:
        query: Search query
        api_page: Page number
        order_by: Sort order
        user_id: User ID for rate limiting (optional)
        
    Returns:
        Tuple of (manga_list, page_navigation)
    """
    # Check cache first for search queries
    if query and api_page == 1:
        filters = {"order_by": order_by}
        cached_ids = await database.get_search_cache(query, filters)
        
        if cached_ids:
            print(f"✅ Cache hit for search query: {query}")
            monitor.log_cache_hit()
            # Get manga details from cache
            mangas = []
            for manga_id in cached_ids[:API_LIMIT]:
                manga = await database.get_manga_from_db(manga_id)
                if manga:
                    # Convert DB format to API format
                    mangas.append({
                        'id': manga['id'],
                        'russian': manga['title_ru'],
                        'name': manga['title_en'],
                        'description': manga['description'],
                        'image': {'original': manga['cover_url']},
                        'score': manga['rating'],
                        'kind': manga['kind'],
                        'status': manga['status']
                    })
            
            if mangas:
                return mangas, {'pages': 1, 'items': len(mangas)}
    
    # Fallback to API
    monitor.log_cache_miss()
    try:
        query = query.strip()
        cache_buster = f"&_={int(time.time() * 1000)}"
        url = f'{BASE_URL}/?search={query}&limit={API_LIMIT}&page={api_page}&order_by={order_by}{cache_buster}'
        
        response = await safe_api_call(url)
        if not response:
            return [], {}
        
        data = response.json()
        mangas = data.get('response', [])
        page_nav = data.get('pageNavParams', {})
        
        # Cache results and manga metadata
        if mangas and query and api_page == 1:
            manga_ids = [m['id'] for m in mangas]
            filters = {"order_by": order_by}
            await database.save_search_cache(query, filters, manga_ids)
            
            # Save individual manga to DB
            for manga in mangas:
                await database.save_manga_to_db(manga)
        
        return mangas, page_nav
        
    except Exception as e:
        print(f"❌ Error in get_mangas: {e}")
        return [], {}


async def get_manga_info(manga_id: str, use_cache: bool = True) -> Dict[str, Any]:
    """Get detailed manga information with caching.
    
    Args:
        manga_id: Manga ID
        use_cache: Whether to use cached data
        
    Returns:
        Manga information dictionary
    """
    # Check cache first
    if use_cache:
        cached = await database.get_manga_from_db(int(manga_id))
        if cached and await database.is_manga_cached(int(manga_id), max_age_hours=24):
            print(f"✅ Cache hit for manga: {manga_id}")
            # Convert DB format to API format
            return {
                'id': cached['id'],
                'russian': cached['title_ru'],
                'name': cached['title_en'],
                'description': cached['description'],
                'image': {'original': cached['cover_url']},
                'score': cached['rating'],
                'kind': cached['kind'],
                'status': cached['status'],
                'chapters': cached['chapters_count']
            }
    
    # Fallback to API
    try:
        url = f'{BASE_URL}/{manga_id}'
        response = await safe_api_call(url)
        
        if not response:
            return {}
        
        manga = response.json().get('response', {})
        
        # Cache the result
        if manga:
            await database.save_manga_to_db(manga)
        
        return manga
        
    except Exception as e:
        print(f"❌ Error in get_manga_info: {e}")
        return {}


async def get_mangas_by_genres_and_kinds(genres: str, kinds: str = "", search: str = "", 
                                         api_page: int = 1, order_by: str = "popular") -> Tuple[List[Dict], Dict]:
    """Get mangas filtered by genres and kinds with caching.
    
    Args:
        genres: Comma-separated genre IDs
        kinds: Comma-separated kind IDs
        search: Search query
        api_page: Page number
        order_by: Sort order
        
    Returns:
        Tuple of (manga_list, page_navigation)
    """
    # Check cache for complex queries
    if api_page == 1 and (genres or kinds):
        filters = {
            "genres": genres,
            "kinds": kinds,
            "order_by": order_by
        }
        cached_ids = await database.get_search_cache(search, filters)
        
        if cached_ids:
            print(f"✅ Cache hit for filtered search")
            mangas = []
            for manga_id in cached_ids[:API_LIMIT]:
                manga = await database.get_manga_from_db(manga_id)
                if manga:
                    mangas.append({
                        'id': manga['id'],
                        'russian': manga['title_ru'],
                        'name': manga['title_en'],
                        'image': {'original': manga['cover_url']},
                        'score': manga['rating'],
                        'kind': manga['kind']
                    })
            
            if mangas:
                return mangas, {'pages': 1, 'items': len(mangas)}
    
    # Fallback to API
    try:
        search = search.strip()
        cache_buster = f"&_={int(time.time() * 1000)}"
        url = f'{BASE_URL}/?limit={API_LIMIT}&page={api_page}&order_by={order_by}{cache_buster}'
        
        if genres:
            url += f"&genres={genres}"
        if kinds:
            url += f"&kinds={kinds}"
        if search:
            url += f"&search={search}"
        
        response = await safe_api_call(url)
        if not response:
            return [], {}
        
        data = response.json()
        mangas = data.get('response', [])
        page_nav = data.get('pageNavParams', {})
        
        # Cache results
        if mangas and api_page == 1:
            manga_ids = [m['id'] for m in mangas]
            filters = {
                "genres": genres,
                "kinds": kinds,
                "order_by": order_by
            }
            await database.save_search_cache(search, filters, manga_ids)
            
            # Save manga metadata
            for manga in mangas:
                await database.save_manga_to_db(manga)
        
        return mangas, page_nav
        
    except Exception as e:
        print(f"❌ Error in get_mangas_by_genres_and_kinds: {e}")
        return [], {}


async def get_chapter(manga_id: int, chapter_number: float, 
                     format_type: str = 'pdf') -> Optional[str]:
    """Get chapter file_id or telegraph URL from cache.
    
    Args:
        manga_id: Manga ID
        chapter_number: Chapter number
        format_type: 'pdf' or 'telegraph'
        
    Returns:
        file_id or telegraph_url if cached, None otherwise
    """
    if format_type == 'pdf':
        return await database.get_chapter_file_id(manga_id, chapter_number)
    elif format_type == 'telegraph':
        return await database.get_chapter_telegraph_url(manga_id, chapter_number)
    return None


async def upload_to_telegraph(manga_name: str, chapter: dict, pages: list, callback) -> str | None:
    """Upload chapter to Telegraph with caching."""
    from aiogram import Bot
    bot = Bot.get_current()
    
    # Check cache first
    manga_id = callback.data.split('_')[1] if '_' in callback.data else None
    if manga_id:
        cached_url = await database.get_chapter_telegraph_url(int(manga_id), float(chapter['ch']))
        if cached_url:
            print(f"✅ Telegraph URL cached for chapter {chapter['ch']}")
            return cached_url
    
    progress_message = await bot.send_message(
        callback.from_user.id,
        f"Загружаю главу {chapter['ch']} в Telegraph (0/{len(pages)})..."
    )
    
    try:
        image_urls = []
        for i, page in enumerate(pages, 1):
            image_urls.append(f"<img src='{page['img']}'/>")
            if i % 10 == 0 or i == len(pages):
                await bot.edit_message_text(
                    f"Подготавливаю главу {chapter['ch']} ({i}/{len(pages)})...",
                    chat_id=callback.from_user.id,
                    message_id=progress_message.message_id
                )
        
        content = "".join(image_urls)
        title = f"{manga_name} - Глава {chapter['ch']}"
        author_name = "AniMangaBot"
        
        response = telegraph.create_page(
            title=title,
            html_content=content,
            author_name=author_name
        )
        
        telegraph_url = response['url']
        
        # Cache the URL
        if manga_id:
            await database.update_chapter_telegraph_url(int(manga_id), float(chapter['ch']), telegraph_url)
        
        await bot.delete_message(chat_id=callback.from_user.id, message_id=progress_message.message_id)
        return telegraph_url
        
    except TelegraphException as e:
        print(f"❌ Telegraph API error: {e}")
        await bot.edit_message_text(
            "❌ Ошибка при создании страницы Telegraph.",
            chat_id=callback.from_user.id,
            message_id=progress_message.message_id
        )
        return None
    except Exception as e:
        print(f"❌ Error in upload_to_telegraph: {e}")
        if progress_message:
            await bot.edit_message_text(
                "❌ Произошла ошибка при загрузке в Telegraph.",
                chat_id=callback.from_user.id,
                message_id=progress_message.message_id
            )
        return None


async def download_chapter(manga_id: str, chapter: dict, callback) -> bytes | None:
    """Download chapter as PDF with caching."""
    from aiogram import Bot
    bot = Bot.get_current()
    
    url = f"{BASE_URL}/{manga_id}/chapter/{chapter['id']}"
    progress_message = None
    
    try:
        response = await safe_api_call(url)
        if not response:
            await bot.send_message(
                callback.from_user.id,
                f"❌ Не удалось получить данные главы {chapter['ch']}."
            )
            return None
        
        data = response.json().get('response')
        if not data or 'pages' not in data or 'list' not in data['pages']:
            await bot.send_message(
                callback.from_user.id,
                f"❌ Ошибка: нет данных о страницах для главы {chapter['ch']}."
            )
            return None
        
        pages = data['pages']['list']
        total_pages = len(pages)
        
        progress_message = await bot.send_message(
            callback.from_user.id,
            f"Скачиваю главу {chapter['ch']} (0/{total_pages} страниц)..."
        )
        
        images_for_pdf = []
        for i, page in enumerate(pages, 1):
            try:
                img_data = download_image(page['img'])
                img = Image.open(BytesIO(img_data))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                output_buffer = BytesIO()
                img.save(output_buffer, format='JPEG', quality=85)
                images_for_pdf.append(output_buffer.getvalue())
                
                if i % 5 == 0 or i == total_pages:
                    await bot.edit_message_text(
                        f"Скачиваю и сжимаю главу {chapter['ch']} ({i}/{total_pages} страниц)...",
                        chat_id=callback.from_user.id,
                        message_id=progress_message.message_id
                    )
            except Exception as e:
                print(f"⚠️ Error downloading page {i}: {e}")
        
        if not images_for_pdf:
            await bot.edit_message_text(
                "❌ Ошибка: не удалось скачать ни одной страницы.",
                chat_id=callback.from_user.id,
                message_id=progress_message.message_id
            )
            return None
        
        await bot.edit_message_text(
            f"⚙️ Конвертирую {len(images_for_pdf)} страниц в PDF...",
            chat_id=callback.from_user.id,
            message_id=progress_message.message_id
        )
        
        pdf_bytes = img2pdf.convert(images_for_pdf)
        
        if len(pdf_bytes) > 50 * 1024 * 1024:
            await bot.delete_message(chat_id=callback.from_user.id, message_id=progress_message.message_id)
            await bot.send_message(
                callback.from_user.id,
                f"❌ Ошибка: Глава {chapter['ch']} слишком большая (> 50 МБ)."
            )
            return None
        
        await bot.delete_message(chat_id=callback.from_user.id, message_id=progress_message.message_id)
        return pdf_bytes
        
    except Exception as e:
        print(f"❌ Error in download_chapter: {e}")
        if progress_message:
            await bot.edit_message_text(
                "❌ Произошла ошибка при скачивании главы.",
                chat_id=callback.from_user.id,
                message_id=progress_message.message_id
            )
        return None
