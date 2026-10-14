# Private Tailscale access

Use `--with-tailscale` during installation to add Tailscale from its signed
official Debian repository. The installer verifies signing fingerprint:

`2596A99EAAB33821893C0A79458CA832957F5868`

It connects with DNS acceptance, subnet routes, exit nodes, and Tailscale SSH
disabled. It then attempts to publish loopback-only motionEye through private
HTTPS Serve on port 443.

If Serve requires one-time tailnet approval, follow the URL printed by:

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8765
```

Confirm the result:

```bash
tailscale status
tailscale serve status
tailscale funnel status
```

Serve must say **tailnet only**. Funnel must not be enabled. Test from a second
device that is connected to the same tailnet; signing into the Tailscale admin
website alone does not connect that device.

To remove private Serve without disconnecting Tailscale:

```bash
sudo tailscale serve reset
```
