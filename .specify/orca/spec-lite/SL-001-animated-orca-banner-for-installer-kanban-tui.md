# Spec-Lite SL-001: Animated ORCA banner for installer + Kanban TUI

**Source Name**: operator
**Created**: 2026-04-16
**Status**: implemented

## Problem
The ORCA ASCII banner currently prints as a static block on speckit-orca installer output and in the Kanban TUI startup. Feels dead. Also, users miss the 'personality' moment that perf-lab established with its PERF LAB rain animation when the TUI boots.

## Solution
Build an animated banner that plays the orca emerging from water: Phase 1 waves-only shift (orca underwater), Phase 2 body rises bottom-up (belly → forehead → head+tail), Phase 3 blowhole erupts water spout upward (' → '":"' → '.' + '":"'). Single Python module 'speckit_orca.banner_anim' stdlib-only (ANSI escapes, time.sleep). Gracefully degrades to static print in non-TTY environments (pipe, CI). Exposed via 'python -m speckit_orca.banner_anim --animate | --static'. Bash installer shells out to it when available, falls back to its current static CYAN banner if the Python module is missing. Kanban TUI calls it directly at startup. Total runtime ~1.5-2s so it doesn't annoy.

## Acceptance Scenario
Given a TTY terminal and 'python -m speckit_orca.banner_anim --animate', when the command runs, then the terminal shows waves shifting, orca rising from the waves bottom-up, water erupting from the blowhole, and the final static banner held for 300ms before exit. Given a non-TTY (piped to file, --static flag, or CI environment), when invoked, then the module prints the final static banner without delay and exits 0. Given the animation is interrupted (Ctrl-C), then the cursor is restored visible and the terminal is left in a clean state.

## Files Affected
- src/speckit_orca/banner_anim.py
- src/speckit_orca/assets/speckit-orca-main.sh
- tests/test_banner_anim.py

## Verification Evidence
17 new banner_anim tests pass; installer renders animated banner in TTY and falls back to static in non-TTY; total 291 tests pass
