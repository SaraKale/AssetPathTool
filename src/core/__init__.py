# -*- coding: utf-8 -*-
"""解析核心：不依赖 tkinter，可单独 import 做脚本 / 单元测试。

    prproj.py    .prproj / .xml（gzip 压缩 XML）
    aep.py       .aep / .aepx（RIFX 或 gzip XML）
    loader.py    按扩展名分派
    usage.py     时间线使用统计
    diff.py      两个项目对比
    remap.py     路径重定向 + 改写工程
    matching.py  按文件名找缺失素材
    update.py    查 GitHub / Gitee 最新 Release tag（检查更新）
"""
