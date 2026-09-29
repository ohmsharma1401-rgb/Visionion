# Validation — v2

Validated on Windows with Python 3.12 and Node 24, 2026-09-29:

- 31 automated backend/grading tests pass. Coverage includes size boundaries, missing calibration, low confidence, unknown defect handling, Grade A denominator policy, configured/disabled URS, transparent score weights, image corruption/empty/size/MIME/blur/light checks, batch partial failures, ownership, rate limits, report generation, record/audit verification and tampered-PDF detection.
- TypeScript and Vite production build pass.
- Playwright/Edge full flow passes: real trained model availability, sign-in, actual held-out image upload, trained health result, clickable region, original/annotated toggle, PDF download, 390px mobile layout and explicit mock multi-onion selection. Desktop/mobile screenshots visually inspected.
- Real live API checks: held-out healthy bulb → HEALTHY_BULB; unhealthy bulb → UNHEALTHY_BULB; leaf-only image → rejected. Grade A, URS and defect score remain null for the real health-only model; no uncalibrated diameters appear.
- Dataset manifest validation passes: 16,271 images, no exact SHA-256 duplicate or proxy sequence group crosses partitions. True lot independence is unknown.
- Isolated unit tests use SQLite. PostgreSQL migration and integration remain to be validated against a running server. This machine has no PostgreSQL installation; a portable binary attempt was blocked by Windows Application Control when it loaded a server library. The previous SQLite file and image/PDF evidence remain in place.
- Actual GPU training completed; held-out and stress metrics are preserved in the model card and JSON. TorchScript export completed and matches eager logits on a reference tensor.
- Three-page real-model report rendered with Poppler; each page visually inspected. Unicode minus was replaced with ASCII for report font compatibility. Optional Symbol/ArialUnicode fallback warnings do not affect the Helvetica document.

One non-failing dependency warning remains: the installed Starlette version deprecates HTTPX TestClient support. It did not cause test failures.

Not validated: real segmentation model, independent field/lot accuracy, expert defect subtypes, calibrated physical size accuracy, Docker execution, physical phone camera behavior, mobile offline inference or production security. No claims are made for these.
