# -*- coding: utf-8 -*-
"""页面①：提取素材路径（树形折叠 + 筛选 + 导出）。"""
import os
from collections import defaultdict

from ..i18n import tr
from ..theme import C
from ..core.loader import PROJECT_FILETYPES, extract_any
from ..core.prproj import summarize, write_csv, write_txt


class ExtractPageMixin:
    def _build_page_extract(self):
        tk, ttk = self.tk, self.ttk
        page = self.page_extract
        page.configure(style="TFrame")

        top, top_in = self.card(page)
        top.pack(fill="x", padx=self.px(2), pady=(self.px(12), self.px(10)))

        self.v_ext_src = tk.StringVar()
        self.ext_entry = self.file_row(top_in, "项目文件", self.v_ext_src,
                                       self._pick_extract)
        self.add_placeholder(self.ext_entry, self.v_ext_src,
                             "把 .prproj / .aep / .sesx 拖到这里，或点「浏览…」")
        self.drop_entries.append((self.ext_entry, self.v_ext_src))

        bar = tk.Frame(top_in, bg=C["card"])
        bar.pack(fill="x")

        self.btn_extract = ttk.Button(bar, text="开始提取", style="Primary.TButton",
                                      command=self.do_extract)
        self.btn_extract.pack(side="left")

        self.form_label(bar, "筛选", bg=C["card"]).pack(
            side="left", padx=(self.px(18), self.px(6)))
        self.v_ext_filter = tk.StringVar()
        ttk.Entry(bar, textvariable=self.v_ext_filter, width=22,
                  font=self.F_SMALL).pack(side="left")
        self.v_ext_filter.trace_add("write", lambda *a: self._render_extract())

        self.v_ext_missing = tk.BooleanVar(value=False)
        self.checkbox(bar, "只看缺失素材", self.v_ext_missing,
                      command=self._render_extract).pack(side="left",
                                                         padx=(self.px(16), 0))

        self.btn_ext_txt = ttk.Button(bar, text="导出 TXT", style="Ghost.TButton",
                                      command=self._export_extract_txt, state="disabled")
        self.btn_ext_txt.pack(side="right")
        self.btn_ext_csv = ttk.Button(bar, text="导出 CSV", style="Ghost.TButton",
                                      command=self._export_extract_csv, state="disabled")
        self.btn_ext_csv.pack(side="right", padx=(0, self.px(8)))

        mid = tk.Frame(page, bg=C["bg"])
        mid.pack(fill="both", expand=True, padx=self.px(2), pady=(0, self.px(12)))

        # 统计徽章 + 树形展开按钮同一行：按钮紧挨着它控制的那棵树，且足够大
        rowbox = tk.Frame(mid, bg=C["bg"])
        rowbox.pack(fill="x", pady=(0, self.px(10)))

        chips_box, self._ext_chip_make, self._ext_chip_update = self.stat_chips(rowbox)
        chips_box.pack(side="left")
        self._ext_chip_make("素材条目", C["text"])
        self._ext_chip_make("有路径", C["ok"])
        self._ext_chip_make("硬盘缺失", C["bad"])
        self._ext_chip_make("文件夹", C["text"])

        tools = tk.Frame(rowbox, bg=C["bg"])
        tools.pack(side="right")
        ttk.Button(tools, text="▾  展开全部", style="Tool.TButton",
                   command=lambda: self._toggle_all(True)).pack(side="left")
        ttk.Button(tools, text="▸  收起全部", style="Tool.TButton",
                   command=lambda: self._toggle_all(False)).pack(
            side="left", padx=(self.px(8), 0))

        self.ext_wrap, self.ext_tree, self.ext_empty = self.make_table(mid, [
            ("path", "硬盘路径", 560, "w", True),
            ("state", "状态", 80, "center", False),
        ], tree_mode=True, tree_title="项目文件夹 / 素材名", tree_width=380,
            empty_text="选择项目文件后点「开始提取」\n\n"
                       "支持 .prproj（无需手动解压）、.aep（After Effects）、"
                       ".sesx（Audition）和已解压的 .xml")
        self.ext_wrap.pack(fill="both", expand=True)
        # 文件夹节点加粗 + 淡蓝底 + 更大的字号
        self.ext_tree.tag_configure("folder", font=(self.FONT_FAMILY, 11, "bold"),
                                    foreground="#243b63", background="#eef3fb")
        # 展开/收起后同步箭头方向；单击箭头区域也能切换
        self.ext_tree.bind("<<TreeviewOpen>>", self._on_tree_toggle)
        self.ext_tree.bind("<<TreeviewClose>>", self._on_tree_toggle)
        self.ext_tree.bind("<Button-1>", self._on_tree_click, add="+")

        # 树形表格没法把复选框做成独立的第一列（#0 树列永远在最左边），
        # 所以把方框画进素材名的文字里：☐ 名字。这里量一下方框占多宽，
        # 点在这个范围内就当作点了复选框。
        import tkinter.font as tkfont
        self._chk_w = tkfont.Font(font=self.F_BODY).measure(self.CHK_OFF + " ") + self.px(2)

        self.ext_records = []
        self.ext_iid = {}
        self.ext_loaded = False     # 区分「还没提取」和「提取了但 0 条」

    def _ext_check_changed(self):
        n = self.count_checked(self.ext_records)
        self.status_var.set(tr("已勾选 {} 条素材").format(n) if n
                            else tr("已取消全部勾选"))

    def _pick_extract(self):
        p = self.filedialog.askopenfilename(
            title=tr("选择项目文件"),
            filetypes=[(tr("项目 / XML / AE / AU 工程"), PROJECT_FILETYPES),
                       ("Premiere 项目", "*.prproj"),
                       ("After Effects 工程", "*.aep *.aepx"),
                       ("Audition 会话", "*.sesx"),
                       ("XML 文件", "*.xml"),
                       (tr("所有文件"), "*.*")])
        if p:
            self.v_ext_src.set(p)

    def do_extract(self):
        src = self.v_ext_src.get().strip().strip('"')
        if not src or not os.path.isfile(src):
            self.show_warn(tr("请先选择一个存在的项目文件（.prproj / .aep / .sesx / .xml）"))
            return
        self._run_task(
            work=lambda q: q.put(("done", extract_any(
                src, progress=lambda m: q.put(("msg", m))))),
            on_done=self._extract_done,
            busy_msg=tr("正在解析项目，大项目需要十几秒…"),
            buttons=[self.btn_extract])

    def _extract_done(self, records):
        self.ext_records = records
        self.ext_loaded = True
        self.btn_ext_txt.configure(state="normal")
        self.btn_ext_csv.configure(state="normal")
        self._render_extract()
        if not records:
            self.status_var.set(tr("这个工程里没找到素材路径"))
            self.show_info(tr("没有从这个工程里找到素材路径。\n\n"
                              "可能的原因：\n"
                              "· 工程里没有引用任何外部素材\n"
                              "· 文件格式不是本工具支持的（.prproj / .aep / .sesx / .xml）\n"
                              "· 文件损坏或被加密"))

    def _render_extract(self):
        t = self.ext_tree
        t.delete(*t.get_children())
        self.ext_iid = {}
        kw = self.v_ext_filter.get().strip().lower()
        only_bad = self.v_ext_missing.get()

        # 有源文件的排前面，序列/调整图层这类没有路径的沉底
        ordered = sorted(self.ext_records,
                         key=lambda r: (not r["path"], r["folder"], r["name"]))

        nodes = {}
        visible = defaultdict(int)
        expand_all = bool(kw) or only_bad
        shown = 0

        def ensure_folders(folder):
            """按层级把文件夹节点建出来，返回最末一级的 iid"""
            parent_iid, acc, depth = "", "", 0
            for part in folder.split("/"):
                acc = f"{acc}/{part}" if acc else part
                iid = nodes.get(acc)
                if iid is None:
                    is_open = (depth == 0 or expand_all)
                    iid = t.insert(parent_iid, "end", iid="F:" + acc,
                                   text=self.folder_name("F:" + acc),
                                   image=self.arrow_for(is_open),
                                   values=("", ""), tags=("folder",),
                                   open=is_open)
                    nodes[acc] = iid
                visible[acc] += 1
                parent_iid = iid
                depth += 1
            return parent_iid

        for r in ordered:
            if only_bad and (not r["path"] or r["exists"]):
                continue
            if kw and kw not in r["folder"].lower() and kw not in r["name"].lower() \
                    and kw not in r["path"].lower():
                continue

            if not r["path"]:
                state, tags = tr("无路径"), ("muted",)
            elif r["exists"]:
                state, tags = tr("正常"), ()          # 正常是常态，不抢视觉
            else:
                state, tags = tr("缺失"), ("bad",)    # 只有异常才上色

            parent = ensure_folders(r["folder"] or tr("（未分类）"))
            tags = (("even" if shown % 2 else "odd"),) + tags
            chk = self.CHK_ON if r.get("_chk") else self.CHK_OFF
            iid = t.insert(parent, "end", text=f"{chk} {r['name']}",
                           values=(r["path"], state), tags=tags)
            self.ext_iid[iid] = r
            shown += 1

        for acc, iid in nodes.items():
            t.item(iid, values=("", tr("{} 项").format(visible[acc])))

        s = summarize(self.ext_records)
        self._ext_chip_update({"素材条目": s["total"], "有路径": s["with_path"],
                               "硬盘缺失": s["missing"], "文件夹": s["folders"]})
        if shown:
            self.ext_empty.place_forget()
        else:
            self.ext_empty.configure(
                text=tr("没有符合条件的素材") if self.ext_records else
                tr("选择项目文件后点「开始提取」\n\n"
                   "支持 .prproj（无需手动解压）、.aep（After Effects）、"
                   ".sesx（Audition）和已解压的 .xml"))
            self.ext_empty.place(relx=0.5, rely=0.5, anchor="center")
        if self.ext_records:
            self.status_var.set(
                tr("提取完成：共 {} 条素材，当前显示 {} 行").format(s["total"], shown))

    def _on_tree_toggle(self, event=None):
        """展开/收起后把箭头方向同步过来"""
        t = self.ext_tree
        iid = t.focus()
        if self.is_folder_node(t, iid):
            self.set_folder_node(t, iid, bool(t.item(iid, "open")))

    def _on_tree_click(self, event):
        """单击 #0 列：文件夹的箭头区域 → 展开/收起；素材行的方框 → 勾选"""
        t = self.ext_tree
        if t.identify_column(event.x) != "#0":
            return
        iid = t.identify_row(event.y)
        if not iid:
            return
        bbox = t.bbox(iid, "#0")
        if not bbox:
            return
        if self.is_folder_node(t, iid):
            if event.x <= bbox[0] + self._arrow_hit + self.px(4):
                self.set_folder_node(t, iid, not bool(t.item(iid, "open")))
                t.focus(iid)
            return
        # 素材行：点最前面的 ☐ 就切换勾选（点名字照常选中）
        rec = self.ext_iid.get(iid)
        if rec is None or event.x > bbox[0] + self._chk_w:
            return
        rec["_chk"] = not rec.get("_chk")
        t.item(iid, text=f"{self.CHK_ON if rec['_chk'] else self.CHK_OFF} {rec['name']}")
        self._ext_check_changed()

    def _toggle_all(self, open_=True):
        """展开 / 收起所有文件夹节点（素材行不动）"""
        t = self.ext_tree
        stack = list(t.get_children(""))
        n = 0
        while stack:
            iid = stack.pop()
            if self.is_folder_node(t, iid):
                self.set_folder_node(t, iid, open_)
                n += 1
                stack.extend(t.get_children(iid))
        if n:
            self.status_var.set(
                (tr("已展开 {} 个文件夹") if open_ else tr("已收起 {} 个文件夹")).format(n))

    def _export_extract_txt(self):
        if not self.ext_records:
            return
        src = self.v_ext_src.get().strip()
        default = os.path.splitext(os.path.basename(src))[0] + "_素材路径.txt"
        out = self.filedialog.asksaveasfilename(
            title=tr("保存为 TXT"), defaultextension=".txt", initialfile=default,
            initialdir=os.path.dirname(src) or None,
            filetypes=[(tr("文本文件"), "*.txt")])
        if not out:
            return
        write_txt(self.ext_records, out)
        self.status_var.set(tr("已导出：{}").format(out))
        self.show_info(tr("已导出：\n{}").format(out))

    def _export_extract_csv(self):
        if not self.ext_records:
            return
        src = self.v_ext_src.get().strip()
        default = os.path.splitext(os.path.basename(src))[0] + "_素材路径.csv"
        out = self.filedialog.asksaveasfilename(
            title=tr("保存为 CSV"), defaultextension=".csv", initialfile=default,
            initialdir=os.path.dirname(src) or None,
            filetypes=[(tr("CSV 文件"), "*.csv")])
        if not out:
            return
        write_csv(self.ext_records, out)
        self.status_var.set(tr("已导出：{}").format(out))
        self.show_info(tr("已导出：\n{}").format(out))
