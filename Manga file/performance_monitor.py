"""Performance monitoring and logging utilities."""
import time
import asyncio
from datetime import datetime
from functools import wraps
from typing import Callable
import database


class PerformanceMonitor:
    """Monitor performance metrics for the bot."""
    
    def __init__(self):
        self.api_calls = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.start_time = time.time()
    
    def log_api_call(self):
        """Log an API call."""
        self.api_calls += 1
    
    def log_cache_hit(self):
        """Log a cache hit."""
        self.cache_hits += 1
    
    def log_cache_miss(self):
        """Log a cache miss."""
        self.cache_misses += 1
    
    def get_stats(self) -> dict:
        """Get current performance statistics."""
        runtime = time.time() - self.start_time
        cache_hit_rate = 0
        if self.cache_hits + self.cache_misses > 0:
            cache_hit_rate = (self.cache_hits / (self.cache_hits + self.cache_misses)) * 100
        
        api_per_hour = (self.api_calls / runtime) * 3600 if runtime > 0 else 0
        
        return {
            'runtime_hours': runtime / 3600,
            'api_calls': self.api_calls,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': cache_hit_rate,
            'api_calls_per_hour': api_per_hour
        }
    
    def print_stats(self):
        """Print performance statistics."""
        stats = self.get_stats()
        print("\n" + "="*50)
        print("📊 Performance Statistics")
        print("="*50)
        print(f"⏱️  Runtime: {stats['runtime_hours']:.2f} hours")
        print(f"🌐 API Calls: {stats['api_calls']}")
        print(f"✅ Cache Hits: {stats['cache_hits']}")
        print(f"❌ Cache Misses: {stats['cache_misses']}")
        print(f"📈 Cache Hit Rate: {stats['cache_hit_rate']:.1f}%")
        print(f"📡 API Calls/Hour: {stats['api_calls_per_hour']:.1f}")
        print("="*50 + "\n")


# Global performance monitor instance
monitor = PerformanceMonitor()


def track_performance(func: Callable):
    """Decorator to track function performance."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start
        
        if duration > 2.0:
            print(f"⚠️ Slow function: {func.__name__} took {duration:.2f}s")
        
        return result
    return wrapper


async def log_request_to_db(user_id: int, request_type: str, cached: bool = False):
    """Log request to database for analytics.
    
    Args:
        user_id: User ID
        request_type: Type of request (search, manga_info, chapter_download)
        cached: Whether the request was served from cache
    """
    # This could be expanded to log to a requests table for detailed analytics
    if cached:
        monitor.log_cache_hit()
    else:
        monitor.log_cache_miss()
        monitor.log_api_call()


async def get_popular_manga(limit: int = 10) -> list:
    """Get most requested manga from cache.
    
    Args:
        limit: Number of manga to return
        
    Returns:
        List of (manga_id, request_count) tuples
    """
    # This would require a request_log table to track
    # For now, return empty list
    # TODO: Implement request logging table
    return []


async def cleanup_old_cache():
    """Clean up expired cache entries."""
    try:
        await database.cleanup_expired_cache()
        print("✅ Cleaned up expired cache entries")
    except Exception as e:
        print(f"❌ Error cleaning up cache: {e}")


async def performance_report() -> str:
    """Generate a performance report.
    
    Returns:
        Formatted performance report string
    """
    stats = monitor.get_stats()
    db_stats = await database.get_cache_stats()
    
    report = f"""
📊 <b>Performance Report</b>

⏱️ <b>Runtime:</b> {stats['runtime_hours']:.2f} hours

🌐 <b>API Usage:</b>
  • Total API Calls: {stats['api_calls']}
  • API Calls/Hour: {stats['api_calls_per_hour']:.1f}

💾 <b>Cache Performance:</b>
  • Cache Hits: {stats['cache_hits']}
  • Cache Misses: {stats['cache_misses']}
  • Hit Rate: {stats['cache_hit_rate']:.1f}%

📚 <b>Database:</b>
  • Manga Cached: {db_stats['manga_count']}
  • Chapters Cached: {db_stats['chapters_count']}
  • Files Ready: {db_stats['cached_files']}
  • Search Queries: {db_stats['search_cache_entries']}

✅ <b>Goal Status:</b>
  • API Reduction: {"✅" if stats['api_calls_per_hour'] < 50 else "⚠️"} {100 - (stats['api_calls_per_hour'] / 50) * 100:.0f}%
  • Cache Hit Rate: {"✅" if stats['cache_hit_rate'] > 80 else "⚠️"} {stats['cache_hit_rate']:.1f}%
"""
    return report


async def periodic_cleanup(interval_hours: int = 24):
    """Periodically clean up expired cache.
    
    Args:
        interval_hours: Hours between cleanups
    """
    while True:
        await asyncio.sleep(interval_hours * 3600)
        await cleanup_old_cache()
        monitor.print_stats()


# Export functions
__all__ = [
    'monitor',
    'track_performance',
    'log_request_to_db',
    'get_popular_manga',
    'cleanup_old_cache',
    'performance_report',
    'periodic_cleanup'
]
