# meetcap — Meeting Auto-Recorder & Summarizer

> Personal CLI tool. Records meetings, transcribes locally, summarizes with Claude, drops a markdown note into the Obsidian vault. No UI, no backend, no accounts.

---

## 1. Problem

Most meeting summarizer apps are SaaS, require accounts, upload audio to their servers, and charge monthly. For personal use this is overkill. I want a single binary I run before a meeting and forget about — when I hit Ctrl+C, a markdown note shows up in my Obsidian vault.

---

## 2. Goals

- Run from terminal — `meetcap` and go
- Capture mic + system audio mixed into one file
- Transcribe locally (Whisper), no audio leaves the machine unless I opt in
- Summarize with Claude, output structured markdown
- Save directly into Obsidian vault, ready to read in seconds
- Cross-platform: Windows + macOS
- Single-developer scope — buildable in 1-2 weekends

## 3. Non-Goals (v1)

- No GUI, no menu bar, no tray icon
- No mobile, no browser extension
- No team features, no sharing, no cloud sync
- No real-time live captions
- No video recording
- No automatic meeting detection (Phase 2)
- No speaker diarization (Phase 2)

---

## 4. User Stories

| # | As a user, I want to... | So that... |
|---|---|---|
| 1 | Run `meetcap` before a meeting starts | I don't fumble with apps when the call begins |
| 2 | Press Ctrl+C when the meeting ends | Recording stops cleanly |
| 3 | See a markdown summary appear in my Obsidian vault automatically | I can review it without manual export |
| 4 | Have action items extracted with names and deadlines | I don't miss commitments |
| 5 | Keep the audio file locally | I can re-listen or re-process later |
| 6 | Configure my vault path once | The tool just works on subsequent runs |
| 7 | Re-summarize an existing recording | If I want a different summary or the LLM was down |
| 8 | Use a local LLM for sensitive meetings | Confidential content never hits a cloud API |

---

## 5. Functional Requirements

### 5.1 Recording

- Capture microphone audio
- Capture system audio (what speakers play) — for hearing the other meeting participants
- Mix both into a single audio file, OR save separately and mix on demand
- Output format: Opus, 16kHz, mono, ~32kbps
- Stop on Ctrl+C, flush buffers, write file cleanly
- Handle audio device disconnect mid-recording without crashing

### 5.2 Transcription

- Default: local transcription via `faster-whisper` with `large-v3` model
- VAD filtering enabled (avoid Whisper hallucinations on silent stretches)
- Output: full text + timestamped segments saved as JSON
- Optional: cloud transcription via Deepgram (paid, fast, better diarization later)

### 5.3 Summarization

- Default: Claude Sonnet via Anthropic API
- Output structured JSON with this schema:
  ```json
  {
    "title": "short meeting title",
    "tldr": "2-3 sentence summary",
    "key_points": ["..."],
    "decisions": ["..."],
    "action_items": [
      {"who": "name or unknown", "what": "task", "when": "date or null"}
    ]
  }
  ```
- For meetings > 30 minutes: chunk transcript into 10-min segments, summarize each in parallel, then synthesize a final summary
- Optional: local LLM via Ollama (Qwen 2.5 14B or Llama 3.1 8B) for offline / private mode
- Cache summary by transcript hash — re-running on the same audio doesn't re-call the API

### 5.4 Output

- Write markdown file to configured Obsidian vault directory
- Filename pattern: `YYYY-MM-DD <title>.md`
- Frontmatter: `date`, `duration`, `audio` (path to original file), `source`
- Sections: TL;DR, Key Points, Decisions, Action Items (as checklist), full Transcript
- Print final note path to stdout when done

### 5.5 CLI Commands

```
meetcap                          start recording, auto-prompt for title or use timestamp
meetcap "<title>"                start recording with given title
meetcap stop                     gracefully stop a running recorder (alt to Ctrl+C)
meetcap transcribe <audio.opus>  transcribe an existing file, write summary
meetcap summarize <audio.opus>   re-summarize an already transcribed file
meetcap config --vault <path>    set Obsidian vault directory
meetcap config --model <name>    set Whisper model (tiny|base|small|medium|large-v3)
meetcap config --llm <provider>  set LLM provider (claude|ollama)
meetcap config --show            show current config
meetcap list                     list recent recordings
```

### 5.6 Configuration

- Config file at `~/.config/meetcap/config.toml` (Mac/Linux) or `%APPDATA%\meetcap\config.toml` (Windows)
- Required keys: `vault_dir`, `recordings_dir`, `whisper_model`, `llm_provider`
- API keys read from environment: `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`
- First run prompts for vault path if not set

---

## 6. Non-Functional Requirements

| Area | Requirement |
|---|---|
| **Install** | One command — `pipx install meetcap` (Python) or download single binary (Rust). No drivers, no reboots |
| **Startup time** | < 500ms from `meetcap` to recording started |
| **CPU during recording** | < 5% on a modern laptop |
| **RAM during recording** | < 200MB |
| **RAM during transcription** | < 4GB (Whisper large-v3 model footprint) |
| **Transcription speed** | Faster than real-time on M-series Mac, at least real-time on modern Windows CPU |
| **Summary speed** | < 30 seconds for a 1-hour meeting (Claude API) |
| **Privacy default** | Audio stays local. Only transcript text leaves the machine, and only when Claude API is used |
| **Cross-platform** | Windows 10+, macOS 12+ |
| **Failure mode** | If transcription or summary fails, the audio file is preserved and the user can retry with `meetcap transcribe` |

---

## 7. Platform Specifics

### 7.1 macOS

- Requires Microphone permission (granted on first run, system prompt)
- For system audio capture, two options:
  - **macOS 13+:** ScreenCaptureKit (native, no driver) — preferred
  - **macOS 12:** BlackHole virtual audio driver — one-time install via Homebrew, no reboot
- Tested on Apple Silicon and Intel Macs

### 7.2 Windows

- WASAPI loopback for system audio — built into Windows, no driver needed
- Use `soundcard` library or `pyaudiowpatch`
- May trigger Windows Defender warning on first run if binary isn't signed — acceptable for personal use
- Bluetooth headsets switch to SCO mode when mic is used (8kHz mono) — warn user to prefer wired audio for important meetings

---

## 8. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Fast to ship, plenty of audio + ML libraries |
| Audio capture (Win) | `soundcard` (WASAPI loopback) | Built-in OS support, no driver |
| Audio capture (Mac) | `sounddevice` + BlackHole, OR Swift sidecar for ScreenCaptureKit | Best path depends on macOS version |
| Audio encoding | `soundfile` with Opus | 40x smaller than WAV, Whisper-compatible |
| Transcription | `faster-whisper` (CTranslate2) | 4x faster than reference Whisper, lower memory |
| LLM (cloud) | Anthropic Claude Sonnet | Best output quality for structured summaries |
| LLM (local) | Ollama + Qwen 2.5 14B | Privacy fallback |
| CLI | `click` | Standard Python CLI ergonomics |
| Config | `tomli` / `tomllib` | Stdlib in 3.11+ |
| Packaging | `pipx` | Isolated install, globally available command |

---

## 9. Data Flow

```
[Mic + System Audio]
        |
        v
[Recorder: opus file in recordings dir]
        |
        v
[faster-whisper: transcript JSON + plain text]
        |
        v
[Claude API: structured summary JSON]
        |
        v
[Markdown writer: note in Obsidian vault]
        |
        v
[stdout: path to final note]
```

---

## 10. File Layout (User Machine)

```
~/Library/Application Support/meetcap/    # Mac
%APPDATA%/meetcap/                         # Windows
├── recordings/
│   ├── 2026-05-09-1430-standup.opus
│   ├── 2026-05-09-1430-standup.transcript.json
│   └── 2026-05-09-1430-standup.summary.json
├── cache/
│   └── <transcript-hash>.summary.json     # cached LLM outputs
└── logs/
    └── meetcap.log

~/.config/meetcap/config.toml              # Mac/Linux config
%APPDATA%/meetcap/config.toml              # Windows config

<Obsidian Vault>/Meetings/
└── 2026-05-09 Daily Standup.md            # final output
```

---

## 11. Constraints & Assumptions

**Constraints**
- Single developer, evenings + weekends
- Personal use first — distribution comes later if at all
- No paid services required by default (Claude API is the only paid dependency, and only ~$0.03 per meeting)

**Assumptions**
- User has Python 3.11+ installed, or is willing to install it
- User has an Anthropic API key (or willing to set one up)
- User already uses Obsidian and has a vault path
- User is technical enough to edit a TOML config file
- English-language meetings for v1 (Whisper handles other languages but prompts are English)

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| BlackHole install friction on macOS < 13 | High — blocks first run | Detect macOS version, fall back to ScreenCaptureKit when possible; clear install instructions |
| Whisper hallucinations on silence | Medium — bad transcripts | Enable VAD filter in faster-whisper |
| Audio device disconnect mid-meeting | Medium — recording dies | Catch exception, attempt re-acquire, log warning, continue if possible |
| Long meetings exceed LLM context window | Medium — quality drops | Map-reduce summarization for transcripts > 30 min |
| Claude API outage | Low — can't summarize | Audio + transcript preserved, retry with `meetcap summarize` |
| Mic-only audio with no system capture | Medium — only hear user side | Run preflight check at start, warn if loopback device not found |
| Bluetooth headset SCO mode (Windows) | Low — bad audio quality | Warn in docs, suggest wired audio |
| Sample rate mismatch (e.g. 48kHz mic + 44.1kHz speaker) | Low — chipmunky audio | Force resample to 16kHz at capture time |

---

## 13. Roadmap

### Phase 1 — Core (1-2 weekends)
- [ ] Project scaffold, CLI with `click`
- [ ] Windows recorder via `soundcard` (mic + WASAPI loopback)
- [ ] macOS recorder via `sounddevice` + BlackHole
- [ ] faster-whisper transcription
- [ ] Claude summarization with structured output
- [ ] Markdown writer to Obsidian vault
- [ ] Config file load/save
- [ ] `transcribe` and `summarize` subcommands for re-processing

### Phase 2 — Quality of Life
- [ ] Speaker diarization via WhisperX (Python sidecar)
- [ ] Auto-stop on N minutes of silence (VAD-based)
- [ ] Voice fingerprint memory — auto-label known speakers
- [ ] Local LLM via Ollama as alternative
- [ ] Deepgram option for cloud transcription

### Phase 3 — Auto Mode
- [ ] Background daemon that watches for meeting apps (Zoom, Teams, Meet)
- [ ] Auto-start recording when meeting detected
- [ ] Calendar integration to pre-fill meeting title from event
- [ ] Process detection via `sysinfo` equivalent

### Phase 4 — Stretch
- [ ] Search across past meeting summaries (SQLite FTS index)
- [ ] Export action items to a todo app (Reminders, Things, Todoist)
- [ ] Daily digest — combine all meetings from a day into one note
- [ ] Polish for distribution — code signing, installers

---

## 14. Success Criteria for v1

I consider v1 done when, on both my Mac and my Windows machine, I can:

1. Run `meetcap` before a Zoom call
2. Have a normal 30-min meeting, hit Ctrl+C when done
3. Get a markdown file in my Obsidian vault within 5 minutes
4. The summary is accurate enough that I trust it without re-listening to the audio
5. The action items are correct enough that I'd actually use them

If any of those five fail, v1 is not done.
