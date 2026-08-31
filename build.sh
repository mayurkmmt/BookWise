#!/usr/bin/env bash
# Render build step: install dependencies and collect static files.
set -o errexit

# Generate a requirements file from the uv lockfile, then install it.
pip install uv
uv export --no-dev --format requirements-txt > requirements.txt
pip install -r requirements.txt

# Collect static assets for WhiteNoise to serve.
python manage.py collectstatic --no-input
