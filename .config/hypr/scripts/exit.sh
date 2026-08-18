#!/usr/bin/env bash

if command -v systemctl &>/dev/null; then
    systemctl --user stop graphical-session.target 2>/dev/null || true
    systemctl --user stop graphical-session-pre.target 2>/dev/null || true
fi

sleep 0.5

command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || hyprctl dispatch "hl.dsp.exit()"

