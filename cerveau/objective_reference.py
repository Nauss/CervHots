"""Bounded independent HUD frame clip. No OCR, statistics or live permission."""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import zipfile


def record_clip(capture, output, stopped, session_token, *, duration=8, interval=.05,
                clock=time.monotonic, sleep=time.sleep):
    """Timestamp capture, not file encoding. Operator must inspect the WHOLE clip.

    Synthetic capture injection is for tests only. Real capture never reads game
    memory. A clip by itself is neither a reference value nor a stable interval.
    """
    if (type(session_token) is not str or not re.fullmatch('[0-9a-f]{32}', session_token)
            or any(type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high
                   for v, low, high in ((duration, .1, 10), (interval, .025, .1)))):
        raise ValueError('invalid_clip_limits')
    index = {'schema_version': 1, 'session_token': session_token,
             'clock_basis': 'host_monotonic', 'transcription': 'manual_required',
             'frames': [], 'max_gap_s': 0, 'max_capture_s': 0, 'complete': False}
    deadline = clock() + duration
    total = 0
    reason = 'duration'
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as archive:
        try:
            while clock() < deadline and len(index['frames']) < 400:
                if stopped():
                    reason = 'stop_file'; break
                start = clock()
                data = capture()
                end = clock()
                if stopped():
                    reason = 'stop_file'; break
                if end >= deadline:
                    break
                if type(data) is not bytes or len(data) > 512 * 1024 or end < start:
                    raise ValueError('invalid_clip_frame')
                total += len(data)
                if total > 16 * 2**20:
                    raise ValueError('clip_byte_limit')
                member = f'frame-{len(index["frames"]):04d}.bmp'
                if index['frames']:
                    index['max_gap_s'] = max(index['max_gap_s'], start - index['frames'][-1]['finished_s'])
                index['max_capture_s'] = max(index['max_capture_s'], end - start)
                archive.writestr(member, data)
                index['frames'].append({'member': member, 'started_s': start, 'finished_s': end,
                                        'sha256': hashlib.sha256(data).hexdigest()})
                if stopped():
                    reason = 'stop_file'; break
                sleep(min(interval, max(0, deadline - clock())))
            index['complete'] = True
        finally:
            archive.writestr('index.json', json.dumps(index, allow_nan=False))
    return {'event': 'hud_clip_closed', 'frames': len(index['frames']), 'reason': reason,
            'memory_opened': False, 'ocr': False}


def game_capture(region):
    """Operator-only OS screen crop. Never focus, inject or read game memory.

    Reject anything but the already foreground game on the primary monitor.
    The operator must reject overlays/black frames and crop names OUT of evidence.
    """
    import ctypes as c
    from ctypes import wintypes as w
    import ntpath
    import struct
    x, y, width, height = region
    if not (0 <= x <= 7680 and 0 <= y <= 4320 and 1 <= width <= 512 and 1 <= height <= 200):
        raise ValueError('invalid_hud_region')
    u, g, k = c.WinDLL('user32', use_last_error=True), c.WinDLL('gdi32', use_last_error=True), c.WinDLL('kernel32', use_last_error=True)
    declarations = (
        (u, 'GetForegroundWindow', [], w.HWND),
        (u, 'GetWindowThreadProcessId', [w.HWND, c.POINTER(w.DWORD)], w.DWORD),
        (u, 'GetWindowRect', [w.HWND, c.POINTER(w.RECT)], w.BOOL),
        (u, 'GetSystemMetrics', [c.c_int], c.c_int),
        (u, 'GetDC', [w.HWND], w.HDC), (u, 'ReleaseDC', [w.HWND, w.HDC], c.c_int),
        (k, 'OpenProcess', [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
        (k, 'QueryFullProcessImageNameW', [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)], w.BOOL),
        (k, 'CloseHandle', [w.HANDLE], w.BOOL),
        (g, 'CreateCompatibleDC', [w.HDC], w.HDC),
        (g, 'CreateCompatibleBitmap', [w.HDC, c.c_int, c.c_int], w.HBITMAP),
        (g, 'SelectObject', [w.HDC, w.HANDLE], w.HANDLE),
        (g, 'DeleteObject', [w.HANDLE], w.BOOL), (g, 'DeleteDC', [w.HDC], w.BOOL),
        (g, 'BitBlt', [w.HDC, c.c_int, c.c_int, c.c_int, c.c_int, w.HDC, c.c_int, c.c_int, w.DWORD], w.BOOL),
        (g, 'GetDIBits', [w.HDC, w.HBITMAP, w.UINT, w.UINT, c.c_void_p, c.c_void_p, w.UINT], c.c_int))
    for dll, name, args, result in declarations:
        function = getattr(dll, name); function.argtypes = args; function.restype = result
    hwnd = u.GetForegroundWindow()
    pid = w.DWORD()
    u.GetWindowThreadProcessId(hwnd, c.byref(pid))
    handle = k.OpenProcess(0x1000, False, pid.value)  # query identity only, no VM access
    if not handle:
        raise ValueError('game_window_unverified')
    try:
        buffer, length = c.create_unicode_buffer(32768), w.DWORD(32768)
        if (not k.QueryFullProcessImageNameW(handle, 0, buffer, c.byref(length))
                or ntpath.basename(buffer.value).casefold() != 'heroesofthestorm_x64.exe'):
            raise ValueError('game_window_unverified')
    finally:
        k.CloseHandle(handle)

    def geometry():
        rect = w.RECT()
        if u.GetForegroundWindow() != hwnd or not u.GetWindowRect(hwnd, c.byref(rect)):
            raise ValueError('game_window_changed')
        left, top = rect.left + x, rect.top + y
        if (x + width > rect.right - rect.left or y + height > rect.bottom - rect.top
                or left < 0 or top < 0 or left + width > u.GetSystemMetrics(0)
                or top + height > u.GetSystemMetrics(1)):
            raise ValueError('hud_region_offscreen')
        return left, top, rect.right, rect.bottom

    def capture():
        before = geometry()
        screen = u.GetDC(None)
        dc = bitmap = previous = None
        try:
            if not screen:
                raise ValueError('hud_capture_unavailable')
            dc = g.CreateCompatibleDC(screen)
            bitmap = g.CreateCompatibleBitmap(screen, width, height)
            if not dc or not bitmap:
                raise ValueError('hud_capture_unavailable')
            previous = g.SelectObject(dc, bitmap)
            if not previous or not g.BitBlt(dc, 0, 0, width, height, screen, before[0], before[1], 0x00CC0020):
                raise ValueError('hud_capture_unavailable')
            g.SelectObject(dc, previous); previous = None
            size = width * height * 4
            header = struct.pack('<IiiHHIIiiII', 40, width, height, 1, 32, 0, size, 0, 0, 0, 0)
            info, pixels = c.create_string_buffer(header), c.create_string_buffer(size)
            if g.GetDIBits(screen, bitmap, 0, height, pixels, info, 0) != height or geometry() != before:
                raise ValueError('hud_capture_unavailable')
            return b'BM' + struct.pack('<IHHI', size + 54, 0, 0, 54) + header + pixels.raw
        finally:
            if previous and dc: g.SelectObject(dc, previous)
            if bitmap: g.DeleteObject(bitmap)
            if dc: g.DeleteDC(dc)
            if screen: u.ReleaseDC(None, screen)
    return capture


def main(argv=None):
    import argparse
    import os
    from pathlib import Path
    from .passive_session import stop_requested
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true', help='operator-only explicit OS HUD capture opt-in')
    parser.add_argument('--output-file', type=Path, help='NEW absolute PRIVATE zip archive')
    parser.add_argument('--session-token', help='random token from this collector status.json, not identity')
    parser.add_argument('--region', type=int, nargs=4, metavar=('X', 'Y', 'WIDTH', 'HEIGHT'), help='HUD-only crop relative to foreground game window; no names')
    parser.add_argument('--stop-file', action='append', type=Path, default=[], help='absolute cooperative STOP; repeat for global STOP')
    parser.add_argument('--max-seconds', type=float, default=8)
    parser.add_argument('--interval', type=float, default=.05)
    args = parser.parse_args(argv)
    if not args.record:
        print(json.dumps({'event': 'hud_clip_preflight', 'ready': os.name == 'nt',
                          'gui_captured': False, 'memory_opened': False, 'dependencies': 'stdlib_only'}))
        return 0 if os.name == 'nt' else 1
    try:
        if (args.output_file is None or not args.output_file.is_absolute() or args.region is None
                or not args.stop_file or any(not p.is_absolute() for p in args.stop_file)):
            raise ValueError('invalid_clip_arguments')
        stopped = lambda: any(stop_requested(p) for p in args.stop_file)
        if stopped():
            print(json.dumps({'event': 'hud_clip_boundary', 'reason': 'stop_file'}))
            return 0
        # Validate limits before any native window query/capture.
        if (type(args.session_token) is not str or not re.fullmatch('[0-9a-f]{32}', args.session_token)
                or not math.isfinite(args.max_seconds) or not .1 <= args.max_seconds <= 10
                or not math.isfinite(args.interval) or not .025 <= args.interval <= .1
                or args.output_file.exists()):
            raise ValueError('invalid_clip_arguments')
        result = record_clip(game_capture(args.region), args.output_file, stopped,
                             args.session_token, duration=args.max_seconds, interval=args.interval)
    except (OSError, ValueError, TypeError, AttributeError):
        print(json.dumps({'event': 'hud_clip_error', 'code': 'clip_unavailable_or_invalid',
                          'memory_opened': False}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
