# -*- coding: utf-8 -*-
"""素材路径提取工具（Asset Path Tool）—— 源码包。

目录约定：
    src/appinfo.py          应用名 / 版本号 / 配置目录
    src/i18n.py             多语言文案表 + 语言检测
    src/theme.py            调色板 + ttk 样式
    src/platform_utils.py   DPI / 控制台 / 拖放（Windows 相关）
    src/cli.py              命令行入口
    src/core/               纯解析逻辑，不依赖 tkinter
    src/ui/                 界面层（App + 四个页面）
"""
