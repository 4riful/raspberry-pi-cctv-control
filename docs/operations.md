# Operations

## Services

| Unit | Purpose |
|---|---|
| `motioneye.service` | motionEye UI and its managed Motion process |
| `cctv-health.timer` | Camera, service, storage, dashboard, and power checks |
| `cctv-retention.timer` | Age and free-space cleanup |
| `cctv-control.service` | Unprivileged HTTPS portal |
| `cctv-control-helper.service` | Fixed privileged actions over a Unix socket |
| `cctv-control-cleanup.timer` | Purges quarantine batches after 24 hours |

## Routine commands

```bash
sudo cctv-validate
sudo systemctl restart motioneye.service
sudo systemctl restart cctv-control.service
sudo journalctl -u motioneye.service -n 100 --no-pager
sudo journalctl -t cctv-health -n 100 --no-pager
sudo systemctl list-timers 'cctv-*'
```

## Configuration

- `/etc/default/raspberry-pi-cctv`: generated deployment values
- `/etc/motioneye/`: motionEye and camera configuration
- `/etc/cctv-control/`: portal config, password hash, and TLS material
- `/var/lib/motion/`: recordings
- `/var/lib/motion/.cctv-quarantine/`: recoverable deleted recordings (same mount as recordings, so moves are instant)
- `/var/lib/cctv-control-web/`: saved console sessions (30-day sliding expiry)
- `/root/cctv-backups/`: pre-install and pre-upgrade backups

Rerun `sudo ./install.sh` from an updated checkout to upgrade. The installer
backs up replaced configuration and preserves existing password hashes.

## Storage behavior

Age retention is a ceiling, not a guarantee. The free-space reserve wins: the
oldest movie may be removed before the age ceiling when space is low. At 4
Mbit/s, three days of continuous footage would be roughly 130 GB before
filesystem/container overhead. Motion-triggered recording normally uses less.

## Power warnings

```bash
vcgencmd get_throttled
```

Only `throttled=0x0` is clear. Any other value indicates a current or historical
power/thermal condition. Replace the supply/cable and use externally powered
USB storage; do not mask the warning in software.
