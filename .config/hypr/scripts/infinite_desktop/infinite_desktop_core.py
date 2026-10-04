#!/usr/bin/env python3
"""
infinite_desktop_core.py
Ultra-smooth 120Hz Infinite 2D Canvas Engine for Hyprland (Lua API).
Supports:
- Middle Mouse Button Drag (Figma/Blender style)
- SUPER + ALT + Mouse Movement
- Momentum / Inertia Glide
- In-memory zero-latency coordinate tracking
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
from hypr_ipc import move_window_exact_lua, batch_async, hyprctl_json

speed = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0

DEVICE_RESCAN_INTERVAL = 3.0
EVENT_SIZE = struct.calcsize('llHHi')
EV_KEY = 1
EV_REL = 2
REL_X = 0
REL_Y = 1

KEY_LEFTMETA = 125
KEY_RIGHTMETA = 126
KEY_LEFTALT = 56
KEY_RIGHTALT = 100
KEY_LEFTCTRL = 29
KEY_RIGHTCTRL = 97

BTN_LEFT = 272
BTN_RIGHT = 273
BTN_MIDDLE = 274

STATE_FILE = "/tmp/infinite-desktop-state"
lock = threading.Lock()

super_pressed = False
alt_pressed = False
ctrl_pressed = False
btn_left = False
btn_middle = False

acc_x = 0.0
acc_y = 0.0
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

    is_mouse = (ecodes.REL_X in rels and ecodes.REL_Y in rels and ecodes.BTN_LEFT in keys)
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
    keyboards, mice = [], []
    for path in list_devices():
        kind = classify_device(path)
        if kind == 'mouse':
            mice.append(path)
        elif kind == 'keyboard':
            keyboards.append(path)
    return keyboards, mice


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
    global acc_x, acc_y, btn_left, btn_middle, mouse_rel_x, mouse_rel_y
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

                is_panning = btn_middle or (super_pressed and alt_pressed and btn_left)
                if is_panning:
                    sign = -1 if read_inverted() else 1
                    if code == REL_X:
                        acc_x += value * effective_speed * sign
                    elif code == REL_Y:
                        acc_y += value * effective_speed * sign
                else:
                    acc_x = 0.0
                    acc_y = 0.0

    try:
        fd.close()
    except Exception:
        pass


_active_kbd_threads = {}
_active_mouse_threads = {}


def device_manager():
    WARMUP_DURATION = 20.0
    WARMUP_INTERVAL = 0.5
    start_time = time.time()

    while True:
        try:
            keyboards, mice = scan_devices()

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
        except Exception:
            pass

        elapsed = time.time() - start_time
        interval = WARMUP_INTERVAL if elapsed < WARMUP_DURATION else DEVICE_RESCAN_INTERVAL
        time.sleep(interval)


def main_panning_loop():
    global drag_active, drag_windows, active_ws_id, last_vel_x, last_vel_y
    global acc_x, acc_y

    while True:
        time.sleep(0.008)  # 125 Hz update loop for buttery smoothness

        with lock:
            is_panning = btn_middle or (super_pressed and alt_pressed and btn_left)
            dx = acc_x
            dy = acc_y
            acc_x = 0.0
            acc_y = 0.0

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
                # Update velocity
                last_vel_x = dx
                last_vel_y = dy

                # Update in-memory coordinates
                exprs = []
                for addr, pos in drag_windows.items():
                    pos[0] += dx
                    pos[1] += dy
                    exprs.append(move_window_exact_lua(int(round(pos[0])), int(round(pos[1])), addr))

                if exprs:
                    batch_async(exprs)

        else:
            if drag_active:
                # Drag ended: Optional subtle inertia glide
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
    main_panning_loop()


if __name__ == "__main__":
    main()