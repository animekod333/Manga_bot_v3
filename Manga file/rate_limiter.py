"""Rate limiting wrapper for API calls."""
import asyncio
import random
from functools import wraps
from typing import Callable
from aiogram.types import Message, CallbackQuery
import database
from vip_manager import check_vip_access


async def get_delay_for_user(user_id: int, is_premium: bool) -> int:
    """Get appropriate delay for user based on premium status.
    
    Args:
        user_id: User ID
        is_premium: Whether user has premium access
        
    Returns:
        Delay in seconds
    """
    if is_premium:
        # Premium: 10-30 seconds
        return random.randint(10, 30)
    else:
        # Regular: 60-120 seconds
        return random.randint(60, 120)


def rate_limit_check(func: Callable):
    """Decorator to check rate limits before executing function.
    
    This decorator checks if the user has exceeded their daily/monthly limits
    and enforces a delay between requests.
    """
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        # Get user_id from event
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        if not user_id:
            return await func(event, *args, **kwargs)
        
        # Check VIP status
        is_premium = check_vip_access(user_id)
        
        # Check rate limits
        can_proceed, message = await database.check_rate_limit(user_id, is_premium)
        
        if not can_proceed:
            # Send rate limit message
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                from aiogram import Bot
                bot = Bot.get_current()
                await bot.answer_callback_query(event.id, message, show_alert=True)
            return
        
        # Increment request count
        await database.increment_request_count(user_id)
        
        # Execute the function
        result = await func(event, *args, **kwargs)
        
        # Add delay for next request (optional, can be removed if too restrictive)
        # delay = await get_delay_for_user(user_id, is_premium)
        # await asyncio.sleep(delay)
        
        return result
    
    return wrapper


async def check_and_enforce_limit(user_id: int, is_premium: bool = False) -> tuple[bool, str]:
    """Check rate limit and return result.
    
    Args:
        user_id: User ID to check
        is_premium: Whether user has premium access
        
    Returns:
        Tuple of (can_proceed, error_message)
    """
    can_proceed, message = await database.check_rate_limit(user_id, is_premium)
    return can_proceed, message


async def increment_user_request(user_id: int) -> None:
    """Increment user's request counter.
    
    Args:
        user_id: User ID
    """
    await database.increment_request_count(user_id)
