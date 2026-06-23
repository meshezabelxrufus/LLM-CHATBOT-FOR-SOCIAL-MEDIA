#!/usr/bin/env bash
# Run inside the container or locally: ./scripts/migrate.sh
set -euo pipefail

echo "Running Alembic migrations..."
alembic -c alembic/alembic.ini upgrade head
echo "Done."
