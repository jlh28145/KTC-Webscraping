#!/usr/bin/env bash
# Restore artifacts/ktc.db from the newest ktc-history-* artifact.
#
# Runs only when the Actions cache had no history (evicted after 7 days without
# use, a failed save, or a new actions/cache major changing the cache version).
# Without it, the scrape would silently start an empty history and the next
# cache save would make that permanent.
#
# Env: GH_TOKEN (needs actions: read), GITHUB_REPOSITORY, START_FRESH ("true" to
# allow starting a new history when no artifact exists either).
set -euo pipefail

target_dir="${HISTORY_DIR:-artifacts}"

latest=$(gh api "repos/${GITHUB_REPOSITORY}/actions/artifacts?per_page=100" --jq '
  [.artifacts[] | select((.name | startswith("ktc-history-")) and (.expired | not))]
  | sort_by(.created_at) | last // empty
  | "\(.workflow_run.id) \(.name) \(.created_at)"')

if [ -n "$latest" ]; then
  read -r run_id name created_at <<<"$latest"
  echo "::warning::History cache missed; restoring ${name} (created ${created_at}) from run ${run_id}"
  mkdir -p "$target_dir"
  gh run download "$run_id" --repo "$GITHUB_REPOSITORY" --name "$name" --dir "$target_dir"
  if [ ! -s "${target_dir}/ktc.db" ]; then
    echo "::error::Downloaded ${name}, but it contained no ktc.db"
    exit 1
  fi
  echo "Restored ${target_dir}/ktc.db ($(wc -c <"${target_dir}/ktc.db") bytes)"
elif [ "${START_FRESH:-false}" = "true" ]; then
  echo "::warning::No history in the cache or any ktc-history artifact; starting a new history (start_fresh=true)"
else
  echo "::error::No history in the cache or any ktc-history artifact. Re-run the workflow manually with start_fresh=true to begin a new history on purpose."
  exit 1
fi
