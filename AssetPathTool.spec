# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 —— 素材路径提取工具 / Asset Path Tool
===========================================================
用法：
    pyinstaller AssetPathTool.spec --noconfirm

产物：
    dist/AssetPathTool/            ← 整个文件夹就是绿色版，压缩后可直接分发
    dist/AssetPathTool/AssetPathTool.exe

想改成「单文件 exe」的话，把下面 ONEFILE 改成 True —— 会变成一个
exe，但启动要先把自身解压到临时目录，首次启动慢 1~3 秒，杀毒软件也
更容易误报。日常分发建议保持 False（文件夹版）。
"""
import os
import re
import sys

# ---------------------------------------------------------------- 基本设置
APP_NAME = "AssetPathTool"             # 纯 ASCII，Release 文件名 / URL 都安全
ENTRY = "AssetPathToolMain.py"         # 入口脚本
VERSION_SRC = os.path.join("src", "appinfo.py")   # 版本号唯一来源
ONEFILE = False                        # True = 单文件；False = 文件夹版

is_win = sys.platform.startswith("win")
is_mac = sys.platform == "darwin"

# 有图标就用，没有也不报错
icon_file = None
for cand in (f"{APP_NAME}.ico", "app.ico"):
    if is_win and os.path.isfile(cand):
        icon_file = cand
        break
for cand in (f"{APP_NAME}.icns", "app.icns"):
    if is_mac and os.path.isfile(cand):
        icon_file = cand
        break


# ---------------------------------------------------------------- 版本号
# 从 src/appinfo.py 的 APP_VER 读，唯一来源；这样 exe 的「属性 → 详细信息」
# 里显示的版本和界面标题栏永远一致。
def _read_version():
    try:
        with open(VERSION_SRC, "r", encoding="utf-8") as f:
            m = re.search(r'^APP_VER\s*=\s*["\']([^"\']+)["\']', f.read(), re.M)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "0.0.0"


app_version = _read_version()
_v = [int(x) for x in (re.findall(r"\d+", app_version) + ["0", "0", "0"])[:3]]

version_file = None
if is_win:
    version_file = os.path.join("build", "version_info.txt")
    os.makedirs("build", exist_ok=True)
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(
            """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(%d, %d, %d, 0),
    prodvers=(%d, %d, %d, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '080404B0',
        [StringStruct('CompanyName', 'SaraKale'),
         StringStruct('FileDescription', '素材路径提取工具'),
         StringStruct('FileVersion', '%s'),
         StringStruct('InternalName', '%s'),
         StringStruct('OriginalFilename', '%s.exe'),
         StringStruct('ProductName', 'Asset Path Tool'),
         StringStruct('ProductVersion', '%s')])
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""
            % (_v[0], _v[1], _v[2], _v[0], _v[1], _v[2],
               app_version, APP_NAME, APP_NAME, app_version)
        )


# ---------------------------------------------------------------- 依赖收集
# tkwebui 是随项目一起分发的纯 Python 包（根目录 tkwebui/），内部有些 import
# 写在函数体里，静态分析偶尔会漏，这里显式补一遍。
# src/ 是自带的多文件包，同样全量收进来，避免某个页面模块被漏掉。
hiddenimports = []
try:
    from PyInstaller.utils.hooks import collect_submodules
    hiddenimports += collect_submodules("tkwebui")
    hiddenimports += collect_submodules("src")
except Exception:
    hiddenimports += ["tkwebui", "src"]

# 明确排掉体积大、本项目完全用不到的科学计算栈，产物能小一半
excludes = [
    "numpy", "scipy", "pandas", "matplotlib", "PIL", "IPython",
    "pytest", "setuptools", "pip", "wheel",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
    # 开发期临时脚本，不要打进包里
    "_shot",
]

a = Analysis(
    [ENTRY],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        icon=icon_file,
        version=version_file,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=is_win,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        icon=icon_file,
        version=version_file,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=is_win,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,          # COLLECT 阶段再压会拖慢启动，且容易触发误报
        name=APP_NAME,
    )

if is_mac and not ONEFILE:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon_file,
        bundle_identifier="com.sarakale.assetpathtool",
        version=app_version,
    )
