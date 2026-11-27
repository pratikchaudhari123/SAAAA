#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
command -v docker >/dev/null
command -v npm >/dev/null
command -v python3 >/dev/null
if lsof -nP -iTCP:8100 -sTCP:LISTEN >/dev/null 2>&1 || lsof -nP -iTCP:5175 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8100 or 5175 is occupied. Use the existing developer update procedure instead."
  exit 1
fi
PRIVATE="$HOME/.saaaa-team"
mkdir -p "$PRIVATE"
chmod 700 "$PRIVATE"
ENVFILE="$PRIVATE/team.env"
if [ ! -f "$ENVFILE" ]; then
  python3 -c 'import secrets; print("POSTGRES_PASSWORD="+secrets.token_hex(32)); print("DJANGO_SECRET_KEY="+secrets.token_hex(48))' > "$ENVFILE"
fi
chmod 600 "$ENVFILE"
dc() { docker compose --project-name saaaa-team --env-file "$ENVFILE" -f compose.team.yml "$@"; }
dc up -d --build
dc exec -T api python manage.py check
dc exec -T api python manage.py makemigrations campus
dc exec -T api python manage.py test campus
dc exec -T api python manage.py migrate
if [ -f package-lock.json ]; then npm ci; else npm install; fi
npm test
npm run build
CREDS=$(mktemp "$PRIVATE/credentials.XXXXXX")
dc exec -T api python manage.py shell < scripts/team_seed.py > "$CREDS"
chmod 600 "$CREDS"
echo "Private synthetic credentials: $CREDS"
echo "Open http://127.0.0.1:5175/ after Vite starts."
npm run dev -- --port 5175 --strictPort
