#!/bin/sh
set -e

# Ensure bind-mounted directories are writable by appuser.
# Docker creates missing host directories as root:root, so we fix
# ownership here before dropping privileges.
chown appuser:appuser /uploads /backups 2>/dev/null || true
# The app rewrites the icon files in place (Settings -> App Icon): files left
# by an older root-run version or baked into the image must be appuser's too.
chown -R appuser:appuser /app/static/icons 2>/dev/null || true

exec gosu appuser "$@"
