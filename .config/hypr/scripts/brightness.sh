#!/usr/bin/env bash
# Brightness helper: always targets class backlight (not keyboard LEDs),
# and persists the last value for restore after boot.
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/hypr"
STATE_FILE="$STATE_DIR/brightness"
CLASS="backlight"

mkdir -p "$STATE_DIR"

get_pct() {
    brightnessctl -c "$CLASS" -m 2>/dev/null | head -n1 | awk -F, '{
        v=$4; gsub(/%/,"",v); v=v+0;
        if (v<0) v=0; if (v>100) v=100;
        print v
    }'
}

set_pct() {
    local pct="${1:-}"
    pct="${pct%\%}"
    if ! [[ "$pct" =~ ^[0-9]+$ ]]; then
        echo "brightness.sh: invalid percent '$1'" >&2
        exit 2
    fi
    # Keep at least 1% so the panel never goes fully black by accident.
    if (( pct < 1 )); then pct=1; fi
    if (( pct > 100 )); then pct=100; fi
    brightnessctl -c "$CLASS" set "${pct}%" >/dev/null
    printf '%s\n' "$pct" > "$STATE_FILE"
}

restore() {
    if [[ ! -f "$STATE_FILE" ]]; then
        return 0
    fi
    local pct
    pct="$(tr -cd '0-9' < "$STATE_FILE")"
    [[ -n "$pct" ]] || return 0
    # Retry a few times: backlight sysfs can appear slightly after session start.
    local i
    for i in 1 2 3 4 5 6 7 8; do
        if brightnessctl -c "$CLASS" info >/dev/null 2>&1; then
            set_pct "$pct"
            return 0
        fi
        sleep 0.25
    done
    return 0
}

case "${1:-}" in
    get) get_pct ;;
    set) set_pct "${2:-}" ;;
    save)
        pct="$(get_pct)"
        [[ -n "$pct" ]] || exit 1
        printf '%s\n' "$pct" > "$STATE_FILE"
        ;;
    restore) restore ;;
    *)
        echo "Usage: $0 {get|set <pct>|save|restore}" >&2
        exit 2
        ;;
esac
