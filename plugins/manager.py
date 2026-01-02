"""
Model Manager for the SoundBox plugin system.

Manages model lifecycle including loading, unloading, and GPU memory management.
Implements TTL-based auto-unloading and LRU eviction for memory optimization.
"""

import gc
import os
import time
import threading
import subprocess
from typing import Dict, Optional, Any, List
from dataclasses import dataclass

from .base import (
    AudioModel,
    ModelCapability,
    ModelStatus,
    GenerationResult,
    ModelLoadError,
    GPUMemoryError,
)
from .registry import ModelRegistry


@dataclass
class LoadedModel:
    """Tracks a loaded model instance."""
    instance: AudioModel
    model_id: str
    loaded_at: float
    last_used: float
    use_count: int = 0


class ModelManager:
    """
    Manages model lifecycle with GPU memory awareness.

    Features:
    - Hot-swapping models without restart
    - Automatic unloading of idle models (TTL-based)
    - Memory-aware loading (waits for available space)
    - Graceful fallback when model unavailable
    - Thread-safe operation

    Usage:
        manager = ModelManager()

        # Get model (loads if needed)
        model = manager.get_model("musicgen-small")
        if model:
            result = model.generate("ambient music", 10.0, "/tmp/out.wav")

        # Or get any model with a capability
        model = manager.get_model_for_capability(ModelCapability.MUSIC)
    """

    def __init__(
        self,
        min_free_memory_gb: float = 2.0,
        idle_timeout_seconds: float = 300.0,
        max_loaded_models: int = 2,
        cleanup_interval_seconds: float = 30.0,
    ):
        """
        Initialize the model manager.

        Args:
            min_free_memory_gb: Minimum free GPU memory to maintain
            idle_timeout_seconds: Time after which idle models are unloaded
            max_loaded_models: Maximum number of models to keep loaded
            cleanup_interval_seconds: How often to check for idle models
        """
        self.min_free_memory_gb = min_free_memory_gb
        self.idle_timeout_seconds = idle_timeout_seconds
        self.max_loaded_models = max_loaded_models
        self.cleanup_interval_seconds = cleanup_interval_seconds

        self._loaded: Dict[str, LoadedModel] = {}
        self._loading: set = set()
        self._lock = threading.RLock()

        # GPU memory cache to avoid frequent nvidia-smi calls
        self._gpu_memory_cache = {'value': 0.0, 'time': 0.0}
        self._gpu_memory_cache_ttl = 1.0  # 1 second cache

        # Start cleanup thread
        self._stop_cleanup = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="ModelManager-Cleanup",
            daemon=True
        )
        self._cleanup_thread.start()

    def get_model(
        self,
        model_id: str,
        wait_for_memory: bool = True,
        timeout: float = 300.0,
    ) -> Optional[AudioModel]:
        """
        Get a model instance, loading it if necessary.

        Args:
            model_id: The model to get
            wait_for_memory: If True, wait for GPU memory to become available
            timeout: Maximum time to wait for memory (seconds)

        Returns:
            The model instance, or None if unavailable
        """
        with self._lock:
            # Already loaded?
            if model_id in self._loaded:
                loaded = self._loaded[model_id]
                loaded.last_used = time.time()
                loaded.use_count += 1
                return loaded.instance

            # Already being loaded by another thread?
            if model_id in self._loading:
                return self._wait_for_loading(model_id, timeout)

        # Need to load
        return self._load_model(model_id, wait_for_memory, timeout)

    def get_model_for_capability(
        self,
        capability: ModelCapability,
        prefer_loaded: bool = True,
        prefer_commercial: bool = False,
    ) -> Optional[AudioModel]:
        """
        Get any model that supports a capability.

        Args:
            capability: Required capability
            prefer_loaded: If True, prefer already-loaded models
            prefer_commercial: If True, prefer commercially-safe models

        Returns:
            A model instance, or None if none available
        """
        available = ModelRegistry.list_by_capability(capability, enabled_only=True)

        if not available:
            print(f"[ModelManager] No models available for capability: {capability.value}")
            return None

        # Prefer commercially-safe models if requested
        if prefer_commercial:
            commercial = [m for m in available if ModelRegistry.get(m).commercial_ok]
            if commercial:
                available = commercial

        # Prefer already loaded
        if prefer_loaded:
            with self._lock:
                for model_id in available:
                    if model_id in self._loaded:
                        loaded = self._loaded[model_id]
                        loaded.last_used = time.time()
                        loaded.use_count += 1
                        print(f"[ModelManager] Using already-loaded model: {model_id}")
                        return loaded.instance

        # Load the first available
        return self.get_model(available[0])

    def _load_model(
        self,
        model_id: str,
        wait_for_memory: bool,
        timeout: float,
    ) -> Optional[AudioModel]:
        """Load a model, managing GPU memory."""
        info = ModelRegistry.get(model_id)
        if not info:
            print(f"[ModelManager] Unknown model: {model_id}")
            return None

        if not info.enabled:
            print(f"[ModelManager] Model disabled: {model_id}")
            return None

        with self._lock:
            self._loading.add(model_id)

        try:
            # Ensure we have enough memory
            required_memory = info.memory_gb + self.min_free_memory_gb

            if wait_for_memory:
                if not self._wait_for_memory(required_memory, timeout):
                    print(f"[ModelManager] Timeout waiting for memory: {model_id}")
                    return None
            else:
                free = self._get_free_gpu_memory()
                if free < required_memory:
                    self._make_room(required_memory)

            # Create and load the model
            print(f"[ModelManager] Loading {model_id}...")
            instance = ModelRegistry.create_instance(model_id)

            if not instance.load():
                print(f"[ModelManager] Failed to load {model_id}")
                return None

            # Track it
            with self._lock:
                self._loaded[model_id] = LoadedModel(
                    instance=instance,
                    model_id=model_id,
                    loaded_at=time.time(),
                    last_used=time.time(),
                    use_count=1,
                )

            print(f"[ModelManager] Loaded {model_id} successfully")
            return instance

        except Exception as e:
            print(f"[ModelManager] Error loading {model_id}: {e}")
            return None

        finally:
            with self._lock:
                self._loading.discard(model_id)

    def unload_model(self, model_id: str) -> bool:
        """
        Unload a specific model.

        Returns:
            True if unloaded, False if not loaded
        """
        with self._lock:
            if model_id not in self._loaded:
                return False

            loaded = self._loaded.pop(model_id)

        try:
            print(f"[ModelManager] Unloading {model_id}...")
            loaded.instance.unload()
        except Exception as e:
            print(f"[ModelManager] Error unloading {model_id}: {e}")

        # Force cleanup
        del loaded
        gc.collect()

        # Clear GPU cache
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except ImportError:
            pass

        print(f"[ModelManager] Unloaded {model_id}")
        return True

    def unload_all(self) -> int:
        """
        Unload all loaded models.

        Returns:
            Number of models unloaded
        """
        with self._lock:
            model_ids = list(self._loaded.keys())

        count = 0
        for model_id in model_ids:
            if self.unload_model(model_id):
                count += 1

        return count

    def _make_room(self, required_gb: float) -> None:
        """Unload least recently used models to free memory."""
        while self._get_free_gpu_memory() < required_gb:
            with self._lock:
                if not self._loaded:
                    break

                # Find LRU model
                lru_id = min(
                    self._loaded.keys(),
                    key=lambda x: self._loaded[x].last_used
                )

            self.unload_model(lru_id)

    def _wait_for_memory(self, required_gb: float, timeout: float) -> bool:
        """Wait for sufficient GPU memory to become available."""
        start = time.time()

        while time.time() - start < timeout:
            free = self._get_free_gpu_memory()

            if free >= required_gb:
                return True

            # Try to make room
            self._make_room(required_gb)

            if self._get_free_gpu_memory() >= required_gb:
                return True

            time.sleep(5.0)

        return False

    def _wait_for_loading(self, model_id: str, timeout: float) -> Optional[AudioModel]:
        """Wait for another thread to finish loading a model."""
        start = time.time()

        while time.time() - start < timeout:
            with self._lock:
                if model_id in self._loaded:
                    loaded = self._loaded[model_id]
                    loaded.last_used = time.time()
                    loaded.use_count += 1
                    return loaded.instance

                if model_id not in self._loading:
                    # Loading failed
                    return None

            time.sleep(0.5)

        return None

    def _get_free_gpu_memory(self) -> float:
        """Get available GPU memory in GB with caching."""
        now = time.time()

        # Return cached value if fresh
        if now - self._gpu_memory_cache['time'] < self._gpu_memory_cache_ttl:
            return self._gpu_memory_cache['value']

        # Try nvidia-smi for system-wide view
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.free',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                free_mb = float(result.stdout.strip().split('\n')[0])
                free_gb = free_mb / 1024.0
                self._gpu_memory_cache = {'value': free_gb, 'time': now}
                return free_gb
        except Exception:
            pass

        # Fallback to torch
        try:
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                total = props.total_memory / (1024 ** 3)
                used = torch.cuda.memory_allocated() / (1024 ** 3)
                free = total - used
                self._gpu_memory_cache = {'value': free, 'time': now}
                return free
        except ImportError:
            pass

        return 0.0

    def _cleanup_loop(self) -> None:
        """Background thread to unload idle models."""
        while not self._stop_cleanup.wait(self.cleanup_interval_seconds):
            self._cleanup_idle_models()

    def _cleanup_idle_models(self) -> None:
        """Unload models that have exceeded idle timeout."""
        now = time.time()
        to_unload = []

        with self._lock:
            for model_id, loaded in self._loaded.items():
                idle_time = now - loaded.last_used
                if idle_time > self.idle_timeout_seconds:
                    to_unload.append(model_id)

        for model_id in to_unload:
            print(f"[ModelManager] Unloading idle model: {model_id}")
            self.unload_model(model_id)

    def get_status(self) -> Dict[str, Any]:
        """Get status of all models."""
        with self._lock:
            loaded_status = {}
            for mid, loaded in self._loaded.items():
                try:
                    status = loaded.instance.get_status()
                    loaded_status[mid] = {
                        'loaded_at': loaded.loaded_at,
                        'last_used': loaded.last_used,
                        'use_count': loaded.use_count,
                        'status': status.to_dict(),
                    }
                except Exception as e:
                    loaded_status[mid] = {'error': str(e)}

            return {
                'loaded': loaded_status,
                'loading': list(self._loading),
                'available': ModelRegistry.list_enabled(),
                'all_models': ModelRegistry.get_all_info(),
                'free_memory_gb': round(self._get_free_gpu_memory(), 2),
            }

    def get_loaded_models(self) -> List[str]:
        """Get list of currently loaded model IDs."""
        with self._lock:
            return list(self._loaded.keys())

    def is_loaded(self, model_id: str) -> bool:
        """Check if a specific model is loaded."""
        with self._lock:
            return model_id in self._loaded

    def shutdown(self) -> None:
        """Clean shutdown - stop cleanup thread and unload all models."""
        print("[ModelManager] Shutting down...")
        self._stop_cleanup.set()
        self._cleanup_thread.join(timeout=5.0)
        self.unload_all()
        print("[ModelManager] Shutdown complete")


# Global manager instance (created on first import)
_manager: Optional[ModelManager] = None
_manager_lock = threading.Lock()


def get_manager(**kwargs) -> ModelManager:
    """
    Get the global ModelManager instance.

    Creates a new manager on first call. Subsequent calls return the same instance.
    Pass kwargs to customize the manager on first creation.
    """
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = ModelManager(**kwargs)
        return _manager


def shutdown_manager() -> None:
    """Shutdown the global manager if it exists."""
    global _manager
    with _manager_lock:
        if _manager is not None:
            _manager.shutdown()
            _manager = None
