#!/usr/bin/env bash
# Send a repository_dispatch event ("ktc-artifact-published") to the downstream repo.
#
# Env: DISPATCH_TOKEN (fine-grained token with Contents: read and write on the
# downstream repo), DOWNSTREAM_REPO (owner/name), RUN_ID (this workflow run).
# Both secrets are optional; without them this is a logged no-op.
set -euo pipefail

if [ -z "${DISPATCH_TOKEN:-}" ] || [ -z "${DOWNSTREAM_REPO:-}" ]; then
  echo "Downstream dispatch not configured (KTC_DOWNSTREAM_DISPATCH_TOKEN / KTC_DOWNSTREAM_REPO); skipping."
  exit 0
fi

GH_TOKEN="$DISPATCH_TOKEN" gh api --method POST "repos/${DOWNSTREAM_REPO}/dispatches" \
  -f event_type=ktc-artifact-published \
  -f "client_payload[run_id]=${RUN_ID}" \
  -f "client_payload[artifact]=scheduled-scrape-${RUN_ID}" >/dev/null
echo "Notified the downstream repo that scheduled-scrape-${RUN_ID} is published."
