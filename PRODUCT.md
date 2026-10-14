# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Dependency-free, server-rendered HTML and CSS with minimal vanilla JavaScript,
served by the Python standard-library HTTPS service on the Raspberry Pi.

## Users

One trusted home or small-network administrator using a phone or desktop browser
on the same private LAN or Tailscale tailnet. Their primary job is to answer “is
the CCTV recording and healthy?” and turn recording on or off without affecting
power to the Raspberry Pi.

## Product Purpose

Provide a small, dependable operations surface for a single-camera Raspberry Pi
CCTV installation. Success means the recording state, hardware warnings, and
primary on/off action are immediately clear while recordings and recovery tools
remain easy to reach.

## Positioning

Unlike a generic camera dashboard, the product combines camera recording,
Raspberry Pi power/storage health, systemd recovery, retention, and recoverable
recording deletion in one private interface. Destructive actions quarantine for
24 hours instead of deleting immediately.

## Operating Context

The interface runs continuously on a resource-constrained Raspberry Pi and is
used intermittently from mobile and desktop browsers. The administrator may be
responding to a stopped recorder, undervoltage warning, low storage, or a need
to find and download a recent motion event.

## Capabilities and Constraints

- Show recorder, camera, dashboard, storage, retention timer, power,
  temperature, memory, restart, uptime, and quarantine status.
- Start, stop, or restart motionEye/Motion without shutting down the Pi.
- Run retention, inspect recent logs, and refresh status.
- List, play, download, quarantine, and restore recordings.
- Require authentication, CSRF protection, and confirmations for disruptive or
  destructive actions.
- Preserve all existing backend API routes and the dependency-free frontend.
- Use progressive disclosure for diagnostics and maintenance rather than
  removing those capabilities.
- Remain usable at narrow mobile widths and with keyboard navigation or reduced
  motion.

## Brand Commitments

The product name is “CCTV Control.” Voice is direct, calm, and operational. The
interface must explicitly distinguish turning CCTV recording off from powering
off the Raspberry Pi. The requested visual direction is minimal.

## Evidence on Hand

- Working interface source in `app/web/`.
- Production-tested backend and portal security behavior.
- Real status, recordings, logs, and quarantine data supplied by existing APIs.
- No approved logo, photography, illustration, customer proof, or marketing
  claims; future work must not fabricate them.

## Product Principles

1. Recording state and the on/off action come first.
2. Warnings interrupt; healthy diagnostics recede.
3. Destructive actions remain deliberate and recoverable.
4. Plain language beats CCTV or railway metaphors.
5. Minimal means less cognitive load, not fewer safeguards.

## Accessibility & Inclusion

Maintain semantic controls, visible keyboard focus, labeled status updates,
mobile touch targets, sufficient contrast, reduced-motion support, and readable
plain-language confirmations.
