# -*- coding: utf-8 -*-
"""命令行模式：不带界面直接出结果，方便批处理 / 定时任务。"""
import argparse
import os

from .appinfo import APP_TITLE, APP_VER
from .core.diff import DIFF_KINDS, build_diff_txt, compare_records, write_diff_csv
from .core.loader import can_rewrite, can_usage, extract_any, project_kind
from .core.prproj import load_root, summarize, write_csv, write_txt
from .core.remap import recompute_remap, remap_records, rewrite_prproj
from .core.usage import analyze_usage, fmt_duration, summarize_usage, write_usage_csv


def run_cli(argv):
    ap = argparse.ArgumentParser(
        prog="AssetPathTool",
        description=f"{APP_TITLE} v{APP_VER}：提取 / 对比 / 重定向 / 使用统计",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  AssetPathToolMain.py --cli A.prproj\n"
               "  AssetPathToolMain.py --cli A.prproj B.prproj --diff\n"
               "  AssetPathToolMain.py --cli A.aep\n"
               "  AssetPathToolMain.py --cli A.sesx\n"
               "  AssetPathToolMain.py --cli A.prproj --usage\n"
               "  AssetPathToolMain.py --cli A.prproj --remap \"D:\\\\旧\" \"E:\\\\新\"\n")
    ap.add_argument("files", nargs="+", help="一个文件=提取；两个文件=对比")
    ap.add_argument("--diff", action="store_true", help="对比模式（需要两个文件）")
    ap.add_argument("--remap", nargs=2, action="append", metavar=("旧前缀", "新前缀"),
                    help="重定向规则，可重复使用")
    ap.add_argument("-o", "--out", help="输出文件路径")
    ap.add_argument("--csv", action="store_true", help="同时导出 CSV")
    ap.add_argument("--rewrite", metavar="输出.prproj",
                    help="另存一份改写后的 prproj（不覆盖原文件）")
    ap.add_argument("--all", action="store_true",
                    help="对比时把序列/调整图层等无源文件的条目也算进去")
    ap.add_argument("--usage", action="store_true",
                    help="统计素材在时间线上的使用情况（次数/时长/所在序列）")
    args = ap.parse_args(argv)

    # 从资源管理器「复制为路径」或 cmd 里粘过来时，路径两边会带引号，先去掉
    args.files = [p.strip().strip('"').strip("'") for p in args.files]
    if args.rewrite:
        args.rewrite = args.rewrite.strip().strip('"').strip("'")

    for p in args.files:
        if not os.path.isfile(p):
            print(f"[错误] 文件不存在：{p}")
            return 1

    # ---------- 对比 ----------
    if args.diff or len(args.files) >= 2:
        if len(args.files) < 2:
            print("[错误] 对比模式需要两个文件")
            return 1
        fa, fb = args.files[0], args.files[1]
        print(f"读取 A：{fa}")
        ra = extract_any(fa)
        print(f"读取 B：{fb}")
        rb = extract_any(fb)
        rows, stats = compare_records(ra, rb, ignore_no_path=not args.all)
        out = args.out or os.path.splitext(fb)[0] + "_对比结果.txt"
        with open(out, "w", encoding="utf-8-sig") as f:
            f.write(build_diff_txt(rows, stats, os.path.basename(fa), os.path.basename(fb)))
        print("\n" + "｜".join(f"{k} {stats.get(k, 0)}" for k in DIFF_KINDS))
        if not args.all:
            print("（已忽略序列/调整图层等无源文件条目，加 --all 可包含）")
        print(f"对比结果已写入：{out}")
        if args.csv:
            c = os.path.splitext(out)[0] + ".csv"
            write_diff_csv(rows, c)
            print(f"CSV 已写入：{c}")
        return 0

    # ---------- 提取 / 重定向 / 使用统计 ----------
    src = args.files[0]
    print(f"读取：{src}")
    kind = project_kind(src)
    root = load_root(src) if kind == "pr" else None
    records = extract_any(src, progress=lambda m: print(f"  {m}"))
    base = os.path.splitext(src)[0]

    if args.usage:
        if not can_usage(src):
            print(f"[提示] {os.path.splitext(src)[1]} 只支持素材路径提取，不支持时间线统计。")
            return 1
        print("分析时间线…")
        rows, seq_rows = analyze_usage(root, records)
        s = summarize_usage(rows, seq_rows)
        print(f"\n素材 {s['total']} 个｜已使用 {s['used']}｜从未使用 {s['unused']}｜"
              f"序列 {s['seqs']} 个｜时间线总长 {fmt_duration(s['seconds'])}")
        out = args.out or base + "_使用统计.csv"
        write_usage_csv(rows, out)
        print(f"使用统计已写入：{out}")
        return 0

    if args.remap:
        rules = [(o, n) for o, n in args.remap]
        remapped = recompute_remap(remap_records(records), rules)
        changed = sum(1 for r in remapped if r["changed"])
        found = sum(1 for r in remapped if r["changed"] and r["exists"])
        print(f"\n命中规则 {changed} 条｜新路径在硬盘上存在 {found} 条")
        out = args.out or base + "_重定向.txt"
        write_txt(remapped, out)
        print(f"新清单已写入：{out}")
        if args.csv:
            write_csv(remapped, base + "_重定向.csv")
            print(f"CSV 已写入：{base}_重定向.csv")
        if args.rewrite:
            if not can_rewrite(src):
                print("[提示] 改写只适用于 .prproj；.aep / .sesx 是只读的。")
            else:
                n = rewrite_prproj(src, args.rewrite, rules)
                print(f"已另存改写后的项目：{args.rewrite}（改写 {n} 条路径）")
        return 0

    out = args.out or base + "_素材路径.txt"
    write_txt(records, out)
    s = summarize(records)
    print(f"\n素材条目 {s['total']} 个｜有路径 {s['with_path']} 个｜"
          f"项目文件夹 {s['folders']} 个｜硬盘上找不到 {s['missing']} 个")
    print(f"结果已写入：{out}")
    if args.csv:
        write_csv(records, base + "_素材路径.csv")
        print(f"CSV 已写入：{base}_素材路径.csv")
    return 0
