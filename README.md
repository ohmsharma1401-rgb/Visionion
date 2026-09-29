# OnionGrade AI

OnionGrade now runs a **real trained bulb-health model using the ZIP you supplied**. The responsive React app supports image upload/camera, per-onion user outlines, reference calibration, explainable grading decisions, history, JSON export, and PDF reports with original/annotated images and hash/QR verification.

**Supported real labels:** healthy bulb, unhealthy bulb and leaf only. The dataset has no instance masks, boxes, measured sizes or defect subtypes. Automatic onion segmentation and separate rotten/damaged/sprouted predictions therefore remain untrained. The app does not invent these capabilities: individual real bulbs are user-confirmed or user-outlined, health-only Grade A remains unresolved, and URS is disabled pending an official definition. An explicitly selected **DEMO ANALYSIS** mode exercises the multi-class segmentation/grading flow with mock geometry and findings.

See [combined architecture and flowcharts](docs/combined-architecture.md), [model card](ml/MODEL_CARD.md), and [validation](docs/validation.md).

For a Vercel web deployment, see [Vercel deployment](docs/vercel-deployment.md). The public site requires a separately hosted HTTPS API and PostgreSQL; a static frontend by itself cannot run the trained model or save reports.

## Start the existing workspace

```powershell
.\.venv\Scripts\python.exe scripts/run_local.py
```

In another terminal:

```powershell
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. The home page is public. To create an account, enter a name, email address and password, verify the six-digit code sent to **that email inbox**, then sign in. This is email delivery, not SMS; you can read the message in Gmail on your phone. Before starting the API, set `SMTP_APP_PASSWORD` privately in its environment for the `amrishs256@gmail.com` sender. The value must be a new 16-character [Google app password](https://support.google.com/accounts/answer/185833); a Google backup code or ordinary account password will not work. Do not put it in `web/`, commit it, or post it in chat. In PowerShell, set it in the same terminal used to start the API:

```powershell
$smtpSecret = Read-Host 'New Gmail app password' -AsSecureString
$env:SMTP_APP_PASSWORD = [System.Net.NetworkCredential]::new('', $smtpSecret).Password
.\.venv\Scripts\python.exe scripts/run_local.py
```

The local API uses SQLite for this local prototype unless PostgreSQL is configured. Set `DATABASE_URL` to a PostgreSQL URL (for example `postgresql+psycopg://oniongrade:password@127.0.0.1:5432/oniongrade`) or set `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` before running the launcher to use PostgreSQL. It applies Alembic migrations and copies previous SQLite records once after verifying their hashes. Protect `data/` like any local credential and evidence store.

For this Windows local workspace, the launcher also reads an existing `data/smtp-app-password.txt` when `SMTP_APP_PASSWORD` is not set. This Git-ignored file should contain only the app password. Replace it and restart the API when rotating the credential; use a private environment variable on a hosted backend.

## Fresh installation

Use Python 3.12 and Node 22+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
npm.cmd ci --prefix web
```

For CPU-only inference use the official PyTorch CPU wheel index instead. The GPU wheel pair used here is documented in [PyTorch's version matrix](https://docs.pytorch.org/get-started/previous-versions/). On macOS/Linux use `.venv/bin/python` and a platform-appropriate PyTorch build.

The active weights are `ml/models/bulb-health-all-v2.pt` (6.21 MB), with the checkpoint hash and training counts in `ml/models/bulb-health-all-v2.json`. This checkpoint uses all 16,271 unique usable images. There is no independent holdout for v2; the v1 evaluation below must not be presented as v2 accuracy. The v1 TorchScript file is not a v2 export or an integrated mobile runtime.

## Real-image flow

1. Select **Trained onion health model**, upload a clear, close photo, or use **Camera**. **Whole photo · no drawing** is the default and ignores unfinished drawing marks.
2. For separate results per bulb, choose **Individual onions · optional**, then **Outline onion**, click around each visible bulb, and **Finish outline** for each. These are user-provided regions, not automatic model detections. A photo containing mixed healthy and unhealthy bulbs receives one combined image-level prediction, so photograph a single onion for the clearest quick result.
3. Physical measurement is optional. Use a printed 50 mm marker or **Reference scale** with two endpoints of a known-size reference in the same plane, and enter its length in millimetres. A valid onion outline is also required to measure a bulb. Whole-photo screening needs neither an outline nor a reference.
4. Sign in and analyze. New health analyses receive an **AI visual grade** of Good, Poor, or Review required, saved in the result and PDF. Leaf-only and uncertain predictions remain visible as review results. These app-defined visual grades do not establish Grade A or URS eligibility.
5. Generate a PDF or export JSON. History contains only saved v2 analyses; old v1 snapshots remain in the database but are hidden because their grading semantics differ.

The health model cannot certify Grade A or calculate the weighted defect quality score. Its healthy prediction does not prove the absence of a specific defect. Unhealthy stays unspecified rather than being relabeled as rot. In demo mode mock findings exercise these rules but are not evidence about the uploaded image.

## Training and dataset preparation

The user supplied `Image Dataset of Red and White Onion Bulbs and Lea.zip`, containing another ZIP. The nested archive was inspected and saved to ignored `ml/datasets/raw/onion-source.zip`. It contains 16,300 images, including bulbs and leaves, with classification folders only. No content was uploaded to an external service.

```powershell
.\.venv\Scripts\python.exe ml/datasets/prepare_dataset.py
.\.venv\Scripts\python.exe ml/datasets/validate_dataset.py
.\.venv\Scripts\python.exe ml/training/train_health.py --epochs 12 --workers 2
.\.venv\Scripts\python.exe ml/training/export_health.py
.\.venv\Scripts\python.exe ml/training/train_all_health.py
```

Preparation removes exact duplicates and conflicting hash labels, decodes every image, and preserves source labels. Multiple-bulb pictures are held out as an image-level stress test. There are no lot IDs: 100-consecutive-file groups provide an explicit proxy split, not proof of independent lots. Mild augmentation applies only to training.

The first v1 run used 8,177 training, 1,726 validation, 2,137 test and 4,231 multiple-bulb stress images. Its provisional held-out accuracy was **99.77%**, macro F1 **0.9970**. A subsequent six-epoch v2 fine-tune used **all 16,271 unique usable images**, including the former validation, test and multi-bulb sets. No independent v2 accuracy estimate remains. See the full model card for confounders and unsupported claims.

YOLO segmentation scaffolding remains in `ml/train.py`, `ml/evaluate.py`, `ml/export.py`, and `ml/dataset.yaml`. It is a separate workflow requiring proper instance annotations; it was not trained using invented masks from this ZIP. `ONION_SEG_WEIGHTS` can enable the optional real segmentation adapter after compatible onion weights and label semantics are validated.

## API

- `POST /api/auth/register`, `/api/auth/verify-otp`, `/api/auth/resend-otp`, `/api/auth/login`; `GET /api/auth/me`
- `POST /api/analyze`: multipart `image`, `mode`, optional `regions` polygons, `calibration_reference_mm`, `calibration_points`, `variety`; health mode runs on the whole image when regions are omitted.
- `POST /api/analyze/batch`: 1–10 independent whole-image health screens. No repeated-onion cross-image deduplication is claimed.
- `GET /api/inspection/{id}`, `/image`, `/annotated`
- `GET /api/inspections`
- `POST /api/report/{id}`, `GET /api/report/{id}/pdf`
- `GET /api/reports/verify/{hash}`
- `GET /api/model/info`, `/api/grading-spec`, `/api/health`, `/api/audit/verify`

OpenAPI is available at `http://127.0.0.1:8000/docs`. Analysis records are immutable. JPEG evidence is re-encoded without EXIF. A canonical analysis hash is embedded in the PDF; the separate PDF byte hash is stored and verified independently. A single document cannot contain its own conventional SHA-256 without a self-reference problem. Hashes are not digital signatures; the local database is not an externally anchored immutable ledger.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests backend/grading/tests -q
npm.cmd run build
.\.venv\Scripts\python.exe scripts/verify_real_model.py
```

The browser check is `scripts/browser-check.cjs` with Playwright and installed Edge; set `PLAYWRIGHT_MODULE` to its module path if using the bundled runtime. `scripts/summarize_training.py` generates an evaluation figure with Matplotlib (optional plotting dependency).

## Deployment and remaining work

Docker Compose builds the CPU inference environment, starts a persistent PostgreSQL service, waits for it to become healthy, applies Alembic migrations, then starts the API. Keep the evaluated weights in `ml/models` before building. Copy `.env.example` to `.env`, replace the demo, JWT and PostgreSQL passwords, then run `docker compose up --build`. Docker has not been executed here. Keep one API worker: local locks and rate counters are not distributed. Docker's database volume is independent of the local launcher database; it does not automatically contain the migrated local history. Its PostgreSQL server is exposed only on `127.0.0.1:5433`; to migrate the previous SQLite records, set `POSTGRES_HOST=127.0.0.1`, `POSTGRES_PORT=5433`, `POSTGRES_USER=oniongrade`, `POSTGRES_DB=oniongrade` and `POSTGRES_PASSWORD` from `.env`, then run `scripts/migrate_sqlite_to_postgres.py` from the host.

The current PostgreSQL snapshot schema is documented in `docs/schema.sql`; Alembic owns changes to the deployed schema. Additional production work includes expert instance annotations, independent-lot evaluation, calibrated size validation, reviewer corrections, full RBAC, TLS, stronger identity/rate controls, external audit anchoring, encrypted storage, multilingual UI/reports and on-device inference. PWA shell caching is not offline inference or automatic sync.
