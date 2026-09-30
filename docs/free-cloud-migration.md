# Remove the laptop dependency

Status: preparation only. The deployed frontend still uses the laptop tunnel.

The Vercel frontend is already hosted. The Python API, model, SQLite database,
SMTP sender, images and PDFs currently depend on the laptop being awake.
Restarting the tunnel does not solve this architectural dependency.

## Free deployment target

- Keep the Vercel frontend.
- Host the API on a free cloud container service such as Render. Confirm that
  memory limits can accommodate model loading and inference before switching traffic.
- Use the existing Supabase project's PostgreSQL database for accounts and records.
- Move original images, annotated images and immutable PDFs to private Supabase
  Storage. Keep owner checks in the API; never make the evidence bucket public.
- Replace direct SMTP delivery with an HTTPS email provider, or move account
  verification to Supabase Auth with configured custom SMTP. Render Free blocks SMTP.

Free Render services sleep after inactivity and have no persistent disk. Supabase
Free can pause inactive projects. This setup removes the laptop dependency but
cannot guarantee uninterrupted availability or instant cold starts.

## Required access and implementation

1. Connect Render and Supabase in this chat. Choose only free resources.
2. Verify the existing Supabase project and back up local records/evidence.
3. Implement private object storage and cloud-compatible email delivery before
   deploying. Do not put the current DATA_DIR on ephemeral cloud storage and
   claim that reports are persistent.
4. Migrate the SQLite accounts, inspections, audit records and report hashes into
   PostgreSQL, and copy evidence files with hash verification.
5. Configure persistent JWT_SECRET, database credentials and email credentials as
   backend-only secrets. Do not place secrets in VITE_ variables or source control.
6. Deploy using infra/Dockerfile, the host's PORT and /api/health checks. Test the
   trained model against actual images within the free instance's memory limit.
7. Test email verification, normal/demo login, uploads, history, report generation,
   report verification and data recovery after a cloud restart.
8. Set Vercel VITE_API_BASE_URL to the verified cloud API and redeploy.
9. Stop the local backend and tunnel and repeat the public workflow. Only then is
   the laptop-independent migration complete. Keep the local backup for rollback.

References: https://render.com/docs/free and
https://supabase.com/docs/guides/platform/free-project-pausing
