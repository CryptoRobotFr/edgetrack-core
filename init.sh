#!/usr/bin/env bash
# EdgeTrack - Environment initialization script (macOS / Linux)
# Usage: chmod +x init.sh && ./init.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
EXAMPLE_FILE="$SCRIPT_DIR/.env.example"

if [ -f "$ENV_FILE" ]; then
    printf "[!] .env file already exists. Overwrite? (y/N): "
    read -r confirm
    if [ "$confirm" != "y" ]; then
        echo "Aborted."
        exit 0
    fi
fi

if [ ! -f "$EXAMPLE_FILE" ]; then
    echo "[ERROR] .env.example not found in $SCRIPT_DIR"
    exit 1
fi

# --- Helper functions ---

generate_password() {
    local length="${1:-32}"
    # Use /dev/urandom with base64, URL-safe
    head -c 48 /dev/urandom | base64 | tr '+/' '-_' | tr -d '=' | head -c "$length"
}

generate_urlsafe_token() {
    local byte_length="${1:-32}"
    head -c "$byte_length" /dev/urandom | base64 | tr '+/' '-_' | tr -d '=' | tr -d '\n'
}

generate_fernet_key() {
    # Fernet key = URL-safe base64 of 32 random bytes (keep padding for valid Fernet)
    head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '\n'
}

# --- Generate secrets ---

POSTGRES_PASSWORD=$(generate_password 24)
PGADMIN_PASSWORD=$(generate_password 16)
SECRET_KEY=$(generate_urlsafe_token 48)
ENCRYPTION_KEY=$(generate_fernet_key)
EMAIL_ENCRYPTION_KEY=$(generate_urlsafe_token 32)
EMAIL_HASH_PEPPER=$(generate_urlsafe_token 32)

# --- Read template and replace ---

sed \
    -e "s|POSTGRES_PASSWORD=postgres|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" \
    -e "s|PGADMIN_DEFAULT_PASSWORD=admin|PGADMIN_DEFAULT_PASSWORD=${PGADMIN_PASSWORD}|" \
    -e "s|SECRET_KEY=change-me-in-production-use-a-long-random-string|SECRET_KEY=${SECRET_KEY}|" \
    -e "s|ENCRYPTION_KEY=change-me-in-production-use-fernet-key|ENCRYPTION_KEY=${ENCRYPTION_KEY}|" \
    -e "s|EMAIL_ENCRYPTION_KEY=change-me-in-production-32-bytes!|EMAIL_ENCRYPTION_KEY=${EMAIL_ENCRYPTION_KEY}|" \
    -e "s|EMAIL_HASH_PEPPER=change-me-in-production-pepper|EMAIL_HASH_PEPPER=${EMAIL_HASH_PEPPER}|" \
    "$EXAMPLE_FILE" > "$ENV_FILE"

echo ""
echo "=== EdgeTrack .env initialized ==="
echo ""
echo "Generated secrets:"
echo "  POSTGRES_PASSWORD    = ${POSTGRES_PASSWORD}"
echo "  PGADMIN_PASSWORD     = ${PGADMIN_PASSWORD}"
echo "  SECRET_KEY           = ${SECRET_KEY:0:12}..."
echo "  ENCRYPTION_KEY       = ${ENCRYPTION_KEY:0:12}..."
echo "  EMAIL_ENCRYPTION_KEY = ${EMAIL_ENCRYPTION_KEY:0:12}..."
echo "  EMAIL_HASH_PEPPER    = ${EMAIL_HASH_PEPPER:0:12}..."
echo ""
echo "File created: $ENV_FILE"
echo ""
echo "[!] WARNING: Keep these keys safe. If you lose ENCRYPTION_KEY or"
echo "    EMAIL_ENCRYPTION_KEY, encrypted data cannot be recovered."
echo ""
