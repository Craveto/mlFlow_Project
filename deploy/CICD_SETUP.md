# CI/CD Setup

This project now includes:

- `.github/workflows/ci.yml`
- `.github/workflows/cd-azure-vm.yml`
- `scripts/ci_smoke_check.py`

## What CI Does

On push or pull request:

1. installs Python 3.12
2. installs project dependencies
3. runs `python dashboard/manage.py check`
4. verifies API routes and required frontend files

## What CD Does

On push to `main` or manual dispatch:

1. runs the same validation as CI
2. uses SSH to connect to the Azure VM
3. syncs the repository to `/home/<vm-user>/timeseries`
4. installs Python dependencies
5. installs the backend and frontend systemd services
6. installs the Nginx config
7. restarts backend, frontend, and Nginx

## Required GitHub Secrets

Add these in your GitHub repository settings:

- `AZURE_VM_HOST`
- `AZURE_VM_USER`
- `AZURE_VM_SSH_KEY`

## Important Requirement

The VM user used in GitHub Actions should have passwordless `sudo` for:

- `cp`
- `ln`
- `rm`
- `systemctl`
- `nginx -t`

Without passwordless `sudo`, the deploy workflow will stop during the remote restart step.

## Recommended Improvement

Before relying on CD, make sure the checked-in Nginx config already contains the correct domain in:

- `deploy/nginx/timeseries-split.conf`

## Optional Next Improvement

If you want safer deployments later, add:

- environment-specific config templates
- rollback scripts
- a health-check endpoint and post-deploy validation
- database backup or artifact backup before deploy
