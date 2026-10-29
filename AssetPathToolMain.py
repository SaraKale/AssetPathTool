# -*- coding: utf-8 -*-
"""素材路径提取工具（Asset Path Tool）—— 程序入口。

四合一：提取 / 对比 / 重定向 / 使用统计　Premiere Pro & After Effects & Audition 素材路径

  ① 提取   从 .prproj（自动 gzip 解压）、.aep / .aepx、.sesx 或 .xml 里提取
           「项目文件夹 → 硬盘真实路径」，并检查文件是否还在硬盘上。
           文件夹按树形折叠展示。
  ② 对比   两个工程互相比，看出新增 / 删除 / 路径变化 / 位置变化。
  ③ 重定向 先列出全部素材路径，双击某一行单独选新位置；也可以在「规则表」里加前缀规则批量换盘。
           可选另存一份改写好的 .prproj（不覆盖原文件）。
  ④ 使用统计 分析时间线，看每个素材被用了多少次、共多少时长、出现在哪些序列，
           顺便列出「一次都没用过」的素材。

支持把 .prproj / .aep / .sesx 直接拖进窗口（拖到哪个输入框就填哪个）。
界面支持 简体中文 / 繁體中文 / English / 日本語，首次启动跟随系统语言。

用法：
  双击运行 / python AssetPathToolMain.py            → 图形界面
  python AssetPathToolMain.py --cli A.prproj                     提取
  python AssetPathToolMain.py --cli A.aep                        提取（AE）
  python AssetPathToolMain.py --cli A.sesx                       提取（Audition）
  python AssetPathToolMain.py --cli A.prproj B.prproj --diff      对比
  python AssetPathToolMain.py --cli A.prproj --remap 旧前缀 新前缀  重定向
  python AssetPathToolMain.py --cli A.prproj --usage              使用统计

依赖：仅 Python 标准库（tkinter / xml / gzip / csv / re / ctypes）。
"""
import os
import sys

# 允许从任意工作目录运行，也兼容 PyInstaller 打包后的路径布局
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.cli import run_cli                          # noqa: E402
from src.platform_utils import attach_console, relaunch_with_tk  # noqa: E402
from src.theme import enable_dpi                     # noqa: E402


def main():
    argv = sys.argv[1:]
    if argv and (argv[0] == "--cli" or os.path.isfile(argv[0])):
        attach_console()

    # DPI 感知必须赶在 tk.Tk() 之前设，否则整窗按 96dpi 画，高分辨率屏上会糊
    enable_dpi()

    if argv and argv[0] == "--cli":
        sys.exit(run_cli(argv[1:]))

    if argv and os.path.isfile(argv[0]):
        sys.exit(run_cli(argv))

    try:
        import tkinter  # noqa: F401
        has_tk = True
    except ImportError:
        has_tk = False

    if not has_tk:
        if relaunch_with_tk():
            return
        print("[错误] 当前 Python 缺少 tkinter，无法打开图形界面。")
        print("请改用：py AssetPathToolMain.py   或   C:\\Python314\\python.exe AssetPathToolMain.py")
        print("命令行模式：py AssetPathToolMain.py --cli 项目.prproj")
        sys.exit(1)

    try:
        import tkinter as tk
        from src.ui.app import App
        root = tk.Tk()
        App(root)
        root.mainloop()
    except Exception as ex:
        print(f"[提示] 图形界面启动失败（{ex}）")
        print("用法：py AssetPathToolMain.py --cli 项目.prproj")
        sys.exit(1)


if __name__ == "__main__":
    main()
