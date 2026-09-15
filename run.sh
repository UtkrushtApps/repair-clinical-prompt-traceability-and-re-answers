#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

pip install -q -r requirements.txt
docker compose up -d --wait

python -m src.readiness
pytest -q

prompt_count="$(docker compose exec -T db psql -U clinical -d clinical_prompts -Atc 'select count(*) from prompts')"
case_count="$(docker compose exec -T db psql -U clinical -d clinical_prompts -Atc 'select count(*) from evaluation_cases')"
test "$prompt_count" -ge 4
test "$case_count" -ge 8

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ -n "${OPENAI_API_KEY:-}" ]; then
  python -m src.ping
  python -m src.evaluate --variant proposed
else
  echo "OPENAI_API_KEY is not configured; skipping provider-backed evaluation"
fi

echo "ready"
