# SoundBox Plugin System Research

> Branch: `dev/model-plugin-system`
> Date: January 2026

## Executive Summary

This document compiles research findings for implementing a plugin architecture in SoundBox that enables swappable AI models for music, sound effects, and speech generation.

---

## 1. Current State Analysis

### Current Models in SoundBox
| Model | Type | License | VRAM | Status |
|-------|------|---------|------|--------|
| MusicGen | Music | CC-BY-NC (weights) | 4-7GB | In use |
| AudioGen | SFX | CC-BY-NC (weights) | 5GB | In use |
| MAGNeT | Both | CC-BY-NC (weights) | 6GB | In use |
| Piper TTS | Voice | MIT | 0.5GB | In use |

**Critical Finding**: MusicGen/AudioGen weights are **CC-BY-NC** (non-commercial). This limits commercial deployment options.

### Coupling Points Requiring Abstraction
1. Hardcoded imports (`from audiocraft.models import MusicGen`)
2. Model instantiation with specific class names
3. Memory requirements in `MODEL_MEMORY_GB` dict
4. Valid model type validation lists
5. Different APIs (AudioCraft vs Piper TTS)

---

## 2. Alternative Models - Summary

### Music Generation

| Model | License | VRAM | Commercial? | Speed | Quality |
|-------|---------|------|-------------|-------|---------|
| **ACE-Step** | Apache 2.0 | 8GB | Yes | Fast | High |
| **DiffRhythm** | Apache 2.0 | 8GB | Yes | Very Fast | Very High |
| **YuE** | Apache 2.0 | 8-80GB | Yes | Moderate | Excellent |
| **Stable Audio** | Community | 12GB | <$1M revenue | Moderate | High |
| **Riffusion** | CreativeML | 8GB | Paid tier | Moderate | Medium |

**Recommendation**: **ACE-Step** - best balance of Apache 2.0 license, 8GB VRAM, quality, and speed.

### Sound Effects Generation

| Model | License | VRAM | Commercial? | Speed | Quality |
|-------|---------|------|-------------|-------|---------|
| **Bark** | MIT | 8-12GB | Yes | Moderate | Medium |
| **Stable Audio Open** | Community | 12GB | <$1M | Moderate | High |
| **TangoFlux** | Non-commercial | 8GB | No | Very Fast | Excellent |
| **MMAudio** | MIT | 6GB | Maybe* | Fast | Good |
| **AudioLCM** | Research | 6GB | No | Ultra-fast | Good |

**Recommendation**: **Stable Audio Open** for quality, **Bark** for full commercial freedom.

### Text-to-Speech

| Model | License | VRAM | Voice Clone | Languages | Speed |
|-------|---------|------|-------------|-----------|-------|
| **Chatterbox** | MIT | Low | Yes (5-10s) | 23 | Very Fast |
| **Fish Speech** | Apache 2.0 | Moderate | Yes (10-30s) | 13 | Fast |
| **Kokoro-82M** | Apache 2.0 | CPU | No (presets) | 8 | Fastest |
| **OpenVoice v2** | MIT | Low | Yes | Multi | Fast |
| **GPT-SoVITS** | MIT | Moderate | Yes (1min) | 5 | Fast |
| XTTS-v2 | Non-commercial | 8GB | Yes (6s) | 17 | Fast |

**Recommendation**: **Chatterbox** (MIT, voice cloning, emotion control) or **Kokoro** (fastest, CPU-only).

---

## 3. Licensing Summary

### Safe for Commercial Use
- **MIT**: Bark, Chatterbox, Kokoro, OpenVoice, GPT-SoVITS, MMAudio
- **Apache 2.0**: ACE-Step, DiffRhythm, YuE, Fish Speech, Tortoise TTS

### Conditional Commercial Use
- **Stability Community License**: Stable Audio Open (free <$1M revenue)
- **Riffusion**: Paid subscription required

### Non-Commercial Only
- **CC-BY-NC**: MusicGen/AudioGen weights, AudioLDM2 weights, XTTS-v2, F5-TTS
- **Research**: AudioLCM, FlashAudio, TangoFlux

### Key Insight
Training your own MusicGen model on licensed data is **commercially safe** - only the pre-trained weights are CC-BY-NC.

---

## 4. Recommended Plugin Architecture

### Pattern: Protocol + Registry + Factory

```
models/
├── __init__.py           # Exports
├── base.py               # Protocol definitions
├── registry.py           # Model discovery
├── manager.py            # Lifecycle management
├── adapters/
│   ├── musicgen.py       # MusicGen adapter
│   ├── ace_step.py       # ACE-Step adapter
│   ├── audiogen.py       # AudioGen adapter
│   ├── stable_audio.py   # Stable Audio adapter
│   ├── piper.py          # Piper TTS adapter
│   └── chatterbox.py     # Chatterbox adapter
└── config.yaml           # Model configuration
```

### Core Interface

```python
@runtime_checkable
class AudioModel(Protocol):
    @property
    def model_id(self) -> str: ...
    @property
    def capabilities(self) -> list[ModelCapability]: ...
    @property
    def memory_requirement_gb(self) -> float: ...

    def load(self) -> bool: ...
    def unload(self) -> bool: ...
    def is_loaded(self) -> bool: ...
    def generate(self, prompt: str, duration: float, **kwargs) -> GenerationResult: ...
```

### Registration Pattern

```python
@ModelRegistry.register(
    model_id="ace-step",
    display_name="ACE-Step Music",
    memory_gb=8.0,
    capabilities=[ModelCapability.MUSIC]
)
class ACEStepAdapter:
    # Implementation
    pass
```

### Memory Management
- **TTL-based unloading**: Idle models auto-unload after 5 minutes
- **LRU eviction**: When memory needed, unload least-recently-used
- **CPU offload queue**: Fast reactivation without full reload

---

## 5. Migration Strategy

### Phase 1: Create Plugin Infrastructure
1. Create `models/` package with base classes
2. Wrap existing MusicGen/AudioGen/Piper as adapters
3. No behavior change - just refactored structure

### Phase 2: Add Model Registry
1. Implement registry with decorator pattern
2. Replace hardcoded model references with registry lookups
3. Configuration-driven model selection

### Phase 3: Add Alternative Models
1. Add ACE-Step adapter for commercial music
2. Add Stable Audio Open adapter for SFX
3. Add Chatterbox adapter for advanced TTS

### Phase 4: UI Integration
1. Model selector in generate form
2. Model status dashboard
3. Model preference settings per user

---

## 6. Quick Start Commands

```bash
# ACE-Step (music)
pip install git+https://github.com/ace-step/ACE-Step.git

# DiffRhythm (music with vocals)
git clone https://github.com/ASLP-lab/DiffRhythm.git

# Stable Audio Open (SFX)
pip install stable-audio-tools

# Chatterbox (TTS)
pip install chatterbox-tts

# Kokoro (fast TTS)
pip install kokoro-onnx
```

---

## 7. Decision Matrix

For **commercial SoundBox deployment**:

| Component | Current | Recommended | Fallback |
|-----------|---------|-------------|----------|
| Music | MusicGen (NC) | ACE-Step (Apache) | YuE (Apache) |
| SFX | AudioGen (NC) | Stable Audio (<$1M) | Bark (MIT) |
| TTS | Piper | Chatterbox (MIT) | Kokoro (Apache) |

For **non-commercial / hobby use**:

| Component | Current | Recommended | Why |
|-----------|---------|-------------|-----|
| Music | MusicGen | Keep / TangoFlux | Quality + speed |
| SFX | AudioGen | Keep / TangoFlux | Best quality |
| TTS | Piper | XTTS-v2 | Voice cloning |

---

## 8. Next Steps

1. [ ] Review this document and confirm direction
2. [ ] Create `models/` package structure
3. [ ] Implement base Protocol and Registry
4. [ ] Wrap existing models as adapters
5. [ ] Add first alternative model (ACE-Step or Stable Audio)
6. [ ] Update UI with model selector

---

## Sources

Research conducted via 6 parallel investigation agents analyzing:
- GitHub repositories and documentation
- Hugging Face model cards
- License files and terms of service
- Academic papers (arXiv, ACL, CVPR)
- Industry benchmarks and comparisons
