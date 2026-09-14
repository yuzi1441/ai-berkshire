# Publishing

Publishing requires an explicit request and a successful `validation.json` for
the same transaction. Revalidate, confirm authority hashes, apply the two
components and pointer under `data/local-daily-review/published/`, then run the
production-equivalent dashboard validation and full tests.

Confirm Canonical 229/229, legacy 0, parser HIGH 0, and no authority changes.
Exact-stage only the dated sentiment/opportunity files and `latest.json`, commit
and push normally, wait for CI, then verify the exact VPS SHA and Dashboard.

Never SSH-edit production JSON. Do not remove VPS secrets or disable the old
model path until a real local review passes the entire chain and cutover is
separately approved.
