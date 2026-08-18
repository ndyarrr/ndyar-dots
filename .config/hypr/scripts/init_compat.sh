#!/usr/bin/env bash
# ==============================================================================
# init_compat.sh — Portable Init System Abstraction Layer
# ==============================================================================
# Source this file to get portable wrappers for service management
# that work on both systemd and OpenRC (Artix Linux).
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/init_compat.sh"
#   detect_init
#   svc_enable NetworkManager
#   svc_start NetworkManager
# ==============================================================================

# Detect the running init system.
# Sets INIT_SYSTEM to "systemd", "openrc", or "unknown".
detect_init() {
    if [ -n "$INIT_SYSTEM" ]; then
        return 0  # Already detected
    fi

    if [ -d /run/systemd/system ]; then
        INIT_SYSTEM="systemd"
    elif [ -f /run/openrc/softlevel ]; then
        INIT_SYSTEM="openrc"
    elif command -v openrc-init >/dev/null 2>&1; then
        INIT_SYSTEM="openrc"
    else
        INIT_SYSTEM="unknown"
    fi

    export INIT_SYSTEM
}

# Always detect on source
detect_init

# ==============================================================================
# System-level service management (requires sudo for openrc/systemd system units)
# ==============================================================================

# Enable a system service at boot.
# Usage: svc_enable <service_name> [runlevel]
svc_enable() {
    local svc="$1"
    local runlevel="${2:-default}"

    case "$INIT_SYSTEM" in
        systemd)
            sudo systemctl enable "${svc}.service" 2>/dev/null || true
            ;;
        openrc)
            sudo rc-update add "$svc" "$runlevel" 2>/dev/null || true
            ;;
        *)
            echo "init_compat: unknown init system, cannot enable $svc" >&2
            return 1
            ;;
    esac
}

# Enable and start a system service immediately.
# Usage: svc_enable_now <service_name> [runlevel]
svc_enable_now() {
    local svc="$1"
    local runlevel="${2:-default}"

    case "$INIT_SYSTEM" in
        systemd)
            sudo systemctl enable --now "${svc}.service" 2>/dev/null || true
            ;;
        openrc)
            sudo rc-update add "$svc" "$runlevel" 2>/dev/null || true
            sudo rc-service "$svc" start 2>/dev/null || true
            ;;
        *)
            echo "init_compat: unknown init system, cannot enable+start $svc" >&2
            return 1
            ;;
    esac
}

# Disable a system service from boot.
# Usage: svc_disable <service_name> [runlevel]
svc_disable() {
    local svc="$1"
    local runlevel="${2:-default}"

    case "$INIT_SYSTEM" in
        systemd)
            sudo systemctl disable "${svc}.service" 2>/dev/null || true
            ;;
        openrc)
            sudo rc-update del "$svc" "$runlevel" 2>/dev/null || true
            ;;
        *)
            echo "init_compat: unknown init system, cannot disable $svc" >&2
            return 1
            ;;
    esac
}

# Start a system service now (does not enable at boot).
# Usage: svc_start <service_name>
svc_start() {
    local svc="$1"

    case "$INIT_SYSTEM" in
        systemd)
            sudo systemctl start "${svc}.service" 2>/dev/null || true
            ;;
        openrc)
            sudo rc-service "$svc" start 2>/dev/null || true
            ;;
        *)
            echo "init_compat: unknown init system, cannot start $svc" >&2
            return 1
            ;;
    esac
}

# Stop a system service now.
# Usage: svc_stop <service_name>
svc_stop() {
    local svc="$1"

    case "$INIT_SYSTEM" in
        systemd)
            sudo systemctl stop "${svc}.service" 2>/dev/null || true
            ;;
        openrc)
            sudo rc-service "$svc" stop 2>/dev/null || true
            ;;
        *)
            echo "init_compat: unknown init system, cannot stop $svc" >&2
            return 1
            ;;
    esac
}

# Check if a system service is enabled at boot.
# Usage: svc_is_enabled <service_name>
# Returns: 0 if enabled, 1 otherwise
svc_is_enabled() {
    local svc="$1"

    case "$INIT_SYSTEM" in
        systemd)
            systemctl is-enabled "${svc}.service" &>/dev/null
            ;;
        openrc)
            rc-update show default 2>/dev/null | grep -q "\b${svc}\b"
            ;;
        *)
            return 1
            ;;
    esac
}

# Check if a system service is currently running.
# Usage: svc_is_active <service_name>
# Returns: 0 if active/running, 1 otherwise
svc_is_active() {
    local svc="$1"

    case "$INIT_SYSTEM" in
        systemd)
            systemctl is-active "${svc}.service" &>/dev/null
            ;;
        openrc)
            rc-service "$svc" status &>/dev/null
            ;;
        *)
            return 1
            ;;
    esac
}

# ==============================================================================
# User-level service management
# Note: OpenRC does not have native user-level service management.
#       User daemons on OpenRC are typically started via session autostart.
# ==============================================================================

# Enable a user-level service (systemd only, no-op on OpenRC).
# Usage: user_svc_enable <service_name>
user_svc_enable() {
    local svc="$1"

    case "$INIT_SYSTEM" in
        systemd)
            systemctl --user enable "${svc}.service" 2>/dev/null || true
            ;;
        openrc)
            # OpenRC has no user-level service manager.
            # User daemons should be started via Hyprland autostart instead.
            return 0
            ;;
    esac
}

# Enable a user-level service globally for all users (systemd only, no-op on OpenRC).
# Usage: user_svc_enable_global <service_name> [...]
user_svc_enable_global() {
    case "$INIT_SYSTEM" in
        systemd)
            sudo systemctl --global enable "$@" 2>/dev/null || true
            ;;
        openrc)
            return 0
            ;;
    esac
}

# Start a user-level service (systemd only, no-op on OpenRC).
# Usage: user_svc_start <service_name> [...]
user_svc_start() {
    case "$INIT_SYSTEM" in
        systemd)
            systemctl --user start "$@" 2>/dev/null || true
            ;;
        openrc)
            return 0
            ;;
    esac
}

# Stop a user-level service (systemd only, no-op on OpenRC).
# Usage: user_svc_stop <service_name>
user_svc_stop() {
    local svc="$1"

    case "$INIT_SYSTEM" in
        systemd)
            systemctl --user stop "$svc" 2>/dev/null || true
            ;;
        openrc)
            return 0
            ;;
    esac
}

# Reload user-level service daemon (systemd only, no-op on OpenRC).
# Usage: user_svc_daemon_reload
user_svc_daemon_reload() {
    case "$INIT_SYSTEM" in
        systemd)
            systemctl --user daemon-reload 2>/dev/null || true
            ;;
        openrc)
            return 0
            ;;
    esac
}

# ==============================================================================
# Portable power actions
# ==============================================================================

# Portable suspend that works on systemd, elogind, and fallback to zzz.
# Usage: do_suspend
do_suspend() {
    if command -v loginctl >/dev/null 2>&1; then
        loginctl suspend
    elif command -v systemctl >/dev/null 2>&1; then
        systemctl suspend
    elif command -v zzz >/dev/null 2>&1; then
        zzz
    else
        echo "init_compat: no suspend backend found" >&2
        return 1
    fi
}
