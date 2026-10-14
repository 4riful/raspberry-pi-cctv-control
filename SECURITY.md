# Security policy

## Exposure model

This project is designed for a trusted private LAN and/or a private Tailscale
tailnet. Do not expose ports 8443, 8765, 7999, or 9081 to the public Internet.
Do not enable Tailscale Funnel for this service.

The control portal binds to one explicitly selected private IPv4 address.
motionEye, Motion control, and the MJPEG stream bind to loopback. The installer
does not change firewall or SSH policy.

## Credentials and keys

- Passwords are randomly generated on the target Pi.
- Only password hashes are stored in application configuration.
- Initial plaintext credentials are stored in a root-only file on the Pi.
- TLS private keys are generated on the Pi and must never be committed.
- Use `sudo cctv-rotate-credentials` after initial setup or suspected exposure.

The repository intentionally contains no credentials, API tokens, SSH keys,
Tailscale auth keys, certificates, device serial numbers, or operational logs.

## Destructive actions

The portal never immediately deletes recordings. It moves them to a protected,
same-filesystem quarantine, offers restore, and purges batches only after 24
hours. Open or recently modified recordings cannot be quarantined individually.
Delete-all requires an exact typed confirmation and temporarily stops recording
to make the move consistent.

## Reporting a vulnerability

Do not open a public issue with exploit details or secrets. Contact the
repository owner privately through GitHub.
