#!/usr/bin/env bash
# Existing developer Mac only. Never use this script on institutional production data.
set -euo pipefail
umask 077
BASE="$HOME/education-erp-saas"
WORK="$HOME/saaaa-tender-demo"
cd "$WORK"
test -f "$BASE/.env.backend"
test -f "$BASE/compose.backend.yml"
test -f "$BASE/compose.integration.yml"
dc() { docker compose -p saaaa-erp --env-file "$BASE/.env.backend" -f "$BASE/compose.backend.yml" -f "$BASE/compose.integration.yml" "$@"; }
echo "===== EXISTING SAAAA STACK ====="
dc ps
echo "===== DATABASE BACKUP ====="
mkdir -p "$HOME/saaaa-backups"
chmod 700 "$HOME/saaaa-backups"
BACKUP=$(mktemp "$HOME/saaaa-backups/release-XXXXXXXX")
docker exec saaaa-erp-db-1 sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' </dev/null > "$BACKUP"
test -s "$BACKUP"
echo "Private backup: $BACKUP"
echo "===== INSTALLED SOURCE ====="
git log -1 --oneline
echo "===== BACKEND DEPENDENCY AND MODEL CHECK ====="
if ! dc exec -T api python -c 'import PIL' </dev/null; then
  dc exec -T api python -m pip install 'Pillow>=11.3,<13' </dev/null
fi
dc exec -T api python -m compileall -q campus config manage.py </dev/null
dc exec -T api python manage.py check </dev/null
dc exec -T api python manage.py makemigrations --check --dry-run </dev/null
dc exec -T api python manage.py test campus </dev/null
echo "===== FRONTEND CHECK ====="
npm test </dev/null
npm run build </dev/null
echo "===== MIGRATION PLAN ====="
dc exec -T api python manage.py migrate --plan </dev/null
dc exec -T api python manage.py migrate </dev/null
echo "===== RESTART AND READINESS ====="
dc restart api </dev/null
ready=0
for i in $(seq 1 30); do
  if curl --max-time 3 -fsS http://127.0.0.1:8100/api/health/ >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  echo "Backend did not become ready. Inspect API logs locally."
  exit 1
fi
curl -fsS --max-time 5 http://127.0.0.1:5175/api/health/
echo ""
echo "===== COMPLETE LIVE REGRESSION ====="
python3 scripts/live_acceptance.py
python3 scripts/connect_acceptance.py
python3 scripts/academic_acceptance.py
python3 scripts/career_acceptance.py
python3 scripts/document_acceptance.py
echo "===== MIGRATION HISTORY ====="
dc exec -T api python manage.py showmigrations campus </dev/null
git status --short -- backend/campus/migrations
echo "===== ERP DATABASE TABLES ====="
dc exec -T api python manage.py shell -c "from django.db import connection; print('ERP tables:',len([t for t in connection.introspection.table_names() if t.startswith('campus_')]))" </dev/null
echo "===== RELEASE VERIFIED ====="
