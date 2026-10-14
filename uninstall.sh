#!/bin/sh
set -eu

[ "$(id -u)" -eq 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
PURGE_DATA=0
[ "${1:-}" != '--purge-recordings' ] || PURGE_DATA=1

systemctl disable --now motioneye.service cctv-retention.timer cctv-health.timer \
  cctv-control.service cctv-control-helper.service cctv-control-cleanup.timer 2>/dev/null || true

rm -f /etc/systemd/system/motioneye.service \
  /etc/systemd/system/cctv-retention.service /etc/systemd/system/cctv-retention.timer \
  /etc/systemd/system/cctv-health.service /etc/systemd/system/cctv-health.timer \
  /etc/systemd/system/cctv-control.service /etc/systemd/system/cctv-control-helper.service \
  /etc/systemd/system/cctv-control-cleanup.service /etc/systemd/system/cctv-control-cleanup.timer
rm -f /usr/local/sbin/cctv-retention /usr/local/sbin/cctv-health /usr/local/sbin/cctv-validate /usr/local/sbin/cctv-rotate-credentials
systemctl daemon-reload

if [ "$PURGE_DATA" -eq 1 ]; then
  echo 'Refusing unattended recording deletion.' >&2
  echo 'Use the control portal quarantine flow, then allow its 24-hour cleanup.' >&2
  exit 2
fi

echo 'Services and custom units removed. Recordings, credentials, configs, packages, and Tailscale were preserved.'
