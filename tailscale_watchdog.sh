#!/usr/bin/env bash
# ==============================================================================
# Tailscale Funnel & Cinema Bridge Watchdog Script
# ==============================================================================
# Purpose:
#   Automatically monitors, verifies, and auto-recovers:
#   1. Local Alice cinema-bridge webhook service (port 8888)
#   2. Tailscale daemon connection and `--accept-dns=false` flag
#      (prevents local AdGuard Home DNS on 127.0.0.1:53 from corrupting the tunnel)
#   3. Tailscale Funnel public HTTPS endpoint for Yandex Alice
#
# Usage:
#   /home/danil/cinema_bridge/tailscale_watchdog.sh [-v|--verbose]
# ==============================================================================

set -o pipefail

VERBOSE=0
if [ "$1" = "-v" ] || [ "$1" = "--verbose" ]; then
    VERBOSE=1
fi

if [ "$EUID" -eq 0 ]; then
    LOCKFILE="/run/tailscale_watchdog.lock"
else
    LOCKFILE="/tmp/tailscale_watchdog_${USER:-danil}.lock"
fi

# Load from .env if present
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env" 2>/dev/null || true
    set +a
fi

WEBHOOK_PORT="${SERVER_PORT:-8888}"
SECRET="${SECRET_TOKEN:-cinema_secret_token_change_me}"
LOCAL_URL="http://127.0.0.1:${WEBHOOK_PORT}/?secret=${SECRET}"

if [ -n "$TAILSCALE_FUNNEL_DOMAIN" ]; then
    PUBLIC_URL="https://${TAILSCALE_FUNNEL_DOMAIN}/?secret=${SECRET}"
else
    TS_DOMAIN=$(tailscale funnel status 2>/dev/null | grep -oE 'https://[a-zA-Z0-9.-]+\.ts\.net' | head -n1)
    if [ -n "$TS_DOMAIN" ]; then
        PUBLIC_URL="${TS_DOMAIN}/?secret=${SECRET}"
    else
        PUBLIC_URL=""
    fi
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WATCHDOG] $*"
}

vlog() {
    if [ "$VERBOSE" -eq 1 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WATCHDOG-VERBOSE] $*"
    fi
}

restart_service() {
    local svc="$1"
    if [ "$EUID" -eq 0 ]; then
        systemctl restart "$svc"
    else
        sudo systemctl restart "$svc"
    fi
}

# 1. Prevent concurrent runs
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    vlog "Another watchdog instance is already executing. Exiting."
    exit 0
fi

vlog "Starting watchdog health check..."

# 2. Check Internet Connectivity
# If the home router or ISP connection is down, avoid cycling services repeatedly.
if ! curl -s -m 3 --connect-timeout 2 -I https://1.1.1.1 >/dev/null 2>&1 && ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    log "WARN: Internet connectivity is unreachable. Skipping recovery to avoid churn."
    exit 0
fi
vlog "Internet connectivity check: OK"

# 3. Check tailscaled.service
if ! systemctl is-active --quiet tailscaled.service; then
    log "ALERT: tailscaled.service is inactive! Restarting..."
    restart_service tailscaled.service
    sleep 3
fi
vlog "tailscaled service check: OK"

# 4. Check cinema-bridge.service
if ! systemctl is-active --quiet cinema-bridge.service; then
    log "ALERT: cinema-bridge.service is inactive! Restarting..."
    restart_service cinema-bridge.service
    sleep 2
fi

LOCAL_CODE=$(curl -s -m 3 -o /dev/null -w "%{http_code}" "$LOCAL_URL" 2>/dev/null || echo "000")
if [ "$LOCAL_CODE" != "200" ]; then
    log "ALERT: Local webhook returned HTTP $LOCAL_CODE (expected 200). Restarting cinema-bridge..."
    restart_service cinema-bridge.service
    sleep 2
    LOCAL_CODE=$(curl -s -m 3 -o /dev/null -w "%{http_code}" "$LOCAL_URL" 2>/dev/null || echo "000")
    if [ "$LOCAL_CODE" = "200" ]; then
        log "Local cinema-bridge recovered successfully (HTTP 200)."
    else
        log "ERROR: Local cinema-bridge still failing with HTTP $LOCAL_CODE."
    fi
else
    vlog "cinema-bridge local HTTP check: OK (200)"
fi

# 5. Check & Enforce --accept-dns=false (AdGuard coexistence)
CORP_DNS=$(tailscale debug prefs 2>/dev/null | jq -r .CorpDNS 2>/dev/null || echo "unknown")
if [ "$CORP_DNS" != "false" ]; then
    log "ALERT: Tailscale CorpDNS is '${CORP_DNS}' (expected false). Enforcing --accept-dns=false..."
    tailscale up --operator=danil --accept-dns=false
    vlog "Tailscale preferences updated: CorpDNS set to false."
else
    vlog "Tailscale CorpDNS check: OK (false)"
fi

# 6. Check Tailscale Backend State
TS_STATE=$(tailscale status --json 2>/dev/null | jq -r .BackendState 2>/dev/null || echo "unknown")
if [ "$TS_STATE" != "Running" ]; then
    log "ALERT: Tailscale backend state is '${TS_STATE}'. Running tailscale up..."
    tailscale up --operator=danil --accept-dns=false
    sleep 2
else
    vlog "Tailscale backend state check: OK (Running)"
fi

# 7. Check Funnel Status & Public Reachability
NEED_FUNNEL_RECOVERY=0
FUNNEL_STATUS=$(tailscale funnel status 2>/dev/null || echo "")

if ! echo "$FUNNEL_STATUS" | grep -q "Funnel on"; then
    log "ALERT: Tailscale Funnel is not reported as 'Funnel on'."
    NEED_FUNNEL_RECOVERY=1
else
    vlog "Tailscale Funnel status: OK (Funnel on)"
fi

# End-to-end HTTPS check
if [ "$NEED_FUNNEL_RECOVERY" -eq 0 ]; then
    PUBLIC_CODE=$(curl -s -m 5 -o /dev/null -w "%{http_code}" "$PUBLIC_URL" 2>/dev/null || echo "000")
    if [ "$PUBLIC_CODE" != "200" ]; then
        log "WARN: Public Funnel check returned HTTP $PUBLIC_CODE. Retrying in 3s..."
        sleep 3
        PUBLIC_CODE=$(curl -s -m 5 -o /dev/null -w "%{http_code}" "$PUBLIC_URL" 2>/dev/null || echo "000")
        if [ "$PUBLIC_CODE" != "200" ]; then
            log "ALERT: Public Funnel failed after retry with HTTP $PUBLIC_CODE."
            NEED_FUNNEL_RECOVERY=1
        else
            vlog "Public Funnel retry succeeded: HTTP 200"
        fi
    else
        vlog "Public Funnel end-to-end check: OK (200)"
    fi
fi

# 8. Perform Funnel Recovery if required
if [ "$NEED_FUNNEL_RECOVERY" -eq 1 ]; then
    log "RECOVERY: Re-registering Tailscale Funnel on port $WEBHOOK_PORT with --accept-dns=false..."
    tailscale up --operator=danil --accept-dns=false
    tailscale funnel reset >/dev/null 2>&1 || true
    tailscale funnel --bg --yes "$WEBHOOK_PORT"
    sleep 3
    
    VERIFY_CODE=$(curl -s -m 5 -o /dev/null -w "%{http_code}" "$PUBLIC_URL" 2>/dev/null || echo "000")
    if [ "$VERIFY_CODE" = "200" ]; then
        log "SUCCESS: Tailscale Funnel recovered successfully! (HTTP 200 OK)"
    else
        log "ERROR: Funnel recovery attempted, but public URL returned HTTP $VERIFY_CODE."
    fi
fi

vlog "Watchdog run completed."
exit 0
