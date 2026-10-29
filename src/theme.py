# -*- coding: utf-8 -*-
"""配色与 ttk 样式。

界面统一用这里的 C 字典取色，不要在别处写死颜色。
"""
import sys

# ---------------------------------------------------------------- tkwebui 探测
# tkwebui：纯标准库的 ttk 主题 + 控件集，随项目一起分发（根目录 tkwebui/）。
# 缺这个文件夹时自动退回原生 ttk，功能不受影响，只是没那么好看。
try:
    import tkwebui
    from tkwebui import (apply_theme as tw_apply_theme,
                         enable_dpi_awareness as tw_enable_dpi,
                         SegmentedControl as TwSegmented,
                         SquareSwitch as TwSwitch,
                         set_placeholder as tw_set_placeholder,
                         ThemedCombobox as TwCombobox,
                         PALETTE as TW_PALETTE)
    HAS_TKWEBUI = True
except Exception:                       # 没装 / 没 tkinter
    tkwebui = None
    tw_apply_theme = tw_enable_dpi = None
    TwSegmented = TwSwitch = tw_set_placeholder = TwCombobox = None
    TW_PALETTE = {}
    HAS_TKWEBUI = False


# ---------------------------------------------------------------- 调色板
C = {
    "bg": "#f2f4f7",          # 页面底色
    "card": "#ffffff",        # 卡片
    "border": "#dfe3e8",
    "line": "#eceff3",
    "text": "#000000",        # 正文 —— 纯黑，用户明确要求
    "sub": "#000000",         # 表单标签（项目文件 / 筛选 / A（旧）…）
    "hint": "#000000",        # 注释 / 提示文字
    "muted": "#9aa3ae",       # 表格里「无路径」这类弱化行（唯一保留的灰）
    "placeholder": "#9aa3ae",  # 输入框空状态提示
    "arrow": "#3d4653",       # 树形展开箭头
    "accent": "#2563eb",
    "accent_dk": "#1d4ed8",
    "accent_lt": "#e8f0fe",
    "ok": "#0f8a4f",
    "bad": "#c0392b",
    "warn": "#b54708",
    "stripe": "#fafbfc",
}

FONT_FAMILY = "Microsoft YaHei UI"


def apply_tkwebui_theme(root, style):
    """装 tkwebui 主题；没有这个库就直接返回，由 init_styles 兜底配色"""
    if not HAS_TKWEBUI:
        return False
    try:
        tw_apply_theme(root, font_family=FONT_FAMILY, font_size=10,
                       accent=C["accent"], accent_hover=C["accent_dk"])
        # tkwebui 默认整窗纯白；本项目用浅灰底 + 白卡片，把页面底色改过来
        style.configure(".", background=C["bg"], foreground=C["text"])
        style.configure("TFrame", background=C["bg"])
        style.configure("TLabel", background=C["bg"], foreground=C["text"])
        style.configure("TNotebook", background=C["bg"])
        root.configure(background=C["bg"])
        return True
    except Exception:
        return False        # 主题装不上也不能让窗口开不出来


def init_styles(root, style, px, fonts, row_h):
    """在 tkwebui 之上叠加本项目需要的变体；没有 tkwebui 时顺便当完整配色。

    px / fonts / row_h 由 App 传进来，避免这里再算一遍 DPI。
    """
    F_BODY = fonts["body"]
    F_H2 = fonts["h2"]
    F_SMALL = fonts["small"]

    # 装了 tkwebui 就沿用它那套主题（圆角图片按钮 / 胶囊滚动条 / 圆角输入框），
    # 千万别再切回 clam，否则 apply_theme 铺好的东西全丢。
    # 下面这些 configure 在 tkwebui 下有一半是「写进去但被图片表面盖住」的，
    # 留着无害（尺寸、字体、行高照样生效），而且没有 tkwebui 时正好当兜底配色。
    if not HAS_TKWEBUI:
        try:
            style.theme_use("clam")
        except Exception:
            pass

    style.configure(".", background=C["bg"], foreground=C["text"],
                    font=F_BODY, borderwidth=0)
    style.configure("TFrame", background=C["bg"])
    style.configure("TLabel", background=C["bg"], foreground=C["text"], font=F_BODY)

    # 选项卡
    style.configure("TNotebook", background=C["bg"], borderwidth=0,
                    tabmargins=(0, 6, 0, 0))
    style.configure("TNotebook.Tab", background="#e6e9ee", foreground=C["sub"],
                    font=F_H2, padding=(px(20), px(9)), borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", C["card"]), ("active", "#eef1f5")],
              foreground=[("selected", C["accent"]), ("active", C["text"])],
              expand=[("selected", (0, 0, 0, 0))])

    # 按钮
    style.configure("Primary.TButton", background=C["accent"], foreground="#ffffff",
                    font=(FONT_FAMILY, 10, "bold"),
                    padding=(px(20), px(9)), borderwidth=0, focusthickness=0)
    style.map("Primary.TButton",
              background=[("active", C["accent_dk"]), ("disabled", "#aec4f0")],
              foreground=[("disabled", "#f0f4fc")])

    style.configure("Ghost.TButton", background=C["card"], foreground=C["text"],
                    font=F_BODY, padding=(px(14), px(8)),
                    borderwidth=1, relief="solid", focusthickness=0)
    style.map("Ghost.TButton",
              background=[("active", "#f3f5f8"), ("disabled", "#eef1f4")],
              foreground=[("disabled", "#8d959f")],
              bordercolor=[("!disabled", C["border"])])

    style.configure("Chip.TButton", background=C["card"], foreground=C["sub"],
                    font=F_SMALL, padding=(px(12), px(6)),
                    borderwidth=1, relief="solid")
    style.map("Chip.TButton",
              background=[("active", C["accent_lt"])],
              foreground=[("active", C["accent"])],
              bordercolor=[("!disabled", C["border"])])

    # 工具按钮：比普通 Ghost 按钮更大更粗，用在「展开全部 / 收起全部」这类
    # 需要一眼看到的辅助操作上
    style.configure("Tool.TButton", background=C["card"], foreground=C["text"],
                    font=(FONT_FAMILY, 10, "bold"),
                    padding=(px(18), px(10)), borderwidth=1,
                    relief="solid", focusthickness=0)
    style.map("Tool.TButton",
              background=[("active", C["accent_lt"])],
              foreground=[("active", C["accent_dk"])],
              bordercolor=[("!disabled", C["border"])],
              relief=[("pressed", "flat")])

    # 输入框
    style.configure("TEntry", fieldbackground="#ffffff", foreground=C["text"],
                    insertcolor=C["text"], bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"],
                    padding=(px(8), px(6)), relief="flat")
    style.map("TEntry", bordercolor=[("focus", C["accent"])])

    # 勾选 / 单选（分两种底色：卡片上、页面底色上）
    for prefix, bg in (("", C["bg"]), ("Card.", C["card"])):
        style.configure(f"{prefix}TCheckbutton", background=bg, foreground=C["text"],
                        font=F_SMALL, focuscolor=bg,
                        indicatorbackground="#ffffff", indicatorcolor=C["accent"],
                        upperbordercolor="#b9c1cc", lowerbordercolor="#b9c1cc",
                        indicatormargin=(0, 0, px(7), 0), padding=(0, px(2)))
        style.map(f"{prefix}TCheckbutton",
                  background=[("active", bg)],
                  indicatorbackground=[("selected", C["accent"])],
                  indicatorcolor=[("selected", "#ffffff")])
        style.configure(f"{prefix}TRadiobutton", background=bg, foreground=C["sub"],
                        font=F_SMALL, focuscolor=bg,
                        indicatorbackground="#ffffff", indicatorcolor=C["accent"],
                        upperbordercolor="#b9c1cc", lowerbordercolor="#b9c1cc",
                        indicatormargin=(0, 0, px(7), 0), padding=(0, px(3)))
        style.map(f"{prefix}TRadiobutton",
                  background=[("active", bg)],
                  foreground=[("selected", C["accent"])],
                  indicatorbackground=[("selected", C["accent"])],
                  indicatorcolor=[("selected", "#ffffff")])

    # 表格
    style.configure("Treeview", background=C["card"], fieldbackground=C["card"],
                    foreground=C["text"], font=F_BODY,
                    rowheight=row_h, borderwidth=0, indent=px(30))
    style.configure("Treeview.Heading", background="#f5f7fa", foreground="#2b3138",
                    font=(FONT_FAMILY, 10, "bold"),
                    padding=(px(10), px(9)), borderwidth=0, relief="flat")
    style.map("Treeview.Heading", background=[("active", "#eef1f5")])
    style.map("Treeview", background=[("selected", C["accent_lt"])],
              foreground=[("selected", C["text"])])

    style.configure("Vertical.TScrollbar", background="#d8dde4", troughcolor=C["card"],
                    borderwidth=0, arrowcolor=C["sub"], width=px(12))
    style.configure("Horizontal.TScrollbar", background="#d8dde4",
                    troughcolor=C["card"], borderwidth=0, arrowcolor=C["sub"])

    # 下拉框（语言选择）
    style.configure("TCombobox", foreground=C["text"], padding=(px(8), px(5)))

    init_tree_layout(style)


def init_tree_layout(style):
    """去掉 ttk 自带的展开三角。

    为什么不用它：Tk 8.6 的这个 indicator 是 C 画的，尺寸固定 9px 左右，
    200% 缩放下基本看不清（用户反馈过两次）；`indicatorsize` 选项虽然能设，
    但实测对绘制大小无效；换成自定义 image 元素的话，open/closed 又拿不到
    可用状态（user1 不触发，只有 user2=叶子 有效）。
    所以：布局里删掉 indicator，改用自绘的 PhotoImage 箭头（见 ui/kit.py），
    尺寸按 DPI 算，想多大就多大。
    """
    try:
        style.layout("Treeview.Item", [
            ("Treeitem.padding", {"sticky": "nswe", "children": [
                ("Treeitem.image", {"side": "left", "sticky": ""}),
                ("Treeitem.text", {"side": "left", "sticky": ""}),
            ]}),
        ])
    except Exception:
        pass        # 改不动就退回系统默认三角，不影响功能


def enable_dpi():
    """DPI 感知必须赶在 tk.Tk() 之前设。tkwebui 用 PerMonitorV2（-4），更准。"""
    if sys.platform != "win32":
        return
    if HAS_TKWEBUI:
        try:
            tw_enable_dpi()
            return
        except Exception:
            pass
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
