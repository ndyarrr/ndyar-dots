#!/usr/bin/env python3

import subprocess
import json


def _run(args, timeout=2):
    try:
        return subprocess.run(["hyprctl"] + args, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def hyprctl_json(args, timeout=2):
    """Llamadas de solo lectura (clients, activewindow, monitors, etc)."""
    try:
        r = _run(args + ["-j"], timeout=timeout)
        if not r or r.returncode != 0 or not r.stdout.strip():
            return None
        return json.loads(r.stdout)
    except Exception:
        return None


def dispatch(lua_expr, timeout=2):
    """Ejecuta hyprctl dispatch '<lua_expr>'."""
    return _run(["dispatch", lua_expr], timeout=timeout)


def dispatch_async(lua_expr):
    try:
        subprocess.Popen(["hyprctl", "dispatch", lua_expr],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def batch(lua_exprs, timeout=5):
    """lua_exprs: lista de llamadas completas a hl.dsp.*(...)"""
    if not lua_exprs:
        return None
    try:
        cmd = " ; ".join(f"dispatch {e}" for e in lua_exprs)
        return subprocess.run(["hyprctl", "--batch", cmd], capture_output=True, timeout=timeout)
    except Exception:
        return None


def batch_async(lua_exprs):
    if not lua_exprs:
        return
    try:
        cmd = " ; ".join(f"dispatch {e}" for e in lua_exprs)
        subprocess.Popen(["hyprctl", "--batch", cmd],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def toggle_floating_lua(address=None):
    w = f', window = "address:{address}"' if address else ""
    return f'hl.dsp.window.float({{ action = "toggle"{w} }})'

def toggle_floating(address=None):
    return dispatch(toggle_floating_lua(address))


def focus_window_lua(address):
    return f'hl.dsp.focus({{ window = "address:{address}" }})'

def focus_window(address):
    res = dispatch(focus_window_lua(address))
    if not res or res.returncode != 0:
        _run(["dispatch", "focuswindow", f"address:{address}"])
    return res


def move_focus_lua(direction):
    mapping = {"l": "left", "r": "right", "u": "up", "d": "down",
               "left": "left", "right": "right", "up": "up", "down": "down"}
    d = mapping.get(direction, direction)
    return f'hl.dsp.focus({{ direction = "{d}" }})'

def move_focus(direction):
    res = dispatch(move_focus_lua(direction))
    if not res or res.returncode != 0:
        short_dir = {"left": "l", "right": "r", "up": "u", "down": "d"}.get(direction, direction)
        _run(["dispatch", "movefocus", short_dir])
    return res


def move_window_tiled_lua(direction):
    mapping = {"l": "left", "r": "right", "u": "up", "d": "down",
               "left": "left", "right": "right", "up": "up", "down": "down"}
    d = mapping.get(direction, direction)
    return f'hl.dsp.window.move({{ direction = "{d}" }})'

def move_window_tiled(direction):
    return dispatch(move_window_tiled_lua(direction))


def exec_cmd_lua(cmd):
    escaped = cmd.replace('\\', '\\\\').replace('"', '\\"')
    return f'hl.dsp.exec_cmd("{escaped}")'


def move_window_exact_lua(x, y, address):
    return (f'hl.dsp.window.move({{ window = "address:{address}", '
            f'x = {int(x)}, y = {int(y)}, relative = false }})')

def move_window_exact(x, y, address, timeout=2):
    return dispatch(move_window_exact_lua(x, y, address), timeout=timeout)

def move_window_exact_async(x, y, address):
    dispatch_async(move_window_exact_lua(x, y, address))


def resize_window_exact_lua(w, h, address):
    return (f'hl.dsp.window.resize({{ window = "address:{address}", '
            f'x = {int(w)}, y = {int(h)}, relative = false }})')

def resize_window_exact(w, h, address, timeout=2):
    return dispatch(resize_window_exact_lua(w, h, address), timeout=timeout)
