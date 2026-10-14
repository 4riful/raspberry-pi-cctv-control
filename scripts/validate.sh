#!/bin/sh
set -eu

# shellcheck source=/dev/null
. /etc/default/raspberry-pi-cctv
failed=0

check_service() {
  if systemctl is-active --quiet "$1"; then
    printf 'PASS service active: %s\n' "$1"
  else
    printf 'FAIL service inactive: %s\n' "$1" >&2
    failed=1
  fi
}

check_service motioneye.service
check_service cctv-control-helper.service
check_service cctv-control.service
check_service cctv-health.timer
check_service cctv-retention.timer
check_service cctv-control-cleanup.timer

if [ -e "$CCTV_CAMERA_DEVICE" ]; then
  printf 'PASS camera exists: %s\n' "$CCTV_CAMERA_DEVICE"
else
  printf 'FAIL camera missing: %s\n' "$CCTV_CAMERA_DEVICE" >&2
  failed=1
fi

if curl -fsS --max-time 10 -o /dev/null http://127.0.0.1:8765/; then
  echo 'PASS motionEye dashboard'
else
  echo 'FAIL motionEye dashboard' >&2
  failed=1
fi

if curl -kfsS --max-time 10 -o /dev/null "https://${CCTV_LISTEN_ADDRESS}:8443/"; then
  echo 'PASS CCTV Control HTTPS'
else
  echo 'FAIL CCTV Control HTTPS' >&2
  failed=1
fi

if command -v vcgencmd >/dev/null 2>&1; then
  printf 'INFO power: %s\n' "$(vcgencmd get_throttled 2>/dev/null || echo unknown)"
fi

exit "$failed"
