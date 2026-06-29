# Deploying Kriti to Cloud Run with live GSC

The Search Console integration needs the service-account key at runtime. We do
**not** bake it into the Docker image (that would leak the secret to anyone who
can pull the image). Instead the key lives in **Secret Manager** and is mounted
into the container as a file.

## What the scripts do

`deploy_cloudrun.ps1` (Windows / PowerShell) and `deploy_cloudrun.sh` (bash) both:

1. Enable the required APIs (`run`, `secretmanager`, `searchconsole`, `cloudbuild`).
2. Create the `gsc-credentials` secret (if missing) and push a new version from
   your local `config/gsc_credentials.json`.
3. Grant the Cloud Run runtime service account `secretAccessor` on that secret.
4. Deploy, mounting the secret at `/secrets/gsc_credentials.json` and setting:
   - `GSC_CREDENTIALS_PATH=/secrets/gsc_credentials.json`
   - `GSC_SITE_URL=https://kriti-maai-268992122217.australia-southeast1.run.app/`

The app reads `GSC_CREDENTIALS_PATH` (env var wins over the config default), so
once deployed the live domain behaves exactly like local.

## Prerequisites

- `gcloud` CLI installed and authenticated: `gcloud auth login`
- The service-account JSON present at `config/gsc_credentials.json`
- The service account already added in **Search Console → Settings → Users and
  permissions** with **Full** access (already done for
  `kriti-project@for-kriti-500207.iam.gserviceaccount.com`).

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

```bash
curl https://kriti-maai-268992122217.australia-southeast1.run.app/api/integrations/gsc/status
```

Expect `"status": "connected"`. The Integrations card in the deployed UI will
then show GSC as connected (green).

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
