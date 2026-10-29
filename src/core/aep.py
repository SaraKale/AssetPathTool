# -*- coding: utf-8 -*-
"""After Effects 工程（.aep / .aepx）的素材路径提取。

.aep 有两种容器：
  ① RIFX（大端 RIFF，form type = Egg!）—— 老版本 AE / 关掉「压缩工程文件」时用。
     素材引用是 LIST Als2 → alas，里面是一段 JSON，形如
       {"fullpath":"F:\\\\...\\\\a.mp4","platform":1,"target_is_folder":false,...}
     这是最可靠的一处，直接 json.loads 就能拿到完整路径。
  ② gzip 压缩的 XML（AE CC 2019+ 默认）—— 解压后按 XML 文本扫 <Path> / fullpath。
两种都做，谁命中用谁；扫不到就返回空表，不会炸。

局限：只读。AE 的工程结构里路径散落在二进制 chunk 和转义 JSON 中，
改写风险太高，所以本项目对 .aep 只做提取。
"""
import gzip
import json
import os
import re
import struct
from xml.sax.saxutils import unescape as xml_unescape

AEP_EXTS = (".aep", ".aepx")

_RE_XML_PATH = re.compile(r"<Path>(.*?)</Path>", re.S)
_RE_JSON_FULLPATH = re.compile(r'"fullpath"\s*:\s*"((?:[^"\\]|\\.)*)"')


def is_aep(path):
    return os.path.splitext(path or "")[1].lower() in AEP_EXTS


def _aep_rifx_refs(data):
    """从 RIFX 结构里挖 alas 的 fullpath，返回 [(path, target_is_folder)]"""
    out = []
    total = len(data)
    i = 0
    while True:
        i = data.find(b"alas", i)
        if i < 0:
            break
        if i + 8 <= total:
            size = struct.unpack(">I", data[i + 4:i + 8])[0]
            if 2 < size < (1 << 20) and i + 8 + size <= total:
                raw = data[i + 8:i + 8 + size].rstrip(b"\x00")
                # 用 '{' 开头做一次廉价校验，避免把别处的 "alas" 误当 chunk
                if raw[:1] == b"{":
                    try:
                        obj = json.loads(raw.decode("utf-8", "replace"))
                    except Exception:
                        obj = None
                    if isinstance(obj, dict) and obj.get("fullpath"):
                        out.append((obj["fullpath"],
                                    bool(obj.get("target_is_folder"))))
        i += 4
    return out


def _aep_xml_refs(text):
    """从解压后的 XML 文本里找路径（<Path> 标签 + JSON 的 fullpath）"""
    out = []
    for m in _RE_XML_PATH.finditer(text):
        p = xml_unescape(m.group(1)).strip()
        if p:
            out.append((p, False))
    for m in _RE_JSON_FULLPATH.finditer(text):
        raw = m.group(1)
        try:
            p = json.loads('"' + raw + '"')      # 还原 \\ 之类的转义
        except Exception:
            p = raw
        if p:
            out.append((p, False))
    return out


def load_aep_refs(path, progress=None):
    """读 .aep/.aepx，返回 [(绝对路径, 是否目录引用)]"""
    def tick(msg):
        if progress:
            progress(msg)

    tick("读取 After Effects 工程…")
    with open(path, "rb") as f:
        data = f.read()

    if data[:2] == b"\x1f\x8b":                  # gzip 压缩的 XML 工程
        tick("解压工程数据…")
        try:
            data = gzip.decompress(data)
        except Exception:
            return []

    if data[:4] == b"RIFX":
        tick("解析 RIFX 结构…")
        return _aep_rifx_refs(data)
    if data[:5] == b"<?xml" or b"<AfterEffectsProject" in data[:4096]:
        tick("解析 XML 结构…")
        return _aep_xml_refs(data.decode("utf-8", "replace"))
    tick("无法识别的 AE 工程格式")
    return []


def extract_aep(path, progress=None):
    """AE 工程 → 与 prproj.extract() 同构的 records"""
    refs = load_aep_refs(path, progress)
    seen = set()
    records = []
    for p, is_folder in refs:
        if not p:
            continue
        if is_folder:            # 目录引用（工程根目录之类）不算素材
            continue
        p = os.path.normpath(p)
        key = p.lower()
        if key in seen:          # 同一个文件可能被多个合成引用
            continue
        seen.add(key)
        parent = os.path.dirname(p)
        records.append({
            "uid": "",
            "mc_uid": "",
            "folder": os.path.basename(parent) if parent else "",
            "name": os.path.basename(p),
            "path": p,
            "exists": os.path.exists(p),
        })
    if progress:
        progress("完成")
    return records
