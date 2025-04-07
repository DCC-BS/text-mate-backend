#!/bin/bash
set -e

uv run fastapi:app --host 0.0.0.0 --port "${PORT:-8090}"
