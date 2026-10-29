# -*- coding: utf-8 -*-
"""两个工程互相比，看出新增 / 删除 / 路径变化 / 位置变化。"""
import csv
import os
import re
from collections import defaultdict

from .remap import apply_rules

DIFF_KINDS = ("新增", "删除", "路径变化", "位置变化", "未变")


def compare_records(a, b, ignore_no_path=True):
    """
    对比两份 records。
    优先用 ObjectUID 配对（同一项目的不同版本 UID 稳定），配对不上再按素材名配对。
    ignore_no_path=True 时忽略序列、调整图层等没有源文件的条目，避免对比结果被噪音淹没。
    返回 (rows, stats)
    """
    if ignore_no_path:
        a = [r for r in a if r["path"]]
        b = [r for r in b if r["path"]]

    def norm(p):
        return (p or "").replace("/", "\\").lower()

    b_by_uid, b_by_name = {}, defaultdict(list)
    for j, rb in enumerate(b):
        if rb["uid"]:
            b_by_uid.setdefault(rb["uid"], j)
        b_by_name[rb["name"]].append(j)

    used_b, matched_a, pairs = set(), set(), []

    for i, ra in enumerate(a):
        j = b_by_uid.get(ra["uid"]) if ra["uid"] else None
        if j is not None and j not in used_b:
            pairs.append((i, j))
            used_b.add(j)
            matched_a.add(i)

    for i, ra in enumerate(a):
        if i in matched_a:
            continue
        for j in b_by_name.get(ra["name"], []):
            if j not in used_b:
                pairs.append((i, j))
                used_b.add(j)
                matched_a.add(i)
                break

    rows = []
    for i, j in pairs:
        ra, rb = a[i], b[j]
        if norm(ra["path"]) != norm(rb["path"]):
            kind = "路径变化"
        elif ra["folder"] != rb["folder"]:
            kind = "位置变化"
        else:
            kind = "未变"
        rows.append({"type": kind, "folder": rb["folder"], "name": rb["name"],
                     "a_path": ra["path"], "b_path": rb["path"]})

    for i, ra in enumerate(a):
        if i not in matched_a:
            rows.append({"type": "删除", "folder": ra["folder"], "name": ra["name"],
                         "a_path": ra["path"], "b_path": ""})
    for j, rb in enumerate(b):
        if j not in used_b:
            rows.append({"type": "新增", "folder": rb["folder"], "name": rb["name"],
                         "a_path": "", "b_path": rb["path"]})

    order = {k: i for i, k in enumerate(DIFF_KINDS)}
    rows.sort(key=lambda r: (order.get(r["type"], 9), r["folder"], r["name"]))

    stats = defaultdict(int)
    for r in rows:
        stats[r["type"]] += 1
    return rows, stats


def write_diff_csv(rows, out_path):
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["变化类型", "项目文件夹", "素材名", "A（旧）路径", "B（新）路径"])
        for r in rows:
            w.writerow([r["type"], r["folder"], r["name"], r["a_path"], r["b_path"]])


def build_diff_txt(rows, stats, name_a, name_b):
    lines = [f"A（旧）：{name_a}", f"B（新）：{name_b}", ""]
    lines.append("变化统计：" + "｜".join(f"{k} {stats.get(k, 0)}" for k in DIFF_KINDS))
    lines.append("=" * 60)

    # 按文件夹汇总，快速看出「整体上多了/少了哪个素材包」
    for kind in ("新增", "删除"):
        block = [r for r in rows if r["type"] == kind]
        if not block:
            continue
        by_folder = defaultdict(int)
        for r in block:
            by_folder[r["folder"] or "(根目录)"] += 1
        lines.append("")
        lines.append(f"【{kind} · 按文件夹汇总】")
        for folder, n in sorted(by_folder.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"  {n:>4} 条  {folder}")

    for kind in ("新增", "删除", "路径变化", "位置变化"):
        block = [r for r in rows if r["type"] == kind]
        if not block:
            continue
        lines.append("")
        lines.append(f"【{kind}】{len(block)} 条")
        for r in block:
            lines.append(f"  文件夹：{r['folder'] or '(根目录)'}")
            lines.append(f"  素材名：{r['name']}")
            if kind == "删除":
                lines.append(f"    A 路径：{r['a_path'] or '(无源文件)'}")
            elif kind == "新增":
                lines.append(f"    B 路径：{r['b_path'] or '(无源文件)'}")
            else:
                lines.append(f"    A 路径：{r['a_path']}")
                lines.append(f"    B 路径：{r['b_path']}")
    return "\n".join(lines)


# ======================================================================
# 对比 → 重定向 联动
# ======================================================================
def _same_path(a, b):
    return re.sub(r"[\\/]+", "/", a or "").lower() == \
        re.sub(r"[\\/]+", "/", b or "").lower()


def path_mapping(rows):
    """对比结果里「路径变化」的行 → {A 旧路径: B 新路径}"""
    out = {}
    for r in rows:
        if r["type"] != "路径变化":
            continue
        a, b = r["a_path"], r["b_path"]
        if a and b and not _same_path(a, b):
            out[a] = b
    return out


def _common_dir_prefix(dirs):
    """一组目录的公共前缀（按分隔符分段比，不会切在半个目录名上）"""
    if not dirs:
        return ""
    sep = "\\" if any("\\" in d for d in dirs) else "/"
    lists = [[s for s in re.split(r"[\\/]+", d) if s] for d in dirs]
    n = 0
    while all(len(l) > n for l in lists):
        cur = lists[0][n].lower()
        if all(l[n].lower() == cur for l in lists):
            n += 1
        else:
            break
    if n == 0:
        return ""
    return sep.join(lists[0][:n]) + sep


def suggest_rules(rows, max_rules=8):
    """
    从「路径变化」的行里提炼前缀规则，用来批量重定向。

    先试「一条公共前缀规则覆盖全部」—— 整体换盘 / 搬目录是最常见的情况，
    能一条搞定就别给用户塞八条。搞不定再按目录对分组，取覆盖最多的几条。

    返回 {"rules": [(旧前缀, 新前缀)], "covered": n, "total": n, "single": bool}
    covered 是这些规则能解释的变化条数（不含「只是改名、目录没动」的）。
    """
    pairs = [(r["a_path"], r["b_path"]) for r in rows
             if r["type"] == "路径变化" and r["a_path"] and r["b_path"]
             and not _same_path(r["a_path"], r["b_path"])]
    total = len(pairs)
    if not total:
        return {"rules": [], "covered": 0, "total": 0, "single": False}

    # ① 一条规则搞定？
    old_pref = _common_dir_prefix([os.path.dirname(p) for p, _ in pairs])
    new_pref = _common_dir_prefix([os.path.dirname(q) for _, q in pairs])
    if old_pref and new_pref and old_pref.lower() != new_pref.lower():
        rule = (old_pref, new_pref)
        if all(_same_path(apply_rules(p, [rule]), q) for p, q in pairs):
            return {"rules": [rule], "covered": total, "total": total, "single": True}

    # ② 按「旧目录 → 新目录」分组，取覆盖最多的
    groups = defaultdict(list)
    for p, q in pairs:
        groups[(os.path.dirname(p), os.path.dirname(q))].append((p, q))

    out, covered = [], 0
    for (od, nd), items in sorted(groups.items(), key=lambda x: -len(x[1])):
        if len(out) >= max_rules:
            break
        if _same_path(od, nd):
            continue          # 同目录只改了文件名，前缀规则帮不上忙
        rule = (od + os.sep, nd + os.sep)
        if all(_same_path(apply_rules(p, [rule]), q) for p, q in items):
            out.append(rule)
            covered += len(items)
    return {"rules": out, "covered": covered, "total": total,
            "single": len(out) == 1}
