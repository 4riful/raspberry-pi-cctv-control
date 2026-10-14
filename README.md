# Raspberry Pi CCTV Control

[![CI](https://github.com/4riful/raspberry-pi-cctv-control/actions/workflows/ci.yml/badge.svg)](https://github.com/4riful/raspberry-pi-cctv-control/actions/workflows/ci.yml)

Turn a Raspberry Pi and a USB webcam into a private, motion-triggered CCTV
recorder. Recordings stay on the Pi. A small HTTPS control panel provides the
day-to-day controls that motionEye does not: service status, power and storage
warnings, start/stop/restart, recent logs, playback, download, retention, and
recoverable deletion.

This is a single-camera installation for a home or small private network. It is
not a cloud camera platform, an NVR for dozens of cameras, or a service that
should be exposed directly to the Internet.

## Project status

The components in this repository are running on a real Raspberry Pi CCTV
installation. The following paths have been exercised on that system:

- 1280×720 UVC/MJPEG capture and motion-triggered H.264/MKV recording
- motionEye login, live view, recording, and playback
- process crash and systemd restart recovery
- age/free-space retention
- control-panel login, CSRF protection, media range requests, quarantine, and restore
- private remote viewing through Tailscale Serve

The all-in-one `install.sh` is shell-checked, covered by boundary tests, and
verified in CI. **It has not yet been run from start to finish on a freshly
imaged second Pi.** Treat the current release as an operator-maintained project,
read the preflight section, and keep console/SSH access available during first
installation.

### Tested baseline

| Component | Tested value |
|---|---|
| Board | Raspberry Pi 3 Model B+ |
| OS | Debian 13 (Trixie), arm64 |
| Python | 3.13 |
| Camera | USB UVC webcam with a stable `video-index0` by-id path |
| Capture | MJPEG, 1280×720, 10 FPS target |
| Motion | Debian package 4.7.x |
| motionEye | 0.44.0, isolated in `/opt/motioneye` |
| Storage policy | Motion events, three-day age ceiling, 8 GiB reserve |

Other Debian/Raspberry Pi OS releases and 32-bit ARM are accepted by the
preflight checks but are not yet part of the tested matrix.

## How it is laid out

```text
USB camera
    │
    ▼
Motion  ◄── managed by motionEye on 127.0.0.1:8765
    │
    ├── H.264/MKV recordings ──► /var/lib/motion
    │                              │
    │                              ├── hourly retention
    │                              └── 24-hour delete quarantine
    │
    └── health check every 2 minutes

Administrator browser
    └── HTTPS :8443 ──► unprivileged control service
                           └── restricted Unix socket
                                  └── fixed-action root helper
```

motionEye, Motion control, and the camera stream stay on loopback. The custom
control panel binds to one private IPv4 address. Optional Tailscale Serve gives
tailnet-only access to motionEye; Funnel is never enabled.

## Before installing

### Hardware

- Raspberry Pi with a supported Debian/Raspberry Pi OS installation
- USB webcam visible as a V4L2 device
- Proper Pi power supply and low-loss cable
- Dedicated powered SSD strongly recommended for recordings
- Working local console or SSH access with `sudo`

Check the camera and power state first:

```bash
find /dev/v4l/by-id -maxdepth 1 -name '*video-index0' -ls
vcgencmd get_throttled
```

`throttled=0x0` is clear. Any other value means a current or historical power or
thermal event. The installer stops unless the risk is explicitly accepted.
Software cannot repair an undervoltage condition.

### Recording storage

Mount the intended recording filesystem at `/var/lib/motion` **before** running
the installer, then verify it is not the root filesystem:

```bash
findmnt / /var/lib/motion
df -h /var/lib/motion
```

This project deliberately does not automate disk formatting, partitioning, or
mount creation. Those operations can destroy data and differ between systems.

### Network

The Pi needs:

- Internet access during package installation
- A stable private IPv4 address, ideally a router-side DHCP reservation
- No public port forwarding to the Pi

The installer does not configure Wi-Fi, Ethernet, firewall rules, SSH policy,
or the router.

## Installation

Because this is a private repository, authenticate with GitHub first, then:

```bash
gh repo clone 4riful/raspberry-pi-cctv-control
cd raspberry-pi-cctv-control
sudo ./install.sh
```

The installer automatically selects the first stable `video-index0` camera and
the private IPv4 address used by the default route. Override either when needed:

```bash
sudo ./install.sh \
  --camera /dev/v4l/by-id/usb-YOUR_CAMERA-video-index0 \
  --camera-name Front-Door \
  --listen-address 192.168.1.50 \
  --retention-days 3 \
  --min-free-gib 8
```

Run `./install.sh --help` for the complete option list.

### What the installer changes

| Area | Change |
|---|---|
| APT | Installs Motion, FFmpeg, Python venv, curl, CA certificates, and OpenSSL |
| Python | Creates `/opt/motioneye` from the pinned dependency lock |
| Configuration | Writes `/etc/motioneye`, `/etc/cctv-control`, and `/etc/default/raspberry-pi-cctv` |
| Services | Installs and enables `motioneye` plus CCTV health, retention, control, and cleanup units |
| Accounts | Uses package account `motion`; creates locked system account `cctv-control` |
| TLS | Generates a local ECDSA certificate and private key on the Pi |
| Credentials | Generates random passwords on the Pi and stores only application hashes |
| Backups | Copies replaced configuration to `/root/cctv-backups/TIMESTAMP/` |

It does **not** upgrade the OS release, kernel, firmware, or bootloader. It does
not alter SSH, firewall policy, router settings, root login, or public exposure.

### Temporary microSD or known power problems

For a lab or temporary installation only:

```bash
sudo ./install.sh --allow-root-storage --accept-power-risk
```

These flags do not solve anything; they only acknowledge that recordings may be
lost, retention may be shorter than requested, USB devices may reset, and the SD
card may wear out or become corrupt.

### Optional Tailscale

```bash
sudo ./install.sh --with-tailscale
```

This installs Tailscale from its signed repository, verifies its signing key,
and starts the interactive device login. Private HTTPS Serve may require a
one-time tailnet approval. See [docs/tailscale.md](docs/tailscale.md).

## First login

A fresh installation prints the path to a root-only credential file, for
example:

```text
Installed successfully. CCTV Control: https://192.168.1.50:8443/
New credentials (root-only): /root/cctv-credentials-20261015T120000Z.txt
```

Read it from the Pi:

```bash
sudo ls -1t /root/cctv-credentials-*.txt | head -1
sudo cat "$(sudo ls -1t /root/cctv-credentials-*.txt | head -1)"
```

There are separate credentials for:

- **CCTV Control:** `https://PI_ADDRESS:8443/`
- **motionEye:** loopback port 8765, normally reached through Tailscale Serve or an SSH tunnel

The CCTV Control certificate is self-signed. Confirm that the address is your Pi
before accepting the browser warning. Rotate both passwords after first use:

```bash
sudo cctv-rotate-credentials
```

Never paste generated passwords into chat, GitHub issues, terminal recordings,
or commits.

## Verify the installation

```bash
sudo cctv-validate
```

A healthy result reports active services, an existing camera, a responsive
motionEye dashboard, and a responsive HTTPS control panel. Also check:

```bash
sudo systemctl --failed
sudo systemctl list-timers 'cctv-*'
sudo journalctl -u motioneye.service -u cctv-health.service --since today
ss -lntp
```

Expected listeners:

| Port | Expected binding | Purpose |
|---|---|---|
| 7999 | `127.0.0.1` | Motion control |
| 8765 | `127.0.0.1` | motionEye |
| 9081 | `127.0.0.1` | MJPEG stream |
| 8443 | Selected private IPv4 | CCTV Control HTTPS |
| 443 | Tailscale address only, when enabled | Private motionEye Serve |

Perform one real walk-through test after installation. Wait for the configured
two-minute event gap, then confirm that the resulting MKV appears in the portal
and plays to completion.

## Daily operation

The control panel provides:

- A prominent **Turn CCTV off/on** control; this stops recording, not the Pi
- Recorder, camera, storage, retention, access, power, memory, and temperature status
- Restart and retention controls
- Recent service logs
- Recording playback and download
- Individual or all-recording quarantine
- Restore during the 24-hour quarantine window

Useful terminal commands:

```bash
sudo cctv-validate
sudo systemctl restart motioneye.service
sudo systemctl restart cctv-control.service
sudo journalctl -u motioneye.service -n 100 --no-pager
sudo journalctl -t cctv-health -n 100 --no-pager
```

More procedures are in [docs/operations.md](docs/operations.md).

## Retention and capacity

The default is **motion-triggered recording**, not continuous recording. Three
days is an age ceiling, not a promise: the free-space reserve removes the oldest
movie sooner when necessary.

Approximate continuous-recording requirements before filesystem overhead:

| Average video bitrate | Per day | Three days | Seven days |
|---:|---:|---:|---:|
| 1 Mbit/s | 10.8 GB | 32.4 GB | 75.6 GB |
| 2 Mbit/s | 21.6 GB | 64.8 GB | 151.2 GB |
| 4 Mbit/s | 43.2 GB | 129.6 GB | 302.4 GB |

The supplied profile allows up to 4 Mbit/s to avoid the severe macroblocking
seen at very low H.264 bitrates. Actual motion-event usage is scene-dependent.
A 256 GB powered SSD is a practical minimum; 512 GB leaves more room for event
spikes, quarantine, and filesystem reserve.

## Security model

- No public listener is configured.
- motionEye and Motion interfaces remain loopback-only.
- CCTV Control uses HTTPS, PBKDF2 password verification, secure cookies, CSRF
  tokens, login throttling, strict browser headers, and authenticated media.
- The web process is unprivileged. A root helper accepts only fixed operations
  through a group-restricted Unix socket; it does not accept shell commands.
- Delete-all requires a typed phrase and moves files to quarantine instead of
  immediately erasing them.
- systemd units use filesystem, capability, device, namespace, and resource
  restrictions.

Read [SECURITY.md](SECURITY.md) before changing listener addresses or remote
access.

## Upgrade, rollback, and removal

Upgrade from the checked-out repository:

```bash
git pull --ff-only
sudo ./install.sh YOUR_ORIGINAL_OPTIONS
sudo cctv-validate
```

The installer preserves existing password hashes and creates a timestamped
configuration backup before replacement.

Remove custom services while preserving all data and installed packages:

```bash
sudo ./uninstall.sh
```

The uninstall script intentionally refuses unattended recording deletion. Use
the portal quarantine flow, verify the result, and allow the 24-hour cleanup.

## Troubleshooting

### `no stable V4L2 by-id index0 camera found`

```bash
v4l2-ctl --list-devices
find /dev/v4l/by-id -maxdepth 1 -type l -ls
```

Use the capture node ending in `video-index0`, not a metadata-only index. Pass it
with `--camera` if auto-detection cannot choose it.

### Installation stops on `throttled=...`

Use a correctly rated Pi supply, a short low-loss cable, and externally powered
USB storage. A reboot or complete power cycle is needed before historical bits
can clear. Use `--accept-power-risk` only when data loss is acceptable.

### The control page does not open

```bash
sudo systemctl status cctv-control cctv-control-helper
sudo journalctl -u cctv-control -u cctv-control-helper -n 100 --no-pager
curl -kI https://PI_ADDRESS:8443/
```

Use the exact address selected during installation and accept the local
certificate warning. The installer does not open a firewall port for you.

### Recordings are blocky or drop frames

Check `vcgencmd get_throttled`, CPU load, USB errors, and the active camera
configuration. The supplied profile uses `movie_quality 85` and
`movie_bps 4000000`. A Pi 3 may still lose frames under high scene complexity or
poor power. Do not lower bitrate first; verify power and capture stability.

### Tailscale works but the browser cannot connect

The viewing device must run the Tailscale client and be connected to the same
tailnet. Signing into the Tailscale admin website is not sufficient. Check
`tailscale status` and `tailscale serve status`; Serve must report `tailnet only`.

## Known limitations

- One local V4L2 camera
- No fresh-image end-to-end installer test yet
- No automatic disk partitioning, formatting, or mounting
- No automatic firewall or SSH hardening
- Locally generated certificate rather than a public CA certificate
- Some UVC/Motion combinations produce non-monotonic DTS warnings even when the
  completed recording decodes successfully
- A reboot recovery test is installation-specific and must be performed by the
  operator when safe
- Power and USB hardware faults cannot be fixed in software

## Repository map

```text
app/                       HTTPS control panel and fixed-action helper
app/web/                   Dependency-free HTML, CSS, and JavaScript
docs/                      Operations and Tailscale procedures
scripts/                   Health, retention, validation, credential rotation
systemd/                   Hardened service and timer units
templates/                 motionEye and Motion configuration templates
tests/                     Path-confinement and identifier boundary tests
install.sh                 Full installer and preflight checks
uninstall.sh               Non-destructive service removal
requirements-motioneye.lock  Pinned Python dependency set
```

## License

Copyright retained. This private repository does not grant redistribution
rights unless a license is added later.
