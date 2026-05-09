---
phase: 01-foundation
plan: "02"
subsystem: cli
tags: [python, toml, platformdirs, tomllib, tomli-w, click, config]

requires:
  - phase: 01-01
    provides: Installable meetcap package with click CLI entry point and all runtime deps declared

provides:
  - TOML config module (config.py) with load_config, save_config, run_first_run_wizard, CONFIG_FILE
  - platformdirs-based config path (~/Library/Application Support/meetcap/config.toml on macOS)
  - First-run wizard that prompts for recordings_dir, expands/resolves path, saves to TOML
  - Config-wired CLI: first run triggers wizard, subsequent runs load config silently
  - 'meetcap config' subcommand displaying current key=value settings

affects:
  - 02-01 (recording backends use recordings_dir from config)
  - future milestone 2 (vault_dir, llm_provider, whisper_model keys added to same config)

tech-stack:
  added:
    - tomllib (stdlib, Python 3.11+) for TOML reading in binary mode
    - tomli-w 1.2.0 for TOML writing in binary mode
    - platformdirs 4.9.6 for OS-appropriate config directory resolution
  patterns:
    - Config module returns None (not silent default) when file missing — forces wizard path
    - Binary mode ("rb"/"wb") for all TOML read/write operations
    - Path.expanduser().resolve() before storing any user-provided path
    - Config dir created with mkdir(parents=True, exist_ok=True) before first write
    - Subcommand routing guard for click TITLE argument vs subcommand name collision

key-files:
  created:
    - src/meetcap/config.py
  modified:
    - src/meetcap/cli.py

key-decisions:
  - "load_config() returns None (not a default dict) so caller always triggers the wizard — no silent defaults per D-03"
  - "CONFIG_FILE uses platformdirs.user_config_dir('meetcap') — resolves to ~/Library/Application Support/meetcap/ on macOS"
  - "click TITLE argument vs 'config' subcommand collision fixed by explicit subcommand forwarding check in main()"
  - "recordings_dir stored as absolute resolved path (expanduser().resolve()) to prevent Phase 2 path confusion"

patterns-established:
  - "Pattern 4: Config module owns all OS path logic — CLI calls load_config()/save_config() without knowing file location"
  - "Pattern 5: First-run wizard as a discrete function (run_first_run_wizard) callable from CLI or future config subcommand"
  - "Pattern 6: click group + positional TITLE arg + subcommands — explicit subcommand name forwarding guard in group callback"

requirements-completed:
  - CLI-02
  - CLI-03

duration: 3min
completed: 2026-05-09
---

# Phase 01 Plan 02: TOML Config System and First-Run Wizard Summary

**TOML config at platformdirs path with first-run interactive wizard for recordings_dir — subsequent runs load config silently, `meetcap config` shows settings**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-09T10:50:46Z
- **Completed:** 2026-05-09T10:53:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- config.py created with load_config (returns None when missing), save_config (binary TOML write), run_first_run_wizard (click.prompt + expanduser/resolve + mkdir)
- cli.py wired to config: first run triggers wizard, subsequent runs proceed directly to recording stub with output path displayed
- 'meetcap config' subcommand correctly routed and displays recordings_dir value

## Task Commits

Each task was committed atomically:

1. **Task 1: Create config module with load, save, and first-run wizard** - `b52aeae` (feat)
2. **Task 2: Wire config loading and first-run wizard into CLI** - `97b34f7` (feat)

**Plan metadata:** (docs commit — created after summary)

## Files Created/Modified

- `src/meetcap/config.py` - Config lifecycle: CONFIG_FILE path via platformdirs, load_config (rb mode), save_config (wb mode + mkdir), run_first_run_wizard (click.prompt + expanduser/resolve)
- `src/meetcap/cli.py` - Wired to config: load on startup, wizard on None, recordings_dir in output, 'config' subcommand, subcommand routing guard

## Decisions Made

- `load_config()` returns `None` (not a default dict) so the caller always knows to trigger the wizard — enforces D-03 (no silent defaults)
- `click` TITLE positional argument parsing conflict with the `config` subcommand name required an explicit forwarding guard in `main()` — checks `if title in main.commands` before proceeding with recording logic
- `recordings_dir` stored as absolute resolved path using `.expanduser().resolve()` — prevents Phase 2 from encountering relative path confusion (per Pitfall 5 in research)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed click TITLE argument consuming 'config' subcommand token**
- **Found during:** Task 2 (wiring CLI) — post-implementation verification
- **Issue:** `meetcap config` treated "config" as the TITLE positional argument instead of routing to the `config` subcommand. The plan and research both document this as Pitfall 4 but the provided code template did not include the fix.
- **Fix:** Added an explicit guard at the top of `main()`: if `title` matches a registered subcommand name, invoke that subcommand and return. This is the standard pragmatic fix for `invoke_without_command=True` + positional TITLE groups in click.
- **Files modified:** src/meetcap/cli.py
- **Verification:** `uv run meetcap config` now displays `recordings_dir = '...'` correctly; `uv run meetcap "My Meeting"` still works; `uv run meetcap` still generates timestamp title
- **Committed in:** 97b34f7 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — click routing collision)
**Impact on plan:** Fix was necessary for the config subcommand to be reachable at all. No scope creep.

## Issues Encountered

- click's positional argument parsing for a group with `invoke_without_command=True` and a `[TITLE]` argument consumes the first token even when it matches a subcommand name. Resolved with explicit subcommand name check in the group callback. The research documented this as Pitfall 4 but the plan template did not include the fix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Full config lifecycle is operational: first-run wizard, TOML persistence, silent reload, and display subcommand
- Phase 2 recording backends can read `config["recordings_dir"]` directly from `load_config()`
- The config module is extensible — milestone 2 keys (vault_dir, llm_provider, whisper_model) can be added to the same config dict and TOML file without structural changes

---
*Phase: 01-foundation*
*Completed: 2026-05-09*
