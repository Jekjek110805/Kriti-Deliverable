<#
.SYNOPSIS
  Deploy the Kriti backend to Cloud Run with the GSC service-account key
  mounted from Secret Manager (so live GSC works on the deployed domain).

.DESCRIPTION
  Run from the project root in PowerShell. Requires the gcloud CLI, an
  authenticated account (`gcloud auth login`), and the service-account JSON at
  config/gsc_credentials.json (or pass -CredentialsFile).

  The key is NEVER baked into the image. It is stored in Secret Manager and
  mounted into the container at /secrets/gsc_credentials.json at runtime.

.EXAMPLE
  .\deploy\deploy_cloudrun.ps1
#>
param(
  [string]$Project        = "for-kriti-500207",
  [string]$Region         = "australia-southeast1",
  [string]$Service        = "kriti-maai",
  [string]$SecretName     = "gsc-credentials",
  [string]$CredentialsFile = "config/gsc_credentials.json",
  [string]$SiteUrl        = "https://selfstorage.help/",
  # OpenRouter (AI) — key goes into Secret Manager, never baked into the image.
  # If -OpenRouterKey is empty, it is read from OPENROUTER_API_KEY in .env.
  [string]$OpenRouterSecret = "openrouter-key",
  [string]$OpenRouterKey    = "",
  [string]$OpenRouterModel  = "nvidia/nemotron-3-super-120b-a12b:free"
)

$ErrorActionPreference = "Stop"
$MountPath = "/secrets/gsc_credentials.json"

# Resolve the OpenRouter key from .env if not supplied on the command line.
if (-not $OpenRouterKey -and (Test-Path ".env")) {
  $line = Select-String -Path ".env" -Pattern '^\s*OPENROUTER_API_KEY=' | Select-Object -First 1
  if ($line) { $OpenRouterKey = ($line.Line -replace '^\s*OPENROUTER_API_KEY=', '').Trim() }
}
if (-not $OpenRouterKey) {
  throw "OpenRouter key not found. Pass -OpenRouterKey '<key>' or set OPENROUTER_API_KEY in .env"
}

if (-not (Test-Path $CredentialsFile)) {
  throw "Credentials file not found: $CredentialsFile"
}

Write-Host "==> Project=$Project Region=$Region Service=$Service" -ForegroundColor Cyan

# 1. Ensure required APIs are enabled.
Write-Host "==> Enabling required APIs..." -ForegroundColor Cyan
gcloud services enable `
  run.googleapis.com `
  secretmanager.googleapis.com `
  searchconsole.googleapis.com `
  cloudbuild.googleapis.com `
  --project $Project

# 2. Create the secret if it does not exist, then add a new version with the key.
$exists = (gcloud secrets describe $SecretName --project $Project 2>$null)
if (-not $exists) {
  Write-Host "==> Creating secret $SecretName..." -ForegroundColor Cyan
  gcloud secrets create $SecretName --replication-policy="automatic" --project $Project
}
Write-Host "==> Adding new secret version from $CredentialsFile..." -ForegroundColor Cyan
gcloud secrets versions add $SecretName --data-file=$CredentialsFile --project $Project

# 3. Grant the Cloud Run runtime service account access to read the secret.
$projectNumber = (gcloud projects describe $Project --format="value(projectNumber)")
$runtimeSa = "$projectNumber-compute@developer.gserviceaccount.com"
Write-Host "==> Granting secret access to runtime SA: $runtimeSa" -ForegroundColor Cyan
gcloud secrets add-iam-policy-binding $SecretName `
  --member="serviceAccount:$runtimeSa" `
  --role="roles/secretmanager.secretAccessor" `
  --project $Project

# 3b. Store the OpenRouter key in Secret Manager and grant the runtime SA access,
#     so AI features work on the deployed domain (the key is never in the image).
$orExists = (gcloud secrets describe $OpenRouterSecret --project $Project 2>$null)
if (-not $orExists) {
  Write-Host "==> Creating secret $OpenRouterSecret..." -ForegroundColor Cyan
  gcloud secrets create $OpenRouterSecret --replication-policy="automatic" --project $Project
}
Write-Host "==> Adding new OpenRouter secret version..." -ForegroundColor Cyan
$orTmp = New-TemporaryFile
try {
  # -NoNewline so no trailing newline sneaks into the key value.
  [System.IO.File]::WriteAllText($orTmp, $OpenRouterKey)
  gcloud secrets versions add $OpenRouterSecret --data-file=$orTmp --project $Project
} finally {
  Remove-Item $orTmp -Force -ErrorAction SilentlyContinue
}
Write-Host "==> Granting OpenRouter secret access to runtime SA: $runtimeSa" -ForegroundColor Cyan
gcloud secrets add-iam-policy-binding $OpenRouterSecret `
  --member="serviceAccount:$runtimeSa" `
  --role="roles/secretmanager.secretAccessor" `
  --project $Project

# 4. Deploy: mount the GSC key file + OpenRouter key (as env var) from Secret
#    Manager, and set the plain env vars (site URL, credentials path, model).
Write-Host "==> Deploying $Service to Cloud Run..." -ForegroundColor Cyan
gcloud run deploy $Service `
  --source . `
  --region $Region `
  --project $Project `
  --allow-unauthenticated `
  --update-secrets="$MountPath=${SecretName}:latest,OPENROUTER_API_KEY=${OpenRouterSecret}:latest" `
  --set-env-vars="GSC_CREDENTIALS_PATH=$MountPath,GSC_SITE_URL=$SiteUrl,OPENROUTER_MODEL=$OpenRouterModel"

Write-Host "==> Done. Verify with:" -ForegroundColor Green
Write-Host "    curl $SiteUrl`api/integrations/gsc/status" -ForegroundColor Green
Write-Host "    (AI) POST a brief/write request and confirm no '[OpenRouter not configured]' text." -ForegroundColor Green
