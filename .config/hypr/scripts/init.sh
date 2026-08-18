#!/usr/bin/env bash

source "$(dirname "${BASH_SOURCE[0]}")/caching.sh"
qs_ensure_cache "wallpaper_picker"

# Restore last backlight level early (amdgpu often boots at ~100%).
bash "$(dirname "${BASH_SOURCE[0]}")/brightness.sh" restore &

FLAG="$QS_STATE_WALLPAPER_PICKER/wallpaper_initialized"
CACHE_IMG="$QS_CACHE_WALLPAPER_PICKER/current_wallpaper.png"

RELOAD_SCRIPT_PATH="$(dirname "${BASH_SOURCE[0]}")/quickshell/wallpaper/matugen_reload.sh"

# If the flag exists, restore wallpaper to awww and run matugen
if [ -f "$FLAG" ]; then
    pgrep -f awww-daemon >/dev/null || awww-daemon &
    sleep 0.2
    
    if [ -f "$CACHE_IMG" ]; then
        awww img "$CACHE_IMG" --transition-type none 2>/dev/null &
        matugen image "$CACHE_IMG" --source-color-index 0
    fi
    
    if [ -f "$RELOAD_SCRIPT_PATH" ]; then
        chmod +x "$RELOAD_SCRIPT_PATH"
        bash "$RELOAD_SCRIPT_PATH"
    fi
    
    exit 0
fi

# If no wallpaper dir is set, default to a common one to prevent find from failing
WALLPAPER_DIR="${WALLPAPER_DIR:-$HOME/Pictures/Wallpapers}"

sleep 0.5

# Find a random file
file=$(find "$WALLPAPER_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) 2>/dev/null | shuf -n 1)

if [ -n "$file" ]; then
    # Copy to our persistent cache location instead of /tmp
    cp "$file" "$CACHE_IMG"
    
    pgrep -f awww-daemon >/dev/null || awww-daemon &
    sleep 0.2
    awww img "$file" --transition-type any --transition-pos 0.5,0.5 --transition-fps 144 --transition-duration 1 &
    
    matugen image "$file" --source-color-index 0
    
    # Execute reload script if it exists
    if [ -f "$RELOAD_SCRIPT_PATH" ]; then
        chmod +x "$RELOAD_SCRIPT_PATH"
        bash "$RELOAD_SCRIPT_PATH"
    fi
fi

mkdir -p "$(dirname "$FLAG")"
touch "$FLAG"
