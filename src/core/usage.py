# -*- coding: utf-8 -*-
"""时间线使用统计：每个素材被用了几次、共多长、出现在哪些序列。"""
import csv
import os
from collections import defaultdict

from .fsinfo import fmt_mtime, fmt_size, file_info

TICKS_PER_SECOND = 254016000000   # Premiere 内部时间单位


def fmt_duration(seconds):
    """秒 → 3:07 / 1:23:45"""
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def analyze_usage(root, records):
    """
    统计每个素材在时间线上被用过多少次、累计时长、出现在哪些序列。

    引用链（ObjectID 在不同类型对象间会重复，必须按标签类型分别索引）：
        Sequence -> TrackGroup/Second -> VideoTrackGroup / AudioTrackGroup
                 -> TrackGroup/Tracks/Track -> VideoClipTrack / AudioClipTrack
                 -> ClipTrack/ClipItems/TrackItems/TrackItem
                 -> VideoClipTrackItem / AudioClipTrackItem -> ClipTrackItem
                 -> SubClip -> MasterClip(ObjectURef) -> Media.FilePath

    返回 (rows, seq_rows)：
      rows     每个项目素材一条：count / seconds / seqs
      seq_rows 每个序列一条：name / clips / seconds
    """
    by_uid, wrap_by_id, sub_by_id, grp_by_id = {}, {}, {}, {}
    for e in root.iter():
        u = e.get("ObjectUID")
        if u:
            by_uid.setdefault(u, e)
        oid = e.get("ObjectID")
        if not oid:
            continue
        if e.tag in ("VideoClipTrackItem", "AudioClipTrackItem"):
            wrap_by_id.setdefault(oid, e)
        elif e.tag == "SubClip":
            sub_by_id.setdefault(oid, e)
        elif e.tag in ("VideoTrackGroup", "AudioTrackGroup"):
            grp_by_id.setdefault(oid, e)

    usage = defaultdict(lambda: {"count": 0, "ticks": 0, "seqs": set()})
    seq_rows = []

    for seq in root.iter():
        if seq.tag != "Sequence" or not seq.get("ObjectUID"):
            continue
        sname = (seq.findtext("Name") or "未命名序列").strip()
        clips, ticks = 0, 0

        for tg in seq.findall("TrackGroups/TrackGroup"):
            second = tg.find("Second")
            grp = grp_by_id.get(second.get("ObjectRef")) if second is not None else None
            if grp is None:
                continue
            for tr in grp.findall("TrackGroup/Tracks/Track"):
                track = by_uid.get(tr.get("ObjectURef"))
                if track is None:
                    continue
                for ti in track.findall("ClipTrack/ClipItems/TrackItems/TrackItem"):
                    wrap = wrap_by_id.get(ti.get("ObjectRef"))
                    if wrap is None:
                        continue
                    is_video = wrap.tag == "VideoClipTrackItem"
                    cti = wrap.find("ClipTrackItem")
                    if cti is None:
                        continue
                    s_ref = cti.find("SubClip")
                    sub = sub_by_id.get(s_ref.get("ObjectRef")) if s_ref is not None else None
                    if sub is None:
                        continue
                    mc = sub.find("MasterClip")
                    if mc is None or not mc.get("ObjectURef"):
                        continue

                    dur = 0
                    t = cti.find("TrackItem")
                    if t is not None:
                        try:
                            dur = int(t.findtext("End") or 0) - int(t.findtext("Start") or 0)
                        except (TypeError, ValueError):
                            dur = 0

                    clips += 1
                    u = usage[mc.get("ObjectURef")]
                    u["count"] += 1
                    u["seqs"].add(sname)
                    if is_video:          # 音视频成对出现，时长只算视频轨，避免翻倍
                        u["ticks"] += dur
                        ticks += dur

        seq_rows.append({"name": sname, "clips": clips,
                         "seconds": ticks / TICKS_PER_SECOND})

    rows = []
    for r in records:
        u = usage.get(r.get("mc_uid") or "")
        rows.append({
            "name": r["name"],
            "folder": r["folder"],
            "path": r["path"],
            "exists": r["exists"],
            "count": u["count"] if u else 0,
            "seconds": (u["ticks"] / TICKS_PER_SECOND) if u else 0.0,
            "seqs": "、".join(sorted(u["seqs"])) if u else "",
        })

    rows.sort(key=lambda x: (x["count"], x["name"]))
    seq_rows.sort(key=lambda x: -x["seconds"])
    return rows, seq_rows


def summarize_usage(rows, seq_rows):
    used = sum(1 for r in rows if r["count"] > 0)
    return {
        "total": len(rows),
        "used": used,
        "unused": len(rows) - used,
        "seqs": len(seq_rows),
        "seconds": sum(r["seconds"] for r in rows),
    }


# 类型分组用的大类名（按扩展名归到这三类 + 其它）
_KIND_BY_EXT = {}
for _e in (".mp4", ".m4v", ".mov", ".flv", ".f4v", ".mkv", ".avi", ".wmv",
           ".mpg", ".mpeg", ".m2v", ".mts", ".mxf", ".webm", ".rmvb", ".rm",
           ".3gp", ".vob"):
    _KIND_BY_EXT[_e] = "视频"
for _e in (".wav", ".mp3", ".aac", ".m4a", ".flac", ".ogg", ".wma", ".aif",
           ".aiff", ".ac3"):
    _KIND_BY_EXT[_e] = "音频"
for _e in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".tga", ".psd",
           ".gif", ".webp", ".dpx", ".exr"):
    _KIND_BY_EXT[_e] = "图片"


def ext_kind(path_or_name):
    """扩展名 → 视频 / 音频 / 图片 / 其它"""
    ext = os.path.splitext(path_or_name or "")[1].lower()
    return _KIND_BY_EXT.get(ext, "其它")


def group_usage(rows, by="folder", size_cache=None):
    """
    把逐条统计汇总成组。

    by="folder" → 按素材所在目录分组
    by="kind"   → 按类型（视频 / 音频 / 图片 / 其它）分组
    by="ext"    → 按具体扩展名分组

    组里除了条数和时长，还算出「一共占多大」—— 硬盘紧张时最想知道
    「哪个目录吃了我一个 T，结果一半没用过」。
    返回按累计时长降序的列表。
    """
    groups = {}
    for r in rows:
        if by == "kind":
            key = ext_kind(r["path"] or r["name"])
        elif by == "ext":
            key = (os.path.splitext(r["path"] or r["name"])[1].lower() or "(无后缀)")
        else:
            key = r["folder"] or "(根目录)"

        g = groups.get(key)
        if g is None:
            g = groups[key] = {"name": key, "total": 0, "used": 0, "unused": 0,
                               "count": 0, "seconds": 0.0, "bytes": 0,
                               "unknown_size": 0}
        g["total"] += 1
        if r["count"] > 0:
            g["used"] += 1
        g["count"] += r["count"]
        g["seconds"] += r["seconds"]
        if r.get("path"):
            size, _mtime = file_info(r["path"], size_cache)
            if size is None:
                g["unknown_size"] += 1
            else:
                g["bytes"] += size

    out = list(groups.values())
    for g in out:
        g["unused"] = g["total"] - g["used"]
    out.sort(key=lambda x: (-x["seconds"], -x["count"], x["name"]))
    return out


def write_group_csv(groups, by, out_path):
    head = {"folder": "文件夹", "kind": "类型", "ext": "后缀"}.get(by, "分组")
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([head, "素材数", "已使用", "从未使用", "使用次数",
                    "累计时长", "占用空间"])
        for g in groups:
            w.writerow([g["name"], g["total"], g["used"], g["unused"], g["count"],
                        fmt_duration(g["seconds"]),
                        fmt_size(g["bytes"]) if g["bytes"] else "—"])


def write_usage_csv(rows, out_path):
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["素材名", "项目文件夹", "使用次数", "累计时长", "出现在序列", "硬盘路径"])
        for r in rows:
            w.writerow([r["name"], r["folder"], r["count"],
                        fmt_duration(r["seconds"]), r["seqs"], r["path"]])
