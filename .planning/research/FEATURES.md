# Feature Research

**Domain:** Meeting recorder / transcriber / summarizer — personal CLI tool
**Researched:** 2026-05-09
**Confidence:** HIGH (cross-referenced 8+ sources including competitor products, open-source tools, and community patterns)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features every tool in this space has. Missing any of these makes the tool feel broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Mic + system audio capture | Capturing only mic misses remote speakers; users expect both sides of a call | MEDIUM | System audio requires OS-specific APIs: ScreenCaptureKit (macOS 13+), WASAPI loopback (Windows) |
| Clean Ctrl+C stop with full output | Users need to stop and immediately get their note — hanging processes or missing output is a blocker | LOW | Must flush audio buffer before process exit; partial writes corrupt output |
| Accurate speech-to-text | Transcript riddled with errors makes downstream summarization garbage | MEDIUM | faster-whisper large-v3 with VAD is current SOTA for local models |
| Structured summary with action items | Users want "what do I need to do" extracted, not just wall-of-text transcript | MEDIUM | Minimum sections: TL;DR, key points, decisions, action items |
| Markdown output with frontmatter | Obsidian users expect YAML frontmatter (date, tags, etc.) for Dataview and search | LOW | YAML block at top: date, duration, source, audio path |
| Re-transcribe and re-summarize commands | Audio files outlive the session; users need to reprocess without re-recording | LOW | `meetcap transcribe <file>` and `meetcap summarize <file>` — decouples pipeline stages |
| Config file with vault path | Hard-coding paths breaks across machines; users expect config-driven setup | LOW | TOML at platform-appropriate path; prompted on first run |
| Named recordings | `meetcap "Weekly Standup"` so the output filename is meaningful, not a timestamp blob | LOW | Falls back to AI-generated title from transcript if not provided |
| Output filename with date prefix | `2026-05-09 Weekly Standup.md` — users rely on date-ordered sorting in Obsidian | LOW | Filename must be OS-safe (strip colons, slashes) |
| Reliable process exit codes | Scripts and shell pipelines that call `meetcap` need reliable exit codes to detect failure | LOW | 0 = success, non-zero = failure with stderr message |

### Differentiators (Competitive Advantage)

Features that separate meetcap from generic tools. Aligned with the core value: "accurate structured note in Obsidian, with privacy, within minutes."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| 100% local transcription | Audio never leaves the machine — Whisper runs on-device; only transcript text hits Claude API | HIGH | faster-whisper + CTranslate2; model download on first run (~1.5GB for large-v3) |
| Map-reduce summarization for long meetings | Meetings > 30 min exceed context windows if naively passed; chunked summarization prevents truncation | HIGH | Split transcript into chunks, summarize each, then reduce to final; invisible to user |
| Summary cache by transcript hash | Re-running `meetcap summarize` never calls Claude twice for the same transcript — instant, zero cost | LOW | SHA-256 hash of transcript text → cache hit → skip API call |
| Opus archival with WAV recording | WAV for Whisper compatibility, auto-converted to Opus for storage (40x smaller) — users keep audio indefinitely without disk bloat | MEDIUM | ffmpeg or pydub for conversion post-transcription |
| First-run onboarding without a manual | New users get vault path prompt — zero config to first successful note | LOW | `if no config → ask → write config → continue` |
| Silent API key detection from env | Users who already set `ANTHROPIC_API_KEY` in their shell see zero friction; no separate config step | LOW | `os.environ.get("ANTHROPIC_API_KEY")` with fallback error message pointing to config |
| Audio device disconnect resilience | Mid-meeting headphone swap or Bluetooth dropout does not corrupt the recording | MEDIUM | Catch device error, log warning, continue with fallback device or buffer from last good frame |
| Timestamped transcript with segments JSON | Full word-level timestamps alongside human-readable transcript enables future search and tooling | MEDIUM | faster-whisper outputs segment objects with start/end times natively |
| Configurable LLM + model | Users may want to swap Claude Sonnet for Haiku (cheaper) or future models without code changes | LOW | `meetcap config --model` exposes the knob; minimal implementation cost |

### Anti-Features (Deliberately NOT Building)

Features that seem attractive but conflict with the tool's constraints or create disproportionate complexity.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time live captions | Feels more "live" during a meeting | Requires streaming pipeline (Whisper chunk latency ~2-5s introduces lag), adds synchronization complexity, and delivers zero value for post-meeting notes workflow | Post-meeting transcription — results in one shot within minutes of stopping |
| Speaker diarization (v1) | "Who said what" is genuinely valuable | pyannote requires HuggingFace token + model download (~1GB), adds significant complexity, and fails on overlapping speech; the user runs solo with known participants | Defer to v2 — label transcript sections by timestamp, let user annotate manually in Obsidian |
| GUI / menu bar / tray icon | Lower barrier to use | Completely separate skill set (AppKit/Qt/Electron); scope explodes; the user already has a terminal open before calls | CLI-only; users who want GUI should use Granola or Otter |
| Automatic meeting detection | Less friction to start | Requires calendar API integration + process monitoring; multiple failure modes; "privacy by default" conflicts with ambient monitoring | Explicit `meetcap` start — one command before a call, intentional |
| Multi-language transcription | Wider audience | English-first scope is correct for v1; multi-language changes model selection, prompt engineering, and summary quality; not the personal tool user's need | Defer to v2 with `--language` flag |
| Local LLM via Ollama | No API cost, full offline | Ollama model quality for summarization is significantly below Claude Sonnet for meeting notes; adds dependency, configuration, and GPU requirement; increases time-to-first-note | Claude API at ~$0.03/meeting is acceptable; revisit in v2 |
| Cloud sync / multi-device | Access notes from anywhere | Obsidian Sync handles this already; implementing it creates a security surface and server dependency — exactly what this tool avoids | Users who want sync use Obsidian Sync or iCloud with their vault |
| Team sharing / collaboration | Useful for teams | meetcap is a personal tool; team features require auth, permissions, server infra — a completely different product | Otter, Fireflies, Fathom serve teams; meetcap stays personal |
| Video recording | Capture screen + audio | Out of scope: video adds massive storage, ffmpeg complexity, and no incremental value for post-meeting markdown notes | Audio-only is sufficient; users who want video use Loom or OBS |
| Deepgram / cloud transcription | Faster first run, no GPU needed | Sends audio to a third party — directly contradicts the privacy constraint; adds API billing complexity | Whisper local transcription is the constraint |

---

## Feature Dependencies

```
[System audio capture]
    └──requires──> [OS audio API] (ScreenCaptureKit on macOS, WASAPI on Windows)
    └──requires──> [Screen Recording permission grant] (macOS)

[Transcription]
    └──requires──> [Audio capture complete] (WAV file on disk)
    └──requires──> [faster-whisper model downloaded] (lazy download on first run)
    └──produces──> [Transcript text + segments JSON]

[Summarization]
    └──requires──> [Transcript text]
    └──requires──> [Anthropic API key]
    └──enhanced by──> [Summary cache] (skip API if hash matches)
    └──enhanced by──> [Map-reduce] (required when transcript > ~30 min / ~8K tokens)

[Obsidian output]
    └──requires──> [Summarization complete]
    └──requires──> [Vault path configured]
    └──produces──> [YYYY-MM-DD <title>.md with YAML frontmatter]

[Opus archival]
    └──requires──> [WAV recording complete]
    └──independent of──> [Transcription] (runs in parallel after recording stops)

[Re-transcribe command]
    └──requires──> [WAV or Opus file on disk]
    └──independent of──> [Live capture pipeline]

[Re-summarize command]
    └──requires──> [Transcript JSON on disk]
    └──independent of──> [Transcription pipeline]

[Summary cache]
    └──enhances──> [Summarization] (prevents redundant API calls)
    └──requires──> [SHA-256 of transcript text as cache key]

[Map-reduce summarization]
    └──enhances──> [Summarization for long meetings]
    └──triggered when──> [Transcript token count > threshold (~8K)]
```

### Dependency Notes

- **Transcription requires audio capture complete:** Whisper reads a file, not a stream — recording must finish and be flushed to disk before transcription begins. This is intentional for simplicity.
- **Re-transcribe / re-summarize are independent of live capture:** These subcommands let users reprocess old recordings without touching the capture pipeline — important for correctness after model upgrades.
- **Opus conversion is independent of transcription:** WAV is kept until transcription finishes (Whisper needs it), then conversion happens. Opus is the archival format; WAV is transient.
- **Map-reduce is a transparent enhancement:** The CLI doesn't expose chunking to the user — it's applied automatically when transcripts exceed threshold. The output markdown is identical.
- **Summary cache enhances but doesn't block:** If cache is unavailable or corrupted, summarization falls back to direct API call. Cache is an optimization, not a dependency.

---

## MVP Definition

### Launch With (v1)

Minimum to validate the core value: "finish a meeting, hit Ctrl+C, get a structured note in Obsidian."

- [ ] Mic + system audio capture simultaneously (macOS + Windows) — without this the tool is useless
- [ ] Clean stop on Ctrl+C with buffer flush — partial output breaks trust immediately
- [ ] WAV recording → local Whisper transcription (faster-whisper large-v3, VAD) — accuracy is the foundation
- [ ] Transcript text + segments JSON output — text for summarization, JSON for future tooling
- [ ] Claude summarization with structured output (title, tldr, key_points, decisions, action_items) — the core value
- [ ] Map-reduce for meetings > 30 min — without this, long meetings silently fail or truncate
- [ ] Obsidian markdown output with YAML frontmatter — the delivery mechanism
- [ ] Filename `YYYY-MM-DD <title>.md` — usable in Obsidian without renaming
- [ ] WAV → Opus conversion for archival — avoids immediate disk bloat
- [ ] Summary cache by transcript hash — prevents wasted API spend on re-runs
- [ ] `meetcap transcribe <file>` and `meetcap summarize <file>` — reprocessing is essential for trust
- [ ] `meetcap config` with --vault, --model, --llm, --show — without config, every install requires code edits
- [ ] First-run vault path prompt — zero-friction first use
- [ ] API key from environment variable — standard CLI convention
- [ ] Audio device disconnect handling — single failure mid-meeting should not lose everything

### Add After Validation (v1.x)

Add once core loop is working and reliable.

- [ ] `meetcap list` — show recent recordings; useful once there are multiple recordings to manage
- [ ] Silence auto-stop — reduces friction for unattended recordings; only worth adding after manual workflow is solid
- [ ] Progress display during transcription — nice to have once the pipeline is fast enough to bother showing
- [ ] Configurable output sections — some users may not want all sections; wait for feedback

### Future Consideration (v2+)

Defer until v1 is proven in regular daily use.

- [ ] Speaker diarization — genuinely valuable but 2x complexity; add after v1 is stable
- [ ] Local LLM via Ollama — revisit when Ollama model quality catches up; not cost-justified yet
- [ ] Automatic meeting detection — requires calendar integration; separate project scope
- [ ] Multi-language support — personal tool is English-first; add if needed
- [ ] "Ask your meetings" (semantic search across transcripts) — high value, high complexity; ownscribe's approach with two-stage LLM + keyword fallback is the reference implementation

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Mic + system audio capture | HIGH | HIGH | P1 |
| Whisper transcription | HIGH | MEDIUM | P1 |
| Claude summarization (structured) | HIGH | MEDIUM | P1 |
| Obsidian markdown output | HIGH | LOW | P1 |
| Ctrl+C clean stop | HIGH | LOW | P1 |
| Map-reduce for long meetings | HIGH | MEDIUM | P1 |
| Summary cache | MEDIUM | LOW | P1 |
| WAV → Opus conversion | MEDIUM | LOW | P1 |
| Re-transcribe / re-summarize commands | HIGH | LOW | P1 |
| Config + first-run onboarding | HIGH | LOW | P1 |
| Audio device disconnect handling | MEDIUM | MEDIUM | P1 |
| `meetcap list` | LOW | LOW | P2 |
| Silence auto-stop | LOW | MEDIUM | P2 |
| Transcription progress display | LOW | LOW | P2 |
| Speaker diarization | HIGH | HIGH | P3 |
| Local LLM (Ollama) | MEDIUM | HIGH | P3 |
| Automatic meeting detection | LOW | HIGH | P3 |
| Semantic transcript search | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for launch — tool is broken without it
- P2: Should have — add in v1.x after core loop validated
- P3: Nice to have — v2+ consideration

---

## Competitor Feature Analysis

Key competitors analyzed: Ownscribe (local-first CLI), Meetily (local GUI), Granola (local macOS app), Otter.ai (SaaS), Fireflies.ai (SaaS).

| Feature | Ownscribe (CLI) | Granola (macOS) | Otter (SaaS) | meetcap approach |
|---------|-----------------|-----------------|--------------|------------------|
| Audio capture | System audio via Core Audio Tap (macOS 14.2+) | In-process transcription, no stored audio | Bot joins call OR local app | ScreenCaptureKit (macOS 13+) + WASAPI (Windows) — broader OS support than ownscribe |
| Transcription | WhisperX (word-level timestamps) | Real-time on-device | Cloud ASR | faster-whisper large-v3 with VAD — comparable accuracy, simpler dependency |
| Summarization | Local LLM (Phi-4-mini), Ollama, OpenAI-compatible | Cloud LLM | Cloud LLM | Claude API — higher quality than local LLM, privacy preserved (transcript only, not audio) |
| Speaker diarization | Yes (pyannote, optional) | No | Yes (cloud) | Deferred to v2 |
| Output format | Markdown in configured folder | In-app notes, export | In-app + integrations | Obsidian vault markdown with YAML frontmatter — directly usable in existing workflow |
| Search / query | "Ask your meetings" NLP query | Chat with transcript | Search + AI query | Not in v1; transcript JSON enables future search |
| Privacy | Audio stays local, LLM local | Audio not stored, cloud LLM | Audio sent to cloud | Audio stays local, only transcript text to Claude |
| Install | Python CLI | macOS app | SaaS / browser extension | `pipx install meetcap` — single command |
| Config | CLI flags + templates | In-app settings | Account settings | TOML file at platform path + env vars |
| Windows support | No (macOS 14.2+ only) | No | Yes (web) | Yes (WASAPI loopback) — key differentiator vs ownscribe |

**Key differentiation for meetcap:**
- Windows support + macOS 13+ (vs ownscribe's macOS 14.2+ only)
- Claude API for summarization quality (vs ownscribe's local LLM)
- Native Obsidian vault output (vs generic markdown folder)
- Single `pipx install` — no drivers, no setup (vs Meetily's Rust/GUI complexity)

---

## Sources

- [Ownscribe (local-first CLI, open source)](https://github.com/paberr/ownscribe) — feature reference for local CLI meeting tool
- [Meetily (Rust-based, local GUI)](https://github.com/Zackriya-Solutions/meetily) — speaker diarization + Ollama patterns
- [Best Meeting Transcription Software 2026](https://meetingnotes.com/blog/best-meeting-transcription-software) — table stakes feature baseline
- [Top 10 AI Meeting Assistants 2026](https://krisp.ai/blog/best-ai-meeting-assistant/) — differentiator landscape
- [Granola AI Review 2026](https://tldv.io/blog/granola-review/) — local-first macOS app comparison
- [VAD vs Speaker Diarization in Whisper](https://www.f22labs.com/blogs/what-is-vad-and-diarization-with-whisper-models-a-complete-guide/) — technical pipeline patterns
- [WhisperX GitHub](https://github.com/m-bain/whisperx) — word-level timestamps, diarization approach
- [Obsidian Meeting Workflows](https://char.com/blog/obsidian-meeting-notes/) — Obsidian-native output format expectations
- [Open Source Meeting Transcription Tools 2026](https://anarlog.so/blog/open-source-meeting-transcription-software/) — ecosystem overview

---
*Feature research for: meeting recorder / summarizer CLI (meetcap)*
*Researched: 2026-05-09*
