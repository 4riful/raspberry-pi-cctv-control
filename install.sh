#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
CAMERA_DEVICE=
CAMERA_NAME=Camera-1
LISTEN_ADDRESS=
RETENTION_DAYS=3
MIN_FREE_GIB=8
ACCEPT_POWER_RISK=0
ALLOW_ROOT_STORAGE=0
WITH_TAILSCALE=0

usage() {
  cat <<'EOF'
Usage: sudo ./install.sh [options]

Options:
  --camera PATH                 V4L2 capture device (default: first by-id index0)
  --camera-name NAME            Display name; letters, numbers, dot, dash, underscore
  --listen-address IPV4         Exact private address for HTTPS control portal
  --retention-days DAYS         Age ceiling for recordings (default: 3)
  --min-free-gib GIB            Free-space reserve (default: 8)
  --accept-power-risk           Continue if Raspberry Pi reports undervoltage/throttling
  --allow-root-storage          Permit recordings on the root filesystem/microSD
  --with-tailscale              Install Tailscale and begin interactive private setup
  -h, --help                    Show this help

The installer never changes SSH, firewall, router, bootloader, kernel, or public exposure.
EOF
}

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "==> $*"; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --camera) [ "$#" -ge 2 ] || die '--camera needs a value'; CAMERA_DEVICE=$2; shift 2 ;;
    --camera-name) [ "$#" -ge 2 ] || die '--camera-name needs a value'; CAMERA_NAME=$2; shift 2 ;;
    --listen-address) [ "$#" -ge 2 ] || die '--listen-address needs a value'; LISTEN_ADDRESS=$2; shift 2 ;;
    --retention-days) [ "$#" -ge 2 ] || die '--retention-days needs a value'; RETENTION_DAYS=$2; shift 2 ;;
    --min-free-gib) [ "$#" -ge 2 ] || die '--min-free-gib needs a value'; MIN_FREE_GIB=$2; shift 2 ;;
    --accept-power-risk) ACCEPT_POWER_RISK=1; shift ;;
    --allow-root-storage) ALLOW_ROOT_STORAGE=1; shift ;;
    --with-tailscale) WITH_TAILSCALE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || die 'run this installer with sudo'
[ -d /run/systemd/system ] || die 'systemd is required'
[ -r /etc/os-release ] || die 'cannot identify the operating system'
# shellcheck source=/dev/null
. /etc/os-release
case "${ID:-}" in debian|raspbian) ;; *) die "unsupported OS: ${ID:-unknown} (Debian/Raspberry Pi OS required)" ;; esac
case "$(uname -m)" in aarch64|armv7l|armv8l) ;; *) die "unsupported architecture: $(uname -m)" ;; esac

case "$CAMERA_NAME" in *[!A-Za-z0-9._-]*|'') die 'camera name contains unsupported characters' ;; esac
case "$RETENTION_DAYS" in *[!0-9]*|'') die 'retention days must be an integer' ;; esac
case "$MIN_FREE_GIB" in *[!0-9]*|'') die 'minimum free GiB must be an integer' ;; esac
[ "$RETENTION_DAYS" -ge 1 ] || die 'retention days must be at least 1'
[ "$MIN_FREE_GIB" -ge 2 ] || die 'minimum free space must be at least 2 GiB'

if [ -z "$CAMERA_DEVICE" ]; then
  CAMERA_DEVICE=$(find /dev/v4l/by-id -maxdepth 1 -type l -name '*video-index0' 2>/dev/null | sort | head -n 1 || true)
fi
[ -n "$CAMERA_DEVICE" ] || die 'no stable V4L2 by-id index0 camera found; use --camera PATH'
[ -e "$CAMERA_DEVICE" ] || die "camera does not exist: $CAMERA_DEVICE"
CAMERA_DEVICE=$(readlink -f "$CAMERA_DEVICE" | awk -v original="$CAMERA_DEVICE" '{print original}')
CAMERA_NODE=$(readlink -f "$CAMERA_DEVICE")
case "$CAMERA_NODE" in /dev/video[0-9]*) ;; *) die "camera does not resolve to a /dev/video node: $CAMERA_DEVICE" ;; esac

if [ -z "$LISTEN_ADDRESS" ]; then
  LISTEN_ADDRESS=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')
fi
[ -n "$LISTEN_ADDRESS" ] || die 'could not determine a private IPv4 address; use --listen-address'
python3 - "$LISTEN_ADDRESS" <<'PY' || exit 1
import ipaddress, sys
address = ipaddress.ip_address(sys.argv[1])
if address.version != 4 or address.is_unspecified or address.is_loopback or address.is_multicast or address.is_global:
    raise SystemExit('listen address must be a private, non-loopback IPv4 address')
PY
ip -4 address show | grep -Fq "inet $LISTEN_ADDRESS/" || die "listen address is not assigned to this host: $LISTEN_ADDRESS"

if command -v vcgencmd >/dev/null 2>&1; then
  POWER=$(vcgencmd get_throttled 2>/dev/null || echo unknown)
  if [ "$POWER" != 'throttled=0x0' ] && [ "$ACCEPT_POWER_RISK" -ne 1 ]; then
    die "power warning is active or historical ($POWER); fix power or rerun with --accept-power-risk"
  fi
  [ "$POWER" = 'throttled=0x0' ] || echo "WARNING: accepting Raspberry Pi power risk: $POWER" >&2
fi

install -d -m 0750 /var/lib/motion
ROOT_SOURCE=$(findmnt -n -o SOURCE --target /)
RECORDING_SOURCE=$(findmnt -n -o SOURCE --target /var/lib/motion)
if [ "$ROOT_SOURCE" = "$RECORDING_SOURCE" ] && [ "$ALLOW_ROOT_STORAGE" -ne 1 ]; then
  die 'recordings would use the root filesystem; mount dedicated storage or rerun with --allow-root-storage'
fi
FREE_KIB=$(df -Pk /var/lib/motion | awk 'NR==2 {print $4}')
MIN_FREE_KIB=$((MIN_FREE_GIB * 1024 * 1024))
[ "$FREE_KIB" -gt "$MIN_FREE_KIB" ] || die "recording filesystem has less than ${MIN_FREE_GIB} GiB free"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/root/cctv-backups/$STAMP
install -d -o root -g root -m 0700 "$BACKUP"
for path in /etc/motioneye /etc/cctv-control /etc/systemd/system/motioneye.service /etc/default/raspberry-pi-cctv; do
  [ ! -e "$path" ] || cp -a "$path" "$BACKUP/"
done

log 'installing signed Debian packages'
export DEBIAN_FRONTEND=noninteractive
MOTION_WAS_MASKED=0
MOTION_MASK_ACTIVE=0
[ "$(systemctl is-enabled motion.service 2>/dev/null || true)" = masked ] && MOTION_WAS_MASKED=1
cleanup_motion_mask() {
  if [ "$MOTION_MASK_ACTIVE" -eq 1 ] && [ "$MOTION_WAS_MASKED" -eq 0 ]; then
    systemctl unmask motion.service >/dev/null 2>&1 || true
  fi
}
trap cleanup_motion_mask EXIT HUP INT TERM
systemctl stop motion.service 2>/dev/null || true
systemctl mask motion.service >/dev/null 2>&1 || true
MOTION_MASK_ACTIVE=1
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl ffmpeg motion openssl python3 python3-venv
systemctl disable --now motion.service 2>/dev/null || true
if [ "$MOTION_WAS_MASKED" -eq 0 ]; then
  systemctl unmask motion.service >/dev/null 2>&1 || true
fi
MOTION_MASK_ACTIVE=0

log 'installing pinned motionEye environment'
if [ ! -x /opt/motioneye/bin/python ]; then
  python3 -m venv /opt/motioneye
fi
/opt/motioneye/bin/pip install --disable-pip-version-check --requirement "$PROJECT_DIR/requirements-motioneye.lock"
/opt/motioneye/bin/pip check

id motion >/dev/null 2>&1 || die 'the Motion package did not create its service account'
install -d -o motion -g motion -m 0750 /etc/motioneye
install -d -o motion -g adm -m 2750 /var/lib/motion
install -d -o motion -g motion -m 0750 /var/lib/motion/"$CAMERA_NAME"
install -o root -g motion -m 0640 "$PROJECT_DIR/templates/motioneye.conf" /etc/motioneye/motioneye.conf

CAMERA_SLUG=$CAMERA_NAME
python3 - "$PROJECT_DIR/templates/camera-1.conf.template" /etc/motioneye/camera-1.conf "$CAMERA_DEVICE" "$CAMERA_NAME" "$CAMERA_SLUG" <<'PY'
from pathlib import Path
import sys
source, destination, device, name, slug = sys.argv[1:]
text = Path(source).read_text()
text = text.replace('@CAMERA_DEVICE@', device).replace('@CAMERA_NAME@', name).replace('@CAMERA_SLUG@', slug)
Path(destination).write_text(text)
PY
chown motion:motion /etc/motioneye/camera-1.conf
chmod 0600 /etc/motioneye/camera-1.conf

CREDENTIAL_OUTPUT=/root/cctv-credentials-$STAMP.txt
CCTV_CREDENTIAL_OUTPUT=$CREDENTIAL_OUTPUT
CCTV_MOTION_TEMPLATE=$PROJECT_DIR/templates/motion.conf.template
CCTV_PORTAL_URL=https://$LISTEN_ADDRESS:8443/
export CCTV_CREDENTIAL_OUTPUT CCTV_MOTION_TEMPLATE CCTV_PORTAL_URL
/opt/motioneye/bin/python <<'PY'
import base64, hashlib, json, os, re, secrets, string
from pathlib import Path
from argon2 import PasswordHasher

alphabet = string.ascii_letters + string.digits
make = lambda: ''.join(secrets.choice(alphabet) for _ in range(28))
notes = []
motion_path = Path('/etc/motioneye/motion.conf')
existing = motion_path.read_text() if motion_path.exists() else ''
match = re.search(r'^# @admin_password (.+)$', existing, re.M)
if match and match.group(1):
    admin_hash = match.group(1)
else:
    password = make()
    admin_hash = PasswordHasher().hash(password)
    notes.append('motionEye\nUsername: admin\nPassword: ' + password + '\nURL: http://127.0.0.1:8765/ (use an SSH tunnel or Tailscale Serve)')

viewer_match = re.search(r'^# @normal_password (.+)$', existing, re.M)
if viewer_match and viewer_match.group(1):
    viewer_hash = viewer_match.group(1)
else:
    viewer_password = make()
    viewer_hash = PasswordHasher().hash(viewer_password)
    notes.append('motionEye viewer\nUsername: viewer\nPassword: ' + viewer_password)

template = Path(os.environ['CCTV_MOTION_TEMPLATE']).read_text()
lines = [line for line in template.splitlines() if not line.startswith('# @admin_password ') and not line.startswith('# @normal_password ')]
admin_at = next(i + 1 for i, line in enumerate(lines) if line.startswith('# @admin_username '))
lines.insert(admin_at, '# @admin_password ' + admin_hash)
viewer_at = next(i + 1 for i, line in enumerate(lines) if line.startswith('# @normal_username '))
lines.insert(viewer_at, '# @normal_password ' + viewer_hash)
motion_path.write_text('\n'.join(lines) + '\n')

portal = Path('/etc/cctv-control/credentials.json')
if not portal.exists():
    portal_password = make()
    salt = secrets.token_bytes(24)
    iterations = 600000
    digest = hashlib.pbkdf2_hmac('sha256', portal_password.encode(), salt, iterations)
    portal.parent.mkdir(parents=True, exist_ok=True)
    portal.write_text(json.dumps({'username': 'admin', 'salt': base64.b64encode(salt).decode(), 'hash': base64.b64encode(digest).decode(), 'iterations': iterations}) + '\n')
    notes.append('CCTV Control\nUsername: admin\nPassword: ' + portal_password + '\nURL: ' + os.environ['CCTV_PORTAL_URL'])

if notes:
    Path(os.environ['CCTV_CREDENTIAL_OUTPUT']).write_text('\n\n'.join(notes) + '\n')
PY
chown motion:motion /etc/motioneye/motion.conf
chmod 0600 /etc/motioneye/motion.conf
[ ! -f "$CREDENTIAL_OUTPUT" ] || chmod 0600 "$CREDENTIAL_OUTPUT"

log 'installing retention, health checks, and hardened units'
install -o root -g root -m 0755 "$PROJECT_DIR/scripts/cctv-retention" /usr/local/sbin/cctv-retention
install -o root -g root -m 0755 "$PROJECT_DIR/scripts/cctv-health" /usr/local/sbin/cctv-health
install -o root -g root -m 0755 "$PROJECT_DIR/scripts/validate.sh" /usr/local/sbin/cctv-validate
install -o root -g root -m 0755 "$PROJECT_DIR/scripts/rotate-credentials.sh" /usr/local/sbin/cctv-rotate-credentials
for unit in cctv-retention.service cctv-retention.timer cctv-health.service cctv-health.timer; do
  install -o root -g root -m 0644 "$PROJECT_DIR/systemd/$unit" "/etc/systemd/system/$unit"
done
python3 - "$PROJECT_DIR/systemd/motioneye.service" /etc/systemd/system/motioneye.service "$CAMERA_NODE" <<'PY'
from pathlib import Path
import sys
Path(sys.argv[2]).write_text(Path(sys.argv[1]).read_text().replace('@CAMERA_NODE@', sys.argv[3]))
PY
chmod 0644 /etc/systemd/system/motioneye.service
python3 - "$PROJECT_DIR/systemd/raspberry-pi-cctv.conf" /etc/default/raspberry-pi-cctv "$CAMERA_DEVICE" "$RETENTION_DAYS" "$MIN_FREE_KIB" "$LISTEN_ADDRESS" <<'PY'
from pathlib import Path
import sys
source, destination, camera, days, free_kib, address = sys.argv[1:]
text = Path(source).read_text().replace('@CAMERA_DEVICE@', camera).replace('@RETENTION_DAYS@', days).replace('@MIN_FREE_KIB@', free_kib).replace('@LISTEN_ADDRESS@', address)
Path(destination).write_text(text)
PY
chmod 0644 /etc/default/raspberry-pi-cctv

log 'installing the authenticated HTTPS control portal'
if ! id -u cctv-control >/dev/null 2>&1; then
  useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin --user-group cctv-control
fi
usermod -a -G adm cctv-control
install -d -o root -g root -m 0755 /opt/cctv-control /opt/cctv-control/web
install -d -o root -g cctv-control -m 0750 /etc/cctv-control
install -o root -g root -m 0755 "$PROJECT_DIR/app/cctv_control.py" /opt/cctv-control/cctv_control.py
install -o root -g root -m 0755 "$PROJECT_DIR/app/cctv_control_helper.py" /opt/cctv-control/cctv_control_helper.py
install -o root -g root -m 0644 "$PROJECT_DIR/app/web/index.html" /opt/cctv-control/web/index.html
install -o root -g root -m 0644 "$PROJECT_DIR/app/web/styles.css" /opt/cctv-control/web/styles.css
install -o root -g root -m 0644 "$PROJECT_DIR/app/web/app.js" /opt/cctv-control/web/app.js
python3 - /etc/cctv-control/config.json "$LISTEN_ADDRESS" "$CAMERA_DEVICE" <<'PY'
import json, sys
path, address, camera = sys.argv[1:]
with open(path, 'w') as handle:
    json.dump({
        'listen_host': address, 'listen_port': 8443,
        'web_root': '/opt/cctv-control/web', 'recordings_root': '/var/lib/motion',
        'quarantine_root': '/var/lib/cctv-control/quarantine',
        'credentials_file': '/etc/cctv-control/credentials.json',
        'cert_file': '/etc/cctv-control/tls.crt', 'key_file': '/etc/cctv-control/tls.key',
        'helper_socket': '/run/cctv-control/control.sock', 'camera_device': camera,
    }, handle, indent=2)
    handle.write('\n')
PY
chown root:cctv-control /etc/cctv-control/config.json /etc/cctv-control/credentials.json
chmod 0640 /etc/cctv-control/config.json /etc/cctv-control/credentials.json

if [ ! -f /etc/cctv-control/tls.key ]; then
  HOST=$(hostname -s | tr -cd 'A-Za-z0-9.-')
  [ -n "$HOST" ] || HOST=raspberry-pi-cctv
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -sha256 -days 825 -nodes \
    -subj "/CN=${HOST}.local" -addext "subjectAltName=DNS:${HOST}.local,IP:${LISTEN_ADDRESS}" \
    -keyout /etc/cctv-control/tls.key -out /etc/cctv-control/tls.crt >/dev/null 2>&1
fi
chown root:cctv-control /etc/cctv-control/tls.key
chmod 0640 /etc/cctv-control/tls.key
chown root:root /etc/cctv-control/tls.crt
chmod 0644 /etc/cctv-control/tls.crt
for unit in cctv-control.service cctv-control-helper.service cctv-control-cleanup.service cctv-control-cleanup.timer; do
  install -o root -g root -m 0644 "$PROJECT_DIR/systemd/$unit" "/etc/systemd/system/$unit"
done

python3 -m py_compile /opt/cctv-control/cctv_control.py /opt/cctv-control/cctv_control_helper.py
systemd-analyze verify /etc/systemd/system/motioneye.service /etc/systemd/system/cctv-*.service /etc/systemd/system/cctv-*.timer
systemctl daemon-reload
systemctl enable --now motioneye.service cctv-retention.timer cctv-health.timer cctv-control-helper.service cctv-control.service cctv-control-cleanup.timer

if [ "$WITH_TAILSCALE" -eq 1 ]; then
  log 'installing Tailscale from its signed Debian repository'
  apt-get install -y --no-install-recommends gnupg
  curl -fsSL https://pkgs.tailscale.com/stable/debian/trixie.noarmor.gpg -o /usr/share/keyrings/tailscale-archive-keyring.gpg
  FINGERPRINT=$(gpg --show-keys --with-colons /usr/share/keyrings/tailscale-archive-keyring.gpg | awk -F: '$1=="fpr" {print $10; exit}')
  [ "$FINGERPRINT" = '2596A99EAAB33821893C0A79458CA832957F5868' ] || die "unexpected Tailscale signing fingerprint: $FINGERPRINT"
  curl -fsSL https://pkgs.tailscale.com/stable/debian/trixie.tailscale-keyring.list -o /etc/apt/sources.list.d/tailscale.list
  apt-get update
  apt-get install -y tailscale
  systemctl enable --now tailscaled.service
  tailscale up --accept-dns=false --accept-routes=false --ssh=false --hostname="$(hostname -s)-cctv"
  tailscale serve --bg --https=443 http://127.0.0.1:8765 || echo 'Tailscale is connected, but Serve needs one-time tailnet approval; see docs/tailscale.md.' >&2
fi

log 'validating deployment'
/usr/local/sbin/cctv-validate
echo
echo "Installed successfully. CCTV Control: https://$LISTEN_ADDRESS:8443/"
if [ -f "$CREDENTIAL_OUTPUT" ]; then
  echo "New credentials (root-only): $CREDENTIAL_OUTPUT"
else
  echo 'Existing credentials were preserved.'
fi
echo "Backups: $BACKUP"
echo 'The local TLS certificate is self-signed; a browser warning is expected until you trust it.'
