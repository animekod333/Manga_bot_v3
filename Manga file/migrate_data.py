"""Utility to migrate data from JSON files to database."""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from config import FAVORITES_FILE, PREMIUM_USERS_FILE, USERS_FILE, SETTINGS_FILE, CACHE_FILE
import database


async def migrate_users():
    """Migrate users from users.json and premium_users.json."""
    print("📦 Migrating users...")
    
    # Migrate basic users
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            data = json.load(f)
            users = data.get('users', [])
            for user_id in users:
                await database.get_or_create_user(user_id, is_premium=False)
            print(f"  ✅ Migrated {len(users)} basic users")
    
    # Migrate premium users
    if os.path.exists(PREMIUM_USERS_FILE):
        with open(PREMIUM_USERS_FILE, 'r') as f:
            premium_data = json.load(f)
            for user_id_str, user_info in premium_data.items():
                user_id = int(user_id_str)
                await database.get_or_create_user(user_id, is_premium=True)
                await database.update_user_premium_status(user_id, True)
            print(f"  ✅ Migrated {len(premium_data)} premium users")


async def migrate_settings():
    """Migrate user settings from settings file."""
    print("⚙️ Migrating user settings...")
    
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            settings_data = json.load(f)
            for user_id_str, settings in settings_data.items():
                user_id = int(user_id_str)
                await database.save_user_settings(user_id, settings)
            print(f"  ✅ Migrated settings for {len(settings_data)} users")


async def migrate_cache():
    """Migrate cached chapters from cache_data.json."""
    print("💾 Migrating cached chapters...")
    
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
            files = cache_data.get('files', {})
            
            migrated = 0
            for key, value in files.items():
                try:
                    # Parse key: manga_id_chapter_num_format
                    parts = key.split('_')
                    if len(parts) >= 3:
                        manga_id = int(parts[0])
                        chapter_num = float(parts[1])
                        format_type = parts[2] if len(parts) > 2 else 'pdf'
                        
                        # Get stored data
                        if isinstance(value, dict):
                            stored_data = value.get('data')
                        else:
                            stored_data = value
                        
                        # Create chapter entry if it doesn't exist
                        chapter_data = {
                            'id': key,
                            'ch': chapter_num
                        }
                        
                        if format_type == 'pdf':
                            await database.save_chapter_to_db(
                                manga_id, chapter_data, file_id=stored_data
                            )
                        elif format_type == 'telegraph':
                            await database.save_chapter_to_db(
                                manga_id, chapter_data, telegraph_url=stored_data
                            )
                        
                        migrated += 1
                        
                except Exception as e:
                    print(f"  ⚠️ Failed to migrate cache key {key}: {e}")
            
            print(f"  ✅ Migrated {migrated} cached chapters")


async def migrate_all():
    """Run all migrations."""
    print("\n" + "="*50)
    print("🔄 Starting data migration to database")
    print("="*50 + "\n")
    
    # Initialize database first
    await database.init_database()
    
    # Run migrations
    await migrate_users()
    await migrate_settings()
    await migrate_cache()
    
    # Show stats
    stats = await database.get_cache_stats()
    
    print("\n" + "="*50)
    print("✅ Migration completed!")
    print("="*50)
    print(f"📊 Database Statistics:")
    print(f"  - Manga entries: {stats['manga_count']}")
    print(f"  - Chapters: {stats['chapters_count']}")
    print(f"  - Cached files: {stats['cached_files']}")
    print(f"  - Search cache entries: {stats['search_cache_entries']}")
    print("="*50 + "\n")


if __name__ == "__main__":
    asyncio.run(migrate_all())
