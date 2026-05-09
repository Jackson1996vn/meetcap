# meetcap

## What This Is

A personal CLI tool that records meetings (mic + system audio), transcribes locally with Whisper, summarizes with Claude, and drops a structured markdown note into an Obsidian vault. No SaaS, no accounts, no UI — run `meetcap` before a call, hit Ctrl+C when done, get a note.

## Core Value

When I finish a meeting and hit Ctrl+C, an accurate, structured markdown summary appears in my Obsidian vault within minutes — without any audio leaving my machine except transcript text to Claude's API.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Record mic + system audio simultaneously
- [ ] Capture system audio via ScreenCaptureKit (macOS 13+) and WASAPI loopback (Windows)
- [ ] Record as WAV, convert to Opus for archival storage
- [ ] Stop cleanly on Ctrl+C with proper buffer flush
- [ ] Handle audio device disconnect mid-recording gracefully
- [ ] Transcribe locally with faster-whisper (large-v3 model, VAD filtering)
- [ ] Output transcript as full text + timestamped segments JSON
- [ ] Summarize transcript with Claude Sonnet via Anthropic API
- [ ] Produce structured summary: title, tldr, key_points, decisions, action_items
- [ ] Map-reduce summarization for meetings > 30 minutes
- [ ] Cache summaries by transcript hash to avoid redundant API calls
- [ ] Write markdown file to configurable Obsidian vault subfolder (default: Meetings/)
- [ ] Filename pattern: `YYYY-MM-DD <title>.md`
- [ ] Include frontmatter (date, duration, audio path, source) and sections (TL;DR, Key Points, Decisions, Action Items checklist, Transcript)
- [ ] CLI: `meetcap` / `meetcap "<title>"` to start recording
- [ ] CLI: `meetcap transcribe <file>` to re-transcribe existing audio
- [ ] CLI: `meetcap summarize <file>` to re-summarize existing transcript
- [ ] CLI: `meetcap config` subcommands (--vault, --model, --llm, --show)
- [ ] CLI: `meetcap list` to show recent recordings
- [ ] Config file at platform-appropriate path (TOML format)
- [ ] First run prompts for vault path if not configured
- [ ] API keys read from environment variables

### Out of Scope

- GUI / menu bar / tray icon — CLI-only for v1
- Mobile / browser extension — desktop CLI only
- Team features / sharing / cloud sync — personal tool
- Real-time live captions — not needed for post-meeting notes
- Video recording — audio only
- Automatic meeting detection — Phase 2
- Speaker diarization — Phase 2
- Local LLM via Ollama — deferred to v2 for budget reasons
- Deepgram cloud transcription — Whisper-only for v1
- BlackHole support for macOS 12 — targeting macOS 13+ with ScreenCaptureKit only

## Context

- Single developer building this for personal use on evenings/weekends
- Target machines: Apple Silicon Mac (macOS 13+) and Windows 10+ PC
- User already has an Obsidian vault and Anthropic API key
- English-language meetings for v1
- Python 3.11+ ecosystem chosen for fast shipping and ML library availability
- Key libraries: faster-whisper (CTranslate2), sounddevice/soundcard, click, anthropic SDK
- Audio pipeline: record WAV → transcribe → convert to Opus for storage
- Claude API cost is ~$0.03 per meeting — acceptable

## Constraints

- **Timeline**: Buildable in 1-2 weekends
- **Budget**: No paid services except Claude API (~$0.03/meeting)
- **Privacy**: Audio stays local by default; only transcript text goes to Claude API
- **Platform**: macOS 13+ (ScreenCaptureKit) and Windows 10+ (WASAPI loopback)
- **Install**: Single command — `pipx install meetcap`, no drivers or reboots
- **Performance**: < 500ms startup, < 5% CPU during recording, < 4GB RAM during transcription
- **Language**: Python 3.11+

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python over Rust | Fast to ship, rich audio/ML ecosystem | — Pending |
| WAV recording → Opus conversion | Whisper reads WAV natively, Opus is 40x smaller for storage | — Pending |
| ScreenCaptureKit only (no BlackHole) | Simpler, no driver install, macOS 13+ covers target machines | — Pending |
| Claude-only for v1 (no Ollama) | Ship faster, lower build cost, add local LLM in v2 | — Pending |
| Whisper-only (no Deepgram) | Local transcription covers core use case, privacy default | — Pending |
| Configurable vault subfolder (default: Meetings/) | Flexibility without manual setup | — Pending |
| TOML config format | Stdlib in Python 3.11+, human-readable | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-09 after initialization*
