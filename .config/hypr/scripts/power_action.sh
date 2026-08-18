#!/usr/bin/env bash
# Portable power actions for systemd (systemctl) and Artix/elogind (loginctl).
set -euo pipefail

action="${1:-}"
LOCK_SCRIPT="${HOME}/.config/hypr/scripts/lock.sh"

do_reboot() {
    if command -v loginctl >/dev/null 2>&1; then
        exec loginctl reboot
    elif command -v systemctl >/dev/null 2>&1; then
        exec systemctl reboot
    else
        exec reboot
    fi
}

do_poweroff() {
    if command -v loginctl >/dev/null 2>&1; then
        exec loginctl poweroff -i
    elif command -v systemctl >/dev/null 2>&1; then
        exec systemctl poweroff -i
    else
        exec poweroff
    fi
}

do_suspend() {
    if command -v loginctl >/dev/null 2>&1; then
        exec loginctl suspend
    elif command -v systemctl >/dev/null 2>&1; then
        exec systemctl suspend
    elif command -v zzz >/dev/null 2>&1; then
        exec zzz
    else
        echo "power_action: no suspend backend found" >&2
        exit 1
    fi
}

case "$action" in
    lock)
        exec bash "$LOCK_SCRIPT"
        ;;
    sleep|suspend)
        # Bring lockscreen up first, then suspend.
        bash "$LOCK_SCRIPT" &
        sleep 0.8
        do_suspend
        ;;
    reboot)
        do_reboot
        ;;
    shutdown|poweroff)
        do_poweroff
        ;;
    *)
        echo "Usage: $0 {lock|sleep|reboot|shutdown}" >&2
        exit 2
        ;;
esac
