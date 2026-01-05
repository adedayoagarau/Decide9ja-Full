"""
Async Helper Utilities for Decide9ja.

Provides safe ways to call async functions from synchronous code,
handling the case where an event loop may already be running.
"""

import asyncio
import functools
from typing import Callable, Any, TypeVar, Coroutine
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Thread pool for running async code in sync context
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="async_helper_")


def run_async_safely(coro: Coroutine[Any, Any, T]) -> T:
    """
    Safely run an async coroutine from synchronous code.

    Handles the case where an event loop may already be running
    (e.g., inside a scheduler or web framework).

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine

    Example:
        result = run_async_safely(some_async_function(arg1, arg2))
    """
    try:
        # Try to get the running loop
        loop = asyncio.get_running_loop()

        # If we're here, there's already a running loop
        # We need to run in a new thread to avoid blocking
        logger.debug("Event loop already running, using thread pool")

        def run_in_new_loop():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        future = _executor.submit(run_in_new_loop)
        return future.result(timeout=300)  # 5 minute timeout

    except RuntimeError:
        # No running event loop - we can use asyncio.run() safely
        return asyncio.run(coro)


def async_to_sync(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    """
    Decorator to convert an async function to a synchronous function.

    The decorated function can be called from synchronous code and will
    handle event loop management automatically.

    Example:
        @async_to_sync
        async def fetch_data(url: str) -> dict:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.json()

        # Can now be called synchronously
        data = fetch_data("https://api.example.com/data")
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        return run_async_safely(func(*args, **kwargs))
    return wrapper


def run_async_with_fallback(
    coro: Coroutine[Any, Any, T],
    fallback_value: T,
    fallback_func: Callable[[], T] = None,
    log_error: bool = True
) -> T:
    """
    Run an async coroutine with a fallback value/function if it fails.

    Args:
        coro: The coroutine to run
        fallback_value: Value to return if coroutine fails
        fallback_func: Optional function to call for fallback (takes precedence over fallback_value)
        log_error: Whether to log errors

    Returns:
        The result of the coroutine, or the fallback value/result

    Example:
        result = run_async_with_fallback(
            fetch_data_async(),
            fallback_value={},
            fallback_func=lambda: fetch_data_sync()
        )
    """
    try:
        return run_async_safely(coro)
    except Exception as e:
        if log_error:
            logger.warning(f"Async operation failed, using fallback: {e}")

        if fallback_func is not None:
            try:
                return fallback_func()
            except Exception as fallback_error:
                if log_error:
                    logger.error(f"Fallback function also failed: {fallback_error}")
                return fallback_value

        return fallback_value


class AsyncBatcher:
    """
    Batch multiple async operations for efficient execution.

    Example:
        batcher = AsyncBatcher(max_concurrent=5)

        async def process_item(item):
            return await some_async_operation(item)

        results = batcher.run_batch(items, process_item)
    """

    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent

    async def _run_with_semaphore(self, coro: Coroutine) -> Any:
        """Run a coroutine with semaphore limiting."""
        async with self.semaphore:
            return await coro

    async def _run_batch_async(
        self,
        items: list,
        async_func: Callable[[Any], Coroutine],
        return_exceptions: bool = True
    ) -> list:
        """Run batch of async operations."""
        tasks = [
            self._run_with_semaphore(async_func(item))
            for item in items
        ]
        return await asyncio.gather(*tasks, return_exceptions=return_exceptions)

    def run_batch(
        self,
        items: list,
        async_func: Callable[[Any], Coroutine],
        return_exceptions: bool = True
    ) -> list:
        """
        Run a batch of async operations synchronously.

        Args:
            items: List of items to process
            async_func: Async function to apply to each item
            return_exceptions: If True, exceptions are returned as results

        Returns:
            List of results (or exceptions if return_exceptions=True)
        """
        return run_async_safely(
            self._run_batch_async(items, async_func, return_exceptions)
        )


# Cleanup function for graceful shutdown
def cleanup():
    """Cleanup thread pool on shutdown."""
    _executor.shutdown(wait=False)


# Register cleanup
import atexit
atexit.register(cleanup)
