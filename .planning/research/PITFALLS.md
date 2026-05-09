# Pitfalls Research

**Domain:** Meeting auto-recorder and summarizer CLI (Python, macOS/Windows, local Whisper, Claude API)
**Researched:** 2026-05-09
**Confidence:** HIGH (most pitfalls verified against official issues trackers, PyObjC bugs, faster-whisper discussions, and Apple developer forums)

---

## Critical Pitfalls

### Pitfall 1: ScreenCaptureKit SCStream Stops Immediately on macOS 15

**What goes wrong:**
SCStream starts without error, then stops within milliseconds. The error is `SCStreamErrorDomain Code=-3805 "connectionInvalid"`. No audio is captured. The process exits silently or appears to succeed while writing zero bytes.

**Why it happens:**
A confirmed PyObjC regression on macOS 15 (tracked in ronaldoussoren/pyobjc#647). The SCStream delegate object gets garbage-collected by Python before the stream fires its first callback, because PyObjC does not automatically retain Objective-C delegates. The run loop may also not be spinning in the thread where the stream was created.

**How to avoid:**
- Hold a strong Python reference to the SCStream delegate object for the lifetime of the recording (store it on a long-lived object, not a local variable).
- Ensure the run loop is spinning (`NSRunLoop.currentRunLoop().run()` or a CF run loop) on the thread that creates the stream.
- Pin PyObjC and pyobjc-framework-ScreenCaptureKit to a known-good version and test explicitly on macOS 15.
- Add a health check: if no audio callback fires within 2 seconds of stream start, raise a loud error instead of silently recording silence.

**Warning signs:**
- `stream.startCapture()` returns without error but callbacks never fire.
- Output WAV file is all zeros or has duration 0.
- No Python exception is raised.

**Phase to address:** Audio capture phase (Phase 1). Write a smoke test that validates at least one audio callback fires before proceeding.

---

### Pitfall 2: WAV Recording Hits the 4 GB RIFF Header Limit

**What goes wrong:**
Long meetings (3+ hours) at 48kHz stereo 16-bit = ~1 GB/hour. At 4+ hours the standard RIFF WAV header overflows its 32-bit size field. Python's `wave` module writes a corrupt file silently. The file appears to exist but transcription fails with a cryptic error or produces garbled output.

**Why it happens:**
WAV's RIFF container uses a 32-bit unsigned int for chunk sizes (max 4 GiB, but many tools cap at 2 GiB with signed interpretation). Python's stdlib `wave` module does not handle size overflow or RF64 format automatically.

**How to avoid:**
- Use `soundfile` (libsndfile) for writing, which handles large files correctly and supports RF64 automatically above the limit.
- Alternatively, record in segments (e.g., 30-minute rolling chunks) and concatenate before transcription.
- For the project's 1-2 hour meeting use case this is unlikely to trigger, but defensive code costs nothing: check file size periodically and warn if approaching 3 GB.

**Warning signs:**
- Meetings longer than ~2.5 hours.
- `wave.open()` raising `Error: file size doesn't fit in a 32-bit integer` during read-back.
- Transcription returning empty or garbage output on long recordings.

**Phase to address:** Audio capture phase (Phase 1). Choose `soundfile` over stdlib `wave` from the start.

---

### Pitfall 3: Whisper Hallucination on Silence and Background Noise

**What goes wrong:**
faster-whisper generates plausible-sounding text that was never spoken — commonly repeated phrases, filler text ("Thank you for watching"), or invented dialogue. This is worst during silence, low-volume gaps, keyboard noise, or hold music. A confirmed research finding: hallucination rate rises sharply on audio segments with no speech (arxiv 2501.11378).

**Why it happens:**
Whisper processes audio in 30-second windows. If a window has no speech, the model still tries to produce tokens. Without VAD pre-filtering, these silence windows are fed directly to the decoder. The model is trained to always output something.

**How to avoid:**
- Always enable `vad_filter=True` in faster-whisper. This uses Silero VAD to skip non-speech segments before decoding.
- Set `vad_parameters={"min_silence_duration_ms": 500}` to tune aggressiveness.
- Set `no_speech_threshold=0.6` as a secondary check.
- Do NOT rely solely on `no_speech_prob` from Whisper itself — the VAD model is more reliable for this signal.
- Before transcription, strip leading/trailing silence with a simple energy threshold (pydub or librosa).

**Warning signs:**
- Transcripts contain phrases that clearly were not said.
- Repeated sentences or phrases in the transcript.
- Transcript length far exceeds what a meeting of that duration would produce.
- High `no_speech_prob` values in the segment metadata that were ignored.

**Phase to address:** Transcription phase (Phase 2). VAD must be enabled from day one, not added later as a fix.

---

### Pitfall 4: Ctrl+C Loses the Last Audio Buffer

**What goes wrong:**
User hits Ctrl+C. Python raises `KeyboardInterrupt`. The audio recording thread is mid-buffer. The last 0.5–2 seconds of the meeting are dropped. If the recording was very short (e.g., a quick standup), the cut can be meaningful. Worse, if the WAV write handle is not closed cleanly, the RIFF header is never finalized and the file is unreadable.

**Why it happens:**
`sounddevice` uses a callback-based model running in a C-level thread. When Python raises `KeyboardInterrupt`, the main thread exits without waiting for the audio callback queue to drain. The `wave.Wave_write.close()` call never executes, leaving the RIFF size fields at zero.

**How to avoid:**
- Use a threading `Event` for graceful shutdown: set the event in a `signal.signal(SIGINT, handler)` handler, have the recording loop check `event.is_set()`, then drain and close cleanly.
- Use a `try/finally` block that always calls `stream.stop()`, `stream.close()`, and the file writer's `close()` method.
- After the stream stops, wait for the callback queue to drain (100ms sleep is sufficient).
- Validate the output file is readable immediately after writing before proceeding to transcription.

**Warning signs:**
- WAV file has 0-byte RIFF size in header (check with `soxi` or `soundfile.info()`).
- Transcription fails on the file written during an interrupted session.
- Missing final words from recordings that were Ctrl+C'd.

**Phase to address:** Audio capture phase (Phase 1). Implement the signal handler before anything else; it is load-bearing for correctness.

---

### Pitfall 5: WASAPI Loopback Is Not Supported by stock sounddevice

**What goes wrong:**
On Windows, `sounddevice` (which wraps stock PortAudio) cannot capture system audio via WASAPI loopback. The device list shows no loopback devices. The developer tries to use a WASAPI device as input and gets `Invalid device` or records silence.

**Why it happens:**
PortAudio's upstream does not expose WASAPI loopback without a custom patch. `sounddevice` wraps unpatched PortAudio. This is a documented open issue (spatialaudio/python-sounddevice#281, still open as of 2025).

**How to avoid:**
- Use `PyAudioWPatch` (pip installable) instead of `sounddevice` for the Windows system audio capture path. It ships a pre-patched PortAudio binary that exposes loopback devices.
- Make the audio backend platform-conditional: `sounddevice`/PyObjC for macOS, `PyAudioWPatch` for Windows.
- Do not try to make a single unified audio capture class — the backends are fundamentally different. Use an abstract interface with platform-specific implementations.

**Warning signs:**
- No "Loopback" suffix in the device list on Windows.
- `sounddevice.query_devices()` on Windows shows only physical input devices.
- System audio capture returns silence while microphone capture works.

**Phase to address:** Audio capture phase (Phase 1). Decide the Windows backend before writing any audio code; retrofitting is painful.

---

### Pitfall 6: Microphone and System Audio Sample Rate Mismatch Causes Drift

**What goes wrong:**
Microphone runs at 44100 Hz, system audio (ScreenCaptureKit or WASAPI) runs at 48000 Hz. Both are recorded simultaneously and mixed. After 30 minutes, they are 41 seconds out of sync. The mixed audio has pitch-shifted artifacts. Whisper produces interleaved garbled text from both speakers.

**Why it happens:**
Different audio sources have different native sample rates. Mixing audio streams without resampling to a common rate first causes the drift to compound linearly over time.

**How to avoid:**
- Decide on a canonical sample rate (48000 Hz) before any audio code is written.
- Resample the microphone stream to 48000 Hz at capture time using `samplerate` library (libsamplerate) — do it in the callback, not post-hoc.
- Alternatively, configure the microphone device to 48000 Hz explicitly when opening the stream (most modern mics support it).
- Whisper expects 16000 Hz — resample the final mixed audio to 16000 Hz before passing to faster-whisper, not before mixing.

**Warning signs:**
- Mixed audio sounds like two people talking at slightly different speeds.
- Transcription quality degrades significantly in the second half of long recordings.
- `sounddevice.query_devices()` shows different `default_samplerate` values for mic vs. output device.

**Phase to address:** Audio capture phase (Phase 1). Sample rate unification must be part of the initial audio pipeline design.

---

### Pitfall 7: faster-whisper large-v3 Runs on CPU Only on Apple Silicon

**What goes wrong:**
Developer expects GPU acceleration on an Apple Silicon Mac. faster-whisper's CTranslate2 backend only supports CUDA (NVIDIA) for GPU inference. On Apple Silicon, it falls back to CPU. A 60-minute meeting transcript takes 10–15 minutes on CPU instead of 2–3 minutes.

**Why it happens:**
CTranslate2 supports Apple's Accelerate framework for CPU BLAS optimizations but does not support Metal or MPS (Metal Performance Shaders). faster-whisper has a documented open issue for this (SYSTRAN/faster-whisper#515, open as of 2025).

**How to avoid:**
- Accept CPU-only on Apple Silicon for v1. For a personal tool with sub-2-hour meetings, 5–10 minute transcription is acceptable.
- Use `int8` quantization (`compute_type="int8"`) to cut CPU time by ~50% with minimal accuracy loss.
- Set `num_workers=4` and `cpu_threads=4` to use multiple cores.
- Do NOT switch to whisper.cpp for Metal acceleration unless you're willing to drop the Python-native path — the integration complexity negates the speed gain for a personal tool.
- Document the expected transcription time so the user (yourself) is not surprised.

**Warning signs:**
- Transcription progress bar is unexpectedly slow.
- `nvidia-smi` shows 0% GPU utilization during transcription on macOS (expected — there is no NVIDIA GPU).

**Phase to address:** Transcription phase (Phase 2). Set compute config in the first transcription implementation; do not defer.

---

### Pitfall 8: Map-Reduce Summarization Loses Cross-Chunk Context

**What goes wrong:**
For meetings > 30 minutes, the transcript is chunked and each chunk summarized independently. The final reduce step asks Claude to synthesize summaries. Action items that span two chunks ("we'll discuss X next week, Alice will prepare the report") are lost because neither chunk contains the full context. Decisions that reference earlier discussion are summarized without their rationale.

**Why it happens:**
Hard chunk boundaries split conversational context. A reduce prompt that asks "combine these summaries" does not reconstruct the original conversational flow.

**How to avoid:**
- Use overlapping chunks: each chunk includes the last 200 tokens of the previous chunk as context prefix.
- In the map prompt, instruct Claude to extract structured fields (decisions, action items, key points) not prose summaries. Structured extraction is more robust to context loss than narrative summarization.
- In the reduce prompt, deduplicate structured fields by semantic similarity, not string matching.
- Cache summaries by transcript hash (as planned) to avoid redoing expensive map-reduce on retry.
- For meetings under ~60 minutes, a single-pass summary is cheaper and better — only use map-reduce above a configurable threshold (e.g., 15,000 tokens).

**Warning signs:**
- Action items in the final summary reference people or topics not mentioned nearby.
- The same action item appears twice with slightly different wording.
- Summaries of short meetings (< 30 min) are poor quality despite a long context window.

**Phase to address:** Summarization phase (Phase 3). Design the chunking strategy before implementation; it cannot be trivially bolted on.

---

### Pitfall 9: Screen Recording Permission Silently Not Granted

**What goes wrong:**
On macOS, ScreenCaptureKit requires Screen Recording permission in System Preferences > Privacy & Security. If the permission is not granted, `SCShareableContent.getWithCompletionHandler` returns an empty list or fails silently. The recording starts (no exception) but captures no system audio. On macOS 15, the TCC prompt may not appear at all for CLI tools not bundled as `.app`.

**Why it happens:**
TCC (Transparency, Consent, and Control) permission prompts are triggered by the bundle identifier of the requesting app. A CLI Python script run via Terminal may inherit Terminal's permissions, or may not trigger the prompt at all if the calling process is already privileged. The behavior changed between macOS versions.

**How to avoid:**
- At startup, explicitly check if screen recording permission is granted before attempting capture. Use the `Quartz` framework or check `SCShareableContent` result length as a proxy.
- If permission is missing, print a clear human-readable error with exact navigation path: "Open System Settings > Privacy & Security > Screen Recording, enable 'Terminal' (or 'meetcap'), then restart."
- Do not silently continue — fail fast with a clear message.
- For the Windows path, WASAPI loopback has no equivalent permission barrier, so this check is macOS-only.

**Warning signs:**
- `SCShareableContent` returns empty list on first run.
- System audio output recorded as silence while microphone works.
- No TCC dialog appears on first run.

**Phase to address:** Audio capture phase (Phase 1). The permission check and error message must exist before any demo or manual test.

---

### Pitfall 10: Obsidian Vault Write Race Condition or Path Escaping

**What goes wrong:**
The markdown file is written to the Obsidian vault while Obsidian is actively watching the folder. On macOS, this usually works fine. On Windows, Obsidian may hold a file lock on the vault folder during indexing, causing a write failure. Additionally, meeting titles with special characters (`/`, `:`, `?`, `"`) become illegal filenames on Windows, silently corrupting the filename or raising an unhandled exception.

**Why it happens:**
The filename is derived from the meeting title (user-supplied or Claude-generated). Claude may produce titles with colons or slashes. Windows NTFS rejects these characters in filenames. Python's `pathlib` on macOS accepts them but Windows raises `OSError`.

**How to avoid:**
- Sanitize filenames on both platforms: replace `/ : * ? " < > |` and `\` with `-` or `_`. Use a dedicated `sanitize_filename()` utility.
- Write to a temp file first, then rename atomically to the final path.
- Wrap vault writes in retry logic (3 retries, 100ms backoff) to handle transient Obsidian lock conflicts.
- Validate the vault path exists and is writable at startup, not at write time.

**Warning signs:**
- `OSError: [Errno 22] Invalid argument` on Windows during file write.
- Files written with garbled names in the vault.
- Write failure on first run because vault path was not pre-validated.

**Phase to address:** Obsidian integration phase (Phase 4). Implement filename sanitization from the first write, not as a follow-up fix.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use stdlib `wave` module for recording | No extra dependency | Silent corruption on files > 2 GB | Never — use `soundfile` from day one |
| Single audio backend for both platforms | Simpler code | Impossible to implement correctly (WASAPI loopback requires PyAudioWPatch on Windows) | Never |
| No VAD filter in faster-whisper | Simpler transcription call | Hallucinated text in every meeting with silence gaps | Never |
| Skip Ctrl+C signal handler, rely on KeyboardInterrupt | Faster initial build | Corrupt WAV files on every interrupted recording | Never for the recording path |
| Hard-code sample rate without resampling | Simpler initial code | Audio drift and pitch artifacts on mixed recordings | Never |
| No filename sanitization | Simpler string formatting | Windows crashes on first meeting with a colon in the title | Never |
| No permission check at startup | Faster first run | Silent recording of silence with no error on macOS | Never |
| Single-pass summarization for all lengths | Simpler code | Token limit errors on long meetings; poor quality on very long calls | Acceptable for v1 if threshold is configurable |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ScreenCaptureKit via PyObjC | Letting the SCStream delegate get garbage-collected | Store delegate as instance attribute on a long-lived object; keep strong reference |
| ScreenCaptureKit via PyObjC | Creating the stream on a thread without a run loop | Spin `NSRunLoop.currentRunLoop().run()` on the capture thread |
| PyAudioWPatch (Windows WASAPI) | Iterating `p.get_device_info_by_index()` for loopback devices the same way as regular devices | Loopback devices appear duplicated at the end of the list with `isLoopbackDevice=True` — filter by that flag |
| faster-whisper | Loading the model inside the recording loop | Load once at startup; model load takes 5–10 seconds |
| faster-whisper | Passing raw WAV bytes | Pass the file path or a 16kHz float32 numpy array; the library handles chunking internally |
| Claude API | Sending the full transcript as a single user message for very long meetings | Use map-reduce with overlap; a 90-minute meeting transcript is ~50K tokens |
| Claude API | No retry on rate limit or transient 5xx | Implement exponential backoff; the Anthropic SDK has built-in retry but it must be configured |
| Obsidian vault | Writing directly to vault root | Always write to a subfolder (`Meetings/`) to avoid cluttering vault root and conflicting with Obsidian's own files |
| Anthropic SDK | Reading `ANTHROPIC_API_KEY` only at import time | Read at invocation time so the user can set the env var after install without reinstalling |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading faster-whisper large-v3 model on every transcription call | 10–15s startup delay per `meetcap transcribe` invocation | Load model once, cache in memory for the duration of the CLI command | Every call — large-v3 is ~1.5 GB |
| Not streaming audio to disk — buffering in memory | OOM kill after 30+ minutes (raw WAV is ~170 MB/min at 48kHz stereo) | Write audio chunks to disk in the callback, never accumulate in RAM | Roughly 20 minutes at 48kHz stereo 16-bit on a 4 GB RAM machine |
| Transcribing the full mixed audio file when only the microphone matters | Worse transcription quality (system audio adds noise) | Consider transcribing the microphone channel only, or the mix — test both | Quality trap, not a scale trap |
| Running faster-whisper with `beam_size=5` (default) on CPU | Transcription 3–5x slower than needed | `beam_size=1` or `beam_size=3` cuts time significantly with minimal WER increase on clean speech | Every CPU transcription run |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging the full transcript to stdout or a log file | Sensitive meeting content exposed in shell history or log rotation | Never log transcript content; log only metadata (duration, word count, file path) |
| Storing `ANTHROPIC_API_KEY` in the TOML config file | API key leaked if vault is synced to cloud (iCloud, Dropbox, Obsidian Sync) | Keys from environment variables only, never written to config file; document this clearly |
| Writing the transcript to the Obsidian vault alongside the summary | Vault may be synced to cloud, sending raw transcript to Obsidian Sync servers | Make transcript storage opt-in; default to storing only the summary markdown |
| No validation of the vault path in config | Path traversal if config is tampered with | Resolve and canonicalize the vault path at config write time; reject paths outside expected locations |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress indicator during transcription | User thinks the tool is frozen for 5–10 minutes on CPU | Print elapsed time and a spinner; faster-whisper yields segments as they complete — print each segment live |
| Silent success with no confirmation | User not sure if the note was written | Always print the full path of the written markdown file on success |
| First-run config prompts buried in error output | User confused on first install | First-run wizard: prompt for vault path, validate it, write config, then confirm "You're ready. Run `meetcap` to start recording." |
| No feedback on permission errors | macOS: silent failure looks like a bug | Detect missing Screen Recording permission and print a specific, actionable error with exact System Settings navigation path |
| `meetcap list` shows nothing if vault doesn't exist yet | Confusing on fresh install | Show a "No recordings yet. Run `meetcap` to start." message instead of an empty list or an error |

---

## "Looks Done But Isn't" Checklist

- [ ] **Audio capture:** Verify the output WAV is not all-zeros by checking RMS energy before transcription — a zero-energy file means silent capture, not a successful recording.
- [ ] **System audio capture (macOS):** Verify at least one ScreenCaptureKit audio callback fires within 2 seconds of stream start, not just that `startCapture()` returned without error.
- [ ] **Whisper VAD:** Verify `vad_filter=True` is active by checking that a silence-only recording produces zero or near-zero transcript tokens, not hallucinated text.
- [ ] **Ctrl+C handling:** Verify the output WAV is readable with `soundfile.info()` after an interrupted recording — a valid RIFF header means the file was closed cleanly.
- [ ] **Filename sanitization:** Verify meeting titles containing `: / * ? "` produce valid filenames on both macOS and Windows.
- [ ] **Map-reduce summarization:** Verify that action items assigned at the end of a meeting appear in the final summary even when the meeting is chunked — test with a 45-minute synthetic transcript.
- [ ] **Obsidian write:** Verify the markdown file opens in Obsidian with correct frontmatter (YAML valid, no unescaped colons in values).
- [ ] **Cache by hash:** Verify that re-running `meetcap summarize <file>` on an already-summarized transcript returns the cached result and does not make an API call.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| SCStream stops immediately (macOS 15) | HIGH | Update PyObjC version; audit delegate lifetime; add run loop; re-test on macOS 15 device |
| Corrupt WAV from Ctrl+C | LOW | Re-record; the meeting audio is lost but the tool itself is not broken |
| Whisper hallucination in existing transcript | LOW | Re-run `meetcap transcribe <file>` with VAD enabled; overwrite the transcript |
| Wrong sample rate causing drift | HIGH | Rewrite audio pipeline with explicit resampling; existing recordings are usable but mixed audio quality is degraded |
| WASAPI loopback not working on Windows | MEDIUM | Swap `sounddevice` for `PyAudioWPatch` on the Windows code path; no audio API is shared between platforms anyway |
| Claude API rate limit during summarization | LOW | Add exponential backoff retry in the summarization module; existing transcript is safe |
| Vault write failure | LOW | File is written to a temp path; user can manually move it |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| SCStream stops immediately (macOS 15) | Phase 1: Audio Capture | Smoke test: confirm audio callback fires within 2s; check output file RMS > 0 |
| WAV 4 GB limit | Phase 1: Audio Capture | Use `soundfile` not stdlib `wave`; add file size warning at 3 GB |
| Whisper hallucination | Phase 2: Transcription | Enable VAD from first implementation; test with silence-only audio |
| Ctrl+C buffer flush | Phase 1: Audio Capture | Implement signal handler before first manual test |
| WASAPI loopback not in sounddevice | Phase 1: Audio Capture | Choose `PyAudioWPatch` for Windows before writing any audio code |
| Sample rate mismatch | Phase 1: Audio Capture | Define canonical 48kHz pipeline; add resampling in callback |
| faster-whisper CPU-only on Apple Silicon | Phase 2: Transcription | Use `int8` + `cpu_threads=4`; document expected time |
| Map-reduce context loss | Phase 3: Summarization | Design chunking with overlap before implementation |
| Screen recording permission silent failure | Phase 1: Audio Capture | Add permission check at startup with actionable error message |
| Obsidian filename sanitization | Phase 4: Vault Integration | Implement `sanitize_filename()` on first write |

---

## Sources

- PyObjC SCStream issue (macOS 15, Code=-3805): https://github.com/ronaldoussoren/pyobjc/issues/647
- faster-whisper Apple Silicon / Metal GPU issue: https://github.com/SYSTRAN/faster-whisper/issues/515
- faster-whisper hallucination with Silero VAD: https://github.com/SYSTRAN/faster-whisper/issues/843
- Whisper hallucination on silence research (arxiv 2501.11378): https://arxiv.org/html/2501.11378v1
- Whisper hallucination prevention community discussion: https://github.com/openai/whisper/discussions/679
- sounddevice WASAPI loopback not supported: https://github.com/spatialaudio/python-sounddevice/issues/281
- PyAudioWPatch for WASAPI loopback: https://github.com/s0d3s/PyAudioWPatch
- WAV 4 GB RIFF limit: https://en.wikipedia.org/wiki/WAV
- sounddevice Ctrl+C audio recording: https://github.com/spatialaudio/python-sounddevice/issues/160
- faster-whisper Apple Silicon discussion: https://github.com/SYSTRAN/faster-whisper/discussions/1227
- macOS TCC screen recording permissions: https://developer.apple.com/forums/thread/760483

---
*Pitfalls research for: meeting auto-recorder and summarizer CLI (meetcap)*
*Researched: 2026-05-09*
