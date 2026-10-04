#!/usr/bin/env python3
"""
floating_tile_toggle.py
Toggle between Tiled layout and Infinite 2D Floating Canvas for Hyprland.
Deterministic state transition using explicit set float actions.
"""

import sys
import os
import json
import fcntl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hypr_ipc import (hyprctl_json, move_window_exact_lua,
                       resize_window_exact_lua, batch, batch_async)

LOCK_FILE  = "/tmp/floating_tile_toggle.lock"
STATE_FILE = "/tmp/floating_tile_state.json"


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def get_active_workspace_id():
    ws = hyprctl_json(["activeworkspace"])
    return ws["id"] if ws else 1


def get_workspace_windows(workspace_id):
    clients = hyprctl_json(["clients"]) or []
    return [
        w for w in clients
        if w.get("workspace", {}).get("id") == workspace_id
    ]


def set_float_lua(address, is_floating):
    val_str = "true" if is_floating else "false"
    return f'hl.dsp.window.float({{ action = "set", value = {val_str}, window = "address:{address}" }})'


def toggle_all():
    ws_id = get_active_workspace_id()
    windows = get_workspace_windows(ws_id)
    if not windows:
        return

    state = load_state()
    saved_positions = state.get(str(ws_id), {})

    # Check current status: if ANY window is tiled, switch to FLOATING mode
    any_tiled = any(not w.get("floating", False) for w in windows)

    if any_tiled:
        # === SWITCH TO FLOATING 2D CANVAS ===
        float_exprs = [set_float_lua(w["address"], True) for w in windows]
        batch(float_exprs, timeout=3)

        # Restore saved canvas positions or arrange cleanly
        move_exprs = []
        cur_x = 100
        cur_y = 100
        
        for w in windows:
            addr = w["address"]
            if addr in saved_positions:
                pos = saved_positions[addr]
                move_exprs.append(move_window_exact_lua(pos["x"], pos["y"], addr))
                if "w" in pos and "h" in pos:
                    move_exprs.append(resize_window_exact_lua(pos["w"], pos["h"], addr))
            else:
                # Default clean floating placement if no saved coordinates
                move_exprs.append(move_window_exact_lua(cur_x, cur_y, addr))
                cur_x += 700
                if cur_x > 2200:
                    cur_x = 100
                    cur_y += 500

        if move_exprs:
            batch_async(move_exprs)
            
    else:
        # === SWITCH TO TILED LAYOUT ===
        # 1. Save all current floating canvas positions first
        new_positions = {}
        for w in windows:
            new_positions[w["address"]] = {
                "x": w["at"][0],
                "y": w["at"][1],
                "w": w["size"][0],
                "h": w["size"][1],
                "class": w.get("class", ""),
                "title": w.get("title", "")
            }
        state[str(ws_id)] = new_positions
        save_state(state)

        # 2. Tile all windows
        tile_exprs = [set_float_lua(w["address"], False) for w in windows]
        batch(tile_exprs, timeout=3)


def main():
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(0)

    try:
        toggle_all()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


if __name__ == "__main__":
    main()
