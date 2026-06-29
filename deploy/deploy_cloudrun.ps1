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
  [string]$SiteUrl        = "https://kriti-maai-268992122217.australia-southeast1.run.app/"
)

$ErrorActionPreference = "Stop"
$MountPath = "/secrets/gsc_credentials.json"

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

# 4. Deploy, mounting the secret as a file and setting the GSC env vars.
Write-Host "==> Deploying $Service to Cloud Run..." -ForegroundColor Cyan
gcloud run deploy $Service `
  --source . `
  --region $Region `
  --project $Project `
  --allow-unauthenticated `
  --update-secrets="$MountPath=${SecretName}:latest" `
  --set-env-vars="GSC_CREDENTIALS_PATH=$MountPath,GSC_SITE_URL=$SiteUrl"

Write-Host "==> Done. Verify with:" -ForegroundColor Green
Write-Host "    curl $SiteUrl`api/integrations/gsc/status" -ForegroundColor Green
