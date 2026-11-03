# Security rollout — SEC-20261103-01

This PR proposes a fail-closed security baseline. **Do not deploy until these gates pass.**

1. **Authentication compatibility:** JWTs signed with HS256 should remain readable when swapping `python-jose` to `PyJWT`. Test with a real existing *non-sensitive test token* in staging, never paste a production token into logs. Set JWT_ALGORITHM to HS256 only.
2. **Existing password hashes:** New hashes use bcrypt exclusively. The previous runtime could create `sha256:` hashes if bcrypt was missing. This PR intentionally rejects those weaker hashes. Count legacy hashes in secure runtime/storage (do not export them), then run a controlled password reset/re-hash migration before cutover. Deploying without migration may block some logins.
3. **Trusted frontend:** `CORS_ORIGINS` is a comma-separated exact-origin list (e.g. https://app.example.test). Default is empty, so only same-origin browser requests work. Set actual trusted production frontend origin(s) before rollout. CORS is a browser restriction, not server-side authorization.
4. **Dependencies:** `python-multipart==0.0.33` needs Python >=3.11; Dockerfile runs Python 3.11. `jinja2==3.1.6` and `PyJWT==2.15.1` replace vulnerable/old packages. Run installation, full pytest, SCA and a smoke test in staging.
5. **Go/no-go:** Verify admin/client login, token refresh, form-data requests, document upload routes, browser preflights, and existing signed token compatibility. Deploy with a rollback plan and on-call owner. Confirm runtime dependency versions after release.
6. **Data and secrets:** These public-code updates are *not* remediation of the private Hermes-owned credential leaks tracked in the private control issue; that requires provider-native rotation and storage migration.

Suggested validations: `python -m pip install -r requirements.txt`, `python -m pytest -q`, `python -m pip check`, and SCA scanning. CI result required before merge.
