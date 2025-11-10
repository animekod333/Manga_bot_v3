"""API client for manga data and image downloading."""
import time
from io import BytesIO
from PIL import Image
import img2pdf
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from http.client import IncompleteRead
from requests.exceptions import RequestException
from telegraph.exceptions import TelegraphException
from config import BASE_URL, session, telegraph, API_LIMIT


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2),
       retry=retry_if_exception_type((IncompleteRead, RequestException)))
def download_image(img_url: str) -> bytes:
    """Download image with retry logic."""
    r = session.get(img_url, timeout=15)
    r.raise_for_status()
    return r.content


def get_mangas(query: str = "", api_page: int = 1, order_by: str = "popular"):
    """Get list of mangas from API."""
    try:
        query = query.strip()
        cache_buster = f"&_={int(time.time() * 1000)}"
        url = f'{BASE_URL}/?search={query}&limit={API_LIMIT}&page={api_page}&order_by={order_by}{cache_buster}'
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get('response', []), data.get('pageNavParams', {})
    except Exception as e:
        print(f"Ошибка в get_mangas: {e}")
        return [], {}


def get_manga_info(manga_id: str):
    """Get detailed manga information."""
    try:
        url = f'{BASE_URL}/{manga_id}'
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json().get('response', {})
    except Exception as e:
        print(f"Ошибка в get_manga_info: {e}")
        return {}


def get_mangas_by_genres_and_kinds(genres, kinds="", search="", api_page=1, order_by="popular"):
    """Get mangas filtered by genres and kinds."""
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
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get('response', []), data.get('pageNavParams', {})
    except Exception as e:
        print(f"Ошибка в get_mangas_by_genres_and_kinds: {e}")
        return [], {}


async def upload_to_telegraph(manga_name: str, chapter: dict, pages: list, callback) -> str | None:
    """Upload chapter to Telegraph."""
    from aiogram import Bot
    bot = Bot.get_current()
    
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
        await bot.delete_message(chat_id=callback.from_user.id, message_id=progress_message.message_id)
        return response['url']
    except TelegraphException as e:
        print(f"Ошибка Telegraph API: {e}")
        await bot.edit_message_text(
            "❌ Ошибка при создании страницы Telegraph.",
            chat_id=callback.from_user.id, 
            message_id=progress_message.message_id
        )
        return None
    except Exception as e:
        print(f"Ошибка в upload_to_telegraph: {e}")
        if progress_message:
            await bot.edit_message_text(
                "❌ Произошла ошибка при загрузке в Telegraph.",
                chat_id=callback.from_user.id, 
                message_id=progress_message.message_id
            )
        return None


async def download_chapter(manga_id: str, chapter: dict, callback) -> bytes | None:
    """Download chapter as PDF."""
    from aiogram import Bot
    bot = Bot.get_current()
    
    url = f"{BASE_URL}/{manga_id}/chapter/{chapter['id']}"
    progress_message = None
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json().get('response')
        if not data or 'pages' not in data or 'list' not in data['pages']:
            await bot.send_message(
                callback.from_user.id,
                f"❌ Ошибка: нет данных о страницах для главы {chapter['ch']}."
            )
            return None

        pages, total_pages = data['pages']['list'], len(data['pages']['list'])
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
                print(f"Ошибка при скачивании/сжатии страницы {i}: {e}")

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
                f"❌ Ошибка: Глава {chapter['ch']} слишком большая даже после сжатия (> 50 МБ). Невозможно отправить."
            )
            return None

        await bot.delete_message(chat_id=callback.from_user.id, message_id=progress_message.message_id)
        return pdf_bytes

    except Exception as e:
        print(f"Ошибка в download_chapter: {e}")
        if progress_message:
            await bot.edit_message_text(
                "❌ Произошла ошибка при скачивании главы.",
                chat_id=callback.from_user.id, 
                message_id=progress_message.message_id
            )
        return None
