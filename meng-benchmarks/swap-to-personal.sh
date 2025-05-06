#!/bin/bash

CRED_FILE="$HOME/.aws/credentials"

if grep -q "\[sigmaos-personal\]" "$CRED_FILE"; then
  cp "$CRED_FILE" "$CRED_FILE.bak"  # Backup
  sed -i '' \
    -e 's/\[sigmaos\]/[sigmaos-pdos]/g' \
    -e 's/\[sigmaos-personal\]/[sigmaos]/g' \
    "$CRED_FILE"
  echo "Updated credentials: swapped [sigmaos] to [sigmaos-pdos], and [sigmaos-personal] to [sigmaos]."
else
  echo "[sigmaos-personal] not found. No changes made."
fi