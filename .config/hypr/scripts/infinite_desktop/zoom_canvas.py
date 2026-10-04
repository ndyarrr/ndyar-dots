#!/usr/bin/env python3
"""
zoom_canvas.py
Zooms all floating windows on the active workspace in/out relative to the monitor center / cursor.

Usage:
  python3 zoom_canvas.py in      # Zoom in (factor 1.15)
  python3 zoom_canvas.py out     # Zoom out (factor 1/1.15)
  python3 zoom_canvas.py reset   # Reset zoom back to 1.0
  python3 zoom_canvas.py <float> # Custom zoom multiplier e.g. 1.25 or 0.8
"""

import sys
import os
import json
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hypr_ipc import (hyprctl_json, move_window_exact_lua,
                       resize_window_exact_lua, batch_async)

ZOOM_STATE_FILE = "/tmp/infinite_desktop_zoom.json"
MIN_W = 120
MIN_H = 80
MAX_W = 7680
MAX_H = 4320


def load_zoom_state():
    try:
        with open(ZOOM_STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_zoom_state(state):
    try:
        with open(ZOOM_STATE_FILE, "w") as f:
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


def get_floating_windows(workspace_id):
    clients = hyprctl_json(["clients"]) or []
    return [
        w for w in clients
        if w.get("floating") and w.get("workspace", {}).get("id") == workspace_id
    ]


def get_monitor_center():
    try:
        monitors = hyprctl_json(["monitors"]) or []
        for m in monitors:
            if m.get("focused"):
                scale = float(m.get("scale", 1.0))
                log_w = int(m["width"] / scale)
                log_h = int(m["height"] / scale)
                reserved = m.get("reserved", [0, 0, 0, 0])
                top_res = reserved[1] if len(reserved) > 1 else 0
                bottom_res = reserved[3] if len(reserved) > 3 else 0
                cx = m.get("x", 0) + (log_w // 2)
                cy = m.get("y", 0) + top_res + ((log_h - top_res - bottom_res) // 2)
                return int(cx), int(cy)
    except Exception:
        pass
    return 960, 540


def get_cursor_pos():
    try:
        cur = hyprctl_json(["cursorpos"])
        if cur and "x" in cur and "y" in cur:
            return int(cur["x"]), int(cur["y"])
    except Exception:
        pass
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: zoom_canvas.py <in|out|reset|<factor>>")
        sys.exit(1)

    arg = sys.argv[1].lower()
    ws_id = get_active_workspace_id()
    windows = get_floating_windows(ws_id)
    if not windows:
        all_ws = get_workspace_windows(ws_id)
        if all_ws:
            float_exprs = [set_float_lua(w["address"], True) for w in all_ws]
            from hypr_ipc import batch
            batch(float_exprs, timeout=2)
            windows = get_floating_windows(ws_id)
    if not windows:
        sys.exit(0)

    state = load_zoom_state()
    ws_key = str(ws_id)
    current_zoom = state.get(ws_key, 1.0)

    if arg == "in":
        factor = 1.15
    elif arg == "out":
        factor = 1.0 / 1.15
    elif arg == "reset":
        if abs(current_zoom - 1.0) < 0.01:
            sys.exit(0)
        factor = 1.0 / current_zoom
    else:
        try:
            factor = float(arg)
        except ValueError:
            print("Invalid argument. Use 'in', 'out', 'reset' or a numeric factor.")
            sys.exit(1)

    # Determine focal center point (cursor pos or monitor center)
    center = get_cursor_pos() or get_monitor_center()
    cx, cy = center[0], center[1]

    exprs = []
    for w in windows:
        addr = w["address"]
        x, y = float(w["at"][0]), float(w["at"][1])
        ww, wh = float(w["size"][0]), float(w["size"][1])

        # Center of the current window
        win_cx = x + ww / 2.0
        win_cy = y + wh / 2.0

        # Scale size
        new_ww = max(MIN_W, min(MAX_W, int(round(ww * factor))))
        new_wh = max(MIN_H, min(MAX_H, int(round(wh * factor))))

        # Scale center distance from focal point
        new_win_cx = cx + (win_cx - cx) * factor
        new_win_cy = cy + (win_cy - cy) * factor

        # Top-left of scaled window
        new_x = int(round(new_win_cx - new_ww / 2.0))
        new_y = int(round(new_win_cy - new_wh / 2.0))

        exprs.append(resize_window_exact_lua(new_ww, new_wh, addr))
        exprs.append(move_window_exact_lua(new_x, new_y, addr))

    if exprs:
        batch_async(exprs)
        state[ws_key] = 1.0 if arg == "reset" else (current_zoom * factor)
        save_zoom_state(state)


if __name__ == "__main__":
    main()
