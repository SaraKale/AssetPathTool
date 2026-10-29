# -*- coding: utf-8 -*-
"""Premiere Pro 工程（.prproj / .xml）的素材路径提取。

.prproj 其实就是 gzip 压缩过的 XML（magic 1f 8b），根节点 <PremiereData>。
"""
import csv
import gzip
import os
import xml.etree.ElementTree as ET
from collections import defaultdict


def load_root(path):
    """读入 .prproj（gzip 压缩的 XML）或普通 .xml，返回根节点"""
    if path.lower().endswith(".prproj"):
        with gzip.open(path, "rb") as f:
            data = f.read()
        return ET.fromstring(data)
    return ET.parse(path).getroot()


def get_item_name(elem):
    for xpath in ("ProjectItem/Name", "Name"):
        n = elem.find(xpath)
        if n is not None and n.text and n.text.strip():
            return n.text.strip()
    return "未命名"


def extract(root, progress=None):
    """
    解析 PR XML，返回 records 列表：
      {"uid", "mc_uid", "folder", "name", "path", "exists"}
    """
    def tick(msg):
        if progress:
            progress(msg)

    tick("建立对象索引…")
    objects_by_uid = {}
    for e in root.iter():
        uid = e.get("ObjectUID")
        if uid:
            objects_by_uid[uid] = e

    tick("提取媒体文件路径…")
    media_to_path = {}
    for e in root.iter():
        if e.tag != "Media":
            continue
        uid = e.get("ObjectUID")
        if not uid:
            continue
        for tag in ("FilePath", "ActualMediaFilePath", "RelativePath"):
            n = e.find(tag)
            if n is not None and n.text and n.text.strip():
                media_to_path[uid] = n.text.strip()
                break

    base_index = defaultdict(list)
    for fp in media_to_path.values():
        base_index[os.path.basename(fp.replace("\\", "/")).lower()].append(fp)

    tick("构建文件夹层级…")
    bins = {}
    item_to_parent = {}
    for e in root.iter():
        if e.tag != "BinProjectItem":
            continue
        uid = e.get("ObjectUID")
        if not uid:
            continue
        children = []
        items = e.find("ProjectItemContainer/Items")
        if items is not None:
            for it in items.findall("Item"):
                ref = it.get("ObjectURef")
                if ref:
                    children.append(ref)
                    item_to_parent[ref] = uid
        bins[uid] = {"name": get_item_name(e), "children": children}

    def folder_path(uid):
        parts, cur, guard = [], uid, 0
        while cur and guard < 500:
            if cur in bins:
                parts.insert(0, bins[cur]["name"])
            cur = item_to_parent.get(cur)
            guard += 1
        return "/".join(parts)

    tick("关联素材与路径…")
    records = []
    for e in root.iter():
        if e.tag != "ClipProjectItem":
            continue
        uid = e.get("ObjectUID")
        name = get_item_name(e)
        path = None

        # ClipProjectItem -> MasterClip -> Media.ObjectUID -> Media.FilePath
        mc = e.find("MasterClip")
        mc_uid = mc.get("ObjectURef") if mc is not None else None
        if mc_uid:
            path = media_to_path.get(mc_uid)
            if not path:
                mc_obj = objects_by_uid.get(mc_uid)
                if mc_obj is not None:
                    for prop in mc_obj.iter("Media.ObjectUID"):
                        if prop.text and prop.text.strip() in media_to_path:
                            path = media_to_path[prop.text.strip()]
                            break

        if not path:
            hit = base_index.get(name.lower())
            if hit:
                path = hit[0]

        records.append({
            "uid": uid or "",
            "mc_uid": mc_uid or "",
            "folder": folder_path(uid),
            "name": name,
            "path": path or "",
            "exists": bool(path) and os.path.exists(path),
        })

    tick("完成")
    return records


def summarize(records):
    return {
        "total": len(records),
        "with_path": sum(1 for r in records if r["path"]),
        "missing": sum(1 for r in records if r["path"] and not r["exists"]),
        "folders": len({r["folder"] for r in records if r["folder"]}),
    }


def build_txt(records):
    grouped = defaultdict(list)
    for r in records:
        if r["path"]:
            grouped[r["folder"]].append(r["path"])
    lines = []
    for folder in sorted(grouped):
        if not folder:
            continue
        lines.append(f"项目文件夹:{folder}")
        for p in sorted(grouped[folder]):
            lines.append(p)
        lines.append("")
    return "\n".join(lines)


def write_txt(records, out_path):
    with open(out_path, "w", encoding="utf-8-sig") as f:
        f.write(build_txt(records))


def write_csv(records, out_path):
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["项目文件夹", "素材名", "硬盘路径", "文件是否存在"])
        for r in records:
            w.writerow([r["folder"], r["name"], r["path"], "是" if r["exists"] else "否"])
