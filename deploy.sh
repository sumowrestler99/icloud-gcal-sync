#!/bin/bash
set -e

if [ $# -ne 2 ]; then
  echo "Usage: ./deploy.sh <user> <host>"
  exit 1
fi

SYNOLOGY_USER="$1"
SYNOLOGY_HOST="$2"
SYNOLOGY_PATH="/volume1/docker/icloud-gcal-sync"

rsync -av --progress --rsync-path=/usr/bin/rsync \
  --exclude venv \
  --exclude .git \
  --exclude .gitignore \
  --exclude .env.example \
  --exclude README.md \
  --exclude auth.py \
  . "$SYNOLOGY_USER@$SYNOLOGY_HOST:$SYNOLOGY_PATH"
