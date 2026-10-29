# -*- coding: utf-8 -*-
"""应用元信息 + 程序目录 / 配置文件位置。

改版本号只改这里一处：spec 会读它生成 exe 的版本资源，界面标题也用它。
"""
import os
import sys

# 窗口标题（中文原文，同时是多语言表的 key）
APP_TITLE = "素材路径提取工具"

# 纯 ASCII 名：打包产物名、配置文件名、Release 文件名都用它
APP_NAME = "AssetPathTool"

# 兼容旧代码的别名
APP_ID = APP_NAME

# 版本号 —— 由维护者手动改，不要自动递增
APP_VER = "1.0.2"

# 作者 / 仓库（发布前把 APP_REPO 改成你自己的仓库地址，README 里的徽章会用到）
APP_AUTHOR = "SaraKale"
APP_REPO = "https://github.com/SaraKale/AssetPathTool"
APP_LICENSE = "MIT"

# 一句话简介（README / 关于 用）
APP_DESC = ("Extract asset paths from Premiere Pro / After Effects / Audition projects,  "
            "Supports comparison, redirection, and usage statistics.")


# ---------------------------------------------------------------- 目录定位
def app_dir():
    """程序所在目录。

    · 打包后（PyInstaller）= exe 所在目录，绿色版拷到哪配置就跟到哪
    · 源码运行 = 项目根目录（src/ 的上一级）
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _writable(d):
    """这个目录能不能写文件（装到 Program Files、macOS .app 包里通常不行）"""
    probe = os.path.join(d, ".write_probe")
    try:
        with open(probe, "w", encoding="utf-8") as f:
            f.write("")
        os.remove(probe)
        return True
    except Exception:
        return False


def _user_config_dir():
    base = (os.environ.get("APPDATA")
            or os.environ.get("XDG_CONFIG_HOME")
            or os.path.join(os.path.expanduser("~"), ".config"))
    return os.path.join(base, APP_NAME)


def config_path():
    """配置文件路径。

    优先放在程序旁边（AssetPathTool.config.json）—— 绿色版拷走配置一起走，
    用户打开 exe 所在文件夹就能看到，比 %APPDATA% 好找。
    目录不可写时（Program Files、macOS .app 内部、/usr/local）退回用户目录。
    """
    d = app_dir()
    if _writable(d):
        return os.path.join(d, APP_NAME + ".config.json")
    return os.path.join(_user_config_dir(), "config.json")


def legacy_config_path():
    """旧版本的配置位置（%APPDATA%\\AssetPathTool\\config.json），只用于迁移"""
    return os.path.join(_user_config_dir(), "config.json")
