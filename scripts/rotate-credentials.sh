#!/bin/sh
set -eu

[ "$(id -u)" -eq 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
umask 077
stamp=$(date -u +%Y%m%dT%H%M%SZ)
output="/root/cctv-credentials-${stamp}.txt"

/opt/motioneye/bin/python - "$output" <<'PY'
import base64, hashlib, json, secrets, string, sys
from pathlib import Path
from argon2 import PasswordHasher

alphabet = string.ascii_letters + string.digits
make = lambda: ''.join(secrets.choice(alphabet) for _ in range(28))
motioneye_password = make()
portal_password = make()

path = Path('/etc/motioneye/motion.conf')
lines = [line for line in path.read_text().splitlines() if not line.startswith('# @admin_password ')]
insert = next((i + 1 for i, line in enumerate(lines) if line.startswith('# @admin_username ')), 1)
lines.insert(insert, '# @admin_password ' + PasswordHasher().hash(motioneye_password))
path.write_text('\n'.join(lines) + '\n')

salt = secrets.token_bytes(24)
iterations = 600000
digest = hashlib.pbkdf2_hmac('sha256', portal_password.encode(), salt, iterations)
Path('/etc/cctv-control/credentials.json').write_text(json.dumps({
    'username': 'admin', 'salt': base64.b64encode(salt).decode(),
    'hash': base64.b64encode(digest).decode(), 'iterations': iterations,
}) + '\n')

Path(sys.argv[1]).write_text(
    'motionEye\nUsername: admin\nPassword: ' + motioneye_password +
    '\n\nCCTV Control\nUsername: admin\nPassword: ' + portal_password + '\n'
)
PY
chown motion:motion /etc/motioneye/motion.conf
chmod 0600 /etc/motioneye/motion.conf
chown root:cctv-control /etc/cctv-control/credentials.json
chmod 0640 /etc/cctv-control/credentials.json
systemctl restart motioneye.service cctv-control.service
echo "Credentials rotated. Root-only copy: $output"
