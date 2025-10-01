import multiprocessing as mp
import threading
import time
import logging
from typing import Dict, Any, Optional, Callable
from concurrent.futures import ProcessPoolExecutor, Future, TimeoutError
from .compute import compute_positions_init, compute_positions

logger = logging.getLogger(__name__)


class SpicePool:
    """
    Bounded process pool for SPICE calculations with kernel preloading.

    Each worker process loads SPICE kernels on initialization and reuses
    them for multiple calculations, avoiding expensive reload overhead.
    """

    def __init__(self, size: int, kernels_dir: str, bundle: str, timeout: float = 30.0):
        """
        Initialize the SPICE worker pool.

        Args:
            size: Number of worker processes
            kernels_dir: Directory containing SPICE kernels
            bundle: Kernel bundle name
            timeout: Default timeout for calculations in seconds
        """
        self.size = size
        self.kernels_dir = kernels_dir
        self.bundle = bundle
        self.timeout = timeout
        self.queue_depth = 0
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self._lock = threading.Lock()
        self._pool: Optional[ProcessPoolExecutor] = None
        self._initialized = False

        logger.info(f"Creating SPICE pool with {size} workers for bundle {bundle}")

    def initialize(self) -> bool:
        """
        Initialize the process pool and preload kernels.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            logger.warning("SPICE pool already initialized")
            return True

        try:
            # Create process pool with initializer
            self._pool = ProcessPoolExecutor(
                max_workers=self.size,
                initializer=compute_positions_init,
                initargs=(self.kernels_dir, self.bundle)
            )

            # Test that workers are properly initialized by submitting a dummy task
            test_future = self._pool.submit(_test_worker_initialization)
            test_result = test_future.result(timeout=10.0)

            if not test_result:
                raise RuntimeError("Worker initialization test failed")

            self._initialized = True
            logger.info(f"SPICE pool initialized successfully with {self.size} workers")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize SPICE pool: {e}")
            self.shutdown()
            return False

    def submit(self, calculation_args: Dict[str, Any], timeout: Optional[float] = None) -> Future:
        """
        Submit a calculation task to the pool.

        Args:
            calculation_args: Arguments for compute_positions function
            timeout: Timeout for this specific calculation

        Returns:
            Future object for the calculation

        Raises:
            RuntimeError: If pool is not initialized
        """
        if not self._initialized or self._pool is None:
            raise RuntimeError("SPICE pool not initialized. Call initialize() first.")

        with self._lock:
            self.queue_depth += 1
            self.total_requests += 1

        def done_callback(future: Future):
            with self._lock:
                self.queue_depth -= 1
                if future.exception() is None:
                    self.successful_requests += 1
                else:
                    self.failed_requests += 1

        calc_timeout = timeout or self.timeout
        future = self._pool.submit(compute_positions, **calculation_args)
        future.add_done_callback(done_callback)

        logger.debug(f"Submitted calculation task, queue depth: {self.queue_depth}")
        return future

    def calculate_sync(self, calculation_args: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Submit calculation and wait for result synchronously.

        Args:
            calculation_args: Arguments for compute_positions function
            timeout: Timeout for the calculation

        Returns:
            Calculation result

        Raises:
            TimeoutError: If calculation times out
            Exception: Any error from the calculation
        """
        future = self.submit(calculation_args, timeout)
        calc_timeout = timeout or self.timeout

        try:
            return future.result(timeout=calc_timeout)
        except TimeoutError:
            logger.error(f"Calculation timed out after {calc_timeout}s")
            future.cancel()  # Attempt to cancel if still pending
            raise
        except Exception as e:
            logger.error(f"Calculation failed: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get pool statistics.

        Returns:
            Dict with pool statistics
        """
        with self._lock:
            return {
                "size": self.size,
                "queue_depth": self.queue_depth,
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "success_rate": (
                    self.successful_requests / max(1, self.total_requests)
                ) * 100,
                "initialized": self._initialized,
                "bundle": self.bundle,
                "kernels_dir": self.kernels_dir
            }

    def is_healthy(self) -> bool:
        """
        Check if the pool is healthy and ready for work.

        Returns:
            True if pool is healthy, False otherwise
        """
        if not self._initialized or self._pool is None:
            return False

        # Could add additional health checks here
        # e.g., test calculation, check worker responsiveness
        return True

    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> None:
        """
        Shutdown the process pool.

        Args:
            wait: Whether to wait for pending tasks to complete
            timeout: Maximum time to wait for shutdown
        """
        if self._pool is not None:
            logger.info("Shutting down SPICE pool")
            try:
                self._pool.shutdown(wait=wait, timeout=timeout)
            except Exception as e:
                logger.error(f"Error during pool shutdown: {e}")
            finally:
                self._pool = None
                self._initialized = False

    def __enter__(self):
        """Context manager entry."""
        if not self.initialize():
            raise RuntimeError("Failed to initialize SPICE pool")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.shutdown(wait=False)


def _test_worker_initialization() -> bool:
    """
    Test function to verify worker initialization.

    Returns:
        True if worker is properly initialized
    """
    # This will be called in each worker process to verify
    # that SPICE kernels are loaded and ready
    try:
        from .compute import KERNELS_LOADED
        return KERNELS_LOADED
    except ImportError:
        return False


class PoolManager:
    """
    Singleton manager for SPICE pools.

    Manages the lifecycle of SPICE pools and provides a single access point.
    """

    _instance: Optional['PoolManager'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'PoolManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._pools = {}
                    cls._instance._initialized = False
        return cls._instance

    def initialize_pool(self, pool_id: str, size: int, kernels_dir: str, bundle: str) -> bool:
        """
        Initialize a named pool.

        Args:
            pool_id: Unique identifier for the pool
            size: Number of worker processes
            kernels_dir: Directory containing SPICE kernels
            bundle: Kernel bundle name

        Returns:
            True if initialization successful
        """
        if pool_id in self._pools:
            logger.warning(f"Pool {pool_id} already exists")
            return self._pools[pool_id].is_healthy()

        pool = SpicePool(size, kernels_dir, bundle)
        if pool.initialize():
            self._pools[pool_id] = pool
            logger.info(f"Initialized pool {pool_id}")
            return True
        else:
            logger.error(f"Failed to initialize pool {pool_id}")
            return False

    def get_pool(self, pool_id: str = "default") -> Optional[SpicePool]:
        """
        Get a pool by ID.

        Args:
            pool_id: Pool identifier

        Returns:
            SpicePool instance or None if not found
        """
        return self._pools.get(pool_id)

    def shutdown_all(self) -> None:
        """Shutdown all managed pools."""
        logger.info("Shutting down all SPICE pools")
        for pool_id, pool in self._pools.items():
            try:
                pool.shutdown()
                logger.info(f"Shutdown pool {pool_id}")
            except Exception as e:
                logger.error(f"Error shutting down pool {pool_id}: {e}")
        self._pools.clear()

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all pools."""
        return {pool_id: pool.get_stats() for pool_id, pool in self._pools.items()}


# Global pool manager instance
pool_manager = PoolManager()