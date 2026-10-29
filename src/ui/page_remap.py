# -*- coding: utf-8 -*-
"""页面③：路径重定向（前缀规则 + 逐条指定 + 改写工程）。

规则不再常驻页面，收进「规则表…」弹窗 —— 主页面只留和「素材使用」一样的
三段式：项目文件 → 统计徽章 / 只看 → 表格。
"""
import csv
import os
import subprocess

from ..i18n import tr
from ..theme import C
from ..core.loader import can_rewrite, extract_any, project_kind, rewrite_project
from ..core.prproj import write_txt
from ..core.remap import recompute_remap, remap_records


class RemapPageMixin:
    # ==================================================
    # 页面骨架
    # ==================================================
    def _build_page_remap(self):
        tk, ttk = self.tk, self.ttk
        page = self.page_remap

        # ---------- 顶部：项目文件 + 操作 ----------
        top, top_in = self.card(page)
        top.pack(fill="x", padx=self.px(2), pady=(self.px(12), self.px(10)))

        self.v_rm_src = tk.StringVar()
        self.rm_entry = self.file_row(top_in, "项目文件", self.v_rm_src,
                                      lambda: self._pick_into(self.v_rm_src))
        self.add_placeholder(self.rm_entry, self.v_rm_src,
                             "拖入 .prproj / .aep / .sesx，或点「浏览…」")
        self.drop_entries.append((self.rm_entry, self.v_rm_src))

        bar = tk.Frame(top_in, bg=C["card"])
        bar.pack(fill="x")

        self.btn_remap = ttk.Button(bar, text="加载全部", style="Primary.TButton",
                                    command=self.do_load_remap)
        self.btn_remap.pack(side="left")

        self.btn_rm_rules = ttk.Button(bar, text="规则表…", style="Ghost.TButton",
                                       command=self._open_rules)
        self.btn_rm_rules.pack(side="left", padx=(self.px(8), 0))

        self.btn_rm_apply = ttk.Button(bar, text="应用规则", style="Ghost.TButton",
                                       command=self.do_apply_rules, state="disabled")
        self.btn_rm_apply.pack(side="left", padx=(self.px(8), 0))

        self.btn_rm_reset = ttk.Button(bar, text="清空手动指定", style="Ghost.TButton",
                                       command=self.do_clear_manual, state="disabled")
        self.btn_rm_reset.pack(side="left", padx=(self.px(8), 0))

        self.btn_rm_find = ttk.Button(bar, text="查找缺失…", style="Ghost.TButton",
                                      command=self._open_finder, state="disabled")
        self.btn_rm_find.pack(side="left", padx=(self.px(8), 0))

        self.btn_rm_csv = ttk.Button(bar, text="导出 CSV", style="Ghost.TButton",
                                     command=self._export_remap_csv, state="disabled")
        self.btn_rm_csv.pack(side="right")
        self.btn_rm_txt = ttk.Button(bar, text="导出清单", style="Ghost.TButton",
                                     command=self._export_remap_txt, state="disabled")
        self.btn_rm_txt.pack(side="right", padx=(0, self.px(8)))
        # 改写工程单独给个按钮：以前只能先「导出清单」再靠规则表里的开关顺带写出，
        # 想直接拿一份改好的 .prproj 得绕两圈
        self.btn_rm_prproj = ttk.Button(bar, text="导出新文件", style="Ghost.TButton",
                                        command=self._export_remap_prproj,
                                        state="disabled")
        self.btn_rm_prproj.pack(side="right", padx=(0, self.px(8)))

        # ---------- 中部：徽章 / 筛选 / 表格 ----------
        mid = tk.Frame(page, bg=C["bg"])
        mid.pack(fill="both", expand=True, padx=self.px(2), pady=(0, self.px(12)))

        chips_box, make, self._rm_chip_update = self.stat_chips(mid)
        chips_box.pack(fill="x", pady=(0, self.px(8)))
        make("命中改写", C["text"])
        make("新路径存在", C["ok"])
        make("新路径缺失", C["bad"])

        filt = tk.Frame(mid, bg=C["bg"])
        filt.pack(fill="x", pady=(0, self.px(10)))
        self.filter_label(filt, "只看").pack(side="left", padx=(0, self.px(10)))
        self.v_rm_filter = tk.StringVar(value="全部")
        self.segmented(filt, ["全部", "已改写", "缺失", "存在"], self.v_rm_filter,
                       command=self._render_remap).pack(side="left")

        # 勾选相关的批量按钮（pack 顺序反过来才是从左到右）
        ttk.Button(filt, text="全不选", style="Ghost.TButton",
                   command=lambda: self._check_visible(False)).pack(side="right")
        ttk.Button(filt, text="全选", style="Ghost.TButton",
                   command=lambda: self._check_visible(True)).pack(
            side="right", padx=(0, self.px(6)))
        ttk.Button(filt, text="勾选", style="Ghost.TButton",
                   command=self._check_selected).pack(
            side="right", padx=(0, self.px(6)))

        self.rm_wrap, self.rm_tree, self.rm_empty = self.make_table(mid, [
            ("folder", "项目文件夹", 165, "w", False),
            ("name", "素材名", 210, "w", False),
            ("old", "原路径", 240, "w", True),
            ("new", "新路径", 240, "w", True),
            ("state", "状态", 90, "center", False),
        ], checkable=True,
            empty_text="点「加载全部」先列出所有素材\n\n"
                       "然后双击任意一行，选择该素材的新位置")
        self.rm_wrap.pack(fill="both", expand=True)
        self.rm_tree.bind("<Double-1>", self._edit_remap_row)

        self._rm_menu_rec = None
        self.rm_menu = tk.Menu(page, tearoff=0)
        self.rm_menu.add_command(label="选择新位置…", command=self._menu_pick)
        self.rm_menu.add_command(label="清除手动指定", command=self._menu_clear)
        self.rm_menu.add_separator()
        self.rm_menu.add_command(label="在资源管理器中定位", command=self._menu_reveal)
        # 菜单项要单独登记：切语言时按「索引」改 label，不能用中文当键，
        # 因为 entryconfigure 用文字查找时，翻译过的菜单就找不到了。
        for idx, key in ((0, "选择新位置…"), (1, "清除手动指定"),
                         (3, "在资源管理器中定位")):
            self._i18n_menu.append((self.rm_menu, idx, key))
        self.rm_tree.bind("<Button-3>", self._rm_context)

        self.rm_records = []
        self.rm_iid = {}        # iid -> record
        self.rules = []
        self.bind_check_column(self.rm_tree, lambda iid: self.rm_iid.get(iid),
                               on_change=self._rm_check_changed)
        # 改写开关放在「规则表」弹窗里，但变量本身常驻，导出时要用
        self.v_rm_rewrite = tk.BooleanVar(value=False)
        self._rules_win = None

    def _rm_check_changed(self):
        n = self.count_checked(self.rm_records)
        if n:
            self.status_var.set(
                tr("已勾选 {} 条素材　「查找缺失…」只处理勾选的行").format(n))
        else:
            self.status_var.set(tr("已取消全部勾选"))

    def _check_selected(self):
        """把表格里选中的行打上勾"""
        if not self.rm_tree.selection():
            self.status_var.set(tr("先在表格里选中要勾选的行（Ctrl / Shift 可多选）"))
            return
        self.check_selected(self.rm_tree, self.rm_iid)
        self.repaint_checks(self.rm_tree, self.rm_iid)
        self._rm_check_changed()

    def _check_visible(self, value):
        """全选只勾当前可见（筛选后）的行；全不选清掉全部行。

        两者故意不对称：全选是「把看到的都选上」，全不选是「一个都别剩」。
        如果全不选也只清可见行，被「只看」筛掉的勾选会残留，用户以为清空了，
        「查找缺失…」却还按残留的勾选在处理。
        """
        if value:
            self.check_visible(self.rm_tree, self.rm_iid, True)
        else:
            self.check_all(self.rm_records, False)
        self.repaint_checks(self.rm_tree, self.rm_iid)
        self._rm_check_changed()

    # ==================================================
    # 规则表弹窗
    # ==================================================
    def _open_rules(self):
        """规则单独开窗：主页面能腾出空间给表格，规则也不用天天看见"""
        if self._rules_win is not None:
            try:
                if self._rules_win.winfo_exists():
                    self._rules_win.deiconify()
                    self._rules_win.lift()
                    self._rules_win.focus_set()
                    return
            except Exception:
                pass
        self._build_rules_window()

    def _build_rules_window(self):
        tk, ttk = self.tk, self.ttk
        win = tk.Toplevel(self.root)
        win.title(tr("重定向规则表"))
        win.configure(bg=C["bg"])
        win.geometry(f"{self.px(760)}x{self.px(500)}")
        win.minsize(self.px(620), self.px(420))
        win.transient(self.root)

        card, body = self.card(win)
        card.pack(fill="both", expand=True, padx=self.px(14), pady=self.px(14))

        self.section_title(body, "重定向规则", "从上到下匹配，命中第一条生效")

        # 前缀输入：两列并排，比上下堆两行省一半高度
        grid = tk.Frame(body, bg=C["card"])
        grid.pack(fill="x", pady=(0, self.px(10)))
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(3, weight=1)

        self.v_rm_old = tk.StringVar()
        self.v_rm_new = tk.StringVar()
        self.form_label(grid, "原路径前缀", bg=C["card"]).grid(
            row=0, column=0, sticky="w", padx=(0, self.px(6)))
        ttk.Entry(grid, textvariable=self.v_rm_old, font=self.F_PATH).grid(
            row=0, column=1, sticky="ew", padx=(0, self.px(16)))
        self.form_label(grid, "新路径前缀", bg=C["card"]).grid(
            row=0, column=2, sticky="w", padx=(0, self.px(6)))
        ttk.Entry(grid, textvariable=self.v_rm_new, font=self.F_PATH).grid(
            row=0, column=3, sticky="ew")

        btns = tk.Frame(body, bg=C["card"])
        btns.pack(fill="x", pady=(0, self.px(10)))
        ttk.Button(btns, text="+ 添加规则", style="Ghost.TButton",
                   command=self._add_rule).pack(side="left")
        ttk.Button(btns, text="删除选中", style="Ghost.TButton",
                   command=self._del_rule).pack(side="left", padx=(self.px(6), 0))
        ttk.Button(btns, text="清空", style="Ghost.TButton",
                   command=self._clear_rules).pack(side="left", padx=(self.px(6), 0))
        ttk.Button(btns, text="上移", style="Ghost.TButton",
                   command=lambda: self._move_rule(-1)).pack(side="left",
                                                             padx=(self.px(16), 0))
        ttk.Button(btns, text="下移", style="Ghost.TButton",
                   command=lambda: self._move_rule(1)).pack(side="left",
                                                            padx=(self.px(6), 0))

        # 底部固定区先 pack，中间的规则表吃掉剩余高度
        foot = tk.Frame(body, bg=C["card"])
        foot.pack(side="bottom", fill="x", pady=(self.px(12), 0))
        tk.Frame(foot, bg=C["line"], height=1).pack(fill="x", pady=(0, self.px(12)))

        self.checkbox(foot, "同时另存改写后的工程文件（不覆盖原文件）",
                      self.v_rm_rewrite).pack(anchor="w")
        self.note_label(foot,
                        "建议先在 PR 里验证清单无误再改写，改写前请备份项目。",
                        bg=C["card"]).pack(anchor="w", pady=(self.px(6), 0))

        act = tk.Frame(foot, bg=C["card"])
        act.pack(fill="x", pady=(self.px(12), 0))
        ttk.Button(act, text="关闭", style="Ghost.TButton",
                   command=win.withdraw).pack(side="right")
        ttk.Button(act, text="应用规则", style="Primary.TButton",
                   command=self.do_apply_rules).pack(side="right",
                                                     padx=(0, self.px(8)))

        self.rule_wrap, self.rule_tree, self.rule_empty = self.make_table(body, [
            ("old", "原前缀", 300, "w", True),
            ("new", "新前缀", 300, "w", True),
        ], height=6, hscroll=False,
            empty_text="还没有规则\n\n填好上面两项后点「+ 添加规则」")
        self.rule_wrap.pack(fill="both", expand=True, pady=(0, self.px(2)))

        # 弹窗是建完主界面之后才出现的，得单独登记一遍再翻译
        self._i18n_title.append((win, "重定向规则表"))
        prev = self.status_var.get()
        self._collect_i18n(win)
        self._apply_i18n()
        self.status_var.set(prev)

        win.bind("<Escape>", lambda e: win.withdraw())
        self._rules_win = win
        self._refresh_rules()

    # ---------------------------------------------------------------- 规则增删
    def _add_rule(self):
        old = self.v_rm_old.get().strip()
        new = self.v_rm_new.get().strip()
        if not old:
            self.show_warn(tr("请填写「原路径前缀」"))
            return
        self.rules.append((old, new))
        self._refresh_rules()
        self.v_rm_old.set("")
        self.v_rm_new.set("")

    def _del_rule(self):
        sel = self.rule_tree.selection()
        if not sel:
            return
        idxs = sorted((self.rule_tree.index(i) for i in sel), reverse=True)
        for idx in idxs:
            if 0 <= idx < len(self.rules):
                del self.rules[idx]
        self._refresh_rules()

    def _move_rule(self, delta):
        sel = self.rule_tree.selection()
        if len(sel) != 1:
            return
        i = self.rule_tree.index(sel[0])
        j = i + delta
        if not (0 <= i < len(self.rules) and 0 <= j < len(self.rules)):
            return
        self.rules[i], self.rules[j] = self.rules[j], self.rules[i]
        self._refresh_rules()
        iid = self.rule_tree.get_children()[j]
        self.rule_tree.selection_set(iid)
        self.rule_tree.focus(iid)

    def _clear_rules(self):
        self.rules = []
        self._refresh_rules()

    def _refresh_rules(self):
        t = getattr(self, "rule_tree", None)
        if t is None:
            return
        try:
            if not t.winfo_exists():
                return
            t.delete(*t.get_children())
            for i, (old, new) in enumerate(self.rules):
                t.insert("", "end", tags=("even" if i % 2 else "odd",),
                         values=(old, new))
            if self.rules:
                self.rule_empty.place_forget()
            else:
                self.rule_empty.place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass

    # ---------------------------------------------------------------- 逐条指定
    def _edit_remap_row(self, event):
        """双击某行 → 弹出文件选择，单独指定这条素材的新位置"""
        iid = self.rm_tree.identify_row(event.y)
        rec = self.rm_iid.get(iid)
        if rec is not None:
            self._pick_new_for(rec)

    def _rm_context(self, event):
        iid = self.rm_tree.identify_row(event.y)
        rec = self.rm_iid.get(iid)
        if rec is None:
            return
        self.rm_tree.selection_set(iid)
        self.rm_tree.focus(iid)
        self._rm_menu_rec = rec
        # 用索引 1 而不是中文 label —— 界面可能已经被翻成别的语言
        self.rm_menu.entryconfigure(
            1, state="normal" if rec["manual"] else "disabled")
        try:
            self.rm_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.rm_menu.grab_release()

    def _menu_pick(self):
        if self._rm_menu_rec is not None:
            self._pick_new_for(self._rm_menu_rec)

    def _menu_clear(self):
        rec = self._rm_menu_rec
        if rec is None:
            return
        rec["manual"] = ""
        recompute_remap([rec], list(self.rules))
        self._render_remap()
        self._select_rec(rec)
        self.status_var.set(tr("已清除手动指定：{}").format(rec["name"]))

    def _menu_reveal(self):
        rec = self._rm_menu_rec
        if rec is None:
            return
        p = rec["manual"] or rec["path"] or rec["old_path"]
        if p and os.path.exists(p):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
        else:
            self.show_info(tr("这条路径现在不存在，无法定位。"))

    def _pick_new_for(self, rec):
        """弹文件选择，把结果记成这条素材的手动指定。返回选中的路径（取消返回 ""）。

        返回路径是给「查找缺失」弹窗用的 —— 它得知道自己这张表该改成什么。
        """
        cur = rec["manual"] or rec["old_path"]
        init_dir = os.path.dirname(cur) if cur else None
        init_name = os.path.basename(cur) if cur else None
        path = self.filedialog.askopenfilename(
            title=tr("选择「{}」的新位置").format(rec["name"]),
            initialdir=init_dir or None, initialfile=init_name or None,
            filetypes=[(tr("所有文件"), "*.*")])
        if not path:
            return ""
        rec["manual"] = path
        recompute_remap([rec], [])
        self._render_remap()
        self._select_rec(rec)
        if rec["exists"]:
            self.status_var.set(tr("已指定：{} → {}").format(rec["name"], path))
        else:
            self.status_var.set(
                tr("已指定：{} → {}（该文件当前不存在，请确认）").format(rec["name"], path))
        return path

    def _select_rec(self, rec):
        """重绘后把光标放回刚操作的那一行，免得滚动条跳回顶部"""
        for iid, r in self.rm_iid.items():
            if r is rec:
                self.rm_tree.selection_set(iid)
                self.rm_tree.focus(iid)
                self.rm_tree.see(iid)
                return

    # ==================================================
    # 主流程
    # ==================================================
    def do_load_remap(self):
        """只读项目，把所有素材路径列出来（不套规则）"""
        src = self.v_rm_src.get().strip().strip('"')
        if not src or not os.path.isfile(src):
            self.show_warn(tr("请先选择项目文件"))
            return

        def work(q):
            q.put(("msg", tr("读取项目…")))
            recs = extract_any(src, progress=lambda m: q.put(("msg", m)))
            q.put(("done", recs))

        self._run_task(work=work, on_done=self._remap_done,
                       busy_msg=tr("正在读取素材路径…"), buttons=[self.btn_remap])

    def do_apply_rules(self):
        """把规则批量套到未手动指定的行上"""
        if not self.rm_records:
            self.show_info(tr("请先点「加载全部」"))
            return
        if not self.rules:
            self.show_info(tr("请先在「规则表」里添加至少一条规则"))
            return
        recompute_remap(self.rm_records, list(self.rules))
        self._render_remap()
        manual = sum(1 for r in self.rm_records if r["manual"])
        self.status_var.set(
            tr("已套用 {} 条规则").format(len(self.rules))
            + (tr("（{} 条手动指定保持不变）").format(manual) if manual else ""))

    def do_clear_manual(self):
        """一次性撤销所有逐条指定的新位置，回到纯规则状态"""
        n = sum(1 for r in self.rm_records if r["manual"])
        if not n:
            self.status_var.set(tr("没有手动指定的条目"))
            return
        # 这个按钮以前叫「清空指定」，容易被当成「清空勾选」，误点一次就白改。
        # 改成明确的名字 + 先问一句。
        if not self.messagebox.askyesno(
                tr(self.APP_TITLE),
                tr("要清除 {} 条手动指定的新位置吗？\n\n"
                   "清除后这些行会重新按规则计算（没有规则就回到原路径）。\n"
                   "「勾选」和「只看」的筛选不受影响。").format(n),
                parent=self.root):
            return
        for r in self.rm_records:
            r["manual"] = ""
        recompute_remap(self.rm_records, list(self.rules))
        self._render_remap()
        self.status_var.set(tr("已清除 {} 条手动指定").format(n))

    def _remap_done(self, records):
        self.rm_records = remap_records(records)
        if self.rules:
            recompute_remap(self.rm_records, list(self.rules))
        for b in (self.btn_rm_txt, self.btn_rm_csv, self.btn_rm_apply,
                  self.btn_rm_reset, self.btn_rm_find, self.btn_rm_prproj):
            b.configure(state="normal")
        self._render_remap()
        self.status_var.set(
            tr("已加载 {} 条路径　双击任意一行可单独指定新位置").format(len(self.rm_records)))

    def _render_remap(self):
        t = self.rm_tree
        t.delete(*t.get_children())
        self.rm_iid = {}
        want = self.v_rm_filter.get()

        shown = 0
        # 手动指定的排最前，其次是被规则改写的，最后是没动过的
        ordered = sorted(self.rm_records,
                         key=lambda r: (not r["changed"], not r["manual"],
                                        not r["path"], r["folder"], r["name"]))
        for r in ordered:
            has = bool(r["path"])
            if want == "已改写" and not r["changed"]:
                continue
            if want == "缺失" and not (has and not r["exists"]):
                continue
            if want == "存在" and not (has and r["exists"]):
                continue

            if not has:
                state, tags = tr("无路径"), ("muted",)
            elif r["exists"]:
                state, tags = tr("存在"), ()
            else:
                state, tags = tr("缺失"), ("bad",)
            if r["changed"]:
                tags = tags + ("chg",)
            tags = (("even" if shown % 2 else "odd"),) + tags
            chk = self.CHK_ON if r.get("_chk") else self.CHK_OFF
            iid = t.insert("", "end", tags=tags,
                           values=(chk, r["folder"], r["name"], r["old_path"],
                                   r["path"], state))
            self.rm_iid[iid] = r
            shown += 1

        changed = sum(1 for r in self.rm_records if r["changed"])
        found = sum(1 for r in self.rm_records if r["changed"] and r["exists"])
        missing = sum(1 for r in self.rm_records
                      if r["path"] and not r["exists"])
        self._rm_chip_update({"命中改写": changed, "新路径存在": found,
                              "新路径缺失": missing})
        if shown:
            self.rm_empty.place_forget()
        else:
            self.rm_empty.configure(
                text=tr("没有符合条件的条目") if self.rm_records else
                tr("点「加载全部」先列出所有素材\n\n"
                   "然后双击任意一行，选择该素材的新位置"))
            self.rm_empty.place(relx=0.5, rely=0.5, anchor="center")
        if self.rm_records:
            scope = "" if want == "全部" else tr("（筛选：{}）").format(tr(want))
            self.status_var.set(
                tr("共 {} 条，已改写 {} 条，路径缺失 {} 条{}　当前显示 {} 行").format(
                    len(self.rm_records), changed, missing, scope, shown))

    # ==================================================
    # 导出
    # ==================================================
    def _export_remap_txt(self):
        if not self.rm_records:
            return
        src = self.v_rm_src.get().strip()
        out = self.filedialog.asksaveasfilename(
            title=tr("保存新清单"), defaultextension=".txt",
            initialfile=os.path.splitext(os.path.basename(src))[0] + "_重定向.txt",
            initialdir=os.path.dirname(src) or None,
            filetypes=[(tr("文本文件"), "*.txt")])
        if not out:
            return
        write_txt(self.rm_records, out)
        self.status_var.set(tr("已导出：{}").format(out))

        if self.v_rm_rewrite.get():
            self._do_rewrite(src)

    def _export_remap_csv(self):
        if not self.rm_records:
            return
        src = self.v_rm_src.get().strip()
        out = self.filedialog.asksaveasfilename(
            title=tr("保存 CSV"), defaultextension=".csv",
            initialfile=os.path.splitext(os.path.basename(src))[0] + "_重定向.csv",
            initialdir=os.path.dirname(src) or None,
            filetypes=[(tr("CSV 文件"), "*.csv")])
        if not out:
            return
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow([tr("项目文件夹"), tr("素材名"), tr("原路径"), tr("新路径"),
                        tr("改动来源"), tr("新路径是否存在")])
            for r in self.rm_records:
                src_kind = tr("手动指定") if r["manual"] else (
                    tr("规则") if r["changed"] else tr("未改"))
                w.writerow([r["folder"], r["name"], r["old_path"], r["path"],
                            src_kind, tr("是") if r["exists"] else tr("否")])
        self.status_var.set(tr("已导出：{}").format(out))

    def _do_rewrite(self, src, dst=None):
        """把改写结果另存出来。dst 为空时按「原名_重定向.<原后缀>」自己起名。"""
        kind = project_kind(src)
        if not can_rewrite(src):
            self.show_info(tr("AE 工程暂不支持改写（改写只适用于 .prproj / .sesx）"))
            return
        if dst is None:
            ext = ".sesx" if kind == "sesx" else ".prproj"
            dst = os.path.splitext(src)[0] + "_重定向" + ext
        # 「绝不覆盖原文件」是这个工具的承诺，用户手选了原路径也得拦住
        if os.path.normcase(os.path.abspath(dst)) == os.path.normcase(os.path.abspath(src)):
            self.show_warn(tr("不能覆盖原工程文件。\n\n请换一个文件名（比如加「_重定向」后缀）。"))
            return
        # 逐条手动指定的路径走精确映射；其余仍按前缀规则兜底
        mapping = {r["old_path"]: r["path"] for r in self.rm_records
                   if r["changed"] and r["old_path"] and r["path"]}
        try:
            n = rewrite_project(src, dst, list(self.rules), mapping=mapping)
        except Exception as ex:
            self.show_error(tr("改写失败：{}").format(ex))
            return
        manual = sum(1 for r in self.rm_records if r["manual"] and r["changed"])
        self.status_var.set(tr("已导出：{}").format(dst))
        head = (tr("已另存改写后的 Audition 会话（原文件未改动）：\n{}")
                if kind == "sesx" else
                tr("已另存改写后的项目（原文件未改动）：\n{}"))
        tail = (tr("。\n\n建议先在 Audition 里打开它确认素材都在线，再决定是否替换原会话。")
                if kind == "sesx" else
                tr("。\n\n建议先在 Premiere 里打开它确认素材都在线，再决定是否替换原项目。"))
        self.show_info(
            head.format(dst) + "\n\n"
            + tr("共改写 {} 条路径{}").format(
                n,
                tr("，其中 {} 条来自你手动指定的位置。").format(manual) if manual else "")
            + tail)

    def _export_remap_prproj(self):
        """「导出新文件」：直接另存一份改写后的工程，不用先导出清单"""
        if not self.rm_records:
            return
        src = self.v_rm_src.get().strip().strip('"')
        kind = project_kind(src)
        if not can_rewrite(src):
            self._do_rewrite(src)          # 复用里面的 .aep 提示
            return
        if kind == "sesx":
            ext, label = ".sesx", tr("Audition 会话")
        else:
            ext, label = ".prproj", tr("Premiere 项目")
        dst = self.filedialog.asksaveasfilename(
            title=tr("保存改写后的项目"), defaultextension=ext,
            initialfile=os.path.splitext(os.path.basename(src))[0] + "_重定向" + ext,
            initialdir=os.path.dirname(src) or None,
            filetypes=[(label, "*" + ext)])
        if not dst:
            return
        self._do_rewrite(src, dst)
