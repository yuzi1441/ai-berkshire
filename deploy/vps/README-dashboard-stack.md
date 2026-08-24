# VPS dashboard stack

The production dashboard uses three separate roots:

- `/opt/ai-berkshire-source`: clean, shallow, read-only `main` checkout.
- `/srv/ai-berkshire/releases/<sha>-<timestamp>`: validated releases.
- `/var/lib/ai-berkshire`: model checkpoints, last-success state and admin review output.

`/srv/ai-berkshire/current` is switched atomically only after migration, build,
compile and unit checks pass. The legacy `/opt/ai-berkshire` checkout is kept as
a rollback copy and is not deleted by these scripts.

## Endpoints

- `http://vps.06070419.xyz/`: public static dashboard; `/api/*` returns 404.
- `https://vps.06070419.xyz:8443/`: Basic-Auth admin origin; username `admin`.
- `127.0.0.1:8080`: Python backend, never bound to a public interface.
- TCP 443 remains owned by Xray and is not referenced by the Caddyfile.

## Initial install

Run from the legacy checkout after the matching `main` revision is available:

```bash
DASHBOARD_TEMP_PASSWORD='<temporary password>' \
  BOOTSTRAP_ROOT=/opt/ai-berkshire \
  bash /opt/ai-berkshire/deploy/vps/install-dashboard-stack.sh
```

After the authenticated smoke test, rotate once and save the printed password:

```bash
sudo /srv/ai-berkshire/current/deploy/vps/rotate-dashboard-password.sh
```

The password is printed once; only its Caddy hash is stored on disk.

## Normal flow and rollback

Pushing `main` is enough. The deploy timer polls every five minutes, builds a
new release and installs changed scripts, services, timers and Caddy config.
Runtime jobs never commit or push generated data. A failed activation restores
the previous `current` symlink and service configuration.

Reports are source files, so a new report is synchronized only after it is
committed and merged into `main`. An uncommitted report on either development
computer remains local and is intentionally not copied by a runtime job. The
VPS never pushes reports or generated data back to `main`; it only pulls the
merged source, validates/builds a release, and keeps sentiment checkpoints,
quotes, scan results and review state under `/var/lib/ai-berkshire`.

Useful checks:

```bash
systemctl status ai-berkshire-dashboard caddy --no-pager
systemctl list-timers 'ai-berkshire-a-share-*.timer' --no-pager
ss -ltnp | grep -E ':(80|443|8443|8080)\b'
```
