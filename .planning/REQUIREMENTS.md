# Requirements: meetcap

**Defined:** 2026-05-09
**Core Value:** When I finish a meeting and hit Ctrl+C, an accurate, structured markdown summary appears in my Obsidian vault within minutes — without any audio leaving my machine except transcript text to OpenAI's API.

**Milestone plan:**
- **Milestone 1** (current): Audio capture — macOS + Windows
- **Milestone 2**: Transcription + summarization + output pipeline
- **Milestone 3**: Real-time live captions during meetings

## v1 Requirements (Milestone 1 — Audio Capture)

Requirements for milestone 1. Each maps to roadmap phases.

### Audio Capture

- [ ] **AUD-01**: User can record microphone and system audio simultaneously into a single WAV file
- [ ] **AUD-02**: Recording stops cleanly on Ctrl+C with proper WAV buffer flush (no corrupt files)
- [ ] **AUD-03**: System audio captured via ScreenCaptureKit on macOS 13+ (no driver install required)
- [ ] **AUD-04**: System audio captured via WASAPI loopback on Windows 10+ (no driver install required)
- [ ] **AUD-05**: Audio streams resampled to canonical rate to prevent drift between mic and system audio

### CLI & Config (Milestone 1 scope)

- [x] **CLI-01
**: User can start recording with `meetcap` or `meetcap "<title>"`
- [x] **CLI-02
**: Config file at platform-appropriate path (TOML format) with recordings_dir
- [x] **CLI-03
**: First run prompts for recordings directory if not configured

## v2 Requirements (Milestone 2 — Summarization Pipeline)

### Transcription

- **TRX-01**: User can transcribe audio locally using faster-whisper with VAD filtering enabled
- **TRX-02**: Transcription output includes full text and timestamped segments saved as JSON
- **TRX-03**: User can re-transcribe an existing audio file via `meetcap transcribe <file>`

### Summarization

- **SUM-01**: Transcript is summarized via OpenAI GPT producing structured JSON (title, tldr, key_points, decisions, action_items)
- **SUM-02**: Summary is cached by transcript SHA-256 hash — re-running on same audio skips the API call
- **SUM-03**: User can re-summarize an existing recording via `meetcap summarize <file>`

### Output

- **OUT-01**: Markdown file written to configurable directory with YAML frontmatter (date, duration, audio path, source)
- **OUT-02**: Markdown includes sections: TL;DR, Key Points, Decisions, Action Items (as checklist), Transcript
- **OUT-03**: Filename pattern: `YYYY-MM-DD <title>.md`
- **OUT-04**: Obsidian vault output is configurable — user can enable/disable and set vault path + subfolder in config
- **OUT-05**: Final note path printed to stdout when complete

### CLI & Config (Milestone 2 scope)

- **CLI-04**: API keys read from environment variables (OPENAI_API_KEY), never stored in config
- **CLI-05**: `meetcap config` subcommands (--vault, --model, --llm, --show)

## v3 Requirements (Milestone 3 — Live Captions)

### Live Captions

- **CAP-01**: Real-time live captions displayed during meeting
- **CAP-02**: Captions update as speech is recognized with low latency
- **CAP-03**: Live caption output configurable (terminal overlay, separate window, etc.)

## Future / Backlog

### Audio Enhancements

- **AUD-06**: Graceful recovery from audio device disconnect mid-recording (Bluetooth dropout)
- **AUD-07**: WAV-to-Opus archival conversion (40x smaller storage)

### Transcription Enhancements

- **TRX-04**: Configurable Whisper model size (tiny|base|small|medium|large-v3) via config
- **TRX-05**: Transcription progress display (rich spinner during CPU wait)
- **TRX-06**: mlx-whisper fast path on Apple Silicon (30-40% faster)

### Summarization Enhancements

- **SUM-04**: Map-reduce summarization for meetings > 30 minutes (chunk + synthesize)
- **SUM-05**: Local LLM via Ollama as privacy fallback

### CLI Enhancements

- **CLI-06**: `meetcap list` to show recent recordings
- **CLI-07**: `meetcap stop` to gracefully stop a running recorder (alternative to Ctrl+C)

### Quality of Life

- **QOL-01**: Speaker diarization via WhisperX
- **QOL-02**: Auto-stop on N minutes of silence (VAD-based)
- **QOL-03**: Deepgram cloud transcription option

### Auto Mode

- **AUTO-01**: Background daemon watching for meeting apps (Zoom, Teams, Meet)
- **AUTO-02**: Calendar integration to pre-fill meeting title

## Out of Scope

| Feature | Reason |
|---------|--------|
| GUI / menu bar / tray icon | CLI-only tool by design |
| Mobile / browser extension | Desktop CLI only |
| Team features / sharing / cloud sync | Personal tool |
| Video recording | Audio only |
| Multi-language support | English-only for v1 |
| Semantic search across transcripts | Stretch goal, not core value |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUD-01 | Phase 3 | Pending |
| AUD-02 | Phase 3 | Pending |
| AUD-03 | Phase 2 | Pending |
| AUD-04 | Phase 2 | Pending |
| AUD-05 | Phase 3 | Pending |
| CLI-01 | Phase 1 | Complete |
| CLI-02 | Phase 1 | Complete |
| CLI-03 | Phase 1 | Complete |

**Coverage:**
- v1 requirements (milestone 1): 8 total
- Mapped to phases: 8
- Unmapped: 0

---
*Requirements defined: 2026-05-09*
*Last updated: 2026-05-09 — traceability mapped during roadmap creation*
