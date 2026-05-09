# Project Research Summary

**Project:** meetcap
**Domain:** Local-first Python CLI — meeting recorder, transcriber, and AI summarizer
**Researched:** 2026-05-09
**Confidence:** HIGH (stack and pitfalls verified against official issue trackers and PyPI; features cross-referenced against 5+ competitors)

## Executive Summary

meetcap is a personal CLI tool that records both microphone and system audio during meetings, transcribes locally with Whisper, and produces a structured Obsidian markdown note via Claude. The established pattern for this class of tool is a sequential pipeline: capture audio to WAV, transcribe to text with VAD pre-filtering, summarize with a map-reduce strategy for long meetings, and write YAML-frontmattered markdown to the user's vault. All audio stays local; only the transcript text touches an external API. The closest open-source reference is ownscribe, but meetcap differentiates on Windows support, Claude summarization quality, and native Obsidian output.

The recommended stack is mature and well-supported: faster-whisper 1.2.1 (or mlx-whisper on Apple Silicon), the Anthropic Python SDK, click for the CLI, sounddevice for microphone capture, and platform-specific backends for system audio (pyobjc-framework-ScreenCaptureKit on macOS, PyAudioWPatch on Windows). The build tool is uv. The architecture is a clean pipeline with a Session dataclass as the data envelope, platform backends behind an abstract interface, and file-based contracts between stages (WAV in, transcript out, summary dict in-memory to markdown writer).

The highest-risk area is macOS system audio capture. PyObjC's ScreenCaptureKit binding has a confirmed macOS 15 regression (issue #647) where the SCStream delegate is garbage-collected before callbacks fire. This must be treated as a spike — build and validate the audio capture backend before building anything else. A secondary risk is sample rate drift when mixing mic (44100 Hz) and system audio (48000 Hz): resampling to a canonical rate must be part of the initial pipeline design, not a retrofit. All other pitfalls are avoidable with upfront decisions (use soundfile not stdlib wave, use PyAudioWPatch on Windows, enable VAD in faster-whisper from day one).

## Key Findings

### Recommended Stack

Python 3.11+ is the runtime constraint (tomllib stdlib, match statements). The transcription path branches by platform: mlx-whisper 0.4.3 on Apple Silicon (30-40% faster via Metal), faster-whisper 1.2.1 everywhere else (CTranslate2-backed, 4x faster than openai/whisper, built-in VAD via silero-vad). System audio capture is the only fundamentally platform-split component: ScreenCaptureKit via PyObjC on macOS 13+, PyAudioWPatch on Windows (stock sounddevice cannot do WASAPI loopback — documented open issue spatialaudio/python-sounddevice#281). uv is the correct build and dependency tool for 2025.

**Core technologies:**
- Python 3.11+: runtime — tomllib stdlib eliminates a dependency; match statements clean up platform branching
- faster-whisper 1.2.1: local transcription — 4x faster than openai/whisper, built-in VAD, lazy segment yielding
- mlx-whisper 0.4.3: Apple Silicon transcription — 30-40% faster than faster-whisper on M-series; macOS-specific fast path only
- anthropic 0.100.0: Claude API client — typed models, built-in token counting, retry logic
- click 8.3.3: CLI framework — decorator-based subcommand tree maps cleanly to all meetcap subcommands
- sounddevice 0.5.5: microphone capture — returns NumPy arrays directly, non-blocking callback
- pyobjc-framework-ScreenCaptureKit 12.1: macOS system audio — only driver-free capture path on macOS 13+; MEDIUM confidence due to macOS 15 PyObjC bug
- PyAudioWPatch 0.2.12.8: Windows system audio — pre-patched PortAudio with WASAPI loopback; the only viable Windows path
- soundfile 0.13.x: WAV write — handles RF64 for files over 4 GB; use instead of stdlib wave from day one
- platformdirs 4.9.6: config directory — cross-platform resolution of ~/.config/meetcap/ vs %APPDATA%\meetcap\
- rich 14.x: terminal output — progress spinner during transcription wait is a meaningful UX improvement
- uv: dependency management and build — fastest resolver, lockfile included, 2025 community standard

### Expected Features

The core value proposition is: finish a meeting, hit Ctrl+C, get a structured note in Obsidian. Every feature decision should be evaluated against this sentence.

**Must have (table stakes):**
- Mic + system audio capture simultaneously
- Clean Ctrl+C stop with WAV buffer flush
- Local Whisper transcription with VAD
- Structured Claude summary (title, TL;DR, key points, decisions, action items)
- Obsidian markdown output with YAML frontmatter
- Filename pattern `YYYY-MM-DD <title>.md`
- Map-reduce summarization for meetings over 30 minutes
- Summary cache by transcript SHA-256 hash
- WAV to Opus conversion for archival
- `meetcap transcribe <file>` and `meetcap summarize <file>` subcommands
- `meetcap config` with --vault, --model, --show
- First-run vault path prompt
- API key from ANTHROPIC_API_KEY environment variable
- Audio device disconnect resilience

**Should have (competitive):**
- 100% local transcription (audio never leaves the machine)
- Timestamped segments JSON alongside transcript
- Configurable model and LLM via `meetcap config`
- `meetcap list`
- Transcription progress display

**Defer (v2+):**
- Speaker diarization
- Local LLM via Ollama
- Automatic meeting detection via calendar integration
- Multi-language support
- Semantic search across transcripts
- GUI / menu bar / tray

### Architecture Approach

The architecture is a four-layer pipeline: CLI layer (click subcommands) → Orchestrator (Session-based dispatcher) → Pipeline components (Recorder, Transcriber, Summarizer) → Storage/Output (WAV temp, Opus archive, transcript JSON, Obsidian markdown). A `Session` dataclass is the data envelope threaded through all stages. Platform-specific audio code is isolated behind a `SystemAudioBackend` protocol. Stage boundaries use filesystem contracts (WAV → transcript file → summary dict) so each stage is independently testable and re-runnable.

### Critical Pitfalls

1. **SCStream delegate garbage-collected on macOS 15 (PyObjC issue #647)** — Store delegate as instance attribute on a long-lived object; spin NSRunLoop on the capture thread; add 2-second health check verifying at least one callback fires.

2. **Ctrl+C truncates WAV file (RIFF header never finalized)** — Use threading.Event for graceful shutdown via signal.signal(SIGINT, handler); wrap all handles in try/finally; validate WAV with soundfile.info() before proceeding.

3. **Sample rate mismatch causes audio drift (mic at 44100 Hz, system audio at 48000 Hz)** — Establish 48000 Hz as canonical capture rate before writing any audio code; resample mic stream in callback via samplerate library.

4. **Whisper hallucination on silence and background noise** — Always enable vad_filter=True and vad_parameters={"min_silence_duration_ms": 500}; add no_speech_threshold=0.6.

5. **WASAPI loopback unavailable in stock sounddevice on Windows** — Use PyAudioWPatch for Windows system audio.

6. **Map-reduce loses cross-chunk context** — Use overlapping chunks (last 200 tokens of previous chunk as prefix); deduplicate action items semantically in reduce step.

7. **Screen Recording permission silently not granted on macOS** — Check permission at startup via SCShareableContent result length; fail fast with actionable error message.

8. **Obsidian filename sanitization failures on Windows** — Strip `/ : * ? " < > | \` from Claude-generated titles; write to temp file then rename atomically.

## Implications for Roadmap

### Phase 1: Audio Pipeline Foundation
**Rationale:** Audio capture is the highest-risk component and the dependency for every downstream stage.
**Delivers:** Reliable dual-stream WAV recording on macOS and Windows; clean Ctrl+C handling; WAV-to-Opus conversion
**Addresses pitfalls:** 1, 2, 3, 5, 7

### Phase 2: Transcription
**Rationale:** Transcription depends entirely on clean WAV output from Phase 1. VAD must be enabled from day one.
**Delivers:** Accurate local transcript with timestamps; segments JSON; VAD pre-filtering
**Addresses pitfalls:** 4

### Phase 3: Summarization and Caching
**Rationale:** Summarization is purely a function of transcript text — no OS-specific code.
**Delivers:** Structured summary for meetings of any length; SHA-256 cache; re-summarize subcommand
**Addresses pitfalls:** 6

### Phase 4: Obsidian Output and CLI Polish
**Rationale:** Markdown writing is pure rendering. Completes the CLI surface.
**Delivers:** Valid YAML-frontmattered Obsidian markdown; `meetcap config`; first-run wizard; `meetcap list`
**Addresses pitfalls:** 8

### Research Flags

Needs research spike: Phase 1 (macOS ScreenCaptureKit on macOS 15), Phase 3 (map-reduce chunk parameters)
Standard patterns (skip research): Phase 2 (faster-whisper well-documented), Phase 4 (markdown rendering trivial)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core Python/click/faster-whisper/anthropic stack verified via PyPI. ScreenCaptureKit PyObjC path is MEDIUM. |
| Features | HIGH | Cross-referenced 5+ tools (ownscribe, Meetily, Granola, Otter, Fireflies). |
| Architecture | HIGH | Build order and component boundaries consistent with open-source reference implementations. |
| Pitfalls | HIGH | Most pitfalls verified against official issue trackers. |

**Overall confidence:** HIGH

### Gaps to Address

- macOS 15 ScreenCaptureKit reliability — treat Phase 1 as a spike with go/no-go gate
- mlx-whisper vs faster-whisper speed claim — unverified, faster-whisper works as fallback
- ffmpeg availability on Windows — evaluate imageio-ffmpeg as pip-installable fallback

## Sources

### Primary (HIGH confidence)
- PyObjC SCStream issue (macOS 15): pyobjc#647
- faster-whisper PyPI and Context7
- Anthropic Python SDK Context7
- sounddevice WASAPI loopback issue: python-sounddevice#281
- faster-whisper Apple Silicon issue: faster-whisper#515
- faster-whisper hallucination VAD issue: faster-whisper#843
- Whisper hallucination research: arxiv 2501.11378

### Secondary (MEDIUM confidence)
- PyAudioWPatch GitHub
- Ownscribe (CLI reference)
- Meetily (GUI reference)
- Anthropic Cookbook summarization guide

---
*Research completed: 2026-05-09*
*Ready for roadmap: yes*
