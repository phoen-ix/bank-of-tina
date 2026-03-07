#!/bin/sh
set -e

# Ensure bind-mounted directories are writable by appuser.
# Docker creates missing host directories as root:root, so we fix
# ownership here before dropping privileges.
chown appuser:appuser /uploads /backups /app/static/icons 2>/dev/null || true

exec gosu appuser "$@"
