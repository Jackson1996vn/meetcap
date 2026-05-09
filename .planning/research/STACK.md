# Stack Research

**Domain:** Personal CLI tool — meeting recorder, local transcriber, AI summarizer
**Researched:** 2026-05-09
**Confidence:** HIGH (core stack verified via PyPI + Context7; ScreenCaptureKit Python path is MEDIUM — known friction)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Runtime | tomllib stdlib (no dep), match statements, per-interpreter GIL prep. 3.11 is the stated constraint. |
| faster-whisper | 1.2.1 | Local speech transcription | CTranslate2-backed reimplementation of Whisper — 4x faster than openai/whisper, lower RAM, built-in VAD via silero-vad, yields segments lazily. large-v3 model downloads from HF Hub automatically. |
| mlx-whisper | 0.4.3 | Apple Silicon transcription (macOS only) | Uses Apple's MLX framework directly — 30–40% faster than faster-whisper on M-series chips. Same API shape as openai/whisper. Use as the macOS code path; fall back to faster-whisper on Windows/CPU. |
| anthropic | 0.100.0 | Claude API client | Official Anthropic Python SDK. Synchronous and async clients, typed request/response models, built-in token counting (`client.messages.count_tokens()`). Required for map-reduce summarization. |
| click | 8.3.3 | CLI framework | Pallets project, de-facto standard for Python CLIs. `@click.group()` + `@cli.command()` pattern maps cleanly to `meetcap`, `meetcap transcribe`, `meetcap summarize`, `meetcap config`, `meetcap list`. |
| sounddevice | 0.5.5 | Microphone capture | PortAudio bindings that return NumPy arrays — integrates directly with WAV writing via soundfile. Non-blocking stream callback API keeps CPU low during recording. |

### Audio Capture — Platform-Specific

| Library | Platform | Version | Purpose | Notes |
|---------|----------|---------|---------|-------|
| pyobjc-framework-ScreenCaptureKit | macOS 13+ | 12.1 | System audio (loopback) via SCStream | MEDIUM confidence — `capturesAudio=True` on `SCStreamConfiguration` is the correct API surface, but PyObjC on macOS 15 has a confirmed bug (issue #647) where callbacks never fire. Requires app entitlement or TCC permission grant. Needs careful threading (run loop). |
| PyAudioWPatch | Windows 10+ | 0.2.12.8 | WASAPI loopback — records speaker output | Drop-in PyAudio fork. Use `get_loopback_device_info()` to find the output device, then open an input stream against its loopback analogue. Pre-built wheels for Python 3.7–3.14 on Windows. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| soundfile | 0.13.x | WAV file read/write | Write mic + system audio to 16-bit 16 kHz WAV; faster-whisper reads WAV natively. Use instead of wave stdlib for cleaner NumPy integration. |
| numpy | 2.x | Audio array operations | Required by sounddevice and soundfile. Mix mic and system audio arrays by summing channels before WAV write. |
| platformdirs | 4.9.6 | Platform config directory | `platformdirs.user_config_dir("meetcap")` → `~/.config/meetcap/` on Linux/Mac, `%APPDATA%\meetcap\` on Windows. Use for config.toml location. |
| tomllib (stdlib) | built-in (3.11+) | Read TOML config | No extra dep — `import tomllib`. For writes use `tomli-w` (separate write-only lib, ~1 kB). |
| tomli-w | 1.x | Write TOML config | stdlib tomllib is read-only. tomli-w provides `tomli_w.dumps(dict)` for writing config. |
| hashlib (stdlib) | built-in | Transcript cache key | `hashlib.sha256(transcript.encode()).hexdigest()` as cache filename. No dep needed. |
| rich | 14.x | Terminal output | Progress spinners during transcription, coloured status lines. Optional but improves UX significantly for a 1-2 minute transcription wait. |

### Development / Packaging Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Dependency management, virtual env, build | `uv init`, `uv add`, `uv build`. As of July 2025, `uv init` defaults to `uv_build` backend. Fastest resolution, lockfile included. Preferred over pip/poetry for new 2025 projects. |
| hatchling | Build backend (alternative) | Use instead of uv_build only if you need custom build hooks (e.g., bundling native libs). For meetcap, uv_build is sufficient. |
| pipx | End-user install | `pipx install meetcap` isolates the tool in its own venv. Define entry point in `[project.scripts]` in pyproject.toml: `meetcap = "meetcap.cli:main"`. |
| ruff | Linting + formatting | Replaces flake8 + black + isort in one binary. `ruff check .` + `ruff format .`. |
| mypy | Static type checking | Worth adding for the audio pipeline where numpy array shapes cause silent bugs. |
| pytest | Testing | Standard. Use `tmp_path` fixture for WAV files, mock `anthropic.Anthropic` client. |

---

## Installation

```bash
# Create project with uv
uv init meetcap --python 3.11
cd meetcap

# Core runtime deps
uv add faster-whisper anthropic click sounddevice soundfile numpy platformdirs tomli-w rich

# macOS system audio
uv add pyobjc-framework-ScreenCaptureKit --platform darwin

# Windows system audio
uv add PyAudioWPatch --platform win32

# Optional: Apple Silicon transcription acceleration
uv add mlx-whisper --platform darwin

# Dev deps
uv add --dev ruff mypy pytest
```

pyproject.toml entry point:
```toml
[project.scripts]
meetcap = "meetcap.cli:main"
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| faster-whisper | openai/whisper | Never for this project — openai/whisper is 4x slower and uses more RAM. No benefit. |
| faster-whisper | whisperx | If speaker diarization (Phase 2) is needed — WhisperX wraps faster-whisper and adds diarization via pyannote. Switch then, not now. |
| mlx-whisper (macOS) | faster-whisper (macOS) | Use faster-whisper on macOS only if mlx-whisper install fails (e.g., Intel Mac). mlx-whisper requires Apple Silicon. |
| sounddevice | PyAudio | PyAudio returns raw bytes, not NumPy arrays. Harder to mix channels. Use PyAudio only via PyAudioWPatch for Windows WASAPI loopback specifically. |
| sounddevice | SoundCard | SoundCard explicitly does NOT support loopback on macOS (returns silence). Ruled out for system audio capture. |
| click | argparse | argparse is stdlib but verbose for subcommand trees. click's decorator pattern is cleaner for `meetcap transcribe <file>`, `meetcap config --vault`. |
| click | typer | typer wraps click with type annotations. Fine for greenfield, but adds a dep. click directly is fine for this scope. |
| anthropic SDK | httpx direct | SDK provides typed models, retry logic, and token counting. No reason to go lower level. |
| subprocess + ffmpeg | pydub | pydub requires ffmpeg anyway and adds a dep layer with no benefit. `subprocess.run(["ffmpeg", "-i", "in.wav", "-c:a", "libopus", "out.opus"])` is 3 lines and zero deps. |
| tomllib + tomli-w | pydantic-settings | Pydantic-settings is heavier. For a config with 4-5 keys, stdlib tomllib + tomli-w is sufficient and faster to load. |
| uv | poetry | Both work. uv is faster (Rust-based) and the 2025 community momentum is clearly behind uv. poetry still valid but no advantage here. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| openai/whisper | ~4x slower than faster-whisper, higher RAM, no built-in VAD | faster-whisper 1.2.1 |
| SoundCard for loopback on macOS | Explicitly unsupported — records silence on macOS loopback | pyobjc-framework-ScreenCaptureKit |
| BlackHole virtual driver | Requires driver install + reboot; project constraint is "no drivers or reboots" | ScreenCaptureKit (macOS 13+) |
| pydub | Adds a dep that just wraps subprocess ffmpeg calls | `subprocess.run(["ffmpeg", ...])` directly |
| opuslib / PyOgg | opuslib is unmaintained; PyOgg is low-level. Both require libopus system install. | ffmpeg via subprocess (ships with most systems, or `brew install ffmpeg`) |
| toml (uiri/toml) | Unmaintained, not compliant with TOML 1.0. Was the pre-3.11 workaround. | `tomllib` (stdlib) + `tomli-w` |
| whisper.cpp Python bindings | Binding quality varies; Apple Silicon path is better served by mlx-whisper | mlx-whisper on macOS, faster-whisper on Windows |
| real-time streaming transcription | Out of scope for v1; adds significant complexity to the audio pipeline | Post-meeting batch transcription |

---

## Stack Patterns by Variant

**macOS 13+ (Apple Silicon M1/M2/M3/M4):**
- Use mlx-whisper for transcription (30–40% faster than faster-whisper on MPS)
- Use pyobjc-framework-ScreenCaptureKit for system audio capture
- Mike capture via sounddevice (PortAudio)
- Mix mic + system audio as NumPy arrays before WAV write

**Windows 10+:**
- Use faster-whisper for transcription (CUDA if GPU available, else int8 CPU)
- Use PyAudioWPatch for WASAPI loopback system audio
- Mic capture also via PyAudioWPatch or sounddevice
- Mix mic + loopback as byte arrays, convert to NumPy for WAV write

**Intel Mac (macOS 13+):**
- mlx-whisper will NOT install (requires Apple Silicon)
- Fall back to faster-whisper with `device="cpu"`, `compute_type="int8"`
- ScreenCaptureKit still available for system audio

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| faster-whisper 1.2.1 | Python 3.8+ | Requires CTranslate2; will auto-download model on first run |
| mlx-whisper 0.4.3 | Python 3.8+, macOS Apple Silicon only | Depends on `mlx` framework — install fails silently on Intel or Windows |
| sounddevice 0.5.5 | Python 3.7+, requires PortAudio | On macOS: PortAudio bundled. On Windows: may need PortAudio DLL. |
| PyAudioWPatch 0.2.12.8 | Python 3.7–3.14, Windows only | Pre-built wheels; no compilation needed |
| pyobjc-framework-ScreenCaptureKit 12.1 | Python 3.9+, macOS 12.3+ | macOS 15 has active bug in audio callback (issue #647) — needs careful run loop threading |
| anthropic 0.100.0 | Python 3.9+ | Token counting API available; use `claude-sonnet-4-5` for summarization |
| click 8.3.3 | Python 3.8+ | Stable; no breaking changes expected |
| platformdirs 4.9.6 | Python 3.8+ | `user_config_dir(appname, ensure_exists=True)` creates directory on first call |

---

## Critical Implementation Notes

### System Audio on macOS — The Hard Part

ScreenCaptureKit via PyObjC is the only driver-free system audio capture path on macOS 13+. The API is real and works in Swift/Objective-C, but the PyObjC binding has a reliability issue on macOS 15 (SCStreamErrorDomain -3805 / callbacks never firing). Mitigation options:

1. Run the SCStream on a dedicated `NSRunLoop` in a background thread (the most common fix in Swift is also required in PyObjC).
2. Request screen recording permission via `SCShareableContent.getShareableContentWithCompletionHandler` before starting the stream.
3. If PyObjC fails, provide a fallback message telling the user to install BlackHole and configure it as an aggregate device — this trades the "no drivers" constraint for reliability.

This is the highest-risk component. Budget time for a standalone macOS audio capture spike before integrating it into the main pipeline.

### Transcription Performance Budget

The project requires < 4 GB RAM during transcription:
- `large-v3` with `compute_type="int8"` on CPU: ~2 GB RAM, adequate accuracy
- `large-v3` with `compute_type="float16"` on GPU (CUDA/MPS): ~3 GB VRAM, fastest
- `mlx-whisper` with `large-v3`: uses unified memory on Apple Silicon, typically 2–3 GB

For the 1-2 weekend build timeline, default to `large-v3` + `int8` on CPU and let users configure the model size via `meetcap config --model`.

### Map-Reduce Summarization

Claude Sonnet's context window is 200k tokens. A 30-minute meeting is roughly 5,000–8,000 transcript tokens. Map-reduce is only needed above ~150k tokens (6+ hour meetings). For v1, call `client.messages.count_tokens()` first; only split into chunks if the transcript exceeds 80% of the context window. This avoids unnecessary API complexity for typical meetings.

---

## Sources

- [faster-whisper PyPI](https://pypi.org/project/faster-whisper/) — version 1.2.1, verified 2026-05-09
- [faster-whisper Context7](/systran/faster-whisper) — VAD parameters, transcription API, segment yielding
- [mlx-whisper PyPI](https://pypi.org/project/mlx-whisper/) — version 0.4.3, Apple Silicon only
- [anthropic PyPI](https://pypi.org/project/anthropic/) — version 0.100.0, verified 2026-05-09
- [anthropic SDK Context7](/anthropics/anthropic-sdk-python) — token counting API, streaming
- [click PyPI](https://pypi.org/project/click/) — version 8.3.3, verified 2026-05-09
- [click Context7](/pallets/click) — group/subcommand decorator patterns
- [sounddevice PyPI](https://pypi.org/project/sounddevice/) — version 0.5.5 (released Jan 2026)
- [SoundCard PyPI](https://pypi.org/project/SoundCard/) — version 0.4.6; macOS loopback confirmed unsupported
- [PyAudioWPatch PyPI](https://pypi.org/project/PyAudioWPatch/) — version 0.2.12.8, Windows WASAPI loopback
- [pyobjc-framework-ScreenCaptureKit PyPI](https://pypi.org/project/pyobjc-framework-ScreenCaptureKit/) — version 12.1
- [PyObjC ScreenCaptureKit issue #647](https://github.com/ronaldoussoren/pyobjc/issues/647) — macOS 15 audio callback bug, MEDIUM confidence flag
- [platformdirs PyPI](https://pypi.org/project/platformdirs/) — version 4.9.6 (released Apr 2026)
- [Python docs: tomllib](https://docs.python.org/3/library/tomllib.html) — stdlib since 3.11, read-only
- WebSearch: uv vs hatchling 2025 — uv_build is default backend as of July 2025

---
*Stack research for: meetcap — Python meeting recorder/transcriber/summarizer CLI*
*Researched: 2026-05-09*
