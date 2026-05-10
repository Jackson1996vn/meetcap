# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`meetcap` is a personal cross-platform CLI that records meetings (mic + system audio), transcribes locally with Whisper, summarizes with an LLM, and writes a markdown note to an Obsidian vault. The tool is being built milestone-by-milestone:

- **Milestone 1 — Audio capture** (current). Phase 1 (foundation) and Phase 2 (platform backends) are complete; Phase 3 (recording pipeline: dual-stream mixer, Ctrl+C handling, WAV writer) is **not started**. The CLI's recording path today is a stub that prints "not yet implemented — stub for Phase 2".
- **Milestone 2** — transcription + summarization + Obsidian output (not started).
- **Milestone 3** — live captions (not started).

Authoritative status lives in `.planning/STATE.md` and `.planning/ROADMAP.md`. Re-read them before doing milestone work — they may have moved on since this file was written.

## Toolchain & commands

Python 3.11+ (the code uses `tomllib`) with `uv` for dependency management. The build backend is `uv_build` and the entry point is `meetcap = "meetcap.cli:main"`.

```bash
uv sync                       # install runtime + platform deps from uv.lock
uv pip install -e .           # editable install so the `meetcap` script works
meetcap                       # run the CLI (triggers first-run wizard if no config)
meetcap "Some title"          # record with an explicit title
meetcap config                # print current config

uv run python -c "from meetcap.audio.backends import get_backend; b=get_backend(); print(type(b).__name__)"
# Quick sanity check that the platform backend imports on this OS.
```

There is **no test suite, no `ruff`/`mypy` config, and no Makefile/CI** in the repo today. Don't fabricate test commands — if you need tests, add them and the dev deps to `pyproject.toml` first. Phase 2 UAT tests are deferred (see `.planning/phases/02-platform-backends/02-UAT.md`); some require physical hardware (a Windows machine, a real mic) that the dev environment doesn't have.

Platform deps are conditional in `pyproject.toml`: `pyobjc-framework-*` only installs on `darwin`, `PyAudioWPatch`/`samplerate` only on `win32`. On Linux, `get_backend()` raises `NotImplementedError` — that's the design, not a bug.

## Architecture

```
src/meetcap/
├── cli.py              # click group + `meetcap [TITLE]` and `meetcap config`
├── config.py           # TOML at platformdirs.user_config_dir("meetcap")/config.toml
└── audio/
    └── backends/
        ├── __init__.py # SystemAudioBackend Protocol + get_backend() factory
        ├── macos.py    # SCStream via PyObjC (ScreenCaptureKit)
        └── windows.py  # WASAPI loopback via PyAudioWPatch
```

The big-picture design that requires reading multiple files to grasp:

- **`SystemAudioBackend` is a `typing.Protocol`** (`audio/backends/__init__.py`). Both implementations satisfy it structurally — there is no inheritance. Both deliver float32 mono numpy arrays at 48 kHz via a user-supplied callback. Phase 3 will consume this protocol; do not add audio-pipeline logic into the backend modules.
- **`get_backend()` is the only platform switch.** It dispatches on `sys.platform` and lazily imports the platform module so a non-darwin machine never tries to import `pyobjc`. Don't sprinkle `if sys.platform` checks elsewhere.
- **CLI title vs subcommand collision.** `meetcap` is a click group with a positional `TITLE` argument *and* registered subcommands. click parses the first token as `TITLE` before subcommand routing, so `cli.py` explicitly forwards to a subcommand when `title` matches a registered command name. Preserve this when adding subcommands or the dispatch breaks.
- **`load_config()` returns `None` (not a default dict)** when the config file is absent. The caller triggers `run_first_run_wizard()`. This is intentional — the project rule (D-03) is *no silent defaults*; absence is always surfaced.
- **`recordings_dir` is stored absolute and resolved.** The wizard runs `Path(input).expanduser().resolve()` before saving so later runs don't depend on `$HOME` or the user's CWD.

### macOS backend (`audio/backends/macos.py`) — load-bearing details

ScreenCaptureKit via PyObjC has well-known traps. Several non-obvious things in this file exist *because* of them — don't simplify them away:

- **Delegate retain (D-07).** `self._delegate` is held as an instance attribute on `MacOSAudioBackend`. PyObjC does not auto-retain ObjC delegates and macOS 15+ garbage-collects them mid-stream (PyObjC issue #647), causing silent zero-byte recordings. If you refactor delegate handling, the strong reference must outlive the stream.
- **`from objc import super`** at the top of the file is required to make `super().init()` work in the `NSObject` subclass. Don't replace it with the stdlib `super`.
- **No `@objc.python_method` / no decorator on `stream_didOutputSampleBuffer_ofType_` and `stream_didStopWithError_`.** Adding decorators that hide methods from the ObjC runtime causes zero callbacks. The naming convention (trailing underscores per arg) is what ObjC dispatches on.
- **Both screen and audio outputs are registered.** SCStream requires a screen output even when only audio is wanted, otherwise it errors with `-3805`. Screen frames are discarded in the delegate. Frame interval is set to 1 fps to minimize overhead.
- **TCC permission flow (D-09).** `_get_shareable_content_with_retry` calls `SCShareableContent.getShareableContentWithCompletionHandler_` twice: the first call detects missing permission (empty displays on macOS 13–15, error `-3801` on macOS 26.x); the second call triggers the TCC dialog and waits up to 30 s for the user to approve. Only after the *retry* fails do we raise `PermissionError` with an actionable message.
- **NSRunLoop thread (D-08).** Async ObjC callbacks need an active run loop on their thread. `_run_loop_thread` spins one while `self._running`. `stop()` joins with a timeout (T-02-04) so a hung run loop never blocks process exit.
- **CMSampleBuffer extraction.** The `(status, lengthAtOffset, dataLength, dataPtr)` tuple shape from `CMBlockBufferGetDataPointer` is the validated pattern on macOS 26.4. Sample count is capped at `_MAX_SAMPLES_PER_BUFFER = 48000` before numpy allocation (T-02-02) to bound memory.
- **Stereo→mono mixdown happens in the callback** (D-12) using the `audioStreamBasicDescription` channel count.
- **Logging is metadata-only** — frame counts, byte sizes, never raw PCM (T-02-03).

### Windows backend (`audio/backends/windows.py`)

- Uses `PyAudioWPatch` (a fork of PyAudio with WASAPI loopback patches). Stock `sounddevice` cannot do WASAPI loopback — don't try to swap it in.
- Stream format is `paInt16` (Pitfall 4 — paFloat32 was unreliable). Bytes are converted to float32 in the callback and normalized to `[-1, 1]`.
- Resampling: `samplerate` library with a `numpy.interp` fallback if the import fails. Target rate is the canonical 48 kHz.
- Buffer length is validated against `frame_count * channels * 2` before `np.frombuffer` (T-02-05).
- The loopback device is discovered by walking `get_loopback_device_info_generator()` and matching the default-output name. Don't iterate `get_device_info_by_index` — loopback devices appear as separate, name-suffixed entries.

## Project conventions

- **Decision tags `D-NN` and threat tags `T-NN-NN`** appear in code comments (e.g. `D-07`, `T-02-04`). They reference entries in `.planning/phases/*/0X-CONTEXT.md` and the phase RESEARCH/PLAN docs. When you change behavior covered by a `D-`/`T-` tag, update the relevant planning doc in the same change.
- **Audio canonical format is float32 mono 48 kHz** (D-11–D-13). Every backend converts to this before invoking the user callback. Don't introduce 16 kHz or stereo at the backend boundary; resample only at the Whisper input edge in Phase 3.
- **Pitfalls reference.** `.planning/research/PITFALLS.md` is the canonical list of known traps (delegate GC, WAV >4 GB, Whisper hallucination on silence, Ctrl+C buffer loss, sample-rate drift, TCC silent failures, …). Skim it before changing anything in `audio/`, transcription, or the recording pipeline. Items called out as "Phase to address: Phase 1" should already be handled by the time Phase 3 lands.
- **GSD planning workflow.** Phase work flows through `.planning/phases/<phase>/`: `*-CONTEXT.md` → `*-RESEARCH.md` → `*-N-PLAN.md` → implementation → `*-N-SUMMARY.md` → `*-VERIFICATION.md` / `*-UAT.md`. State is tracked in `.planning/STATE.md` and `.planning/ROADMAP.md` (front-matter `status:`, phase progress table). If you implement phase work, update the corresponding plan/summary and `STATE.md`.
- **Commit message style.** `<type>(<scope>): <subject>` with scopes that match phase IDs, e.g. `feat(02-02): …`, `docs(state): …`, `chore(02-02): …`. Match this style for new commits.
- **`src/` layout is deliberate** — it prevents accidental imports of un-installed packages. Always work via the editable install rather than adding `src/` to `sys.path`.

## Things to avoid

- Don't promote the `SystemAudioBackend` `Protocol` to an abstract base class or add inheritance — structural typing is the design.
- Don't add `if sys.platform` branches outside `audio/backends/__init__.py`.
- Don't load the Whisper model inside any per-call hot path (when Phase 2 of milestone 2 lands, model load is a singleton — see `ARCHITECTURE.md` Anti-Pattern 2).
- Don't use stdlib `wave` for WAV writing — Phase 3 will use `soundfile` (RF64 support, correct flush semantics). See Pitfall 2 / Pitfall 4.
- Don't store API keys or other secrets in `config.toml`. Keys come from environment variables (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) read at invocation time.
- Don't log raw PCM, transcripts, or audio buffer bytes — only metadata (T-02-03, T-02-06, and the Security Mistakes table in PITFALLS.md).
