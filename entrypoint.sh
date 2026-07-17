#!/bin/sh
set -e

varlock load
FORCE_COLOR=1 varlock run -- fastapi run /app/src/text_mate_backend/app.py --host 0.0.0.0 --port "${PORT:-8090}"
