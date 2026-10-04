#!/usr/bin/env python3
"""
infinite_desktop_core.py
Ultra-smooth 120Hz Infinite 2D Canvas Engine for Hyprland (Lua API).
Supports:
- Middle Mouse Button Drag (Figma/Blender style)
- SUPER + ALT + Mouse Movement Drag
- Momentum / Inertia Glide
- In-memory zero-latency coordinate tracking
- Multi-Touch Touchpad Pinch In / Pinch Out Zoom
- SUPER + Scroll Wheel Zoom
"""

import sys
import struct
import threading
import time
import subprocess
import json
import os
import math
from evdev import InputDevice, list_devices, ecodes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hypr_ipc import (move_window_exact_lua, resize_window_exact_lua,
                       batch_async, hyprctl_json)

speed = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0

DEVICE_RESCAN_INTERVAL = 3.0
EVENT_SIZE = struct.calcsize('llHHi')
EV_SYN = 0
EV_KEY = 1
EV_REL = 2
EV_ABS = 3

REL_X = 0
REL_Y = 1
REL_WHEEL = 8
REL_WHEEL_HI_RES = 11

ABS_X = 0
ABS_Y = 1
ABS_MT_SLOT = 47
ABS_MT_TOUCH_MAJOR = 48
ABS_MT_POSITION_X = 53
ABS_MT_POSITION_Y = 54
ABS_MT_TRACKING_ID = 57

KEY_LEFTMETA = 125
KEY_RIGHTMETA = 126
KEY_LEFTALT = 56
KEY_RIGHTALT = 100
KEY_LEFTCTRL = 29
KEY_RIGHTCTRL = 97

BTN_LEFT = 272
BTN_RIGHT = 273
BTN_MIDDLE = 274
BTN_TOUCH = 330
BTN_TOOL_FINGER = 325
BTN_TOOL_DOUBLETAP = 333
BTN_TOOL_TRIPLETAP = 334

STATE_FILE = "/tmp/infinite-desktop-state"
ZOOM_STATE_FILE = "/tmp/infinite_desktop_zoom.json"
MIN_W = 120
MIN_H = 80

lock = threading.Lock()

super_pressed = False
alt_pressed = False
ctrl_pressed = False
btn_left = False
btn_middle = False

acc_x = 0.0
acc_y = 0.0
acc_zoom = 0.0
mouse_rel_x = 0
mouse_rel_y = 0

# Active in-memory tracked window coordinates during drag
drag_active = False
drag_windows = {}  # { address: [x, y] }
active_ws_id = None
last_vel_x = 0.0
last_vel_y = 0.0


def read_inverted():
    try:
        with open(STATE_FILE) as f:
            return f.read().strip() == 'inverse'
    except Exception:
        return False


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


def get_monitor_scale():
    try:
        monitors = hyprctl_json(["monitors"]) or []
        for m in monitors:
            if m.get("focused"):
                return float(m.get("scale", 1.0))
        if monitors:
            return float(monitors[0].get("scale", 1.0))
    except Exception:
        pass
    return 1.5


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


def get_floating_windows(workspace_id):
    try:
        clients = hyprctl_json(["clients"]) or []
        return [
            w for w in clients
            if w.get("floating") and w.get("workspace", {}).get("id") == workspace_id
        ]
    except Exception:
        return []


def get_active_workspace_id():
    try:
        ws = hyprctl_json(["activeworkspace"])
        return ws["id"] if ws else 1
    except Exception:
        return 1


def classify_device(path):
    try:
        dev = InputDevice(path)
        caps = dev.capabilities()
        dev.close()
    except Exception:
        return None

    keys = set(caps.get(ecodes.EV_KEY, []))
    rels = set(caps.get(ecodes.EV_REL, []))
    abss = set(caps.get(ecodes.EV_ABS, []))

    # Touchpad / Touchscreen device
    is_touchpad = (
        (ecodes.BTN_TOUCH in keys or ecodes.BTN_TOOL_FINGER in keys or ecodes.BTN_TOOL_DOUBLETAP in keys)
        and (ecodes.ABS_X in abss or ecodes.ABS_MT_POSITION_X in abss)
    )
    if is_touchpad:
        return 'touchpad'

    is_mouse = (ecodes.REL_X in rels and ecodes.REL_Y in rels and (ecodes.BTN_LEFT in keys or ecodes.BTN_MOUSE in keys))
    if is_mouse:
        return 'mouse'

    is_keyboard = (
        ecodes.KEY_A in keys and ecodes.KEY_Z in keys and ecodes.KEY_LEFTSHIFT in keys
        and (ecodes.KEY_LEFTMETA in keys or ecodes.KEY_RIGHTMETA in keys)
    )
    if is_keyboard:
        return 'keyboard'

    return None


def scan_devices():
    keyboards, mice, touchpads = [], [], []
    for path in list_devices():
        kind = classify_device(path)
        if kind == 'mouse':
            mice.append(path)
        elif kind == 'keyboard':
            keyboards.append(path)
        elif kind == 'touchpad':
            touchpads.append(path)
    return keyboards, mice, touchpads


def kbd_reader_device(path):
    global super_pressed, alt_pressed, ctrl_pressed
    try:
        fd = open(path, 'rb')
    except Exception:
        return

    while True:
        try:
            data = fd.read(EVENT_SIZE)
        except Exception:
            break
        if not data or len(data) < EVENT_SIZE:
            break
        _, _, etype, code, value = struct.unpack('llHHi', data)
        if etype != EV_KEY:
            continue
        if value == 2:  # key repeat
            continue

        with lock:
            if code in (KEY_LEFTMETA, KEY_RIGHTMETA):
                super_pressed = (value == 1)
            elif code in (KEY_LEFTALT, KEY_RIGHTALT):
                alt_pressed = (value == 1)
            elif code in (KEY_LEFTCTRL, KEY_RIGHTCTRL):
                ctrl_pressed = (value == 1)

    try:
        fd.close()
    except Exception:
        pass


def mouse_reader_device(path):
    global acc_x, acc_y, acc_zoom, btn_left, btn_middle, mouse_rel_x, mouse_rel_y
    try:
        fd = open(path, 'rb')
    except Exception:
        return

    mon_scale = get_monitor_scale()
    effective_speed = speed / mon_scale

    while True:
        try:
            data = fd.read(EVENT_SIZE)
        except Exception:
            break
        if not data or len(data) < EVENT_SIZE:
            break
        _, _, etype, code, value = struct.unpack('llHHi', data)

        with lock:
            if etype == EV_KEY:
                if code == BTN_LEFT:
                    btn_left = (value == 1)
                elif code == BTN_MIDDLE:
                    btn_middle = (value == 1)
            elif etype == EV_REL:
                if code == REL_X:
                    mouse_rel_x += value
                elif code == REL_Y:
                    mouse_rel_y += value
                elif code in (REL_WHEEL, REL_WHEEL_HI_RES):
                    # SUPER + Wheel Zoom
                    if super_pressed:
                        step = (value / 120.0) if code == REL_WHEEL_HI_RES else float(value)
                        acc_zoom += step * 0.12

                is_panning = btn_middle or (super_pressed and alt_pressed and btn_left)
                if is_panning:
                    sign = -1 if read_inverted() else 1
                    if code == REL_X:
                        acc_x += value * effective_speed * sign
                    elif code == REL_Y:
                        acc_y += value * effective_speed * sign
                elif not super_pressed:
                    acc_x = 0.0
                    acc_y = 0.0

    try:
        fd.close()
    except Exception:
        pass


def touchpad_reader_device(path):
    global acc_zoom
    try:
        fd = open(path, 'rb')
    except Exception:
        return

    slots = {}
    current_slot = 0
    prev_distance = None

    while True:
        try:
            data = fd.read(EVENT_SIZE)
        except Exception:
            break
        if not data or len(data) < EVENT_SIZE:
            break
        _, _, etype, code, value = struct.unpack('llHHi', data)

        if etype == EV_ABS:
            if code == ABS_MT_SLOT:
                current_slot = value
            elif code == ABS_MT_TRACKING_ID:
                if value == -1:
                    slots.pop(current_slot, None)
                    if len(slots) < 2:
                        prev_distance = None
                else:
                    if current_slot not in slots:
                        slots[current_slot] = {"x": 0, "y": 0}
            elif code == ABS_MT_POSITION_X:
                if current_slot in slots:
                    slots[current_slot]["x"] = value
            elif code == ABS_MT_POSITION_Y:
                if current_slot in slots:
                    slots[current_slot]["y"] = value

        elif etype == EV_SYN:
            active_slots = list(slots.values())
            if len(active_slots) >= 2:
                p0 = active_slots[0]
                p1 = active_slots[1]
                dx = float(p1["x"] - p0["x"])
                dy = float(p1["y"] - p0["y"])
                dist = math.hypot(dx, dy)

                if prev_distance is not None and prev_distance > 10.0:
                    delta_d = dist - prev_distance
                    if abs(delta_d) > 1.0:
                        with lock:
                            # Pinch out (dist increases) -> Zoom In (> 0)
                            # Pinch in (dist decreases)  -> Zoom Out (< 0)
                            acc_zoom += delta_d * 0.003
                prev_distance = dist
            else:
                prev_distance = None

    try:
        fd.close()
    except Exception:
        pass


_active_kbd_threads = {}
_active_mouse_threads = {}
_active_tp_threads = {}


def device_manager():
    WARMUP_DURATION = 20.0
    WARMUP_INTERVAL = 0.5
    start_time = time.time()

    while True:
        try:
            keyboards, mice, touchpads = scan_devices()

            for path in keyboards:
                t = _active_kbd_threads.get(path)
                if t is None or not t.is_alive():
                    nt = threading.Thread(target=kbd_reader_device, args=(path,), daemon=True)
                    nt.start()
                    _active_kbd_threads[path] = nt

            for path in mice:
                t = _active_mouse_threads.get(path)
                if t is None or not t.is_alive():
                    nt = threading.Thread(target=mouse_reader_device, args=(path,), daemon=True)
                    nt.start()
                    _active_mouse_threads[path] = nt

            for path in touchpads:
                t = _active_tp_threads.get(path)
                if t is None or not t.is_alive():
                    nt = threading.Thread(target=touchpad_reader_device, args=(path,), daemon=True)
                    nt.start()
                    _active_tp_threads[path] = nt
        except Exception:
            pass

        elapsed = time.time() - start_time
        interval = WARMUP_INTERVAL if elapsed < WARMUP_DURATION else DEVICE_RESCAN_INTERVAL
        time.sleep(interval)


def apply_zoom_delta(zoom_delta):
    ws_id = get_active_workspace_id()
    windows = get_floating_windows(ws_id)
    if not windows:
        return

    factor = max(0.5, min(1.8, 1.0 + zoom_delta))
    cx, cy = get_monitor_center()

    exprs = []
    for w in windows:
        addr = w["address"]
        x, y = float(w["at"][0]), float(w["at"][1])
        ww, wh = float(w["size"][0]), float(w["size"][1])

        win_cx = x + ww / 2.0
        win_cy = y + wh / 2.0

        new_ww = max(MIN_W, int(round(ww * factor)))
        new_wh = max(MIN_H, int(round(wh * factor)))

        new_win_cx = cx + (win_cx - cx) * factor
        new_win_cy = cy + (win_cy - cy) * factor

        new_x = int(round(new_win_cx - new_ww / 2.0))
        new_y = int(round(new_win_cy - new_wh / 2.0))

        exprs.append(resize_window_exact_lua(new_ww, new_wh, addr))
        exprs.append(move_window_exact_lua(new_x, new_y, addr))

    if exprs:
        batch_async(exprs)
        state = load_zoom_state()
        cur_z = state.get(str(ws_id), 1.0)
        state[str(ws_id)] = cur_z * factor
        save_zoom_state(state)


def main_canvas_loop():
    global drag_active, drag_windows, active_ws_id, last_vel_x, last_vel_y
    global acc_x, acc_y, acc_zoom

    while True:
        time.sleep(0.008)  # 125 Hz update loop

        with lock:
            is_panning = btn_middle or (super_pressed and alt_pressed and btn_left)
            dx = acc_x
            dy = acc_y
            z_delta = acc_zoom
            acc_x = 0.0
            acc_y = 0.0
            acc_zoom = 0.0

        # Zoom handling (Pinch / Wheel)
        if abs(z_delta) > 0.003:
            apply_zoom_delta(z_delta)

        # Pan handling (Drag)
        if is_panning:
            if not drag_active:
                # Drag started: Initialize in-memory window coordinates
                active_ws_id = get_active_workspace_id()
                floating = get_floating_windows(active_ws_id)
                drag_windows = {
                    w["address"]: [float(w["at"][0]), float(w["at"][1])]
                    for w in floating
                }
                drag_active = True
                last_vel_x = 0.0
                last_vel_y = 0.0

            if drag_windows and (abs(dx) > 0.01 or abs(dy) > 0.01):
                last_vel_x = dx
                last_vel_y = dy

                exprs = []
                for addr, pos in drag_windows.items():
                    pos[0] += dx
                    pos[1] += dy
                    exprs.append(move_window_exact_lua(int(round(pos[0])), int(round(pos[1])), addr))

                if exprs:
                    batch_async(exprs)

        else:
            if drag_active:
                # Inertia glide
                if abs(last_vel_x) > 2.0 or abs(last_vel_y) > 2.0:
                    vx = last_vel_x * 0.75
                    vy = last_vel_y * 0.75
                    for _ in range(8):
                        if not drag_windows:
                            break
                        exprs = []
                        for addr, pos in drag_windows.items():
                            pos[0] += vx
                            pos[1] += vy
                            exprs.append(move_window_exact_lua(int(round(pos[0])), int(round(pos[1])), addr))
                        if exprs:
                            batch_async(exprs)
                        vx *= 0.75
                        vy *= 0.75
                        time.sleep(0.012)

                drag_active = False
                drag_windows = {}
                last_vel_x = 0.0
                last_vel_y = 0.0


def main():
    threading.Thread(target=device_manager, daemon=True).start()
    main_canvas_loop()


if __name__ == "__main__":
    main()