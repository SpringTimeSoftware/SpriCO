# Production Deployment Checklist

This checklist covers the current SpriCO AI Audit Platform repository. It assumes the frontend is a Vite/React app and the backend is the FastAPI app at `pyrit.backend.main:app`.

## 1. Deployable Inputs

Deploy these repository folders/files:

- `pyrit/`
- `audit/`
- `scoring/`
- `frontend/dist/` after a production frontend build
- `pyproject.toml`
- `package-lock.json` and `frontend/package-lock.json`, if rebuilding on the server
- `docs/`, optional but recommended for operator reference
- `THIRD_PARTY_NOTICES.md`
- `third_party/`
- `dbdata/`, only when migrating existing live/dev data

Do not rely on the frontend build alone. Live history, targets, evidence, findings, scanner runs, and artifacts live in backend data stores.

## 1.1 Release Package

Create a release package from the current repository state. Do not manually copy random folders from a developer machine.

Recommended package contents:

- application code: `pyrit/`, `audit/`, `scoring/`, `pyproject.toml`
- frontend build output: `frontend/dist/`
- legal/operator docs: `docs/`, `THIRD_PARTY_NOTICES.md`, `third_party/`
- dependency lock files, if rebuilding on the server

Keep application code separate from persistent data:

- code package: safe to replace during releases
- persistent data: must be backed up and migrated intentionally

Hard rule: never overwrite production `dbdata` during code deployment. A code release must not delete, replace, or reset production data unless a deliberate data migration/restore plan has been approved and tested.

Do not package stale saved localhost HTML. The only production frontend artifact should be `frontend/dist/` produced by `npm run build`.

## 2. Frontend Build

From the frontend directory:

```powershell
cd frontend
npm ci
npm run build
```

Build output:

- `frontend/dist/`

Deploy `frontend/dist/` as the static web root, or copy it into the production static hosting location used by IIS/Nginx.

Production HTML/title check:

- Open the deployed site in a browser.
- The browser title must be `SpriCO AI Audit Platform`.
- If the tab title shows an unrelated app name or old localhost content, the wrong frontend files were deployed.
- Rebuild with `npm run build` and redeploy only `frontend/dist/`.

## 3. Backend Install

Recommended production install from repository root:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

If tests/build tools are needed on the server:

```powershell
python -m pip install -e ".[dev]"
```

Use a dedicated virtual environment if possible. Avoid installing into a shared system Python on production servers.

## 4. Optional garak Install

garak is optional and provides scanner evidence only. It is not SpriCO's final verdict engine.

Install optional garak support:

```powershell
python -m pip install -e ".[garak]"
```

Or with dev/test dependencies:

```powershell
python -m pip install -e ".[dev,garak]"
```

Verify garak:

```powershell
python -c "import garak; print('garak import OK')"
python -m garak --help
```

Verify through SpriCO:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/garak/status
```

Expected:

- `available: true`
- `import_error: null`
- `advanced.python_executable` points to the backend Python environment

If garak is not installed, SpriCO should still start and the status endpoint should return an install hint.

## 5. Backend Startup

Development/local command:

```powershell
python -m uvicorn pyrit.backend.main:app --host 127.0.0.1 --port 8000
```

Production command behind a reverse proxy:

```powershell
python -m uvicorn pyrit.backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Use one worker unless the storage and PyRIT memory configuration has been reviewed for concurrent production writes.

Health checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/version
Invoke-RestMethod http://127.0.0.1:8000/api/storage/status
Invoke-RestMethod http://127.0.0.1:8000/api/scans/garak/reports
Invoke-RestMethod http://127.0.0.1:8000/api/judge/status
```

## 6. Reverse Proxy Requirements

The browser must reach:

- static frontend files
- backend API under `/api/*`
- backend `/version` if used by the app outside `/api`

Required behavior:

- Proxy `/api/` to the FastAPI backend.
- Preserve request method, body, query string, and headers.
- Support long-running scanner requests. Use timeouts of at least 5 minutes for `/api/scans/garak`.
- Set request body limits high enough for target config/import workflows.
- Serve the frontend fallback route to `index.html` for client-side `currentView` usage.
- Terminate TLS at the proxy or load balancer in production.
- Do not expose backend data files such as `dbdata/` as static files.

## 7. VITE_API_URL Behavior

Frontend API base behavior:

- `frontend/src/services/api.ts` uses `import.meta.env.VITE_API_URL || '/api'`.
- If `VITE_API_URL` is not set, the browser calls relative `/api`.
- In Vite dev mode, `frontend/vite.config.ts` proxies `/api` to `http://127.0.0.1:8000`.
- In production, configure IIS/Nginx so `/api` routes to the backend.

Recommended production build when frontend and API share one origin:

```powershell
npm run build
```

Recommended production build when API is on another origin:

```powershell
$env:VITE_API_URL="https://api.example.com/api"
npm run build
```

If `VITE_API_URL` points to a different origin, configure backend CORS with `PYRIT_CORS_ORIGINS`.

## 8. Persistent Data Paths

Default stores are under `dbdata/` relative to the backend working directory/repository path.

| Data | Default path | Environment/config override | Used by |
| --- | --- | --- | --- |
| SpriCO SQLite | `dbdata/sprico.sqlite3` | `SPRICO_SQLITE_PATH` | Evidence, Findings, Shield, Red, garak runs, policies, projects, custom conditions |
| SpriCO JSON fallback | `dbdata/sprico_storage.json` | `SPRICO_STORAGE_BACKEND=json` | Dev fallback only |
| PyRIT memory | `dbdata/pyrit.db` | backend startup memory configuration | Interactive Audit and Attack History |
| Audit DB | `dbdata/audit.db` | `AuditDatabase` constructor/config | Audit Runs, dashboards, benchmark library |
| Target configuration | `dbdata/audit.db` | `SPRICO_TARGET_DB_PATH` | Target Configuration, scanner/Red target registry |
| garak artifacts | `dbdata/garak_scans/{scan_id}/` | based on PyRIT `DB_DATA_PATH` | LLM Vulnerability Scanner artifacts |
| Target secrets key | `dbdata/target_secrets.key` | target store configuration | encrypted target secrets |
| Uploaded/PyRIT media | `dbdata/` | PyRIT `DB_DATA_PATH` derivation | media and serialized prompt artifacts |

Verify active paths:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/storage/status
```

## 9. Preserve Old History

Before deploying or replacing a server, back up:

- `dbdata/sprico.sqlite3`
- `dbdata/sprico_storage.json`, if JSON fallback was used
- `dbdata/pyrit.db`
- `dbdata/audit.db`
- `dbdata/garak_scans/`
- `dbdata/target_secrets.key`
- uploaded media and serialized PyRIT files under `dbdata/`

To migrate old history:

1. Stop backend and frontend services.
2. Back up current production `dbdata/`.
3. Copy the source `dbdata` files/folders to the production backend working directory.
4. Preserve file permissions for the backend service account.
5. Restart backend.
6. Verify `/api/storage/status` record counts.

Static exported HTML transcripts are rendered snapshots. They do not repopulate PyRIT memory, audit DB, Evidence Center, Findings, or scanner history automatically. Import exported HTML transcript is not implemented.

If Attack History is empty after deployment, first verify that `dbdata/pyrit.db` or the configured PyRIT memory database path was copied to the production data location and is readable by the backend service account.

If LLM Vulnerability Scanner says garak is unavailable, verify garak is installed in the same virtual environment or Python installation used by the backend service, not only in an administrator shell or a different Python environment.

## 10. Verify Data In The UI And API

Attack History:

- Data source: PyRIT CentralMemory attack sessions, usually `dbdata/pyrit.db`.
- API check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/storage/status
```

Check `record_counts.pyrit_attacks`.

Evidence Center:

- Data source: SpriCO SQLite `evidence_items`.
- API checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/evidence
Invoke-RestMethod http://127.0.0.1:8000/api/storage/status
```

Check `record_counts.evidence`.

Scanner History / Scanner Run Reports:

- Data source: SpriCO SQLite `garak_runs` plus `garak_artifacts`.
- API checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/scans/garak
Invoke-RestMethod http://127.0.0.1:8000/api/scans/garak/reports
Invoke-RestMethod http://127.0.0.1:8000/api/scans/garak/reports/summary
Invoke-RestMethod http://127.0.0.1:8000/api/storage/status
```

Check `record_counts.scanner_runs`.

Targets, policies, findings:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/targets
Invoke-RestMethod http://127.0.0.1:8000/api/policies
Invoke-RestMethod http://127.0.0.1:8000/api/storage/status
```

Check `record_counts.policies`, `record_counts.findings`, and expected targets in Target Configuration.

## 11. Windows Server / IIS Notes

Recommended layout:

- App code: `C:\SpriCOApp\`
- Persistent data: `C:\SpriCOData\`
- IIS serves `C:\SpriCOApp\frontend\dist\` as the website root.
- IIS URL Rewrite + ARR proxies `/api/*` to `http://127.0.0.1:8000/api/*`.
- Backend runs as a Windows service or scheduled task using the same app directory and venv every time.

Recommended environment:

- `SPRICO_SQLITE_PATH=C:\SpriCOData\sprico.sqlite3`
- `SPRICO_TARGET_DB_PATH=C:\SpriCOData\audit.db`
- PyRIT memory path should resolve to `C:\SpriCOData\pyrit.db` through the backend startup/memory configuration.
- garak artifacts should be stored under `C:\SpriCOData\garak_scans\` if `DB_DATA_PATH` is configured outside the app directory.

Checklist:

- Install URL Rewrite and Application Request Routing.
- Enable proxy in ARR.
- Set IIS site physical path to `frontend/dist`.
- Add rewrite rule for `/api/(.*)` to `http://127.0.0.1:8000/api/{R:1}`.
- Add rewrite fallback for non-file frontend routes to `index.html`.
- Increase proxy timeout for scanner runs.
- Confirm backend service account has read/write permissions for `dbdata/`.
- Confirm the backend service account has read/write permissions for `C:\SpriCOData\`.
- Confirm the scheduled task/service working directory is `C:\SpriCOApp\`.
- Restart backend after code updates; otherwise new routes may still return 404.

Windows verification:

```powershell
Invoke-RestMethod http://localhost/api/version
Invoke-RestMethod http://localhost/api/storage/status
Invoke-RestMethod http://localhost/api/garak/status
```

If the frontend is served by Vite on port `3000`, remember that `/api` is proxied to `127.0.0.1:8000`. A 404 on `localhost:3000/api/...` usually means the backend on port `8000` is stale or missing that route.

## 12. Linux / Nginx Notes

Recommended layout:

- App code: `/opt/sprico/`
- Persistent data: `/opt/sprico-data/`
- Nginx serves `/opt/sprico/frontend/dist/`.
- Nginx proxies `/api/` to `http://127.0.0.1:8000/api/`.
- Backend runs under systemd with a dedicated virtual environment.

Recommended environment:

- `SPRICO_SQLITE_PATH=/opt/sprico-data/sprico.sqlite3`
- `SPRICO_TARGET_DB_PATH=/opt/sprico-data/audit.db`
- PyRIT memory path should resolve to `/opt/sprico-data/pyrit.db` through the backend startup/memory configuration.
- garak artifacts should be stored under `/opt/sprico-data/garak_scans/` if `DB_DATA_PATH` is configured outside the app directory.

Example Nginx shape:

```nginx
server {
    listen 443 ssl;
    server_name sprico.example.com;

    root /opt/sprico/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Example systemd service command:

```ini
ExecStart=/opt/sprico/.venv/bin/python -m uvicorn pyrit.backend.main:app --host 127.0.0.1 --port 8000 --workers 1
WorkingDirectory=/opt/sprico
```

Linux verification:

```bash
curl -s http://127.0.0.1:8000/api/version
curl -s http://127.0.0.1:8000/api/storage/status
curl -s http://127.0.0.1:8000/api/garak/status
curl -s https://sprico.example.com/api/scans/garak/reports
```

Ensure the service user owns or can write `/opt/sprico-data/`.

## 13. Backup And Rollback

Before release:

1. Stop backend.
2. Back up code version or deployment package.
3. Back up `frontend/dist/`.
4. Back up the complete `dbdata/` directory.
5. Record active environment variables:
   - `SPRICO_SQLITE_PATH`
   - `SPRICO_STORAGE_BACKEND`
   - `SPRICO_TARGET_DB_PATH`
   - `PYRIT_CORS_ORIGINS`
   - `SPRICO_OPENAI_JUDGE_ENABLED`
   - `SPRICO_OPENAI_JUDGE_MODEL`
   - `OPENAI_API_KEY`, record presence only, not the secret value

Rollback:

1. Stop backend and frontend/reverse proxy if needed.
2. Restore previous code package.
3. Restore previous `frontend/dist/`.
4. Restore previous `dbdata/` files if storage schema/data changed or data loss is suspected.
5. Restore previous environment variables/service configuration.
6. Restart backend.
7. Verify `/api/version`, `/api/storage/status`, Attack History, Evidence Center, Scanner Run Reports, Target Configuration, and Findings.

## 13.1 Pre-Deploy Checklist

| Check | Required result |
| --- | --- |
| Release package built from current repo | App code and `frontend/dist/` are from the intended commit/build |
| Frontend build completed | `npm run build` succeeded and produced `frontend/dist/` |
| Browser title checked in build | `frontend/dist/index.html` contains `SpriCO AI Audit Platform` |
| Persistent data separated | Production data is outside the replaceable app package, e.g. `C:\SpriCOData\` or `/opt/sprico-data/` |
| Production data backup completed | Current data directory and all configured DB paths are backed up |
| `dbdata` overwrite blocked | Deployment plan does not replace production data with packaged/dev data |
| Backend venv identified | Service uses the intended Python/venv |
| garak checked, if required | `python -c "import garak"` succeeds in the backend service environment |
| Reverse proxy reviewed | `/api/*` proxies to backend and long scanner timeout is configured |
| Rollback package ready | Previous app package, frontend build, config, and data backup are available |

## 13.2 Post-Deploy Checklist

| Check | Required result |
| --- | --- |
| Backend starts | `/api/version` returns 200 |
| Storage paths correct | `/api/storage/status` shows expected production data paths |
| Frontend title correct | Browser title is `SpriCO AI Audit Platform` |
| Targets visible | Target Configuration shows expected production targets |
| Attack History verified | Expected PyRIT sessions appear, or `record_counts.pyrit_attacks` explains empty state |
| Evidence Center verified | Evidence count and UI records match expected migrated data |
| Scanner reports verified | `/api/scans/garak/reports` returns 200 and Scanner Run Reports loads |
| garak status verified | `/api/garak/status` returns expected installed/unavailable status |
| Findings verified | Findings page shows actionable findings only |
| Dashboard verified | Structured Dashboard shows scanner run coverage metrics |

## 14. Final Production Smoke Test

Run after deployment:

```powershell
Invoke-RestMethod https://YOUR_HOST/api/version
Invoke-RestMethod https://YOUR_HOST/api/storage/status
Invoke-RestMethod https://YOUR_HOST/api/garak/status
Invoke-RestMethod https://YOUR_HOST/api/scans/garak/reports
Invoke-RestMethod https://YOUR_HOST/api/judge/status
```

Then verify in the UI:

- Home loads without the compact left rail.
- Target Configuration shows expected targets.
- Attack History explains PyRIT-backed sessions and shows expected records if `pyrit.db` was migrated.
- LLM Vulnerability Scanner loads targets and scanner history.
- Scanner Run Reports shows no-finding and failed/timeout scanner runs.
- Evidence Center shows expected normalized evidence.
- Findings shows actionable findings only.
- Structured Dashboard shows scanner run coverage metrics.
