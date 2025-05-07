"""
Performance optimization module for ClaryAI.

This module provides functions for optimizing the performance of ClaryAI,
including caching, parallel processing, and memory management.
"""

import os
import time
import logging
import hashlib
import json
import threading
import multiprocessing
from functools import lru_cache
from typing import Dict, Any, List, Optional, Callable, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CACHE_SIZE = 1024
DEFAULT_CACHE_TTL = 3600  # 1 hour
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MB
DEFAULT_MAX_WORKERS = multiprocessing.cpu_count()


class MemoryCache:
    """In-memory cache with TTL."""
    
    def __init__(self, max_size: int = DEFAULT_CACHE_SIZE, ttl: int = DEFAULT_CACHE_TTL):
        """Initialize the cache.
        
        Args:
            max_size: Maximum number of items in the cache
            ttl: Time-to-live in seconds
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get an item from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        with self.lock:
            if key not in self.cache:
                return None
            
            item = self.cache[key]
            if time.time() > item["expires"]:
                del self.cache[key]
                return None
            
            return item["value"]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set an item in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (overrides default)
        """
        with self.lock:
            # Evict oldest items if cache is full
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.cache.items(), key=lambda x: x[1]["expires"])[0]
                del self.cache[oldest_key]
            
            # Set new item
            self.cache[key] = {
                "value": value,
                "expires": time.time() + (ttl or self.ttl)
            }
    
    def delete(self, key: str) -> None:
        """Delete an item from the cache.
        
        Args:
            key: Cache key
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
    
    def clear(self) -> None:
        """Clear the cache."""
        with self.lock:
            self.cache.clear()


# Global cache instance
memory_cache = MemoryCache()


def cache_key(data: Any) -> str:
    """Generate a cache key for the given data.
    
    Args:
        data: Data to generate a key for
        
    Returns:
        Cache key as a string
    """
    if isinstance(data, str):
        serialized = data.encode('utf-8')
    else:
        try:
            serialized = json.dumps(data, sort_keys=True).encode('utf-8')
        except (TypeError, ValueError):
            serialized = str(data).encode('utf-8')
    
    return hashlib.md5(serialized).hexdigest()


def cached(ttl: Optional[int] = None) -> Callable:
    """Decorator for caching function results.
    
    Args:
        ttl: Time-to-live in seconds (overrides default)
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            key_data = {
                "func": func.__name__,
                "args": args,
                "kwargs": kwargs
            }
            key = cache_key(key_data)
            
            # Check cache
            cached_result = memory_cache.get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Call function
            result = func(*args, **kwargs)
            
            # Cache result
            memory_cache.set(key, result, ttl)
            logger.debug(f"Cached result for {func.__name__}")
            
            return result
        return wrapper
    return decorator


def parallel_map(func: Callable, items: List[Any], max_workers: int = DEFAULT_MAX_WORKERS) -> List[Any]:
    """Apply a function to items in parallel.
    
    Args:
        func: Function to apply
        items: List of items to process
        max_workers: Maximum number of worker processes
        
    Returns:
        List of results
    """
    with multiprocessing.Pool(processes=max_workers) as pool:
        results = pool.map(func, items)
    return results


def chunked_read(file_path: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> List[bytes]:
    """Read a file in chunks.
    
    Args:
        file_path: Path to the file
        chunk_size: Size of each chunk in bytes
        
    Returns:
        List of chunks
    """
    chunks = []
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
    return chunks


def optimize_memory_usage(func: Callable) -> Callable:
    """Decorator for optimizing memory usage.
    
    Args:
        func: Function to optimize
        
    Returns:
        Decorated function
    """
    def wrapper(*args, **kwargs) -> Any:
        # Get initial memory usage
        import psutil
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Call function
        result = func(*args, **kwargs)
        
        # Force garbage collection
        import gc
        gc.collect()
        
        # Log memory usage
        final_memory = process.memory_info().rss
        memory_diff = final_memory - initial_memory
        logger.debug(f"Memory usage for {func.__name__}: {memory_diff / 1024 / 1024:.2f} MB")
        
        return result
    return wrapper


def timed(func: Callable) -> Callable:
    """Decorator for timing function execution.
    
    Args:
        func: Function to time
        
    Returns:
        Decorated function
    """
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        logger.debug(f"Execution time for {func.__name__}: {duration:.2f} seconds")
        return result
    return wrapper


def adaptive_chunk_size(file_size: int) -> int:
    """Calculate an adaptive chunk size based on file size.
    
    Args:
        file_size: Size of the file in bytes
        
    Returns:
        Chunk size in bytes
    """
    # For small files, use a smaller chunk size
    if file_size < 1024 * 1024:  # < 1 MB
        return 64 * 1024  # 64 KB
    
    # For medium files, use a medium chunk size
    if file_size < 10 * 1024 * 1024:  # < 10 MB
        return 256 * 1024  # 256 KB
    
    # For large files, use a large chunk size
    if file_size < 100 * 1024 * 1024:  # < 100 MB
        return 1024 * 1024  # 1 MB
    
    # For very large files, use a very large chunk size
    return 4 * 1024 * 1024  # 4 MB


def optimize_document_processing(document_processor: Callable) -> Callable:
    """Optimize document processing with caching and timing.
    
    Args:
        document_processor: Document processing function
        
    Returns:
        Optimized document processing function
    """
    @timed
    @cached()
    def optimized_processor(*args, **kwargs) -> Any:
        return document_processor(*args, **kwargs)
    
    return optimized_processor


def optimize_query_processing(query_processor: Callable) -> Callable:
    """Optimize query processing with caching and timing.
    
    Args:
        query_processor: Query processing function
        
    Returns:
        Optimized query processing function
    """
    @timed
    @cached()
    def optimized_processor(*args, **kwargs) -> Any:
        return query_processor(*args, **kwargs)
    
    return optimized_processor


def optimize_llm_processing(llm_processor: Callable) -> Callable:
    """Optimize LLM processing with caching and timing.
    
    Args:
        llm_processor: LLM processing function
        
    Returns:
        Optimized LLM processing function
    """
    @timed
    @cached(ttl=86400)  # Cache for 24 hours
    def optimized_processor(*args, **kwargs) -> Any:
        return llm_processor(*args, **kwargs)
    
    return optimized_processor
