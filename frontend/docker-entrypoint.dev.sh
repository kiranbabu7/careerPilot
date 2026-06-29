#!/bin/sh
set -e

export NODE_ENV=development

mkdir -p /app/.next
if ! touch /app/.next/.write-test 2>/dev/null; then
  echo "frontend: .next volume not writable — clearing cache"
  rm -rf /app/.next/*
fi
rm -f /app/.next/.write-test

exec "$@"
