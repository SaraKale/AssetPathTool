# -*- coding: utf-8 -*-
"""公共控件工厂（mixin）。

所有方法都假设 self 上有：tk / ttk / S / F_* 字体 / _i18n_* 登记表。
这些由 App.__init__ 准备好，mixin 不自己初始化任何东西。
"""
from ..i18n import tr
from ..theme import C, HAS_TKWEBUI, TwSegmented, TwSwitch, tw_set_placeholder


class UiKit:
    """各页面共用的控件。用 mixin 而不是工具函数，是为了少传一堆 self.xxx。"""

    # ---------------------------------------------------------------- 尺寸
    def px(self, v):
        """逻辑像素 → 物理像素（按系统 DPI 缩放）"""
        return int(round(v * self.S))

    # ---------------------------------------------------------------- 卡片
    def card(self, parent, pad=None):
        tk = self.tk
        pad = pad or self.px(14)
        outer = tk.Frame(parent, bg=C["card"], highlightbackground=C["border"],
                         highlightthickness=1, bd=0)
        inner = tk.Frame(outer, bg=C["card"])
        inner.pack(fill="both", expand=True, padx=pad, pady=pad)
        return outer, inner

    def section_title(self, parent, text, hint=""):
        tk = self.tk
        row = tk.Frame(parent, bg=C["card"])
        row.pack(fill="x", pady=(0, self.px(10)))
        tk.Label(row, text=text, bg=C["card"], fg=C["text"],
                 font=self.F_H2).pack(side="left")
        if hint:
            tk.Label(row, text=hint, bg=C["card"], fg=C["hint"],
                     font=self.F_SMALL).pack(side="left", padx=(self.px(10), 0))
        return row

    # ---------------------------------------------------------------- 表单标签
    def form_label(self, parent, text, bg=None, **pack):
        """普通表单标签（项目文件 / 筛选 / 原路径前缀…）。纯黑，不用灰。"""
        lb = self.tk.Label(parent, text=text, bg=bg or C["card"],
                           fg=C["text"], font=self.F_SMALL, anchor="w")
        if pack:
            lb.pack(**pack)
        return lb

    def filter_label(self, parent, text="只看", bg=None, **pack):
        """「只看」这种筛选标题：比普通标签大一号并加粗，一眼能看到。"""
        lb = self.tk.Label(parent, text=text, bg=bg or C["bg"],
                           fg=C["text"], font=self.F_LABEL, anchor="w")
        if pack:
            lb.pack(**pack)
        return lb

    def note_label(self, parent, text, bg=None, **pack):
        """灰色小字说明。项目要求纯黑，所以只是小一号，不再降亮度。"""
        lb = self.tk.Label(parent, text=text, bg=bg or C["card"], fg=C["hint"],
                           font=self.F_SMALL, anchor="w", justify="left")
        if pack:
            lb.pack(**pack)
        return lb

    # ---------------------------------------------------------------- 表格
    # 首列复选框用的字符。用文字而不是图片，是因为 ttk.Treeview 的普通列
    # 只能放字符串（只有 #0 树列能放 image），而 #0 在 headings 模式下是隐藏的。
    CHK_ON = "☑"
    CHK_OFF = "☐"
    CHK_BLANK = ""

    def make_table(self, parent, columns, height=12, empty_text="",
                   tree_mode=False, tree_title="名称", tree_width=380,
                   selectmode="extended", checkable=False, hscroll=True):
        """columns: [(key, 标题, 宽度, 对齐, 是否拉伸)]，返回 (容器, 表格, 空状态文字)

        selectmode 默认 "extended"：支持 Ctrl 点选、Shift 连选。
        checkable=True 时在最前面插一列复选框（列名固定 "chk"）。
        hscroll=False 时不建横向滚动条（列宽够用、不想看到那根灰条的场合）。
        """
        tk, ttk = self.tk, self.ttk
        if checkable:
            columns = [("chk", "", 44, "center", False)] + list(columns)
        wrap = tk.Frame(parent, bg=C["card"], highlightbackground=C["border"],
                        highlightthickness=1, bd=0)
        tree = ttk.Treeview(wrap, columns=[c[0] for c in columns],
                            show=("tree headings" if tree_mode else "headings"),
                            height=height, selectmode=selectmode)
        if tree_mode:
            tree.heading("#0", text=tree_title, anchor="w")
            tree.column("#0", width=self.px(tree_width), minwidth=self.px(120),
                        stretch=True)
            self._i18n_head.append((tree, "#0", tree_title))
        for key, title, width, anchor, stretch in columns:
            is_chk = (key == "chk")
            tree.heading(key, text=title,
                         anchor="center" if is_chk else "w")
            tree.column(key, width=self.px(width),
                        minwidth=self.px(30 if is_chk else 60),
                        anchor=anchor, stretch=stretch)
            if title:
                self._i18n_head.append((tree, key, title))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        if hscroll:
            hsb = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
            tree.configure(xscrollcommand=hsb.set)
            hsb.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        empty = tk.Label(wrap, text=empty_text, bg=C["card"], fg=C["hint"],
                         font=self.F_BODY, justify="center")
        empty.place(relx=0.5, rely=0.5, anchor="center")

        tree.tag_configure("odd", background="#ffffff")
        tree.tag_configure("even", background=C["stripe"])
        tree.tag_configure("bad", foreground=C["bad"])
        tree.tag_configure("muted", foreground=C["muted"])
        tree.tag_configure("good", foreground=C["ok"])
        tree.tag_configure("warn", foreground=C["warn"])
        tree.tag_configure("new", foreground=C["ok"])
        tree.tag_configure("del", foreground=C["bad"])
        tree.tag_configure("chg", foreground=C["warn"])
        return wrap, tree, empty

    # ---------------------------------------------------------------- 首列复选框
    def bind_check_column(self, tree, get_rec, on_change=None):
        """
        让首列复选框可点。

        get_rec(iid) -> 该行对应的记录 dict；勾选状态直接记在 dict 的
        "_chk" 上（重绘表格后状态还在）。返回 None 表示这是分组行
        （比如树形表格里的文件夹）—— 点它就把整组一起勾上 / 取消。

        on_change() 在状态变化后调用，页面用它刷新状态栏。
        """
        on_header = on_change

        def descendants(iid=""):
            out, stack = [], list(tree.get_children(iid))
            while stack:
                cur = stack.pop()
                out.append(cur)
                stack.extend(tree.get_children(cur))
            return out

        def paint(iid):
            rec = get_rec(iid)
            if rec is not None:
                tree.set(iid, "chk", self.CHK_ON if rec.get("_chk") else self.CHK_OFF)

        def click(event):
            if tree.identify_column(event.x) != "#1":
                return None
            if tree.identify_region(event.x, event.y) != "cell":
                return None
            iid = tree.identify_row(event.y)
            if not iid:
                return None
            rec = get_rec(iid)
            if rec is None:
                # 分组行：整组切换
                kids = descendants(iid)
                recs = [r for r in (get_rec(k) for k in kids) if r is not None]
                if not recs:
                    return None
                want = not all(r.get("_chk") for r in recs)
                for r in recs:
                    r["_chk"] = want
                for k in kids:
                    paint(k)
                tree.set(iid, "chk", self.CHK_ON if want else self.CHK_OFF)
            else:
                rec["_chk"] = not rec.get("_chk")
                paint(iid)
            if on_change:
                on_change()
            return "break"      # 别让 Treeview 顺手改掉选中状态

        def toggle_all():
            recs = [r for r in (get_rec(i) for i in descendants()) if r is not None]
            if not recs:
                return
            want = not all(r.get("_chk") for r in recs)
            for r in recs:
                r["_chk"] = want
            for iid in descendants():
                paint(iid)
            if on_header:
                on_header()

        tree.bind("<Button-1>", click, add="+")
        tree.heading("chk", command=toggle_all)

    def checked(self, records):
        """挑出被勾选的记录"""
        return [r for r in records if r.get("_chk")]

    def count_checked(self, records):
        return sum(1 for r in records if r.get("_chk"))

    # ---------------------------------------------------------------- 勾选批量操作
    def check_selected(self, tree, iid_map):
        """把表格里当前选中的行打上勾，返回改动的条数"""
        n = 0
        for iid in tree.selection():
            rec = iid_map.get(iid)
            if rec is not None and not rec.get("_chk"):
                rec["_chk"] = True
                n += 1
        return n

    def check_visible(self, tree, iid_map, value=True):
        """把当前表格里可见（= 筛选后）的行全部打勾 / 取消，返回改动的条数"""
        n = 0
        for iid in iid_map:
            rec = iid_map[iid]
            if rec is None:
                continue
            if bool(rec.get("_chk")) != value:
                rec["_chk"] = value
                n += 1
        return n

    def check_all(self, records, value=True):
        """不筛可见与否，整份记录全部打勾 / 取消。

        「全不选」走这里而不是 check_visible：如果只清可见行，被「只看」
        筛掉的那些勾选会留着，用户以为清空了，「查找缺失…」却还按它们
        在处理 —— 这是最难查的那种「怪行为」。
        """
        n = 0
        for rec in records:
            if rec is None:
                continue
            if bool(rec.get("_chk")) != value:
                rec["_chk"] = value
                n += 1
        return n

    def repaint_checks(self, tree, iid_map):
        """重绘复选框格子（不重建表格）"""
        for iid, rec in iid_map.items():
            if rec is None:
                continue
            try:
                tree.set(iid, "chk", self.CHK_ON if rec.get("_chk") else self.CHK_OFF)
            except Exception:
                pass


    # ---------------------------------------------------------------- 文件行
    def file_row(self, parent, label, var, on_browse, hint=""):
        tk, ttk = self.tk, self.ttk
        row = tk.Frame(parent, bg=C["card"])
        row.pack(fill="x", pady=(0, self.px(10)))
        tk.Label(row, text=label, bg=C["card"], fg=C["text"], font=self.F_BODY,
                 width=8, anchor="w").pack(side="left")
        entry = ttk.Entry(row, textvariable=var, font=self.F_PATH)
        entry.pack(side="left", fill="x", expand=True, padx=(self.px(6), self.px(8)))
        ttk.Button(row, text="浏览…", style="Ghost.TButton",
                   command=on_browse).pack(side="left")
        if hint:
            tk.Label(row, text=hint, bg=C["card"], fg=C["hint"],
                     font=self.F_SMALL).pack(side="left", padx=(self.px(10), 0))
        return entry

    def add_placeholder(self, entry, var, text):
        """
        输入框为空时显示灰色提示。优先用 tkwebui 的 set_placeholder
        （它处理了焦点、只读、销毁等细节），没有这个库时退回自己贴的 Label。
        """
        if HAS_TKWEBUI:
            try:
                ph = tw_set_placeholder(entry, text)
                self._i18n_ph.append((ph, text))
                return ph
            except Exception:
                pass
        tk = self.tk
        ph = tk.Label(entry, text=text, bg="#ffffff", fg=C["placeholder"],
                      font=self.F_SMALL, cursor="xterm")
        ph.bind("<Button-1>", lambda e: entry.focus_set())

        def refresh(*_):
            if var.get().strip():
                ph.place_forget()
            else:
                ph.place(in_=entry, x=self.px(10), rely=0.5, anchor="w")

        var.trace_add("write", refresh)
        refresh()
        return ph

    # ---------------------------------------------------------------- 开关
    def checkbox(self, parent, text, var, bg=None, command=None):
        """
        勾选框。优先用 tkwebui 的 SquareSwitch —— 它是真正的 ttk.Checkbutton，
        指示器是按 DPI 缩放后栅格化的图片，200% 屏上够大，键盘/焦点行为也原生。
        没有这个库时退回原来的 Canvas 自绘版本。
        """
        if HAS_TKWEBUI:
            try:
                holder = self.tk.Frame(parent, bg=bg or C["card"])
                sw = TwSwitch(holder, text=text, variable=var,
                              command=command or (lambda: None),
                              cursor="hand2")
                sw.pack(side="left")
                return holder
            except Exception:
                pass

        tk = self.tk
        bg = bg or C["card"]
        size = self.px(16)

        holder = tk.Frame(parent, bg=bg, cursor="hand2")
        cv = tk.Canvas(holder, width=size, height=size, bg=bg,
                       highlightthickness=0, bd=0, cursor="hand2")
        cv.pack(side="left")
        lb = tk.Label(holder, text=text, bg=bg, fg=C["text"],
                      font=self.F_SMALL, cursor="hand2")
        lb.pack(side="left", padx=(self.px(8), 0))

        def render():
            cv.delete("all")
            if var.get():
                cv.create_rectangle(1, 1, size - 1, size - 1,
                                    fill=C["accent"], outline=C["accent"])
                cv.create_line(size * 0.24, size * 0.52, size * 0.43, size * 0.70,
                               size * 0.77, size * 0.29, fill="#ffffff",
                               width=max(2, self.px(2)),
                               capstyle="round", joinstyle="round")
            else:
                cv.create_rectangle(1, 1, size - 1, size - 1,
                                    fill="#ffffff", outline="#b9c1cc")

        def toggle(_=None):
            var.set(not var.get())
            render()
            if command:
                command()

        for w in (holder, cv, lb):
            w.bind("<Button-1>", toggle)
        render()
        return holder

    # ---------------------------------------------------------------- 分段
    def segmented(self, parent, options, var, command=None, bg=None):
        """
        分段筛选按钮。

        注意 command 的签名：tkwebui 的 SegmentedControl 会以 command(value)
        回调（带一个参数），而下面自绘版是 command()。这里统一包一层，
        让外面永远写 command=self._render_xxx（不带参数）就行 ——
        以前就是这里没包，点「只看」会抛
        "App._render_remap() takes 1 positional argument but 2 were given"。
        """
        cb = None
        if command is not None:
            def cb(*_a, _fn=command):
                _fn()

        if HAS_TKWEBUI:
            try:
                return TwSegmented(parent, [(o, o) for o in options], var,
                                   command=cb)
            except Exception:
                pass

        tk = self.tk
        bg = bg or C["card"]
        holder = tk.Frame(parent, bg=bg, highlightbackground=C["border"],
                          highlightthickness=1, bd=0)
        labels = {}

        def render():
            for opt, lb in labels.items():
                sel = (var.get() == opt)
                lb.configure(bg=C["accent"] if sel else bg,
                             fg="#ffffff" if sel else C["text"])

        def pick(opt):
            var.set(opt)
            render()
            if cb:
                cb()

        for opt in options:
            lb = tk.Label(holder, text=opt, font=self.F_SMALL, bg=bg,
                          fg=C["text"], padx=self.px(13), pady=self.px(6),
                          cursor="hand2")
            lb.pack(side="left")
            lb.bind("<Button-1>", lambda e, o=opt: pick(o))
            labels[opt] = lb

        render()
        # 代码里直接改 var 时也要跟着变（否则筛选状态和按钮高亮会对不上）
        var.trace_add("write", lambda *a: render())
        return holder

    # ---------------------------------------------------------------- 徽章
    def stat_chips(self, parent):
        """统计徽章卡片，返回 (frame, 建徽章函数, 更新函数)"""
        tk = self.tk
        outer = tk.Frame(parent, bg=C["card"], highlightbackground=C["border"],
                         highlightthickness=1, bd=0)
        frame = tk.Frame(outer, bg=C["card"])
        frame.pack(fill="x", padx=self.px(16), pady=self.px(10))
        labels = {}

        def make(key, color):
            box = tk.Frame(frame, bg=C["card"])
            box.pack(side="left", padx=(0, self.px(24)))
            num = tk.Label(box, text="0", bg=C["card"], fg=color,
                           font=(self.FONT_FAMILY, 16, "bold"))
            num.pack(side="left")
            cap = tk.Label(box, text=key, bg=C["card"], fg=C["text"],
                           font=self.F_SMALL)
            cap.pack(side="left", padx=(self.px(5), 0), pady=(self.px(6), 0))
            labels[key] = num

        def update(mapping):
            for k, v in mapping.items():
                if k in labels:
                    labels[k].configure(text=str(v))

        return outer, make, update

    # ---------------------------------------------------------------- 树形箭头
    def init_arrows(self):
        """
        自绘展开/收起箭头。

        为什么不用 ttk 自带的三角：Tk 8.6 那个 indicator 是 C 画的，固定 9px，
        200% 缩放下看不清；`indicatorsize` 实测无效；换自定义 image 元素又拿不到
        open/closed 状态。所以干脆用 PhotoImage 自己画三角形，尺寸跟着 DPI 走，
        用户想多大就多大。
        """
        size = self.px(19)
        gap = self.px(8)
        self._arrow_size = size
        self._arrow_hit = size + gap
        self._arrow_open = self._triangle(size, gap, point_down=True)
        self._arrow_closed = self._triangle(size, gap, point_down=False)

    def _triangle(self, size, gap, point_down):
        """画一个实心三角。左侧 size×size 是三角形，右边 gap 留白当间距。"""
        tk = self.tk
        w, h = size + gap, size
        img = tk.PhotoImage(width=w, height=h)
        pad = max(1, round(size * 0.14))
        span = max(2, size - 2 * pad)
        cx = size // 2
        color = C["arrow"]
        for i in range(span):
            # frac: 0 = 最宽那条边，1 = 顶点
            frac = i / max(1, span - 1)
            half = max(1, round(span * (1 - frac) / 2))
            if point_down:
                y = pad + i                       # 上宽下尖
                x0, x1 = max(0, cx - half), min(size, cx + half + 1)
                img.put(color, to=(x0, y, x1, y + 1))
            else:
                x = pad + i                       # 左宽右尖
                y0, y1 = max(0, cx - half), min(h, cx + half + 1)
                img.put(color, to=(x, y0, x + 1, y1))
        return img

    @staticmethod
    def folder_name(iid):
        """文件夹节点的显示名（iid 形如 F:一级/二级）"""
        return iid[2:].split("/")[-1] if iid.startswith("F:") else iid

    def arrow_for(self, is_open):
        return self._arrow_open if is_open else self._arrow_closed

    def set_folder_node(self, tree, iid, is_open):
        """同步文件夹节点的箭头方向和展开状态"""
        tree.item(iid, open=is_open, image=self.arrow_for(is_open))

    def is_folder_node(self, tree, iid):
        return bool(iid) and tree.tag_has("folder", iid)

    # ---------------------------------------------------------------- 小工具
    def _msg(self, kind, text, parent=None):
        """统一走这里，标题永远带当前语言的 App 名。"""
        fn = getattr(self.messagebox, kind)
        title = tr(self.APP_TITLE)
        if parent is None:
            fn(title, text)
        else:
            fn(title, text, parent=parent)

    def show_info(self, text, parent=None):
        self._msg("showinfo", text, parent)

    def show_warn(self, text, parent=None):
        self._msg("showwarning", text, parent)

    def show_error(self, text, parent=None):
        self._msg("showerror", text, parent)

