# Raspberry Pi CCTV Control

A production-minded, private CCTV stack for Raspberry Pi. It installs Motion,
motionEye, retention and health automation, and an authenticated HTTPS control
portal for starting/stopping recording, diagnostics, playback, download, and
recoverable deletion.

## What it installs

- Motion with motionEye 0.44.0 in an isolated Python virtual environment
- Motion-triggered H.264/MKV recording at 1280×720, targeting 10 FPS
- Three-day age ceiling and an independent free-space reserve
- systemd restart policies, two-minute health checks, and hourly retention
- Authenticated HTTPS control portal on one private LAN address
- 24-hour same-filesystem quarantine before permanent recording deletion
- Optional signed-repository Tailscale installation and private motionEye Serve

It does **not** modify SSH policy, firewall rules, router configuration, public
port forwarding, the kernel, firmware, bootloader, or OS release.

## Requirements

- Raspberry Pi running 32-bit or 64-bit Debian/Raspberry Pi OS with systemd
- UVC/V4L2 USB camera, preferably exposed under `/dev/v4l/by-id/`
- Stable power supply
- Dedicated recording storage strongly recommended
- At least 2 GiB more free space than the configured reserve

> [!WARNING]
> Continuous recording can destroy an SD card or fill the root filesystem.
> The installer stops if it detects root-filesystem storage or a Raspberry Pi
> power warning unless you explicitly accept those risks.

## Quick start

```bash
git clone https://github.com/4riful/raspberry-pi-cctv-control.git
cd raspberry-pi-cctv-control
sudo ./install.sh
```

For a deliberately temporary microSD deployment on a Pi whose power warning
cannot yet be corrected:

```bash
sudo ./install.sh --allow-root-storage --accept-power-risk
```

Add `--with-tailscale` for interactive private tailnet setup. Nothing is made
public, and Funnel is never enabled.

Run `sudo ./install.sh --help` for camera, address, retention, and reserve
options. The script is rerunnable: existing credentials are preserved and
changed configuration is backed up under `/root/cctv-backups/`.

## First login

On a fresh install, generated credentials are written to a timestamped,
root-only file:

```bash
sudo ls -1t /root/cctv-credentials-*.txt | head -1
sudo cat "$(sudo ls -1t /root/cctv-credentials-*.txt | head -1)"
```

Open `https://PI_PRIVATE_IP:8443/`. The installer creates a local self-signed
certificate, so the browser warning is expected until you trust that
certificate on the administrator device.

Rotate both administrator passwords after first login:

```bash
sudo cctv-rotate-credentials
```

Never paste generated passwords into chat, issues, logs, or commits.

## Operations

```bash
sudo cctv-validate
sudo systemctl status motioneye cctv-control cctv-health.timer cctv-retention.timer
sudo journalctl -u motioneye -u cctv-health -u cctv-control --since today
```

The red **Turn CCTV off** control stops camera/motion recording only. The
Raspberry Pi and control portal remain online, and the control changes to
**Turn CCTV on**.

See [Operations](docs/operations.md), [Security](SECURITY.md), and
[Tailscale](docs/tailscale.md) for more detail.

## Removal

```bash
sudo ./uninstall.sh
```

Removal preserves recordings, quarantine, credentials, configs, packages, and
Tailscale. Recording deletion is intentionally available only through the
portal's recoverable quarantine flow.

## Current limits

- One local V4L2 camera
- The control portal certificate is locally generated, not publicly trusted
- motionEye and Motion may emit non-monotonic DTS warnings with some UVC cameras
- Actual retention depends on motion frequency, bitrate, and available storage
- Power faults cannot be repaired or safely hidden in software

## License

Copyright retained. This private repository does not grant redistribution
rights unless a license is added later.
