# -*- coding: utf-8 -*-
"""路径重定向：按前缀规则批量换盘 / 换目录，以及把结果写回 .prproj。"""
import gzip
import os
import re

from xml.sax.saxutils import escape as xml_escape, unescape as xml_unescape

PATH_TAG_RE = re.compile(r"<(FilePath|ActualMediaFilePath)>(.*?)</\1>", re.S)


def clean_prefix(s, sep="\\"):
    """把连续的分隔符压成一个，并去掉结尾分隔符。
    某些 shell（如 Git Bash）会把 D:\\xxx 传成 D://xxx，粘贴路径也可能带多余斜杠。"""
    return re.sub(r"[\\/]+", lambda m: sep, s.strip()).rstrip("\\/")


def apply_rules(path, rules):
    """
    按顺序套用 (旧前缀, 新前缀) 规则，命中第一条就返回。
    匹配时忽略大小写、忽略 / 和 \\ 的差别，并容忍首尾多余的分隔符。
    """
    if not path:
        return path

    def norm(s):
        return s.replace("/", "\\").lower()

    np_ = norm(path)
    sep = "\\" if "\\" in path else "/"
    for old, new in rules:
        if not old:
            continue
        o = clean_prefix(old)
        if not o:
            continue
        idx = np_.find(norm(o))
        if idx >= 0:
            prefix = clean_prefix(new, sep)
            return prefix + path[idx + len(o):]
    return path


def remap_records(records, rules=None):
    """
    把提取结果转成「重定向条目」：新路径先等于原路径，
    manual 记录用户双击单独指定的新位置。
    """
    out = []
    for r in records:
        out.append({
            "uid": r["uid"],
            "folder": r["folder"],
            "name": r["name"],
            "old_path": r["path"],
            "manual": "",
            "path": r["path"],
            "changed": False,
            "exists": bool(r["path"]) and os.path.exists(r["path"]),
        })
    return out


def recompute_remap(rows, rules):
    """按规则重算新路径；手动指定过的行保持手动值"""
    for r in rows:
        if r["manual"]:
            new = r["manual"]
        else:
            new = apply_rules(r["old_path"], rules)
        r["path"] = new
        r["changed"] = new != r["old_path"]
        r["exists"] = bool(new) and os.path.exists(new)
    return rows


def path_key(s):
    """把路径压成「大小写无关 + 分隔符无关」的比对键"""
    return re.sub(r"[\\/]+", "/", (s or "").strip()).lower()


def rewrite_prproj(src, dst, rules=None, mapping=None):
    """
    直接对解压后的 XML 文本做精确替换（不重新序列化，最大限度保留原文件结构），
    再 gzip 压回。只写新文件，绝不覆盖原项目。

    mapping: {旧路径: 新路径} 精确映射，优先级高于 rules —— 用户逐条双击指定时用这个，
             保证只改他点过的那几条，不会误伤同名路径。
    返回被改写的路径条数。
    """
    raw = gzip.open(src, "rb").read().decode("utf-8", errors="surrogateescape")
    counter = [0]

    lut = {}
    for k, v in (mapping or {}).items():
        if k and v and path_key(k) != path_key(v):
            lut[path_key(k)] = v

    def repl(m):
        tag, inner = m.group(1), m.group(2)
        old_path = xml_unescape(inner)
        new_path = lut.get(path_key(old_path)) if lut else None
        if new_path is None:
            new_path = apply_rules(old_path, rules or [])
        if new_path == old_path:
            return m.group(0)
        counter[0] += 1
        return f"<{tag}>{xml_escape(new_path)}</{tag}>"

    out = PATH_TAG_RE.sub(repl, raw)
    with gzip.open(dst, "wb", compresslevel=6) as f:
        f.write(out.encode("utf-8", errors="surrogateescape"))
    return counter[0]
