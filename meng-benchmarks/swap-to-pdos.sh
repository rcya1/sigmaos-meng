#!/bin/bash

CRED_FILE="$HOME/.aws/credentials"

if grep -q "\[sigmaos-pdos\]" "$CRED_FILE"; then
  cp "$CRED_FILE" "$CRED_FILE.bak"  # Backup
  sed -i '' \
    -e 's/\[sigmaos\]/[sigmaos-personal]/g' \
    -e 's/\[sigmaos-pdos\]/[sigmaos]/g' \
    "$CRED_FILE"
  echo "Updated credentials: swapped [sigmaos] to [sigmaos-personal], and [sigmaos-pdos] to [sigmaos]."
else
  echo "[sigmaos-pdos] not found. No changes made."
fi