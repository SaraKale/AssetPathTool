# -*- coding: utf-8 -*-
"""文件大小 / 修改时间：取值与格式化。

单独一个模块，是因为「查找缺失」和「素材使用」都要用，
而这两块谁 import 谁都不合适。
"""
import os
import time

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


def fmt_size(n):
    """字节数 → 1.2 MB / 340 KB。拿不到大小时返回「—」"""
    if n is None:
        return "—"
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "—"
    if n < 0:
        return "—"
    if n < 1024:
        return f"{n} B"
    v = float(n)
    for u in _UNITS[1:]:
        v /= 1024.0
        if v < 1024 or u == _UNITS[-1]:
            return f"{v:.1f} {u}"
    return f"{v:.1f} PB"


def fmt_mtime(ts):
    """时间戳 → 2026-10-28 16:38。拿不到时返回「—」"""
    if not ts:
        return "—"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except (OSError, ValueError, OverflowError):
        return "—"


def file_info(path, cache=None):
    """
    返回 (字节数, 修改时间戳)。文件不存在 / 无权限时两项都是 None。

    cache 传一个 dict 进来可以避免同一个文件反复 stat ——
    查找缺失的候选里，同一目录下几百个文件挨个 stat 是要花时间的。
    """
    if cache is not None:
        hit = cache.get(path)
        if hit is not None:
            return hit
    try:
        st = os.stat(path)
        info = (st.st_size, st.st_mtime)
    except OSError:
        info = (None, None)
    if cache is not None:
        cache[path] = info
    return info
