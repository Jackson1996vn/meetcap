# Phase 1: Foundation - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a working Python package that installs via `pipx install .`, provides a `meetcap` CLI entry point with click, and includes a TOML-based config system with first-run interactive setup. Recording itself is stubbed — this phase builds the shell that Phase 2 and 3 will fill.

</domain>

<decisions>
## Implementation Decisions

### Package & Build Setup
- **D-01:** Use `uv` as the build tool with `pyproject.toml` configuration
- **D-02:** Entry point registered as `[project.scripts] meetcap = "meetcap.cli:main"`

### Claude's Discretion
- Project layout (src/meetcap/ vs flat meetcap/) — Claude picks best approach

### Config System
- **D-03:** User must explicitly configure recordings directory — no silent defaults. Config is set either via first-run interactive prompt or via `meetcap config`
- **D-04:** Config file is TOML format at platform-appropriate path (use `platformdirs` for cross-platform resolution)
- **D-05:** Required config keys for milestone 1: `recordings_dir`
- **D-06:** API keys are read from environment variables only, never stored in config file

### CLI Behavior
- **D-07:** When user runs `meetcap` with no config, show interactive prompt asking for required settings (recordings directory), save to config, then proceed
- **D-08:** When user runs `meetcap` without a title, auto-generate a timestamp-based title (e.g., `2026-05-09-1430`) — no prompt, just start
- **D-09:** `meetcap "<title>"` accepts a user-provided title for the recording session

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements fully captured in decisions above

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project

### Established Patterns
- None — first phase establishes patterns

### Integration Points
- Entry point will be extended by Phase 2 (platform backends) and Phase 3 (recording pipeline)
- Config system will be extended in milestone 2 (vault_dir, llm_provider, whisper_model)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-05-09*
