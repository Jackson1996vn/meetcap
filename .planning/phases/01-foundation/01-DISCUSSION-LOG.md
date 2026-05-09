# Phase 1: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 01-foundation
**Areas discussed:** Package & build setup, Config system design, CLI behavior

---

## Package & Build Setup

| Option | Description | Selected |
|--------|-------------|----------|
| src/meetcap/ layout (Recommended) | Standard for pip-installable packages, prevents import issues | |
| Flat meetcap/ layout | Simpler but can cause import conflicts during development | |
| You decide | Claude picks the best approach | ✓ |

**User's choice:** You decide — Claude's discretion on project layout

| Option | Description | Selected |
|--------|-------------|----------|
| uv (Recommended) | Fastest resolver, lockfile, 2025 standard | ✓ |
| setuptools + pip | Traditional approach, broader compatibility | |
| You decide | Claude picks | |

**User's choice:** uv

---

## Config System Design

| Option | Description | Selected |
|--------|-------------|----------|
| Just recordings directory | Minimal — ask only recordings dir | |
| Recordings dir + vault path | Ask both upfront | |
| Interactive walkthrough | Full setup wizard | |

**User's choice:** User needs to configure it when starting or via set profile (explicit config, no defaults)

| Option | Description | Selected |
|--------|-------------|----------|
| ~/meetcap/recordings/ | Simple, visible | |
| Platform app data dir | OS-specific app data | |
| You decide | Claude picks | |

**User's choice:** Users need to configure when use or set profile (no silent defaults)

---

## CLI Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Interactive prompt for required settings | Ask for recordings dir, save, then start | ✓ |
| Error with instructions | Print error and exit | |
| You decide | Claude picks | |

**User's choice:** Interactive prompt for required settings

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-generate timestamp title | e.g., 2026-05-09-1430, no prompt | ✓ |
| Prompt for title | Ask before starting | |
| You decide | Claude picks | |

**User's choice:** Auto-generate timestamp title

---

## Claude's Discretion

- Project layout (src/meetcap/ vs flat)

## Deferred Ideas

None
