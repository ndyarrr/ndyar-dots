#!/usr/bin/env python3
"""
navigate_windows.py
Navigate between windows on active workspace using Super+Arrows.

- Floating (Infinite Canvas): smoothly pans canvas to center the target window in chosen direction and focuses it.
- Tiled: moves focus in the chosen direction (left/right/up/down).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hypr_ipc import hyprctl_json, move_focus, move_window_exact_lua, focus_window, batch_async


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
    return 640, 380


def get_window_center(w):
    return w["at"][0] + w["size"][0] // 2, w["at"][1] + w["size"][1] // 2


def get_window_bounds(w):
    x, y = w["at"][0], w["at"][1]
    ww, wh = w["size"][0], w["size"][1]
    return {
        "left": x, "right": x + ww,
        "top": y, "bottom": y + wh,
        "center_x": x + ww // 2,
        "center_y": y + wh // 2
    }


def overlap_h(b1, b2):
    return not (b1["right"] <= b2["left"] or b1["left"] >= b2["right"])


def overlap_v(b1, b2):
    return not (b1["bottom"] <= b2["top"] or b1["top"] >= b2["bottom"])


def find_target(floating, current_bounds, center, direction):
    cx, cy = center

    # 1. Look for windows directly aligned in the requested direction
    aligned = []
    for w in floating:
        b = get_window_bounds(w)
        wx, wy = b["center_x"], b["center_y"]
        if direction == "left"  and overlap_v(current_bounds, b) and wx < cx:
            aligned.append((w, cx - wx))
        elif direction == "right" and overlap_v(current_bounds, b) and wx > cx:
            aligned.append((w, wx - cx))
        elif direction == "up"   and overlap_h(current_bounds, b) and wy < cy:
            aligned.append((w, cy - wy))
        elif direction == "down" and overlap_h(current_bounds, b) and wy > cy:
            aligned.append((w, wy - cy))

    if aligned:
        return sorted(aligned, key=lambda x: x[1])[0][0]

    # 2. Look for any window in the general direction
    same_dir = []
    for w in floating:
        b = get_window_bounds(w)
        wx, wy = b["center_x"], b["center_y"]
        if direction == "left"  and wx < cx: same_dir.append((w, cx - wx))
        elif direction == "right" and wx > cx: same_dir.append((w, wx - cx))
        elif direction == "up"   and wy < cy: same_dir.append((w, cy - wy))
        elif direction == "down" and wy > cy: same_dir.append((w, wy - cy))

    if same_dir:
        return sorted(same_dir, key=lambda x: x[1])[0][0]

    # 3. Wrap around to the farthest window in the opposite direction
    opp = {"left": "right", "right": "left", "up": "down", "down": "up"}[direction]
    wrap = []
    for w in floating:
        b = get_window_bounds(w)
        wx, wy = b["center_x"], b["center_y"]
        if opp == "left"  and wx < cx: wrap.append((w, cx - wx))
        elif opp == "right" and wx > cx: wrap.append((w, wx - cx))
        elif opp == "up"   and wy < cy: wrap.append((w, cy - wy))
        elif opp == "down" and wy > cy: wrap.append((w, wy - cy))

    if wrap:
        return sorted(wrap, key=lambda x: x[1], reverse=True)[0][0]

    return None


def pan_to_window(floating, target_addr, center_x, center_y):
    target = next((w for w in floating if w["address"] == target_addr), None)
    if not target:
        return

    tx = target["at"][0] + target["size"][0] // 2
    ty = target["at"][1] + target["size"][1] // 2
    dx = center_x - tx
    dy = center_y - ty

    exprs = []
    for w in floating:
        nx = w["at"][0] + dx
        ny = w["at"][1] + dy
        exprs.append(move_window_exact_lua(int(round(nx)), int(round(ny)), w["address"]))

    batch_async(exprs)
    focus_window(target_addr)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("left", "right", "up", "down"):
        print("Usage: navigate_windows.py <left|right|up|down>")
        sys.exit(1)

    direction = sys.argv[1]

    ws = hyprctl_json(["activeworkspace"])
    if not ws:
        sys.exit(0)
    workspace_id = ws.get("id", 1)

    clients = hyprctl_json(["clients"]) or []
    ws_clients = [w for w in clients if w.get("workspace", {}).get("id") == workspace_id]
    if not ws_clients:
        sys.exit(0)

    floating = [w for w in ws_clients if w.get("floating")]

    # ── Tiled Mode ────────────────────────────────────────────────────────────
    if not floating:
        move_focus(direction)
        return

    # ── Floating Mode (Infinite Canvas) ───────────────────────────────────────
    center_x, center_y = get_monitor_center()

    if len(floating) == 1:
        pan_to_window(floating, floating[0]["address"], center_x, center_y)
        return

    focused = hyprctl_json(["activewindow"])

    # Determine reference window
    window_near_center = any(
        abs(get_window_center(w)[0] - center_x) < 150 and
        abs(get_window_center(w)[1] - center_y) < 150
        for w in floating
    )

    if not focused or not focused.get("address") or not window_near_center:
        closest = min(
            floating,
            key=lambda w: (
                (get_window_center(w)[0] - center_x) ** 2 +
                (get_window_center(w)[1] - center_y) ** 2
            )
        )
        pan_to_window(floating, closest["address"], center_x, center_y)
        return

    current_bounds = get_window_bounds(focused)
    target = find_target(floating, current_bounds, (center_x, center_y), direction)
    if target and target["address"] != focused.get("address"):
        pan_to_window(floating, target["address"], center_x, center_y)
    elif target:
        focus_window(target["address"])


if __name__ == "__main__":
    main()
