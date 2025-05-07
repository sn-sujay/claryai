"""
Redis client for ClaryAI.
This module provides functionality to interact with Redis for asynchronous processing.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union
import redis
from redis.exceptions import RedisError

# Configure logging
logger = logging.getLogger("claryai.redis")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

class RedisClient:
    """
    Redis client for ClaryAI.
    
    This class provides methods to:
    1. Store and retrieve task results
    2. Manage task queues
    3. Implement caching for LLM responses
    """
    
    def __init__(self):
        """Initialize the Redis client."""
        self.redis = None
        self.connected = False
        try:
            self.redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
            self.redis.ping()  # Test connection
            self.connected = True
            logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        except RedisError as e:
            logger.warning(f"Failed to connect to Redis: {str(e)}")
            self.connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        return self.connected
    
    def store_task_result(self, task_id: str, result: Dict[str, Any], expiry: int = 3600) -> bool:
        """
        Store task result in Redis.
        
        Args:
            task_id: Task ID
            result: Task result
            expiry: Expiry time in seconds (default: 1 hour)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected:
            logger.warning("Not connected to Redis")
            return False
        
        try:
            key = f"task:{task_id}"
            self.redis.set(key, json.dumps(result), ex=expiry)
            logger.info(f"Stored task result for {task_id}")
            return True
        except RedisError as e:
            logger.error(f"Failed to store task result: {str(e)}")
            return False
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task result from Redis.
        
        Args:
            task_id: Task ID
            
        Returns:
            dict: Task result or None if not found
        """
        if not self.connected:
            logger.warning("Not connected to Redis")
            return None
        
        try:
            key = f"task:{task_id}"
            result = self.redis.get(key)
            if result:
                return json.loads(result)
            return None
        except RedisError as e:
            logger.error(f"Failed to get task result: {str(e)}")
            return None
    
    def cache_llm_response(self, prompt: str, response: str, expiry: int = 86400) -> bool:
        """
        Cache LLM response in Redis.
        
        Args:
            prompt: LLM prompt
            response: LLM response
            expiry: Expiry time in seconds (default: 24 hours)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected:
            logger.warning("Not connected to Redis")
            return False
        
        try:
            # Use hash of prompt as key to avoid storing large keys
            import hashlib
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
            key = f"llm:cache:{prompt_hash}"
            self.redis.set(key, response, ex=expiry)
            logger.info(f"Cached LLM response for prompt hash {prompt_hash}")
            return True
        except RedisError as e:
            logger.error(f"Failed to cache LLM response: {str(e)}")
            return False
    
    def get_cached_llm_response(self, prompt: str) -> Optional[str]:
        """
        Get cached LLM response from Redis.
        
        Args:
            prompt: LLM prompt
            
        Returns:
            str: Cached LLM response or None if not found
        """
        if not self.connected:
            logger.warning("Not connected to Redis")
            return None
        
        try:
            # Use hash of prompt as key
            import hashlib
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
            key = f"llm:cache:{prompt_hash}"
            return self.redis.get(key)
        except RedisError as e:
            logger.error(f"Failed to get cached LLM response: {str(e)}")
            return None
    
    def add_to_queue(self, queue_name: str, item: Dict[str, Any]) -> bool:
        """
        Add item to a queue.
        
        Args:
            queue_name: Queue name
            item: Item to add
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected:
            logger.warning("Not connected to Redis")
            return False
        
        try:
            key = f"queue:{queue_name}"
            self.redis.lpush(key, json.dumps(item))
            logger.info(f"Added item to queue {queue_name}")
            return True
        except RedisError as e:
            logger.error(f"Failed to add item to queue: {str(e)}")
            return False
    
    def get_from_queue(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """
        Get item from a queue.
        
        Args:
            queue_name: Queue name
            
        Returns:
            dict: Item from queue or None if queue is empty
        """
        if not self.connected:
            logger.warning("Not connected to Redis")
            return None
        
        try:
            key = f"queue:{queue_name}"
            item = self.redis.rpop(key)
            if item:
                return json.loads(item)
            return None
        except RedisError as e:
            logger.error(f"Failed to get item from queue: {str(e)}")
            return None
