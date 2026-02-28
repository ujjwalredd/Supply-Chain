#!/bin/bash
# Fix "docker-credential-desktop: executable file not found" error
# Backs up ~/.docker/config.json and removes credsStore

CONFIG="$HOME/.docker/config.json"
if [ -f "$CONFIG" ]; then
  cp "$CONFIG" "$CONFIG.backup.$(date +%s)"
  # Remove credsStore/credHelpers to use default auth
  if command -v jq &>/dev/null; then
    jq 'del(.credsStore, .credHelpers)' "$CONFIG" > "$CONFIG.tmp" && mv "$CONFIG.tmp" "$CONFIG"
  else
    echo "Install jq or manually edit $CONFIG to remove credsStore/credHelpers"
    echo "Example: {\"auths\":{}}"
  fi
  echo "Updated $CONFIG"
else
  echo "No config found at $CONFIG"
fi
