#!/usr/bin/env bash
# Nightly Postgres dump, 14-day local retention. Schedule via host cron:
#   10 4 * * *  /opt/gulp/infra/backup.sh >> /var/log/gulp-backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE=(docker compose --env-file infra/.env -f infra/compose.prod.yml)

DIR=/var/backups/gulp
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT="${DIR}/gulp-${TS}.sql.gz"
mkdir -p "$DIR"

"${COMPOSE[@]}" exec -T db pg_dump -U gulp gulp | gzip > "$OUT"
echo "wrote $OUT"

# Off-host copy (configure ossutil first — see infra/README.md):
#   ossutil cp "$OUT" oss://<bucket>/gulp/ --region ap-southeast-1
# Also back up (rarely changes): infra/.env  and  the `media` volume.

# Retain 14 days locally.
find "$DIR" -name 'gulp-*.sql.gz' -mtime +14 -delete
