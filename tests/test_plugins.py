"""
Tests for the SoundBox plugin system.

Run with: pytest tests/test_plugins.py -v
"""

import os
import sys
import pytest
import tempfile
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.base import (
    ModelCapability,
    GenerationResult,
    ModelStatus,
    AudioModelBase,
    PluginError,
    ModelLoadError,
)
from plugins.registry import ModelRegistry, ModelInfo
from plugins.manager import ModelManager


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_success_when_audio_path_and_no_error(self):
        result = GenerationResult(
            audio_path="/tmp/test.wav",
            sample_rate=32000,
            duration=10.0,
        )
        assert result.success is True

    def test_failure_when_error_present(self):
        result = GenerationResult(
            audio_path="/tmp/test.wav",
            sample_rate=32000,
            duration=10.0,
            error="Generation failed",
        )
        assert result.success is False

    def test_failure_when_no_audio_path(self):
        result = GenerationResult(
            audio_path="",
            sample_rate=32000,
            duration=0,
        )
        assert result.success is False


class TestModelStatus:
    """Tests for ModelStatus dataclass."""

    def test_to_dict_serialization(self):
        status = ModelStatus(
            model_id="test-model",
            display_name="Test Model",
            loaded=True,
            capabilities=[ModelCapability.MUSIC, ModelCapability.SFX],
        )
        d = status.to_dict()

        assert d['model_id'] == 'test-model'
        assert d['display_name'] == 'Test Model'
        assert d['loaded'] is True
        assert 'music' in d['capabilities']
        assert 'sfx' in d['capabilities']


class MockAudioModel(AudioModelBase):
    """Mock audio model for testing."""

    def __init__(self, model_id: str = "mock-model"):
        self._model_id = model_id
        self._loaded = False
        self._mock_model = None

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def display_name(self) -> str:
        return "Mock Model"

    @property
    def capabilities(self):
        return [ModelCapability.MUSIC]

    @property
    def memory_requirement_gb(self) -> float:
        return 1.0

    def load(self) -> bool:
        self._mock_model = "loaded"
        self._loaded = True
        return True

    def unload(self) -> bool:
        self._mock_model = None
        self._loaded = False
        return True

    def generate(self, prompt, duration, output_path, **kwargs):
        if not self._loaded:
            raise Exception("Not loaded")

        # Create a dummy file
        with open(output_path, 'wb') as f:
            f.write(b'RIFF' + b'\x00' * 40)  # Fake WAV header

        return GenerationResult(
            audio_path=output_path,
            sample_rate=32000,
            duration=duration,
            metadata={'prompt': prompt},
        )


class TestModelRegistry:
    """Tests for ModelRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        ModelRegistry.clear()

    def test_register_decorator(self):
        @ModelRegistry.register(
            model_id="test-decorator",
            display_name="Test Decorator Model",
            memory_gb=2.0,
            capabilities=[ModelCapability.MUSIC],
        )
        class TestModel:
            pass

        assert "test-decorator" in ModelRegistry.list_all()
        info = ModelRegistry.get("test-decorator")
        assert info is not None
        assert info.display_name == "Test Decorator Model"
        assert info.memory_gb == 2.0

    def test_register_class_directly(self):
        ModelRegistry.register_class(
            model_id="test-direct",
            model_cls=MockAudioModel,
            display_name="Direct Registration",
            memory_gb=1.5,
            capabilities=[ModelCapability.SFX],
        )

        assert "test-direct" in ModelRegistry.list_all()
        info = ModelRegistry.get("test-direct")
        assert info.display_name == "Direct Registration"

    def test_list_by_capability(self):
        ModelRegistry.register_class(
            "music-model", MockAudioModel,
            capabilities=[ModelCapability.MUSIC],
        )
        ModelRegistry.register_class(
            "sfx-model", MockAudioModel,
            capabilities=[ModelCapability.SFX],
        )
        ModelRegistry.register_class(
            "both-model", MockAudioModel,
            capabilities=[ModelCapability.MUSIC, ModelCapability.SFX],
        )

        music_models = ModelRegistry.list_by_capability(ModelCapability.MUSIC)
        assert "music-model" in music_models
        assert "both-model" in music_models
        assert "sfx-model" not in music_models

    def test_list_commercial_safe(self):
        ModelRegistry.register_class(
            "commercial", MockAudioModel,
            commercial_ok=True,
        )
        ModelRegistry.register_class(
            "noncommercial", MockAudioModel,
            commercial_ok=False,
        )

        safe = ModelRegistry.list_commercial_safe()
        assert "commercial" in safe
        assert "noncommercial" not in safe

    def test_create_instance(self):
        ModelRegistry.register_class(
            "creatable", MockAudioModel,
            config={'model_id': 'creatable'},
        )

        instance = ModelRegistry.create_instance("creatable")
        assert instance is not None
        assert isinstance(instance, MockAudioModel)

    def test_enable_disable(self):
        ModelRegistry.register_class(
            "toggleable", MockAudioModel,
            enabled=True,
        )

        assert "toggleable" in ModelRegistry.list_enabled()

        ModelRegistry.set_enabled("toggleable", False)
        assert "toggleable" not in ModelRegistry.list_enabled()

        ModelRegistry.set_enabled("toggleable", True)
        assert "toggleable" in ModelRegistry.list_enabled()

    def test_unregister(self):
        ModelRegistry.register_class("removable", MockAudioModel)
        assert "removable" in ModelRegistry.list_all()

        result = ModelRegistry.unregister("removable")
        assert result is True
        assert "removable" not in ModelRegistry.list_all()

    def test_get_all_info(self):
        ModelRegistry.register_class(
            "info-test", MockAudioModel,
            display_name="Info Test",
            license="MIT",
        )

        all_info = ModelRegistry.get_all_info()
        assert "info-test" in all_info
        assert all_info["info-test"]["license"] == "MIT"


class TestModelManager:
    """Tests for ModelManager."""

    def setup_method(self):
        """Setup fresh registry and manager for each test."""
        ModelRegistry.clear()
        ModelRegistry.register_class(
            "test-model",
            MockAudioModel,
            memory_gb=1.0,
            capabilities=[ModelCapability.MUSIC],
            enabled=True,
        )

    def test_get_model_loads_on_demand(self):
        manager = ModelManager(
            min_free_memory_gb=0,
            idle_timeout_seconds=60,
        )

        try:
            model = manager.get_model("test-model")
            assert model is not None
            assert manager.is_loaded("test-model")
        finally:
            manager.shutdown()

    def test_get_model_returns_cached(self):
        manager = ModelManager(min_free_memory_gb=0)

        try:
            model1 = manager.get_model("test-model")
            model2 = manager.get_model("test-model")
            assert model1 is model2  # Same instance
        finally:
            manager.shutdown()

    def test_unload_model(self):
        manager = ModelManager(min_free_memory_gb=0)

        try:
            manager.get_model("test-model")
            assert manager.is_loaded("test-model")

            result = manager.unload_model("test-model")
            assert result is True
            assert not manager.is_loaded("test-model")
        finally:
            manager.shutdown()

    def test_get_model_for_capability(self):
        manager = ModelManager(min_free_memory_gb=0)

        try:
            model = manager.get_model_for_capability(ModelCapability.MUSIC)
            assert model is not None
        finally:
            manager.shutdown()

    def test_get_loaded_models(self):
        manager = ModelManager(min_free_memory_gb=0)

        try:
            assert manager.get_loaded_models() == []

            manager.get_model("test-model")
            loaded = manager.get_loaded_models()
            assert "test-model" in loaded
        finally:
            manager.shutdown()

    def test_get_status(self):
        manager = ModelManager(min_free_memory_gb=0)

        try:
            manager.get_model("test-model")
            status = manager.get_status()

            assert "loaded" in status
            assert "test-model" in status["loaded"]
            assert "available" in status
            assert "all_models" in status
        finally:
            manager.shutdown()

    def test_unknown_model_returns_none(self):
        manager = ModelManager(min_free_memory_gb=0)

        try:
            model = manager.get_model("nonexistent-model")
            assert model is None
        finally:
            manager.shutdown()


class TestMockGeneration:
    """Test generation with mock models."""

    def setup_method(self):
        ModelRegistry.clear()
        ModelRegistry.register_class(
            "gen-test", MockAudioModel,
            capabilities=[ModelCapability.MUSIC],
        )

    def test_generate_creates_file(self):
        manager = ModelManager(min_free_memory_gb=0)

        try:
            model = manager.get_model("gen-test")
            assert model is not None

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                output_path = f.name

            try:
                result = model.generate(
                    prompt="test prompt",
                    duration=5.0,
                    output_path=output_path,
                )

                assert result.success
                assert result.audio_path == output_path
                assert os.path.exists(output_path)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            manager.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
