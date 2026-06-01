#!/bin/sh
set -e

APP_UID="${APP_UID:-10001}"
APP_GID="${APP_GID:-10001}"
DATA_DIR="${TR_DATA_DIR:-/data}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR"
  if ! chown -R "$APP_UID:$APP_GID" "$DATA_DIR"; then
    echo "Warning: could not chown $DATA_DIR. Check host bind-mount permissions." >&2
  fi
  exec gosu "$APP_UID:$APP_GID" "$@"
fi

exec "$@"
