# -*- coding: utf-8 -*-
"""按扩展名把工程文件分派给对应的解析器。"""
import os

from .aep import AEP_EXTS, extract_aep, is_aep
from .prproj import extract, load_root
from .remap import rewrite_prproj
from .sesx import SESX_EXTS, extract_sesx, is_sesx, rewrite_sesx

# 界面 / 文件对话框共用
PROJECT_EXTS = (".prproj", ".xml") + AEP_EXTS + SESX_EXTS
PROJECT_FILETYPES = "*.prproj *.xml *.aep *.aepx *.sesx"

# 能改写的格式。AE 的 .aep 是 RIFX 二进制，改起来风险太大，不做。
REWRITABLE_EXTS = (".prproj", ".sesx")


def extract_any(path, progress=None):
    """按扩展名分派：.aep/.aepx → AE；.sesx → Audition；.prproj/.xml → PR"""
    if is_aep(path):
        return extract_aep(path, progress)
    if is_sesx(path):
        return extract_sesx(path, progress)
    return extract(load_root(path), progress)


def project_kind(path):
    """给界面用：'aep' / 'sesx' / 'pr'"""
    if is_aep(path):
        return "aep"
    if is_sesx(path):
        return "sesx"
    return "pr"


def can_rewrite(path):
    """能不能把改写结果另存出来 —— .prproj 和 .sesx 可以，AE 不行"""
    return os.path.splitext(path or "")[1].lower() in REWRITABLE_EXTS


def rewrite_project(src, dst, rules=None, mapping=None):
    """
    按格式分派改写。返回被改写的路径条数。
    不支持的格式抛 ValueError，调用方负责翻译成人话。
    """
    if is_sesx(src):
        return rewrite_sesx(src, dst, rules, mapping)
    if os.path.splitext(src or "")[1].lower() == ".prproj":
        return rewrite_prproj(src, dst, rules, mapping)
    raise ValueError(f"unsupported format: {os.path.splitext(src or '')[1]}")


def can_usage(path):
    """有没有 PR 那套序列 / 轨道结构可以拿来做时间线统计"""
    return project_kind(path) == "pr"


def is_project_file(path):
    """拖放 / 文件过滤用：是不是本工具认识的工程文件"""
    return os.path.splitext(path or "")[1].lower() in PROJECT_EXTS
