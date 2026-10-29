# -*- coding: utf-8 -*-
"""主窗口：骨架、头部、状态栏、语言切换、后台任务调度。

四个页面的具体内容在 page_*.py 里，用 mixin 拼进来 —— 这样 App 只剩
「窗口怎么长」和「活儿怎么派」，不用一口气读两千行。
"""
import os
import queue
import threading
import traceback

from .. import i18n
from ..appinfo import APP_TITLE, APP_VER
from ..i18n import (I18N_KEYS, LANGS, NAMES, load_lang, save_lang, tr)
from ..platform_utils import (WIN, WindowsDropTarget, ctypes, detect_dpi,
                              wintypes)
from ..theme import (C, FONT_FAMILY, HAS_TKWEBUI, TwCombobox,
                     apply_tkwebui_theme, init_styles)
from ..core.loader import is_project_file
from .finder import FinderMixin
from .kit import UiKit
from .page_diff import DiffPageMixin
from .page_extract import ExtractPageMixin
from .page_remap import RemapPageMixin
from .page_usage import UsagePageMixin
from .update_win import UpdateMixin


class App(FinderMixin, ExtractPageMixin, DiffPageMixin, RemapPageMixin,
          UsagePageMixin, UpdateMixin, UiKit):
    def __init__(self, root_win):
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        import tkinter.font as tkfont

        self.APP_TITLE = APP_TITLE
        self.FONT_FAMILY = FONT_FAMILY

        # 语言：有配置用配置，没有就跟随系统
        i18n.set_current(load_lang())

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.root = root_win

        # ---------- DPI 缩放（解决高分辨率屏上字小、行距挤 ----------
        dpi = detect_dpi()
        self.S = max(1.0, round(dpi / 96.0, 3))
        root_win.tk.call("tk", "scaling", dpi / 72.0)

        # 全局默认字体
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                f = tkfont.nametofont(name)
                f.configure(family=FONT_FAMILY, size=10)
            except Exception:
                pass

        self.F_TITLE = (FONT_FAMILY, 15, "bold") # 标题字体
        self.F_SUB = (FONT_FAMILY, 9) # 子标题字体
        self.F_H2 = (FONT_FAMILY, 10, "bold") # 二级标题字体
        self.F_BODY = (FONT_FAMILY, 10) # 正文字体
        self.F_SMALL = (FONT_FAMILY, 9) # 小号字体
        # 「只看」这类筛选标题：大一号 + 加粗
        self.F_LABEL = (FONT_FAMILY, 11, "bold") # 筛选标题字体
        # 路径栏统一用和正文一样的字体（等宽字体在中文路径下混排很难看）
        self.F_PATH = (FONT_FAMILY, 10)
        self.ROW_H = self.px(27) # 行高

        root_win.title(f"{tr(APP_TITLE)} v{APP_VER}") # 窗口标题
        root_win.geometry(f"{self.px(1000)}x{self.px(680)}") # 初始窗口大小
        root_win.minsize(self.px(800), self.px(440)) # 最小窗口大小
        root_win.configure(bg=C["bg"]) # 背景颜色

        # ---------- 多语言登记表 ----------
        self._i18n_text = []        # [(widget, 中文原文)]
        self._i18n_head = []        # [(Treeview, 列, 中文原文)]
        self._i18n_tab = []         # [(Notebook, page, 中文原文)]
        self._i18n_menu = []        # [(Menu, 索引, 中文原文)]
        self._i18n_ph = []          # [(tkwebui Placeholder, 中文原文)]
        self._i18n_title = []       # [(Toplevel, 中文原文)]，弹窗标题

        # tkwebui 主题要先装好，后面 init_styles 只在它上面加变体
        self.style = ttk.Style(root_win)
        apply_tkwebui_theme(root_win, self.style)
        init_styles(root_win, self.style, self.px, {
            "body": self.F_BODY, "h2": self.F_H2, "small": self.F_SMALL,
        }, self.ROW_H)
        self.init_arrows()

        self._build_header()

        self.drop_entries = []      # [(Entry, StringVar)]，拖放目标
        self.drop = None

        self.nb = ttk.Notebook(root_win)
        self.nb.pack(fill="both", expand=True, padx=self.px(18), pady=(0, self.px(6)))

        self.page_extract = ttk.Frame(self.nb)
        self.page_diff = ttk.Frame(self.nb)
        self.page_remap = ttk.Frame(self.nb)
        self.page_usage = ttk.Frame(self.nb)
        for page, key in ((self.page_extract, "  ① 提取路径  "),
                          (self.page_diff, "  ② 对比项目  "),
                          (self.page_remap, "  ③ 路径重定向  "),
                          (self.page_usage, "  ④ 素材使用  ")):
            self.nb.add(page, text=key)
            self._i18n_tab.append((self.nb, page, key))

        self._build_footer()

        self.status_var = self.tk.StringVar(value="就绪")
        self.status_label.configure(textvariable=self.status_var)

        self._build_page_extract()
        self._build_page_diff()
        self._build_page_remap()
        self._build_page_usage()

        # 界面建完再统一登记 + 翻译一次
        self._collect_i18n()
        self._apply_i18n()

        # 拖放要在窗口真正建好之后再挂，失败就重试几次
        self.root.after(120, self._setup_drop)

    # ==================================================
    # 多语言
    # ==================================================
    def _collect_i18n(self, subtree=None):
        """把界面上带文案的控件登记下来（中文原文当 key，不用改创建代码）"""
        ttk = self.ttk
        seen = set()

        def add(w, kind, extra, orig):
            key = (id(w), kind, extra)
            if key in seen:
                return
            seen.add(key)
            if kind == "text":
                self._i18n_text.append((w, orig))
            elif kind == "head":
                self._i18n_head.append((w, extra, orig))

        def visit(w):
            for c in w.winfo_children():
                # 带 textvariable 的控件文字是动态的，别登记（会顶掉绑定）
                try:
                    has_var = bool(c.cget("textvariable"))
                except Exception:
                    has_var = False
                if not has_var:
                    try:
                        v = c.cget("text")
                    except Exception:
                        v = None
                    if isinstance(v, str) and v in I18N_KEYS:
                        add(c, "text", None, v)
                if isinstance(c, ttk.Treeview):
                    try:
                        cols = c["columns"]
                    except Exception:
                        cols = ()
                    for col in (["#0"] + list(cols)) if c["show"] != "headings" else list(cols):
                        try:
                            h = c.heading(col, "text")
                        except Exception:
                            continue
                        if h in I18N_KEYS:
                            add(c, "head", col, h)
                visit(c)

        visit(subtree or self.root)

    def _apply_i18n(self):
        """按当前语言刷新所有已登记的文案"""
        for w, orig in list(self._i18n_text):
            try:
                if w.winfo_exists():
                    w.configure(text=tr(orig))
            except Exception:
                pass
        for tree, col, orig in list(self._i18n_head):
            try:
                if tree.winfo_exists():
                    tree.heading(col, text=tr(orig))
            except Exception:
                pass
        for nb, page, orig in list(self._i18n_tab):
            try:
                if nb.winfo_exists():
                    nb.tab(page, text=tr(orig))
            except Exception:
                pass
        for menu, idx, orig in list(self._i18n_menu):
            try:
                menu.entryconfigure(idx, label=tr(orig))
            except Exception:
                pass
        for ph, orig in list(self._i18n_ph):
            try:
                ph.set_text(tr(orig))
            except Exception:
                pass
        for win, orig in list(self._i18n_title):
            try:
                if win.winfo_exists():
                    win.title(tr(orig))
            except Exception:
                pass
        try:
            self.status_var.set(tr("就绪"))
            self.root.title(f"{tr(APP_TITLE)} v{APP_VER}")
        except Exception:
            pass

    def set_language(self, lang):
        """切语言：只换文案，不重建窗口，路径和数据都还在"""
        if lang not in dict(LANGS) or lang == i18n.LANG:
            return
        i18n.set_current(lang)
        save_lang(lang)
        try:
            self.v_lang.set(NAMES[lang])
        except Exception:
            pass
        self._apply_i18n()
        # 「检查更新」窗口里的文案是建窗时定死的，切语言后没法整体重刷，
        # 直接关掉让用户重点一次 —— 比留一窗中英混排干净
        upd = getattr(self, "_upd_win", None)
        if upd is not None:
            try:
                upd.destroy()
            except Exception:
                pass
            self._upd_win = None
        # 表格里的单元格 / 空状态文字是现算的，重绘一遍即可。
        # 注意顺序：把「当前可见页」放到最后，否则状态栏会停在其他页的
        # 统计结果上（四个 _render_* 都会写 status_var）。
        fns = [self._render_extract, self._render_diff,
               self._render_remap, self._render_usage]
        try:
            active = self.nb.index(self.nb.select())
        except Exception:
            active = 0
        for i in [n for n in range(len(fns)) if n != active] + [active]:
            try:
                fns[i]()
            except Exception:
                pass
        # 查找缺失窗口：底部提示是动态文本，表格里也有「手动指定」这种要翻译的
        # 单元格（其余列是文件名 / 目录，不翻译），所以顺手重铺一遍
        try:
            f = self._finder
            if f["win"].winfo_exists():
                f["label"].configure(text="")
                if not f["busy"]["busy"] and f["busy"]["last"]:
                    f["refill"]()
        except Exception:
            pass

    def _on_lang_pick(self, *_):
        """下拉框选中语言。tkwebui 会带一个 value 参数，自绘版不带，统一兼容。"""
        name = self.v_lang.get()
        for code, native in LANGS:
            if native == name:
                self.set_language(code)
                return

    # ==================================================
    # 头部 / 底部
    # ==================================================
    def _build_header(self):
        tk = self.tk
        head = tk.Frame(self.root, bg=C["bg"])
        head.pack(fill="x", padx=self.px(18), pady=(self.px(14), self.px(10)))

        # 语言选择放右边，先 pack 右侧的，左边标题才能吃掉剩余宽度
        right = tk.Frame(head, bg=C["bg"])
        right.pack(side="right", anchor="e")
        self.form_label(right, "语言", bg=C["bg"]).pack(
            side="left", padx=(0, self.px(8)))

        self.v_lang = tk.StringVar(value=NAMES[i18n.LANG])
        self._lang_ctl = self._make_lang_combo(right)
        self._lang_ctl.pack(side="left")

        # 版本号 + 「检查更新」：版本号取自 appinfo.APP_VER，和标题栏永远一致
        tk.Label(right, text="v" + APP_VER, bg=C["bg"], fg=C["hint"],
                 font=self.F_SMALL).pack(side="left",
                                         padx=(self.px(16), self.px(8)))
        self.btn_update = self.ttk.Button(right, text="检查更新",
                                          style="Ghost.TButton",
                                          command=self.check_update)
        self.btn_update.pack(side="left")

        left = tk.Frame(head, bg=C["bg"])
        left.pack(side="left")
        tk.Label(left, text=APP_TITLE, bg=C["bg"], fg=C["text"],
                 font=self.F_TITLE).pack(anchor="w")
        tk.Label(left,
                 text="提取 · 对比 · 重定向 · 使用统计　"
                      "Premiere Pro / After Effects / Audition 项目素材路径",
                 bg=C["bg"], fg=C["hint"], font=self.F_SUB).pack(
            anchor="w", pady=(self.px(3), 0))

    def _make_lang_combo(self, parent):
        """语言下拉框。值用语言代码，显示用各自的自称（不翻译）。"""
        names = [n for _, n in LANGS]
        if HAS_TKWEBUI and TwCombobox is not None:
            try:
                cb = TwCombobox(parent, textvariable=self.v_lang, values=names,
                                state="readonly", width=10, font=self.F_BODY)
                cb.bind("<<ComboboxSelected>>", self._on_lang_pick)
                return cb
            except Exception:
                pass
        cb = self.ttk.Combobox(parent, textvariable=self.v_lang, values=names,
                               state="readonly", width=10, font=self.F_BODY)
        cb.bind("<<ComboboxSelected>>", self._on_lang_pick)
        return cb

    def _build_footer(self):
        tk = self.tk
        bar = tk.Frame(self.root, bg=C["bg"])
        bar.pack(fill="x", side="bottom")
        tk.Frame(bar, bg=C["line"], height=1).pack(fill="x")
        wrap = tk.Frame(bar, bg=C["bg"])
        wrap.pack(fill="x", padx=self.px(18), pady=self.px(7))
        self.status_label = tk.Label(wrap, text="就绪", bg=C["bg"], fg=C["sub"],
                                     font=self.F_SMALL, anchor="w")
        self.status_label.pack(side="left")

    # ==================================================
    # 文件拖放
    # ==================================================
    def _setup_drop(self, retry=0):
        if self.drop is not None and self.drop.ok:
            return
        try:
            self.drop = WindowsDropTarget(self.root, self._on_files_dropped)
        except Exception:
            self.drop = None
        if (self.drop is None or not self.drop.ok) and retry < 5:
            self.root.after(250, lambda: self._setup_drop(retry + 1))

    def _var_at_cursor(self):
        """拖放时鼠标落在哪个输入框上，就填哪个"""
        if not WIN:
            return None
        try:
            pt = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        except Exception:
            return None
        for entry, var in self.drop_entries:
            try:
                # 隐藏页的控件坐标和当前页是重叠的，必须跳过
                if not entry.winfo_ismapped():
                    continue
                x, y = entry.winfo_rootx(), entry.winfo_rooty()
                w, h = entry.winfo_width(), entry.winfo_height()
            except Exception:
                continue
            if x <= pt.x <= x + w and y <= pt.y <= y + h:
                return var
        return None

    def _on_files_dropped(self, paths):
        dirs = [p for p in paths if os.path.isdir(p)]
        projects = [p for p in paths if is_project_file(p)]

        # 拖进来的是文件夹 → 交给「查找缺失」的搜索目录
        if dirs and not projects:
            self._handle_dir_drop(dirs)
            return
        if not projects:
            self.status_var.set(tr("拖入的不是项目文件，已忽略"))
            return

        page = self.nb.index(self.nb.select())
        hit = self._var_at_cursor()

        # 对比页一次拖两个文件：自动分给 A（旧）和 B（新）
        if len(projects) >= 2 and page == 1 and hit is None:
            self.v_diff_a.set(projects[0])
            self.v_diff_b.set(projects[1])
            self.status_var.set(tr("已载入对比文件：A = {}，B = {}　点「开始对比」").format(
                os.path.basename(projects[0]), os.path.basename(projects[1])))
            return

        targets = (self.v_ext_src, self.v_diff_b, self.v_rm_src, self.v_usage_src)
        var = hit or targets[min(page, len(targets) - 1)]
        var.set(projects[0])
        self.status_var.set(tr("已载入：{}　点上方按钮开始").format(
            os.path.basename(projects[0])))

    def _handle_dir_drop(self, dirs):
        """拖进来的是文件夹 —— 本工具里只有「查找缺失」有搜索目录"""
        finder = getattr(self, "_finder", None)
        win = finder.get("win") if finder else None
        alive = False
        if win is not None:
            try:
                alive = bool(win.winfo_exists())
            except Exception:
                alive = False
        if not alive:
            self.status_var.set(
                tr("拖入的是文件夹。搜索目录在「查找缺失…」窗口里 —— "
                   "先打开它，再把文件夹拖到那个窗口上。"))
            return
        path = os.path.normpath(dirs[0])
        finder["dir"].set(path)
        try:
            win.deiconify()
            win.lift()
            win.focus_set()
        except Exception:
            pass
        try:
            finder["label"].configure(
                text=tr("已拖入搜索目录：{}　点「开始扫描」").format(path))
        except Exception:
            pass
        self.status_var.set(tr("已把文件夹填进搜索目录"))

    # ==================================================
    # 通用任务执行（后台线程 + 进度）
    # ==================================================
    def _run_task(self, work, on_done, busy_msg, buttons):
        for b in buttons:
            b.configure(state="disabled")
        self.status_var.set(busy_msg)

        q = queue.Queue()

        def runner():
            try:
                work(q)
            except Exception as ex:
                q.put(("err", f"{ex}\n\n{traceback.format_exc()}"))

        threading.Thread(target=runner, daemon=True).start()

        def poll():
            try:
                while True:
                    kind, payload = q.get_nowait()
                    if kind == "msg":
                        self.status_var.set(payload)
                    elif kind == "done":
                        for b in buttons:
                            b.configure(state="normal")
                        on_done(payload)
                        return
                    elif kind == "err":
                        for b in buttons:
                            b.configure(state="normal")
                        self.status_var.set(tr("操作失败"))
                        self.show_error(payload)
                        return
            except queue.Empty:
                pass
            self.root.after(120, poll)

        self.root.after(120, poll)
