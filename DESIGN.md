---
name: CCTV Control
description: A calm, precise wall control for a Raspberry Pi CCTV recorder.
colors:
  cool-field: "#f3f5f3"
  white-panel: "#ffffff"
  charcoal-ink: "#18201c"
  quiet-ink: "#65706a"
  fine-rule: "#d7dcd8"
  recording-green: "#176b43"
  recording-green-soft: "#e4f2e9"
  warning-amber: "#8b4b08"
  warning-amber-soft: "#fff3dc"
  fault-red: "#a12a24"
  fault-red-soft: "#fbe9e7"
  focus-blue: "#126b95"
typography:
  display:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "clamp(3rem, 7vw, 5.5rem)"
    fontWeight: 700
    lineHeight: 0.92
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "clamp(2rem, 5vw, 3.2rem)"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.035em"
  title:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1.8rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  body:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 700
    lineHeight: 1.35
rounded:
  action-sm: "0.35rem"
  control: "0.4rem"
  field: "0.45rem"
  dialog: "0.6rem"
  circular: "50%"
spacing:
  xs: "0.35rem"
  sm: "0.5rem"
  md: "1rem"
  lg: "1.5rem"
  xl: "2rem"
  section: "3.5rem"
components:
  button-primary:
    backgroundColor: "{colors.charcoal-ink}"
    textColor: "{colors.white-panel}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0.65rem 1rem"
    height: "2.8rem"
  button-primary-hover:
    backgroundColor: "{colors.recording-green}"
    textColor: "{colors.white-panel}"
  button-secondary:
    backgroundColor: "{colors.white-panel}"
    textColor: "{colors.charcoal-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0.65rem 1rem"
    height: "2.8rem"
  button-danger:
    backgroundColor: "{colors.fault-red}"
    textColor: "{colors.white-panel}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0.65rem 1rem"
    height: "2.8rem"
  input:
    backgroundColor: "{colors.white-panel}"
    textColor: "{colors.charcoal-ink}"
    rounded: "{rounded.field}"
    padding: "0.75rem 0.85rem"
    height: "3rem"
  power-control:
    backgroundColor: "{colors.white-panel}"
    textColor: "{colors.charcoal-ink}"
    rounded: "{rounded.circular}"
    padding: "1rem"
    size: "12rem"
---

# Design System: CCTV Control

## Overview

**Creative North Star: "The Recorder Wall Control"**

CCTV Control behaves like a precise architectural faceplate: one unmistakable operating state, one tactile primary control, and supporting facts arranged with quiet discipline. The mood is calm, dependable, and utilitarian without becoming industrial theater. A matte cool-white field, charcoal type, fine rules, and compact native system typography keep the interface fast and credible on a resource-constrained device.

Healthy information recedes; recording state and actionable warnings surface immediately. Green communicates confirmed operation, while amber and red appear only when the system requires attention or an action is destructive. Flat planes and open spacing replace dashboard cards, gauges, decorative metaphor, and equal-weight controls.

**Key Characteristics:**
- Matte cool-white field with crisp white controls
- Oversized, tightly set recording state
- Circular status lamps and one circular primary control
- Fine structural rules instead of card containers
- Sparse, semantic green, amber, and red
- Progressive disclosure for maintenance and diagnostics

## Colors

The palette is cool, restrained, and operational; chromatic color always carries state or interaction meaning.

### Primary
- **Recording Green:** Confirms healthy recording, connected subsystems, and the start-state power glyph; it also provides the primary button's positive hover response.
- **Recording Green Soft:** Forms the restrained halo behind a healthy state lamp.

### Secondary
- **Warning Amber:** Marks unknown, degraded, or caution states that need attention but are not confirmed failures.
- **Warning Amber Soft:** Supports warning banners, degraded lamp halos, and busy-state pulses without flooding the page.
- **Fault Red:** Marks stopped recording, destructive actions, and errors.
- **Fault Red Soft:** Provides restrained hover and lamp-halo support for fault or quarantine states.
- **Focus Blue:** Exists only for the high-contrast keyboard focus outline and focused field border.

### Neutral
- **Cool Field:** The continuous page and sticky-header ground.
- **White Panel:** The control, field, and dialog surface.
- **Charcoal Ink:** Primary text, dark actions, code/log surfaces, and high-contrast hover inversion.
- **Quiet Ink:** Secondary copy, timestamps, metadata, and subdued actions.
- **Fine Rule:** Borders and dividers that establish structure without card chrome.

### Named Rules

**The Semantic Color Rule.** Green means confirmed operation, amber means attention or unknown, red means stopped, destructive, or failed, and blue means keyboard focus; never use them as decoration.

**The Quiet Health Rule.** Healthy diagnostics stay neutral except for small status indicators or values where confirmation is useful; warnings may claim a full-width tinted plane.

## Typography

**Display Font:** Native UI sans-serif stack (with Segoe UI and generic sans-serif fallbacks)  
**Body Font:** Native UI sans-serif stack (with Segoe UI and generic sans-serif fallbacks)  
**Label/Mono Font:** Native UI sans-serif for labels; `ui-monospace, monospace` for service logs

**Character:** Compact system typography makes the panel feel immediate and appliance-like. Tight display tracking gives the recording state authority, while smaller labels, metadata, and tabular figures keep operational detail dense and scannable.

### Hierarchy
- **Display:** The live recording-state statement only; large, tightly tracked, balanced, and constrained to a short measure.
- **Headline:** Major section headings such as recent recordings.
- **Title:** Dialog titles and other contained moments requiring clear hierarchy.
- **Body:** Explanatory state copy, warnings, and confirmation language; keep operational prose concise and around 45 characters wide where the layout permits.
- **Label:** Controls, field labels, subsystem facts, and compact status text; bold weight supplies hierarchy without uppercase styling.
- **Operational Data:** Timestamps and diagnostic values use tabular numerals so changing values do not jitter.

### Named Rules

**The One Loud Sentence Rule.** Reserve display scale for the current recording state; no secondary metric competes at that size.

**The Plain Label Rule.** Use sentence case and direct language rather than all-caps commands, jargon, or metaphorical names.

## Layout

The application uses a centered content measure capped at 68rem with 1.5rem desktop gutters. A sticky, full-width top bar aligns its contents to the same measure. Main sections are separated by fine horizontal rules and generous vertical spacing rather than boxed into cards.

The overview is a two-column composition: state copy occupies the flexible column and the circular power control anchors the right side. Camera, storage, and retention facts span the full width beneath them in three equal columns. Recordings use aligned rows with time, file information, and actions; diagnostics use a two-column definition-list grid and remain inside a disclosure.

At 720px and below, content gutters contract to 1rem, the power control shrinks from 12rem to 7.5rem, recording rows become single-column, and diagnostics collapse to one column. At 430px, section headings and the footer stack. The layout retains a 20rem minimum canvas and touch-friendly controls.

**The Open Plane Rule.** Use spacing and rules to group content; do not introduce a dashboard wall of separate cards.

## Elevation & Depth

The system is flat by default. Background contrast, one-pixel rules, circular halos, and control inversion communicate hierarchy. Shadows are exceptional: a soft ring expands a state lamp, while dialogs and toasts lift above the operating plane because they interrupt the workflow.

### Shadow Vocabulary
- **State halo** (`0 0 0 0.35–0.4rem` in the matching soft semantic color): Makes a tiny state lamp legible without becoming a badge.
- **Dialog lift** (`0 1.5rem 4rem rgba(0, 0, 0, 0.24)`): Reserved for blocking confirmation dialogs.
- **Toast lift** (`0 0.8rem 2rem rgba(0, 0, 0, 0.2)`): Reserved for transient feedback above page content.

### Named Rules

**The Flat-Until-Interrupted Rule.** Resting page surfaces have no shadow; only state lamps, modal dialogs, and transient toasts may lift or glow.

## Shapes

The dominant form language pairs flat rectangular planes with gently curved controls and one emphatic circle. Standard controls use compact radii between 0.35rem and 0.6rem. Status dots and lamps are circular, and the recording power control is a full circle. Fine one-pixel borders remain visible around fields and controls; content sections use divider lines rather than rounded containers.

**The One Circle Rule.** Large circular geometry belongs to the primary recording control; supporting circles remain tiny status indicators.

## Components

### Buttons
- **Shape:** Compact gently curved controls with a 2.8rem minimum height; the primary recording control is circular and substantially larger.
- **Primary:** Charcoal surface with white text and icon. Its positive hover state turns recording green.
- **Secondary:** White panel surface, charcoal text, and a fine-rule border; hover inverts to charcoal with white text.
- **Danger:** Fault-red fill and white text for confirmed destructive actions. Text-only destructive actions use fault red without a filled plane.
- **Hover / Focus:** Hover transitions complete in 200ms with ease-out where movement is present. All controls receive the shared 3px focus-blue outline with 3px offset.
- **Disabled:** Reduce opacity and replace the pointer cursor; the power control uses a wait cursor while a command is pending.

### Status Indicators
- **Style:** Small circular pins summarize global and subsystem state. The larger state lamp includes a matching soft halo.
- **State:** Green is live, amber is degraded or unknown, and red is stopped or problematic. A pending command pulses the amber halo only.

### Alerts
- **Style:** Full-width, square-cornered amber-soft planes with a fixed-width bold title column and readable explanatory copy.
- **Behavior:** Alerts appear only for actionable power, camera, storage, or timer conditions; healthy states do not create banners.

### Recording Rows
- **Style:** Border-separated list rows, not cards. Time and size are muted; the filename is bold; actions stay compact at the trailing edge.
- **Actions:** Play uses the charcoal primary treatment. Download is quiet until hover. Quarantine turns red on a fault-red-soft hover plane.
- **Responsive:** Below 720px, metadata and actions stack beneath the filename and long names may wrap anywhere.

### Inputs / Fields
- **Style:** White surface, fine-rule stroke, gently curved field corners, dark text, and a green caret.
- **Focus:** The border changes to focus blue in addition to the shared focus-visible outline.
- **Error / Disabled:** Errors use fault-red text at bold compact size. Disabled controls reduce opacity.

### Navigation
- **Style:** The sticky top bar uses a translucent cool-field surface and a bottom rule. Brand, centered live status, and sign-out action form a quiet three-part line.
- **Mobile:** Below 720px the status moves under the brand while sign-out spans both header rows on the right.

### Disclosure and Dialogs
- **Disclosure:** System details and logs use native `details` behavior, rule-separated summaries, and a 200ms chevron rotation.
- **Dialog:** Confirmation content sits on a white surface with the system's largest corner radius; a dark translucent backdrop isolates the decision. Actions align to the trailing edge.

## Do's and Don'ts

### Do:
- **Do** make recording state the clearest sentence and the recording power control the clearest action.
- **Do** distinguish stopping CCTV from powering off the Raspberry Pi in adjacent plain language.
- **Do** use fine rules, spacing, and disclosure to organize dense operational information.
- **Do** preserve visible keyboard focus, semantic status announcements, mobile touch targets, and reduced-motion behavior.
- **Do** keep destructive actions deliberate, fault-red, confirmed, and visibly recoverable through quarantine.

### Don't:
- **Don't** use semantic green, amber, red, or focus blue as decorative accent colors.
- **Don't** turn diagnostics, recordings, or maintenance actions into an equal-weight grid of cards or gauges.
- **Don't** add decorative CCTV imagery, gradients, glass effects, or ornamental metaphor.
- **Don't** let maintenance and logs occupy the first view when the user has not requested them.
- **Don't** animate continuously except for the bounded pending-state pulse, and suppress that pulse when reduced motion is requested.
