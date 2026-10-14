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

## Layout: one screen, one scroll

The app fills exactly one viewport (`100dvh`, with safe-area padding for notches). The page itself never scrolls; only the recordings list does, with a sticky table header. Rows load 40 at a time as you near the bottom. On short viewports (height ≤ 600px, or phones ≤ 700px tall) the shell falls back to normal page scrolling so the list keeps a usable 80dvh.

1. **Header**: brand, a REC/WARN/OFF tag, a clock (hover it for the last sync time), and a logout icon.
2. **State row**: lamp, RECORDING / DEGRADED / STOPPED label, then icon controls for restart, cleanup, refresh, log, and **Pi power off** (red), plus the **TURN ON / TURN OFF** recording button. On phones the recording button comes first and spans the row.
3. **Alerts**: an icon, a label, and the text, shown only when action is needed.
4. **Metrics grid**: 6 columns on desktop, 4 at ≤860px, 2 on phones. Each label has an icon; disk and memory show `█░` bars.
5. **Recordings**: fills the remaining height. The header carries the count, restore (amber, with the quarantine count) and quarantine-all icons. The footer shows how many rows are loaded and the keyboard hints.

The service log, confirmations and the player are dialogs, so they never change the layout.

## Interaction

- Every control is an SVG icon with a tooltip naming its shortcut: `s` recording on/off, `P` power off the Pi, `r` restart, `c` cleanup, `f` refresh, `l` log, `q` logout, `Q` quarantine all, `j`/`k`/arrows to select, `enter` to play, `x` to quarantine.
- Powering off the Pi requires typing `POWER OFF`, because it can only be switched back on at the power plug. The server checks the phrase as well.
- Shortcuts are ignored while typing or while a dialog is open. Touch targets are at least 38–44px on phones, and login inputs are 16px on touch screens to stop iOS from zooming.

## Runtime budget

- No web fonts, images, frameworks, blur or animated shadows. Busy state is a stepped blink on the lamp (off under reduced motion).
- Status polls every 30s. Polling and the 1s clock stop while the tab is hidden.
- `/api/status` does not walk the recordings directory. The recordings list is fetched only on load, after actions, and on refresh.
- The server keeps only the newest 250 recordings in memory while scanning.
- Playback media is created when the player opens and destroyed when it closes.
