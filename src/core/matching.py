# -*- coding: utf-8 -*-
"""按文件名找缺失素材。

策略：不要求文件名完全一致，而是「规范化主干 + 前缀匹配 + 相似度打分」。
理由：素材被改名是很常见的（加了版本号、导出了一次后缀变了、素材站
自动加了 ID），只要开头几个字对得上，人眼就能认出来。
"""
import difflib
import os
import re
import unicodedata
from collections import defaultdict

_NAME_NOISE = re.compile(
    r"[\s\u3000_\-—–·．.、,，。:：;；!！?？'\"“”‘’()（）\[\]【】《》〈〉<>/\\|+*#@&~]+")

# 默认只索引这些「媒体类」扩展名：既能容忍后缀不同（flv/mp4/mov 互相认），
# 又不会把游戏资源目录里成千上万个 .dat/.pak 全拉进来
VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".flv", ".f4v", ".mkv", ".avi", ".wmv",
              ".mpg", ".mpeg", ".m2v", ".mts", ".mxf", ".webm", ".rmvb", ".rm",
              ".3gp", ".vob"}
AUDIO_EXTS = {".wav", ".mp3", ".aac", ".m4a", ".flac", ".ogg", ".wma", ".aif",
              ".aiff", ".ac3"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".tga", ".psd",
              ".gif", ".webp", ".dpx", ".exr"}
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS

_EXT_FAMILY = {}
for _e in VIDEO_EXTS:
    _EXT_FAMILY[_e] = "video"
for _e in AUDIO_EXTS:
    _EXT_FAMILY[_e] = "audio"
for _e in IMAGE_EXTS:
    _EXT_FAMILY[_e] = "image"


def ext_family(ext):
    """扩展名 → 大类（video / audio / image / 空）"""
    return _EXT_FAMILY.get((ext or "").lower(), "")


def norm_stem(name):
    """文件名 → 比对用的规范化主干：去扩展名、全角转半角、小写、去标点空格"""
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    stem = unicodedata.normalize("NFKC", stem).lower()
    return _NAME_NOISE.sub("", stem)


def _no_digits(s):
    return re.sub(r"\d+", "", s)


def stem_score(a, b):
    """
    两段规范化文件名主干有多像，0~1。
    除了 difflib 的编辑相似度，额外照顾三种常见改名：
      · 前缀匹配（xxx.mp4 → xxx_修正版.mp4 / xxx.406029846.flv）
      · 一边完整包含另一边
      · 尾部被加了一串数字
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    r = difflib.SequenceMatcher(None, a, b).ratio()

    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    # 前缀匹配：短的那个是长的开头。太短的不算（否则 "01" 会匹配一切）
    if len(short) >= 4 and long_.startswith(short):
        r = max(r, 0.80 + 0.18 * len(short) / len(long_))
    elif len(short) >= 4 and short in long_:
        r = max(r, 0.55 + 0.42 * len(short) / len(long_))

    # 「同名但带一串数字后缀」单独加分
    a2, b2 = _no_digits(a), _no_digits(b)
    if a2 and b2:
        if a2 == b2:
            r = max(r, 0.94)
        else:
            r = max(r, difflib.SequenceMatcher(None, a2, b2).ratio() * 0.96)
    return min(r, 1.0)


def scan_media_index(roots, exts=None, progress=None, max_depth=None,
                     max_files=120000):
    """
    递归扫描目录，建文件名索引。
    返回 (索引, 是否被截断)。
    索引元素 = (规范化主干, 完整路径, 小写扩展名, 字符集合, 去数字后的长度)

    素材盘动辄几十万个文件（实测 D:\\仙剑奇侠传 深度 4 就有 40 万个），
    所以必须给深度和总量都设上限，否则点一下要等好几分钟。
    字符集合和去数字长度都用于后续「便宜的预筛」，避免对每个候选都跑 SequenceMatcher。
    """
    idx = []
    truncated = False
    for root_dir in roots:
        base = root_dir.rstrip("\\/")
        base_depth = base.count(os.sep)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            if max_depth is not None and dirpath.count(os.sep) - base_depth >= max_depth:
                dirnames[:] = []          # 到深度上限就不再往下走
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if exts and ext not in exts:
                    continue
                stem = norm_stem(fn)
                if not stem:
                    continue
                idx.append((stem, os.path.join(dirpath, fn), ext, set(stem),
                            len(_no_digits(stem))))
                if progress and len(idx) % 800 == 0:
                    progress(f"已扫描 {len(idx)} 个文件…")
                if len(idx) >= max_files:
                    truncated = True
                    return idx, truncated
    return idx, truncated


def match_missing(targets, index, min_score=0.62, top_n=3, progress=None):
    """
    targets: [{"key","stem","ext"}]，key 由调用方自己定义（这里只做回传）
    返回 {key: [{"path","score","folder"}]}，按相似度降序，每条最多 top_n 个建议

    为了在几十万文件的索引上还能秒出结果，做了两级预筛：
      ① 按「去掉数字后的长度」分桶，只比对长度相近的（改名很少大幅改变长度；
         用去数字后的长度分桶，是为了不漏掉「名字尾部被加了一串数字」这种情况）
      ② 字符集合重合度太低直接跳过，避免跑昂贵的 SequenceMatcher
    """
    out = {}
    buckets = defaultdict(list)
    for item in index:
        buckets[item[4] // 3].append(item)

    total = len(targets) or 1
    for i, t in enumerate(targets):
        tstem = t.get("stem") or ""
        text_ = (t.get("ext") or "").lower()
        if not tstem:
            out[t["key"]] = []
            continue
        tset = set(tstem)
        tcore = _no_digits(tstem)
        tlen = len(tcore) or len(tstem)
        # 放宽到接近 2 倍长度：允许候选名比原名长出一截（加后缀、加版本号）
        slack = max(8, int(0.9 * tlen))
        pool_items = []
        for b in range(max(0, (tlen - slack) // 3), (tlen + slack) // 3 + 1):
            pool_items.extend(buckets.get(b, ()))

        cands = []
        for stem, path, ext, cset, clen in pool_items:
            if len(tset & cset) < max(2, 0.5 * min(len(tset), len(cset))):
                continue
            if abs(clen - tlen) > slack:
                continue
            sc = stem_score(tstem, stem)
            if ext == text_:
                sc = min(1.0, sc + 0.03)         # 后缀完全一样，稍微加分
            elif text_ and ext:
                fa, fb = ext_family(text_), ext_family(ext)
                if fa and fb and fa != fb:
                    # 视频配到音频/图片，几乎一定是误判：压到自动选中线以下，
                    # 但仍然列出来让用户自己判断
                    sc -= 0.16
            if sc >= min_score:
                cands.append((sc, path, ext))
        cands.sort(key=lambda x: -x[0])
        seen, keep = set(), []
        for sc, path, ext in cands:
            k = (norm_stem(os.path.basename(path)), ext)
            if k in seen:                    # 同名文件只留一条
                continue
            seen.add(k)
            keep.append({"path": path, "score": sc,
                         "folder": os.path.dirname(path)})
            if len(keep) >= top_n:
                break
        out[t["key"]] = keep
        if progress and (i + 1) % 5 == 0:
            progress(f"已匹配 {i + 1}/{total} 条…")
    return out
