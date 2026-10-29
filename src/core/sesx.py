# -*- coding: utf-8 -*-
"""Adobe Audition 会话文件（.sesx）的素材路径提取。

.sesx 是**纯文本 XML**（UTF-8 带 BOM，不压缩、不加密）。素材路径在
`<files>` 下每个 `<file>` 元素的**属性**里，而不是子标签：

    <files>
      <file absolutePath="D:\\Music\\童话\\Conformed Files\\a.wav"
            relativePath="Conformed Files/a.wav"
            id="0" mediaHandler="AmioWav"/>
    </files>

`absolutePath` 是原始绝对路径；`relativePath` 是相对会话目录的路径 ——
整个会话文件夹搬到别的盘时，Audition 靠 relativePath 还能找回文件。
本工具以 `absolutePath` 为准（那才是工程里记的东西），
absolutePath 缺失时才用 relativePath 拼会话目录。

老版本 / 其他变体可能写成子标签 `<filePath>...</filePath>`，一并兼容；
结构化解析一条都没拿到时，再从原文里按「盘符开头」正则兜一次底。

改写（`rewrite_sesx`）：只换 `<file>` 开标签里的 `absolutePath` 属性值，
不动 `id`、不动其它任何字节 —— 元素顺序、缩进、注释、换行符全都原样保留。
`relativePath` 按新位置重算（新文件仍在会话目录下时），跑到会话目录外面就
把这个属性删掉：没有相对关系了还留着旧的相对路径，Audition 打开时两边打架。
UTF-8 BOM 原样带回。
"""
import os
import re
import xml.etree.ElementTree as ET

from .remap import apply_rules, path_key
from xml.sax.saxutils import escape as xml_escape, unescape as xml_unescape

SESX_EXTS = (".sesx",)

# 属性名（小写）——absolutePath 优先，其余算别名
_ABS_ATTRS = ("absolutepath", "filepath", "videopath", "mediapath", "path")
_REL_ATTRS = ("relativepath",)

# 子标签名（小写）
_PATH_TAGS = ("filepath", "videopath", "mediapath", "absolutepath")

# 最后兜底：从原文里直接抓绝对路径（盘符开头或 UNC 开头）
_RE_ABS_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/])[^<>\"'|*?\r\n]{1,300}?\.[A-Za-z0-9]{2,6}")


def is_sesx(path):
    return os.path.splitext(path or "")[1].lower() in SESX_EXTS


def _local(name):
    """去掉 XML 命名空间，取小写名字"""
    return (name or "").rsplit("}", 1)[-1].lower()


def _read_text(path):
    """按常见编码把文件读成文本。.sesx 一般是 UTF-8 BOM，但改过的可能是 GBK。"""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "replace")


def _parse_root(path):
    """先让 ET 自己解析（它能处理 BOM 和 XML 声明），失败再退回手工解码"""
    try:
        return ET.parse(path).getroot()
    except Exception:
        pass
    try:
        return ET.fromstring(_read_text(path))
    except Exception:
        return None


def load_sesx_paths(path, progress=None):
    """读 .sesx，返回路径字符串列表（未去重、未规范化）"""
    def tick(msg):
        if progress:
            progress(msg)

    tick("读取 Audition 会话…")
    session_dir = os.path.dirname(os.path.abspath(path))
    root = _parse_root(path)

    out = []
    if root is not None:
        for e in root.iter():
            abs_p = ""
            rel_p = ""
            for k, v in e.attrib.items():
                lk = _local(k)
                v = (v or "").strip()
                if not v:
                    continue
                if lk in _REL_ATTRS:
                    rel_p = v
                elif lk in _ABS_ATTRS and not abs_p:
                    abs_p = v
            if abs_p:
                out.append(abs_p)
            elif rel_p:
                # 只有相对路径：按会话所在目录还原
                out.append(os.path.join(session_dir, rel_p))

            if _local(e.tag) in _PATH_TAGS and e.text and e.text.strip():
                out.append(e.text.strip())

    # 结构化解析什么都没拿到（标签名变了 / 编码坏了）→ 从原文里直接抓路径
    if not out:
        tick("按文本兜底扫描…")
        for m in _RE_ABS_PATH.finditer(_read_text(path)):
            out.append(m.group(0))

    return out


def _normalize(p, session_dir):
    """把路径整理成当前平台的写法；相对路径按会话目录补全"""
    p = (p or "").strip().strip('"')
    if not p:
        return ""
    if os.sep == "\\":
        p = p.replace("/", "\\")
    else:
        p = p.replace("\\", "/")
    # 跨平台写法（/Volumes/... 之类）别硬拼会话目录
    if not os.path.isabs(p) and not p.startswith(("\\", "/")):
        p = os.path.join(session_dir, p)
    return os.path.normpath(p)


def extract_sesx(path, progress=None):
    """Audition 会话 → 与 prproj.extract() 同构的 records"""
    refs = load_sesx_paths(path, progress)
    session_dir = os.path.dirname(os.path.abspath(path))
    seen = set()
    records = []
    for raw in refs:
        p = _normalize(raw, session_dir)
        if not p:
            continue
        key = p.lower()
        if key in seen:          # 同一个文件会被多个片段 / 多条轨道引用
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


# ======================================================================
# 改写
# ======================================================================
# 只匹配 <file ...> 开标签（含自闭合），不碰 <fileID> 这类同前缀的标签
_RE_FILE_TAG = re.compile(r"<file\b[^>]*>", re.I | re.S)

# 属性候选：写回时用第一个真实存在的那个，保持原文件用的是什么名字
_REWRITE_ATTRS = ("absolutePath", "filePath", "videoPath", "mediaPath", "path")


def _attr_re(name):
    return re.compile(r"(\b%s\s*=\s*)([\"'])(.*?)\2" % re.escape(name),
                      re.I | re.S)


def _get_attr(tag, name):
    m = _attr_re(name).search(tag)
    return m.group(3) if m else None


def _set_attr(tag, name, value):
    """改属性值；属性本来不存在就补一个（补在 `/>` 或 `>` 前面）"""
    pat = _attr_re(name)
    if pat.search(tag):
        return pat.sub(lambda m: m.group(1) + m.group(2) + value + m.group(2),
                       tag, count=1)
    m = re.search(r"\s*/>$", tag)
    if m:
        return tag[:m.start()] + f' {name}="{value}"' + tag[m.start():]
    return tag[:-1] + f' {name}="{value}">'


def _del_attr(tag, name):
    pat = re.compile(r"\s+\b%s\s*=\s*([\"']).*?\1" % re.escape(name),
                     re.I | re.S)
    return pat.sub("", tag, count=1)


def rewrite_sesx(src, dst, rules=None, mapping=None):
    """
    把 .sesx 里的素材路径按 rules / mapping 改掉，另存为 dst。

    mapping: {旧路径: 新路径} 精确映射，优先于 rules（逐条双击指定的走这个）。
    返回被改写的路径条数。

    只替换属性值，不重新序列化 XML —— 重新序列化会丢掉缩进、注释、
    属性顺序，Audition 虽然还能读，但用户 diff 起来一片红。
    """
    with open(src, "rb") as f:
        raw = f.read()
    has_bom = raw[:3] == b"\xef\xbb\xbf"
    # surrogateescape 是双向的：非 UTF-8 的字节原样带到输出，不会被替换成 �
    text = raw.decode("utf-8-sig", errors="surrogateescape")
    session_dir = os.path.dirname(os.path.abspath(src))

    lut = {}
    for k, v in (mapping or {}).items():
        if k and v and path_key(k) != path_key(v):
            lut[path_key(k)] = v

    counter = [0]

    def fix_tag(m):
        tag = m.group(0)

        attr_name, old_raw = "", ""
        for cand in _REWRITE_ATTRS:
            v = _get_attr(tag, cand)
            if v is not None and v.strip():
                attr_name, old_raw = cand, v
                break
        if not attr_name:
            return tag

        old_path = xml_unescape(old_raw)
        new_path = lut.get(path_key(old_path))
        if new_path is None:
            new_path = apply_rules(old_path, rules or [])
        if not new_path or path_key(new_path) == path_key(old_path):
            return tag

        counter[0] += 1
        tag = _set_attr(tag, attr_name, xml_escape(new_path))

        # relativePath 跟着一起处理：还在会话目录下就重算，出去了就删
        if _get_attr(tag, "relativePath") is not None:
            rel = ""
            try:
                rel = os.path.relpath(new_path, session_dir)
            except (ValueError, OSError):
                rel = ""
            if rel and not rel.startswith(".."):
                tag = _set_attr(tag, "relativePath",
                                xml_escape(rel.replace(os.sep, "/")))
            else:
                tag = _del_attr(tag, "relativePath")
        return tag

    out = _RE_FILE_TAG.sub(fix_tag, text)
    data = out.encode("utf-8", errors="surrogateescape")
    if has_bom:
        data = b"\xef\xbb\xbf" + data
    with open(dst, "wb") as f:
        f.write(data)
    return counter[0]

