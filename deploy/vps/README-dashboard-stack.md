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

After the one-time guard migration below, pushing `main` is enough. The deploy timer polls every five minutes, builds a
new release and installs changed scripts, services, timers and Caddy config.
Runtime jobs never commit or push generated data. A failed activation restores
the previous `current` symlink and service configuration.

Reports are source files, so a new report is synchronized only after it is
committed and merged into `main`. An uncommitted report on either development
computer remains local and is intentionally not copied by a runtime job. The
VPS never pushes reports or generated data back to `main`; it only pulls the
merged source, validates/builds a release, and keeps sentiment checkpoints,
quotes, scan results and review state under `/var/lib/ai-berkshire`.

## One-time release guard migration — NOT executed by this change

The publisher installed by older `main` revisions does not check GitHub CI.
Updating the repository's publisher does **not** constrain that running copy:
it installs its successor only after switching `current`. Before merging the
first release that relies on this guard, an operator must perform these steps
on the VPS. This implementation has only been tested locally; no SSH, bootstrap
installation on the VPS, or production release has been performed.

1. Mask the deploy service and stop its timer **before merging**. Masking does
   not kill an already running publisher; wait for it to finish. Keep deploy
   masked throughout migration, including if any later command fails.
   ```bash
   sudo systemctl mask ai-berkshire-a-share-scheduler@deploy.service
   sudo systemctl stop ai-berkshire-a-share-deploy.timer
   systemctl is-active ai-berkshire-a-share-scheduler@deploy.service
   ```
2. Place the reviewed revision containing this guard in a separate, clean
   checkout at `/opt/ai-berkshire-gate-bootstrap`. Verify its full SHA and diff
   against the approved revision. Do not use the old `current` or a dirty tree.
   Install the bootstrap while holding the same runtime lock as the scheduler:
   First install the reviewed `requirements-technical.txt` into the service
   venv (`/opt/ai-berkshire-venv/bin/python -m pip install -r
   /opt/ai-berkshire-gate-bootstrap/requirements-technical.txt`) during this
   maintenance window. Existing venvs also need the new exchange-calendars
   dependency; the publisher checks its exact reviewed version before any
   release/source mutation and blocks on absence. Do not resume publishing if
   dependency installation fails. This dependency upgrade has not been run on
   the VPS by this change. The bundled XSHG holiday data currently ends in 2026;
   update and test the calendar before 2027 (outside coverage, quotes fail closed).
   ```bash
   git -C /opt/ai-berkshire-gate-bootstrap rev-parse HEAD
   git -C /opt/ai-berkshire-gate-bootstrap status --porcelain --untracked-files=all
   sudo flock -x /run/lock/ai-berkshire-runtime.lock \
     env BOOTSTRAP_ROOT=/opt/ai-berkshire-gate-bootstrap \
     bash /opt/ai-berkshire-gate-bootstrap/deploy/vps/install-release-guard.sh
   sudo head -n 5 /usr/local/sbin/ai-berkshire-publish-release
   ```
   The installer changes only the publisher/refresh entries and a private bundle beneath
   `/usr/local/lib/ai-berkshire-release-gate/`. The entry pins the publisher and
   both validation tools and the compatible refresh script together, and forces CI checking. It does not fetch,
   publish, restart services, install skills, or call a model. Any previous
   entries are retained as `previous-entry` / `previous-refresh` in the printed bundle directory.
3. Merge the approved revision and verify that its **main push** workflow has
   completed successfully; PR validation alone is insufficient. Then unmask
   deploy and resume polling:
   ```bash
   sudo systemctl unmask ai-berkshire-a-share-scheduler@deploy.service
   sudo systemctl start ai-berkshire-a-share-deploy.timer
   ```
   Pending, failed or missing push CI keeps the prior release active. Initial
   stack installation and subsequent service refreshes use the same bootstrap
   installer, so neither path replaces the guard with an unwrapped publisher.
   The pinned refresh script also retains the guard when rolling back to a
   legacy release without the bootstrap installer; it does not reinstall that
   release's old publisher or old refresh script.

A same-SHA release is skipped only when both copies of its schema-v2 validation
record match the requested SHA/tree, contain complete input hashes, and record
successful service activation. Missing, malformed, legacy or unactivated records
go through CI and a fresh staging build. Hashes describe the inputs at validation
time, not later runtime updates; live data changes do not trigger redeployment.
These local provenance records are not cryptographic attestations.

If migration fails, leave deploy masked and the prior dashboard serving. Do not
restore an older unguarded entry and resume polling. Bundle backups are retained
for operator inspection; removing the guard is not an automatic rollback step.

Useful checks:

```bash
systemctl status ai-berkshire-dashboard caddy --no-pager
systemctl list-timers 'ai-berkshire-a-share-*.timer' --no-pager
ss -ltnp | grep -E ':(80|443|8443|8080)\b'
```
