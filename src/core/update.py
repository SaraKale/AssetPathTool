# -*- coding: utf-8 -*-
"""检查更新：查 GitHub / Gitee 的最新 Release tag，跟本地版本比大小。

放在 core/ 是因为这里不 import tkinter —— 可以单独跑、也能做单元测试：

    python -m src.core.update

取 tag 的顺序：GitHub → Gitee(releases) → Gitee(tags)。
国内直连 api.github.com 经常超时，所以 Gitee 必须当兜底而不是备选。
"""
import json
import re
import urllib.request

from ..appinfo import APP_VER

# ------------------------------------------------------------------ 仓库
# 发版时把 tag 打成 v<APP_VER>（例如 v1.0.0），「检查更新」就是拿 tag 比大小。
GH_REPO = "SaraKale/AssetPathTool"
GITEE_REPO = "sarakale/AssetPathTool"

GH_RELEASES_API = "https://api.github.com/repos/%s/releases" % GH_REPO
GITEE_RELEASES_API = "https://gitee.com/api/v5/repos/%s/releases" % GITEE_REPO
GITEE_TAGS_API = "https://gitee.com/api/v5/repos/%s/tags" % GITEE_REPO

# ------------------------------------------------------------- 下载地址
# (标识, 链接, 提取码)。提取码没有就留空字符串。
# 标识只用来挑显示名，界面上的平台名不翻译（GitHub / Gitee 都是品牌名）。
DOWNLOAD_SOURCES = (
    ("github", "https://github.com/SaraKale/AssetPathTool/releases", ""),
    ("gitee", "https://gitee.com/sarakale/AssetPathTool/releases", ""),
    ("lanzou", "https://wwavg.lanzoum.com/b0rbjanfg", "914k"),
    ("mediafire", "https://www.mediafire.com/folder/1ik8qiblrl7s1/AssetPathTool", ""),
)

# 平台显示名。品牌名不翻译，蓝奏云/MediaFire 也照原样写。
SOURCE_LABEL = {
    "github": "GitHub",
    "gitee": "Gitee",
    "lanzou": "蓝奏云",
    "mediafire": "MediaFire",
}


def parse_version(text):
    """把 v1.2.3 / 1.2 / 1.2.3-beta 之类解析成可比较的数字元组。

    只取数字段：'v1.10.2' → (1, 10, 2)，这样 1.10 > 1.9 不会比错。
    """
    nums = re.findall(r"\d+", str(text or ""))
    if not nums:
        return (0,)
    return tuple(int(n) for n in nums[:4])


def version_label(tag):
    """统一显示成 vX.Y.Z —— tag 本身可能已经带 v，别拼成 vv1.2.3。"""
    s = str(tag or "").strip()
    if not s:
        return ""
    mt = re.match(r"^[vV]?(\d.*)$", s)
    return ("v" + mt.group(1)) if mt else s


def is_newer(tag, cur=None):
    """tag 是否比当前版本新"""
    return parse_version(tag) > parse_version(cur if cur is not None else APP_VER)


def _http_json(url, timeout):
    req = urllib.request.Request(url, headers={
        "User-Agent": "AssetPathTool/%s" % APP_VER,
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _tags_github(data):
    """GitHub /releases：优先正式版；一个都没有就放宽到「非 draft」。"""
    out = [r.get("tag_name") for r in data
           if isinstance(r, dict) and r.get("tag_name")
           and not r.get("draft") and not r.get("prerelease")]
    if out:
        return out
    return [r.get("tag_name") for r in data
            if isinstance(r, dict) and r.get("tag_name")
            and not r.get("draft")]


def _tags_gitee_releases(data):
    return [r.get("tag_name") for r in data
            if isinstance(r, dict) and r.get("tag_name")
            and not r.get("prerelease")]


def _tags_gitee_tags(data):
    return [t.get("name") for t in data
            if isinstance(t, dict) and t.get("name")]


def fetch_latest_version(timeout=12):
    """依次尝试 GitHub → Gitee(releases) → Gitee(tags)。

    返回 (最新 tag, 来源名)；任一源取到 tag 就返回。
    全部失败抛最后一个异常；全都连上但都没有 tag 时返回 (None, None)。
    """
    last = None
    for name, url, extract in (
            ("github", GH_RELEASES_API, _tags_github),
            ("gitee", GITEE_RELEASES_API, _tags_gitee_releases),
            ("gitee", GITEE_TAGS_API, _tags_gitee_tags)):
        try:
            tags = [x for x in extract(_http_json(url, timeout)) if x]
            if tags:
                return max(tags, key=parse_version), name
        except Exception as e:                      # 换下一个源继续试
            last = e
    if last is not None:
        raise last
    return None, None


if __name__ == "__main__":                          # 手工验一下
    print("current:", version_label(APP_VER))
    try:
        tag, src = fetch_latest_version()
        print("latest :", version_label(tag), "via", src)
        print("newer? :", is_newer(tag))
    except Exception as ex:
        print("failed :", "%s: %s" % (type(ex).__name__, ex))
