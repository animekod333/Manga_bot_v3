"""Telegram channel storage manager for PDF files."""
from typing import Optional
from io import BytesIO
from aiogram import Bot
from aiogram.types import BufferedInputFile
from config import STORAGE_CHANNEL_ID
import database


async def upload_chapter_to_channel(bot: Bot, manga_id: int, chapter_number: float, 
                                    pdf_bytes: bytes, filename: str) -> Optional[str]:
    """Upload chapter PDF to storage channel and save file_id.
    
    Args:
        bot: Bot instance
        manga_id: Manga ID
        chapter_number: Chapter number
        pdf_bytes: PDF file bytes
        filename: File name
        
    Returns:
        file_id if successful, None otherwise
    """
    try:
        # Create BufferedInputFile from bytes
        document = BufferedInputFile(pdf_bytes, filename=filename)
        
        # Send to storage channel
        message = await bot.send_document(
            chat_id=STORAGE_CHANNEL_ID,
            document=document,
            caption=f"Manga: {manga_id}, Chapter: {chapter_number}"
        )
        
        # Get file_id
        file_id = message.document.file_id
        
        # Save to database
        await database.update_chapter_file_id(manga_id, chapter_number, file_id)
        
        print(f"✅ Uploaded chapter {chapter_number} of manga {manga_id} to storage channel")
        return file_id
        
    except Exception as e:
        print(f"❌ Failed to upload chapter to storage channel: {e}")
        return None


async def get_chapter_from_channel(manga_id: int, chapter_number: float) -> Optional[str]:
    """Get chapter file_id from database cache.
    
    Args:
        manga_id: Manga ID
        chapter_number: Chapter number
        
    Returns:
        file_id if cached, None otherwise
    """
    return await database.get_chapter_file_id(manga_id, chapter_number)


async def forward_chapter_to_user(bot: Bot, user_id: int, manga_id: int, 
                                  chapter_number: float) -> bool:
    """Forward cached chapter from storage channel to user.
    
    Args:
        bot: Bot instance
        user_id: User ID to send to
        manga_id: Manga ID
        chapter_number: Chapter number
        
    Returns:
        True if successful, False otherwise
    """
    try:
        file_id = await get_chapter_from_channel(manga_id, chapter_number)
        
        if not file_id:
            return False
        
        # Send document by file_id
        await bot.send_document(
            chat_id=user_id,
            document=file_id,
            caption=f"📖 Глава {chapter_number} (из кэша)"
        )
        
        print(f"✅ Forwarded cached chapter {chapter_number} to user {user_id}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to forward chapter from cache: {e}")
        return False


async def download_and_cache_chapter(bot: Bot, user_id: int, manga_id: int, 
                                    chapter_number: float, chapter_data: dict) -> bool:
    """Download chapter, upload to storage, and send to user.
    
    This is the full flow when chapter is not cached:
    1. Download chapter from API
    2. Upload to storage channel
    3. Send to user
    
    Args:
        bot: Bot instance
        user_id: User ID
        manga_id: Manga ID
        chapter_number: Chapter number
        chapter_data: Chapter metadata
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Import here to avoid circular dependency
        from api_client_enhanced import download_chapter
        
        # Create a mock callback object for download_chapter
        class MockCallback:
            def __init__(self, user_id):
                self.from_user = type('obj', (object,), {'id': user_id})
                self.data = f"download_{manga_id}_{chapter_number}"
        
        mock_callback = MockCallback(user_id)
        
        # Download chapter
        pdf_bytes = await download_chapter(str(manga_id), chapter_data, mock_callback)
        
        if not pdf_bytes:
            return False
        
        # Generate filename
        filename = f"manga_{manga_id}_chapter_{chapter_number}.pdf"
        
        # Upload to storage channel
        file_id = await upload_chapter_to_channel(
            bot, manga_id, chapter_number, pdf_bytes, filename
        )
        
        if not file_id:
            # Even if upload to channel fails, still send to user
            document = BufferedInputFile(pdf_bytes, filename=filename)
            await bot.send_document(
                chat_id=user_id,
                document=document,
                caption=f"📖 Глава {chapter_number}"
            )
            return True
        
        # Send to user using file_id
        await bot.send_document(
            chat_id=user_id,
            document=file_id,
            caption=f"📖 Глава {chapter_number}"
        )
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to download and cache chapter: {e}")
        return False
