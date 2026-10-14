---
name: CCTV Control
description: A terminal / NOC-style control console for a Raspberry Pi CCTV recorder.
colors:
  bg: "#0a0d0b"
  bg-2: "#0f1411"
  line: "#1f2b23"
  text: "#c9d4cc"
  dim: "#66776b"
  bright: "#eef5f0"
  green: "#3ddc84"
  amber: "#ffb627"
  red: "#ff5f56"
  cyan: "#6cd4ff"
typography:
  family: "ui-monospace, SF Mono, Cascadia Mono, Menlo, Consolas, DejaVu Sans Mono, monospace"
  base: "13px / 1.55"
  state: "28px, 700, 0.06em tracking (24px on phones)"
  rule-label: "11px, 700, uppercase, 0.08em tracking"
rounded:
  all: "2px"
---

# Design System: CCTV Control

## Character

A dark, monospaced operator console. It reads like a status board: aligned columns, section rules, and keyboard hints. Colour carries state and nothing else.

- **Green** (phosphor): recording, healthy, section labels, usage bars.
- **Amber**: warnings (power, restarts, quarantine notice).
- **Red**: stopped, failures, destructive commands.
- **Cyan**: keyboard hints (`kbd`) and focus rings only.

The app is dark only, by choice (`color-scheme: dark`).

## Priority order (top to bottom)

1. **Header**: `CCTV://recorder`, a REC/WARN/OFF tag, a live clock, and logout.
2. **State**: the lamp plus a large RECORDING / DEGRADED / STOPPED label in its state colour, a one-line detail, and the start/stop command (full width on phones).
3. **Alerts**: `!! PWR` style rows with a coloured left rule, shown only when action is needed.
4. **System**: a bordered metric grid (4 columns, 2 on phones, 1 below 380px), with `█░` text bars for disk and memory, then the command keys.
5. **Recordings**: a DATE / TIME / FILE / SIZE table with ▶ ↓ ✕ actions and 25 rows per page. FILE is hidden on phones. Rows are selectable.
6. **Service log**: loaded only on request (`l`).

## Interaction

- Every command button shows its key: `s` start/stop, `r` restart, `c` cleanup, `f` refresh, `l` log, `q` logout, `Q` quarantine all, `j`/`k` or arrows to select a row, `enter` to play, `x` to quarantine.
- Shortcuts are ignored while typing or while a dialog is open. Destructive commands still confirm.
- Touch targets are at least 40px on phones.

## Runtime budget

- No web fonts, images, frameworks, blur or animated shadows. Busy state is a stepped blink on the lamp (off under reduced motion).
- Status polls every 30s. Polling and the 1s clock stop while the tab is hidden.
- `/api/status` does not walk the recordings directory. The recordings list is fetched only on load, after actions, and on refresh.
- The server keeps only the newest 250 recordings in memory while scanning.
- Playback media is created when the player opens and destroyed when it closes.
