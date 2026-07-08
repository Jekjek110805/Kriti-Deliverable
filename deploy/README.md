# Deploying Kriti to Cloud Run with live GSC + OpenRouter AI

Two things need secrets at runtime: the GSC service-account key **and** the
OpenRouter API key. We do **not** bake either into the Docker image (that would
leak them to anyone who can pull the image). Both live in **Secret Manager** —
the GSC key is mounted as a file, the OpenRouter key as an env var.

## What the scripts do

`deploy_cloudrun.ps1` (Windows / PowerShell) and `deploy_cloudrun.sh` (bash) both:

1. Enable the required APIs (`run`, `secretmanager`, `searchconsole`, `cloudbuild`).
2. Create the `gsc-credentials` secret (if missing) and push a new version from
   your local `config/gsc_credentials.json`.
3. Create the `openrouter-key` secret (if missing) and push a new version from
   the `OPENROUTER_API_KEY` in your local `.env` (or a passed parameter).
4. Grant the Cloud Run runtime service account `secretAccessor` on both secrets.
5. Deploy, mounting the GSC key at `/secrets/gsc_credentials.json`, injecting the
   OpenRouter key as an env var, and setting:
   - `GSC_CREDENTIALS_PATH=/secrets/gsc_credentials.json`
   - `GSC_SITE_URL=https://selfstorage.help/`
   - `OPENROUTER_API_KEY` (from the `openrouter-key` secret)
   - `OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free`

The app reads these env vars (env wins over any config-file default), so once
deployed the live domain behaves exactly like local — **including AI features**,
which would otherwise fail with `[OpenRouter not configured]` because `.env` is
never copied into the image.

## Prerequisites

- `gcloud` CLI installed and authenticated: `gcloud auth login`
- The service-account JSON present at `config/gsc_credentials.json`
- `OPENROUTER_API_KEY` present in `.env` (or pass `-OpenRouterKey` / `OPENROUTER_KEY=`)
- The service account already added in **Search Console → Settings → Users and
  permissions** with **Full** access (done for
  `selfstorage@for-kriti-500207.iam.gserviceaccount.com` on `selfstorage.help`).

## Run it

PowerShell (from the project root):

```powershell
.\deploy\deploy_cloudrun.ps1
```

bash:

```bash
./deploy/deploy_cloudrun.sh
```

Override any default via parameters / env vars, e.g.:

```powershell
.\deploy\deploy_cloudrun.ps1 -SiteUrl "https://yourdomain.com/"
```

```bash
SITE_URL="https://yourdomain.com/" ./deploy/deploy_cloudrun.sh
```

## Verify after deploy

GSC (replace with your deployed service URL):

```bash
curl https://<your-cloud-run-url>/api/integrations/gsc/status
```

Expect `"status": "connected"`. The Integrations card in the deployed UI will
then show GSC as connected (green).

OpenRouter / AI: generate a brief or draft in the deployed UI (Content → Write)
and confirm the output is real text, **not** `[OpenRouter not configured: set
OPENROUTER_API_KEY in .env]`.

## Rotating the key

After regenerating the key in Google Cloud, just push a new secret version and
redeploy (or the next deploy picks up `:latest`):

```bash
gcloud secrets versions add gsc-credentials \
  --data-file=config/gsc_credentials.json --project for-kriti-500207
```

## Notes

- `config/gsc_credentials.json` is excluded by both `.gitignore` and
  `.dockerignore`, so it is never committed or copied into the image.
- A connected deployment can still return `empty_data` if the property has no
  Search traffic in the requested window — that is expected, not an error.
- Alternative (no key file): since the app runs in the same project, you could
  use the Cloud Run runtime service account via Application Default Credentials
  instead. That needs a small code change in `gsc_client.py`
  (`google.auth.default()`); the Secret Manager route above works with the code
  as-is.
