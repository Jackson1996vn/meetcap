# Architecture Research

**Domain:** Meeting recorder / transcriber / summarizer — local-first Python CLI
**Researched:** 2026-05-09
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                             │
│  ┌──────────┐  ┌────────────────┐  ┌──────────────────┐     │
│  │ meetcap  │  │meetcap         │  │meetcap config    │     │
│  │ [title]  │  │transcribe/     │  │--vault/--model/  │     │
│  │ (record) │  │summarize <file>│  │--show            │     │
│  └────┬─────┘  └───────┬────────┘  └──────────┬───────┘     │
│       │                │                       │             │
├───────┼────────────────┼───────────────────────┼─────────────┤
│                    Orchestrator                               │
│  ┌────┴────────────────┴───────────────────────┴───────────┐ │
│  │         Session / Command Dispatcher                     │ │
│  │  (routes to pipeline stages, manages state file)        │ │
│  └──────┬─────────────────────────────────────┬────────────┘ │
│         │                                     │              │
├─────────┼─────────────────────────────────────┼──────────────┤
│                    Pipeline Layer                            │
│  ┌──────┴──────────┐   ┌─────────────┐   ┌───┴───────────┐  │
│  │  Audio Recorder  │   │ Transcriber │   │  Summarizer   │  │
│  │  (dual-stream   │   │(faster-     │   │ (Claude API   │  │
│  │   capture +     │   │ whisper)    │   │  map-reduce)  │  │
│  │   WAV writer)   │   │             │   │               │  │
│  └──────┬──────────┘   └──────┬──────┘   └───────┬───────┘  │
│         │                     │                   │          │
├─────────┼─────────────────────┼───────────────────┼──────────┤
│                    Storage / Output Layer                    │
│  ┌──────┴──┐  ┌────────────┐  ┌──────┴──┐  ┌─────┴──────┐   │
│  │ WAV tmp │  │ Opus       │  │Transcript│  │  Obsidian  │   │
│  │  file   │  │ archive    │  │  JSON +  │  │  Markdown  │   │
│  │         │  │ (.ogg)     │  │  .txt    │  │   Note     │   │
│  └─────────┘  └────────────┘  └─────────┘  └────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| CLI (click) | Parse user intent, display progress, handle Ctrl+C signal | Orchestrator |
| Config Manager | Read/write TOML at platform path, first-run prompt | CLI, all pipeline stages |
| Orchestrator | Sequence pipeline stages, manage temp paths, error propagation | All pipeline components |
| Audio Recorder | Capture mic + system audio in parallel threads, mix to WAV | Filesystem (WAV temp), Orchestrator |
| Platform Audio Backend | OS-specific system audio capture (ScreenCaptureKit / WASAPI) | Audio Recorder |
| Transcriber | Load faster-whisper, run VAD, produce segments + full text | Filesystem (WAV in, JSON + .txt out) |
| Summarizer | Chunk transcript, call Claude API (map-reduce), structure output | Claude API, Cache, Filesystem |
| Cache | Hash transcript, store/retrieve summary to avoid redundant API calls | Summarizer |
| Opus Converter | Convert WAV to Opus for long-term storage after transcription | Filesystem |
| Markdown Writer | Render frontmatter + structured sections, write to Obsidian vault | Filesystem (vault path from Config) |

## Recommended Project Structure

```
meetcap/
├── __init__.py
├── cli.py                  # Click entry point, command group, subcommands
├── config.py               # TOML read/write, first-run prompt, platform path resolution
├── session.py              # Session state: paths, metadata, orchestration logic
├── audio/
│   ├── __init__.py
│   ├── recorder.py         # Dual-stream capture loop, threading, WAV write, Ctrl+C flush
│   ├── mixer.py            # Combine mic + system audio streams into single WAV
│   ├── converter.py        # WAV → Opus via ffmpeg subprocess or pydub
│   └── backends/
│       ├── __init__.py
│       ├── macos.py        # ScreenCaptureKit via PyObjC / subprocess bridge
│       └── windows.py      # WASAPI loopback via PyAudioWPatch or SoundCard
├── transcribe/
│   ├── __init__.py
│   └── whisper.py          # faster-whisper wrapper, VAD config, segment + full-text output
├── summarize/
│   ├── __init__.py
│   ├── claude.py           # Anthropic SDK calls, prompt templates
│   ├── chunker.py          # Split transcript into ~15-min segments for map-reduce
│   └── cache.py            # SHA-256 hash of transcript → cached summary JSON
├── output/
│   ├── __init__.py
│   ├── markdown.py         # Frontmatter + section rendering
│   └── vault.py            # Resolve vault path, write file, filename pattern
└── utils/
    ├── __init__.py
    └── platform.py         # OS detection, config dir resolution (XDG / AppData)
```

### Structure Rationale

- **audio/backends/:** Platform-specific system audio code is isolated so the rest of the codebase is OS-agnostic. The recorder calls into the backend abstraction; tests can mock it.
- **audio/recorder.py vs mixer.py:** Separation allows testing mixing logic independently from the OS-level capture loop.
- **summarize/chunker.py:** Chunking logic is separate from Claude API calls so the map-reduce strategy can be changed without touching API code.
- **summarize/cache.py:** Cache is a dedicated module, not embedded in claude.py, making it easy to replace (disk → SQLite) later.
- **output/:** Markdown rendering and vault I/O are separated from summarization so the output format can evolve (e.g., add JSON export) without touching pipeline logic.
- **session.py:** Holds the ephemeral state for a single run (temp paths, title, timestamps). Acts as the data envelope passed between stages rather than passing individual arguments everywhere.

## Architectural Patterns

### Pattern 1: Pipeline with Session Envelope

**What:** A `Session` dataclass carries all per-run state (audio path, transcript path, title, duration, metadata) and is threaded through each pipeline stage. Each stage reads from and writes to the session rather than returning bare values.

**When to use:** Always — it avoids long argument chains between stages and makes it easy to add new fields (e.g., speaker count) without changing function signatures.

**Trade-offs:** Slightly less obvious data flow at a glance, but massively simplifies stage coordination and error recovery.

```python
@dataclass
class Session:
    title: str
    started_at: datetime
    wav_path: Path
    opus_path: Path | None = None
    transcript_path: Path | None = None
    summary: dict | None = None
    duration_seconds: float | None = None
```

### Pattern 2: Producer-Consumer Queue for Dual Audio Streams

**What:** Mic and system audio each run in their own thread writing to a `queue.Queue`. A mixer thread reads from both queues, combines the numpy arrays, and writes interleaved frames to the WAV file.

**When to use:** Any time two audio sources must be captured simultaneously without one blocking the other.

**Trade-offs:** Slight latency from buffering (negligible for post-meeting notes). Requires careful thread shutdown on Ctrl+C to flush the queue before closing the WAV file.

```python
mic_queue: queue.Queue = queue.Queue()
sys_queue: queue.Queue = queue.Queue()

def mic_callback(indata, frames, time, status):
    mic_queue.put(indata.copy())

def sys_callback(indata, frames, time, status):
    sys_queue.put(indata.copy())

# Mixer thread reads both queues and writes to WAV writer
```

### Pattern 3: Map-Reduce for Long Transcripts

**What:** For recordings over ~30 minutes, split the transcript into overlapping 15-minute chunks. Summarize each chunk with Claude independently (map). Combine all chunk summaries into a final meta-summary call (reduce). Cache the final result keyed by SHA-256 of the full transcript text.

**When to use:** Meetings longer than ~30 minutes. Under that threshold, a single API call is cheaper and sufficient.

**Trade-offs:** More API calls = slightly higher cost (~$0.05 vs $0.03 for a 60-min meeting). Avoids context window issues and keeps per-chunk prompts focused.

```
Transcript (60 min)
  → Chunk 1 (0-15 min)  → Summary 1
  → Chunk 2 (12-27 min) → Summary 2   (3-min overlap prevents split decisions)
  → Chunk 3 (24-39 min) → Summary 3
  → Chunk 4 (36-51 min) → Summary 4
  → Chunk 5 (48-60 min) → Summary 5
       ↓ reduce
  → Final structured summary (title, tldr, key_points, decisions, action_items)
```

### Pattern 4: Platform Backend Abstraction

**What:** Define a simple protocol/interface for system audio capture. macOS and Windows implementations satisfy the same interface. The recorder imports the right backend at runtime based on `sys.platform`.

**When to use:** Any cross-platform feature with fundamentally different OS APIs.

**Trade-offs:** Slight indirection. Benefit is that the entire recorder.py is testable on either platform by mocking the backend.

```python
class SystemAudioBackend(Protocol):
    def start(self) -> None: ...
    def read_chunk(self) -> np.ndarray: ...
    def stop(self) -> None: ...
```

## Data Flow

### Happy Path: `meetcap "Team Standup"`

```
User runs: meetcap "Team Standup"
    │
    ▼
CLI (cli.py)
  - Parse title arg
  - Load config (vault path, model, API key env check)
  - Create Session(title="Team Standup", wav_path=tmp/...)
    │
    ▼
Audio Recorder (audio/recorder.py)
  - Start mic stream (sounddevice)
  - Start system audio stream (platform backend)
  - Queue → mixer → write WAV frames
  - Block until SIGINT (Ctrl+C)
  - Flush queue, close WAV file
  - Set session.duration_seconds
    │
    ▼
Transcriber (transcribe/whisper.py)
  - Load faster-whisper model (large-v3, cached after first run)
  - Run VAD filter pass
  - Transcribe → segments (list of {start, end, text}) + full text
  - Write session.transcript_path (.txt full text, .json segments)
    │
    ▼
Opus Converter (audio/converter.py)
  - ffmpeg: WAV → .ogg (Opus codec, 32kbps mono)
  - Set session.opus_path
  - Delete WAV temp file
    │
    ▼
Summarizer (summarize/)
  - Check cache: SHA-256(transcript text) → cache hit? return early
  - If < 30 min: single Claude call
  - If >= 30 min: chunk → map → reduce
  - Set session.summary (dict with title, tldr, key_points, decisions, action_items)
  - Write summary to cache
    │
    ▼
Markdown Writer (output/)
  - Resolve filename: YYYY-MM-DD <title>.md
  - Render frontmatter (date, duration, audio_path, source: meetcap)
  - Render sections: TL;DR, Key Points, Decisions, Action Items, Transcript
  - Write to vault_path/Meetings/<filename>
    │
    ▼
CLI output: "Note saved: ~/vault/Meetings/2026-05-09 Team Standup.md"
```

### Re-processing Flows

```
meetcap transcribe <wav_file>
  → Skip recorder
  → Start from Transcriber
  → Continue through pipeline

meetcap summarize <transcript_file>
  → Skip recorder + transcriber
  → Check cache → Summarizer → Markdown Writer
```

### Config Write Flow

```
meetcap config --vault ~/Documents/Obsidian
  → Config Manager
  → Write vault_path to ~/.config/meetcap/config.toml (macOS/Linux)
                     or %APPDATA%\meetcap\config.toml  (Windows)
  → Print confirmation
```

## Build Order (Dependencies)

Build in this sequence — each layer depends on the one above it being stable:

| Order | Component | Depends On | Why Build Here |
|-------|-----------|------------|----------------|
| 1 | Config + platform utils | Nothing | Every other component needs config |
| 2 | Session dataclass | Config | Pipeline envelope used by all stages |
| 3 | CLI skeleton (click group + stubs) | Config, Session | Gives runnable entry point early |
| 4 | Platform audio backend (macOS first) | Nothing else | Most complex, most risk — flush early |
| 5 | Audio recorder (mic + queue) | Platform backend | Requires backend to be callable |
| 6 | WAV writer + Opus converter | Recorder | Post-recording conversion |
| 7 | Transcriber (faster-whisper) | WAV output | Needs real audio to validate |
| 8 | Summarizer — single-call path | Transcript output | Start simple, no chunking |
| 9 | Cache | Summarizer | Wrap the simple path first |
| 10 | Summarizer — map-reduce path | Cache, chunker | Add after single-call is stable |
| 11 | Markdown writer + vault output | Summary dict, Session | Pure rendering, low risk |
| 12 | Windows platform backend | Backend interface | Second platform after macOS is solid |
| 13 | `meetcap transcribe` / `summarize` sub-commands | All stages | Re-use already-built stages |
| 14 | `meetcap list` / `meetcap config` sub-commands | Config, vault | Quality-of-life polish |

## Anti-Patterns

### Anti-Pattern 1: Blocking Main Thread During Recording

**What people do:** Run the audio callback on the main thread, blocking until done.
**Why it's wrong:** Ctrl+C cannot be cleanly caught, the queue never flushes, and the WAV file ends up truncated or corrupt.
**Do this instead:** Run the audio stream callback in sounddevice's internal thread. Main thread blocks on `threading.Event` that SIGINT sets. On event, signal all stream threads to stop and join them before closing the WAV file.

### Anti-Pattern 2: Loading faster-whisper Model Per Invocation

**What people do:** Construct `WhisperModel(...)` inside the transcription function.
**Why it's wrong:** On CPU, large-v3 takes 15-30 seconds to load from disk. `meetcap transcribe` would feel broken.
**Do this instead:** Load the model once at process start (lazy singleton), keep it in memory for the duration of the command. First run is slow; subsequent re-processing commands are fast.

### Anti-Pattern 3: Writing WAV Directly During Callback

**What people do:** Open a `wave.Wave_write` in the audio callback and write frames inline.
**Why it's wrong:** `wave.Wave_write` is not thread-safe and disk I/O in an audio callback causes buffer underruns on slow storage.
**Do this instead:** Callback puts numpy arrays into a queue. A dedicated writer thread drains the queue and does all disk writes.

### Anti-Pattern 4: Mixing Platform Code Into Core Logic

**What people do:** `if sys.platform == 'darwin': ... else: ...` scattered through recorder.py.
**Why it's wrong:** Untestable on the other platform, grows unmaintainable as edge cases accumulate.
**Do this instead:** Backend protocol with two implementations. Recorder imports the backend and calls a stable interface. Platform detection is a single import-time switch in `audio/backends/__init__.py`.

### Anti-Pattern 5: Calling Claude With Raw Transcript Bytes

**What people do:** Pass the full transcript text to Claude without any preprocessing.
**Why it's wrong:** For 60-min meetings, the transcript can be 30k+ tokens. Whisper output includes filler words, repeated phrases, and timestamp noise. Sending all of it increases cost and degrades summary quality.
**Do this instead:** Strip VAD-filtered low-confidence segments before summarizing. Use chunker for long transcripts. The chunker should split on sentence boundaries, not character count.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Anthropic Claude API | `anthropic` SDK, synchronous calls | API key from `ANTHROPIC_API_KEY` env var; never write to config file |
| faster-whisper model (HuggingFace Hub) | Auto-download on first use to `~/.cache/huggingface/` | large-v3 is ~3GB; warn user before first download |
| ffmpeg (for Opus conversion) | Subprocess call (`ffmpeg -i input.wav ...`) | Bundled via `imageio-ffmpeg` or detected from PATH |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI → Orchestrator | Direct function call, passes Session | CLI owns display; orchestrator owns pipeline |
| Recorder → Transcriber | Filesystem (WAV temp path in Session) | No in-memory audio passed; file is the contract |
| Transcriber → Summarizer | Filesystem (.txt transcript path in Session) | Same pattern — file is the contract |
| Summarizer → Markdown Writer | In-memory dict (session.summary) | Summary is small; no need for intermediate file |
| All stages → Config | Read-only import of config singleton | Config is loaded once at CLI startup, passed via Session or imported |

## Scaling Considerations

This is a personal CLI tool — scaling means handling edge cases, not user growth.

| Concern | Handling |
|---------|----------|
| Very long meetings (2h+) | Map-reduce chunker handles; model stays in memory across chunks |
| Large model memory (large-v3 ~3GB) | Falls back to `medium` or `small` if user configures; lazy load |
| No internet (Claude API down) | Transcription completes; summarizer fails gracefully with partial output (transcript saved) |
| Interrupted recording (crash, battery) | WAV is written incrementally; transcriber can handle truncated WAV |
| First run (no model cached) | Warn user, show download size, block transcription until complete |

## Sources

- [SYSTRAN/faster-whisper — GitHub](https://github.com/SYSTRAN/faster-whisper)
- [SoundCard PyPI](https://pypi.org/project/SoundCard/)
- [PyAudioWPatch — WASAPI loopback for Windows](https://github.com/s0d3s/PyAudioWPatch)
- [Summarization with Claude — Anthropic Cookbook](https://platform.claude.com/cookbook/capabilities-summarization-guide)
- [Building a local AI meeting transcriber and summarizer — Botmonster](https://botmonster.com/posts/build-local-ai-meeting-transcriber-summarizer/)
- [jfcostello/meeting-transcriber — GitHub](https://github.com/jfcostello/meeting-transcriber)
- [python-sounddevice concurrent recording issue](https://github.com/spatialaudio/python-sounddevice/issues/76)
- [ScreenCaptureKit — Apple Developer Documentation](https://developer.apple.com/documentation/screencapturekit/)
- [Click command groups — Real Python](https://realpython.com/python-click/)

---
*Architecture research for: meeting recorder / transcriber / summarizer CLI (meetcap)*
*Researched: 2026-05-09*
