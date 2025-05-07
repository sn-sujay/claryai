"""
Distributed processing module for ClaryAI.

This module provides functions for distributed processing of documents,
including task distribution, load balancing, and fault tolerance.
"""

import os
import time
import logging
import json
import uuid
import socket
import threading
import multiprocessing
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 30  # 30 seconds
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 5  # 5 seconds
DEFAULT_MAX_WORKERS = multiprocessing.cpu_count()
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MB


class TaskManager:
    """Task manager for distributed processing."""
    
    def __init__(self, redis_client=None):
        """Initialize the task manager.
        
        Args:
            redis_client: Redis client for task distribution
        """
        self.redis_client = redis_client
        self.local_tasks: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
    
    def create_task(self, task_type: str, params: Dict[str, Any]) -> str:
        """Create a new task.
        
        Args:
            task_type: Type of task
            params: Task parameters
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "type": task_type,
            "params": params,
            "status": "pending",
            "created_at": time.time(),
            "updated_at": time.time(),
            "result": None,
            "error": None
        }
        
        # Store task in Redis if available, otherwise store locally
        if self.redis_client and self.redis_client.is_connected():
            self.redis_client.store_task(task_id, task)
        else:
            with self.lock:
                self.local_tasks[task_id] = task
        
        logger.info(f"Created task {task_id} of type {task_type}")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task or None if not found
        """
        # Try to get task from Redis if available, otherwise get from local storage
        if self.redis_client and self.redis_client.is_connected():
            task = self.redis_client.get_task(task_id)
        else:
            with self.lock:
                task = self.local_tasks.get(task_id)
        
        return task
    
    def update_task(self, task_id: str, status: str, result: Any = None, error: str = None) -> None:
        """Update a task.
        
        Args:
            task_id: Task ID
            status: Task status
            result: Task result
            error: Task error
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return
        
        task["status"] = status
        task["updated_at"] = time.time()
        
        if result is not None:
            task["result"] = result
        
        if error is not None:
            task["error"] = error
        
        # Store updated task in Redis if available, otherwise store locally
        if self.redis_client and self.redis_client.is_connected():
            self.redis_client.store_task(task_id, task)
        else:
            with self.lock:
                self.local_tasks[task_id] = task
        
        logger.info(f"Updated task {task_id} with status {status}")
    
    def get_pending_tasks(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending tasks.
        
        Args:
            task_type: Type of task to filter by
            
        Returns:
            List of pending tasks
        """
        # Get tasks from Redis if available, otherwise get from local storage
        if self.redis_client and self.redis_client.is_connected():
            tasks = self.redis_client.get_tasks_by_status("pending")
        else:
            with self.lock:
                tasks = [task for task in self.local_tasks.values() if task["status"] == "pending"]
        
        # Filter by task type if specified
        if task_type:
            tasks = [task for task in tasks if task["type"] == task_type]
        
        return tasks
    
    def process_task(self, task_id: str, processor: Callable) -> None:
        """Process a task.
        
        Args:
            task_id: Task ID
            processor: Task processor function
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return
        
        # Update task status to processing
        self.update_task(task_id, "processing")
        
        try:
            # Process task
            result = processor(task["params"])
            
            # Update task status to completed
            self.update_task(task_id, "completed", result=result)
        except Exception as e:
            # Update task status to failed
            self.update_task(task_id, "failed", error=str(e))
            logger.error(f"Task {task_id} failed: {str(e)}")


class WorkerPool:
    """Worker pool for distributed processing."""
    
    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS, task_manager: Optional[TaskManager] = None):
        """Initialize the worker pool.
        
        Args:
            max_workers: Maximum number of worker processes
            task_manager: Task manager for task distribution
        """
        self.max_workers = max_workers
        self.task_manager = task_manager or TaskManager()
        self.workers: List[multiprocessing.Process] = []
        self.stop_event = multiprocessing.Event()
        self.task_processors: Dict[str, Callable] = {}
    
    def register_task_processor(self, task_type: str, processor: Callable) -> None:
        """Register a task processor.
        
        Args:
            task_type: Type of task
            processor: Task processor function
        """
        self.task_processors[task_type] = processor
        logger.info(f"Registered processor for task type {task_type}")
    
    def worker_process(self, worker_id: int) -> None:
        """Worker process function.
        
        Args:
            worker_id: Worker ID
        """
        logger.info(f"Worker {worker_id} started")
        
        while not self.stop_event.is_set():
            # Get pending tasks
            pending_tasks = []
            for task_type in self.task_processors:
                pending_tasks.extend(self.task_manager.get_pending_tasks(task_type))
            
            if not pending_tasks:
                # No pending tasks, sleep for a while
                time.sleep(1)
                continue
            
            # Process the first pending task
            task = pending_tasks[0]
            task_id = task["id"]
            task_type = task["type"]
            
            if task_type in self.task_processors:
                processor = self.task_processors[task_type]
                self.task_manager.process_task(task_id, processor)
            else:
                logger.warning(f"No processor registered for task type {task_type}")
        
        logger.info(f"Worker {worker_id} stopped")
    
    def start(self) -> None:
        """Start the worker pool."""
        # Create and start worker processes
        for i in range(self.max_workers):
            worker = multiprocessing.Process(target=self.worker_process, args=(i,))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started worker pool with {self.max_workers} workers")
    
    def stop(self) -> None:
        """Stop the worker pool."""
        # Set stop event
        self.stop_event.set()
        
        # Wait for workers to stop
        for worker in self.workers:
            worker.join(timeout=5)
            if worker.is_alive():
                worker.terminate()
        
        # Clear workers
        self.workers.clear()
        
        logger.info("Stopped worker pool")


def distributed_task(task_type: str, task_manager: Optional[TaskManager] = None) -> Callable:
    """Decorator for distributed tasks.
    
    Args:
        task_type: Type of task
        task_manager: Task manager for task distribution
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> str:
            # Create task manager if not provided
            nonlocal task_manager
            if not task_manager:
                task_manager = TaskManager()
            
            # Create task
            params = {
                "args": args,
                "kwargs": kwargs
            }
            task_id = task_manager.create_task(task_type, params)
            
            return task_id
        return wrapper
    return decorator


def retry(max_retries: int = DEFAULT_RETRY_COUNT, delay: int = DEFAULT_RETRY_DELAY) -> Callable:
    """Decorator for retrying functions.
    
    Args:
        max_retries: Maximum number of retries
        delay: Delay between retries in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retries = 0
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries > max_retries:
                        raise
                    logger.warning(f"Retry {retries}/{max_retries} for {func.__name__}: {str(e)}")
                    time.sleep(delay)
        return wrapper
    return decorator
