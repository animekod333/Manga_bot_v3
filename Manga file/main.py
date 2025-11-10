"""Main entry point for the manga bot."""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import TOKEN
from handlers import register_all_handlers
import database
from performance_monitor import periodic_cleanup


# Create bot instance
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


async def main():
    """Main function to start the bot."""
    print("Бот запущен...")
    
    # Initialize database
    await database.init_database()
    
    # Make bot available to handlers via dp workflow_data
    dp.workflow_data.update({"bot": bot})
    
    # Register all handlers
    register_all_handlers(dp)
    
    # Start periodic cleanup task
    asyncio.create_task(periodic_cleanup(interval_hours=24))
    
    # Start polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
