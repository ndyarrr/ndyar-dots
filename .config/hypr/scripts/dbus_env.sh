#!/usr/bin/env bash
# ==============================================================================
# dbus_env.sh — Portable D-Bus Environment Propagation
# ==============================================================================
# Propagates Wayland/display environment variables to the D-Bus session bus.
#
# On systemd: uses --systemd flag to also update systemd user manager env.
# On OpenRC/elogind: omits --systemd flag (not supported by elogind).
# ==============================================================================

VARS="WAYLAND_DISPLAY XDG_CURRENT_DESKTOP DBUS_SESSION_BUS_ADDRESS DISPLAY"

if [ -d /run/systemd/system ]; then
    # systemd — propagate to both D-Bus and systemd user manager
    dbus-update-activation-environment --systemd $VARS
else
    # OpenRC / elogind / other — propagate to D-Bus session only
    dbus-update-activation-environment $VARS
fi
