# -*- coding: utf-8 -*-
"""页面②：对比两个项目（A 旧 / B 新）。"""
import os

from ..i18n import tr
from ..theme import C
from ..core.diff import (DIFF_KINDS, build_diff_txt, compare_records,
                         path_mapping, suggest_rules, write_diff_csv)
from ..core.loader import PROJECT_FILETYPES, extract_any
from ..core.remap import path_key, recompute_remap


class DiffPageMixin:
    def _build_page_diff(self):
        tk, ttk = self.tk, self.ttk
        page = self.page_diff

        top, top_in = self.card(page)
        top.pack(fill="x", padx=self.px(2), pady=(self.px(12), self.px(10)))

        self.v_diff_a = tk.StringVar()
        self.v_diff_b = tk.StringVar()
        self.diff_a_entry = self.file_row(top_in, "A（旧）", self.v_diff_a,
                                          lambda: self._pick_into(self.v_diff_a))
        self.diff_b_entry = self.file_row(top_in, "B（新）", self.v_diff_b,
                                          lambda: self._pick_into(self.v_diff_b))
        self.add_placeholder(self.diff_a_entry, self.v_diff_a,
                             "拖入旧版本 .prproj / .aep，或点「浏览…」")
        self.add_placeholder(self.diff_b_entry, self.v_diff_b,
                             "拖入新版本 .prproj / .aep，或点「浏览…」")
        self.drop_entries.append((self.diff_a_entry, self.v_diff_a))
        self.drop_entries.append((self.diff_b_entry, self.v_diff_b))

        bar = tk.Frame(top_in, bg=C["card"])
        bar.pack(fill="x")
        self.btn_diff = ttk.Button(bar, text="开始对比", style="Primary.TButton",
                                   command=self.do_diff)
        self.btn_diff.pack(side="left")

        self.v_diff_all = tk.BooleanVar(value=False)
        self.checkbox(bar, "包含序列/调整图层等无源文件条目",
                      self.v_diff_all).pack(side="left", padx=(self.px(18), 0))

        self.btn_diff_csv = ttk.Button(bar, text="导出 CSV", style="Ghost.TButton",
                                       command=self._export_diff_csv, state="disabled")
        self.btn_diff_csv.pack(side="right")
        self.btn_diff_txt = ttk.Button(bar, text="导出报告", style="Ghost.TButton",
                                       command=self._export_diff_txt, state="disabled")
        self.btn_diff_txt.pack(side="right", padx=(0, self.px(8)))
        # 对比出来的「路径变化」直接喂给重定向页：以前得自己看报告抄旧前缀/新前缀
        self.btn_diff_fill = ttk.Button(bar, text="填到重定向表", style="Ghost.TButton",
                                        command=self.do_fill_remap, state="disabled")
        self.btn_diff_fill.pack(side="right", padx=(0, self.px(8)))
        self.v_diff_rules = tk.BooleanVar(value=False)
        self.checkbox(bar, "同时提炼前缀规则", self.v_diff_rules).pack(
            side="right", padx=(0, self.px(12)))

        mid = tk.Frame(page, bg=C["bg"])
        mid.pack(fill="both", expand=True, padx=self.px(2), pady=(0, self.px(12)))

        chips_box, make, self._diff_chip_update = self.stat_chips(mid)
        chips_box.pack(fill="x", pady=(0, self.px(8)))
        make("新增", C["ok"])
        make("删除", C["bad"])
        make("路径变化", C["warn"])
        make("位置变化", C["warn"])
        make("未变", "#5a626d")

        filt = tk.Frame(mid, bg=C["bg"])
        filt.pack(fill="x", pady=(0, self.px(10)))
        self.filter_label(filt, "只看").pack(side="left", padx=(0, self.px(10)))
        self.v_diff_filter = tk.StringVar(value="全部")
        self.segmented(filt, ("全部",) + DIFF_KINDS, self.v_diff_filter,
                       command=self._render_diff).pack(side="left")

        self.diff_wrap, self.diff_tree, self.diff_empty = self.make_table(mid, [
            ("type", "变化", 80, "center", False),
            ("folder", "项目文件夹", 170, "w", False),
            ("name", "素材名", 200, "w", False),
            ("a_path", "A（旧）路径", 310, "w", True),
            ("b_path", "B（新）路径", 310, "w", True),
        ], checkable=True,
            empty_text="选两个项目文件（A 旧 / B 新）后点「开始对比」\n\n"
                      "建议用同一个项目不同时期的两个 .prproj，或项目与自动保存副本")
        self.diff_wrap.pack(fill="both", expand=True)

        self.diff_rows = []
        self.diff_stats = {}
        self.diff_names = ("", "")
        self.diff_iid = {}
        self.bind_check_column(self.diff_tree, lambda iid: self.diff_iid.get(iid),
                               on_change=self._diff_check_changed)

    def _diff_check_changed(self):
        n = self.count_checked(self.diff_rows)
        self.status_var.set(tr("已勾选 {} 条素材").format(n) if n
                            else tr("已取消全部勾选"))

    def _pick_into(self, var):
        p = self.filedialog.askopenfilename(
            title=tr("选择项目文件"),
            filetypes=[(tr("项目 / XML / AE / AU 工程"), PROJECT_FILETYPES),
                       (tr("所有文件"), "*.*")])
        if p:
            var.set(p)

    def do_diff(self):
        fa = self.v_diff_a.get().strip().strip('"')
        fb = self.v_diff_b.get().strip().strip('"')
        if not (fa and fb and os.path.isfile(fa) and os.path.isfile(fb)):
            self.show_warn(tr("请选择两个都存在项目文件（A 旧 / B 新）"))
            return

        # Tk 变量必须在主线程读；工作线程里碰 StringVar/BooleanVar 会报
        # "main thread is not in main loop"，所以先取出来再丢给线程。
        ignore_no_path = not self.v_diff_all.get()

        def work(q):
            q.put(("msg", tr("读取 A…")))
            ra = extract_any(fa)
            q.put(("msg", tr("读取 B…")))
            rb = extract_any(fb)
            q.put(("msg", tr("对比中…")))
            q.put(("done", (compare_records(ra, rb, ignore_no_path=ignore_no_path),
                            (fa, fb))))

        self._run_task(work=work, on_done=self._diff_done,
                       busy_msg=tr("正在对比两个项目…"), buttons=[self.btn_diff])

    def _diff_done(self, payload):
        (rows, stats), (fa, fb) = payload
        self.diff_rows = rows
        self.diff_stats = stats
        self.diff_names = (os.path.basename(fa), os.path.basename(fb))
        self.btn_diff_txt.configure(state="normal")
        self.btn_diff_csv.configure(state="normal")
        self.btn_diff_fill.configure(
            state="normal" if any(r["type"] == "路径变化" for r in rows) else "disabled")
        self._render_diff()

    def _render_diff(self):
        t = self.diff_tree
        t.delete(*t.get_children())
        self.diff_iid = {}
        want = self.v_diff_filter.get()
        tag_of = {"新增": "new", "删除": "del",
                  "路径变化": "chg", "位置变化": "chg", "未变": "muted"}

        shown = 0
        for r in self.diff_rows:
            if want != "全部" and r["type"] != want:
                continue
            tags = (("even" if shown % 2 else "odd"), tag_of.get(r["type"], "muted"))
            a_txt = r["a_path"] or ("—" if r["type"] == "新增" else tr("(无源文件)"))
            b_txt = r["b_path"] or ("—" if r["type"] == "删除" else tr("(无源文件)"))
            chk = self.CHK_ON if r.get("_chk") else self.CHK_OFF
            iid = t.insert("", "end", tags=tags,
                           values=(chk, tr(r["type"]), r["folder"] or tr("(根目录)"),
                                   r["name"], a_txt, b_txt))
            self.diff_iid[iid] = r
            shown += 1

        self._diff_chip_update({k: self.diff_stats.get(k, 0) for k in DIFF_KINDS})
        if shown:
            self.diff_empty.place_forget()
        else:
            self.diff_empty.configure(
                text=tr("没有符合条件的变化") if self.diff_rows else
                tr("选两个项目文件（A 旧 / B 新）后点「开始对比」\n\n"
                   "建议用同一个项目不同时期的两个 .prproj，或项目与自动保存副本"))
            self.diff_empty.place(relx=0.5, rely=0.5, anchor="center")
        if self.diff_rows:
            self.status_var.set(
                tr("对比完成：A={}，B={}，当前显示 {} 行").format(
                    self.diff_names[0], self.diff_names[1], shown))

    def _export_diff_txt(self):
        if not self.diff_rows:
            return
        out = self.filedialog.asksaveasfilename(
            title=tr("保存对比报告"), defaultextension=".txt",
            initialfile=os.path.splitext(self.diff_names[1])[0] + "_对比结果.txt",
            filetypes=[(tr("文本文件"), "*.txt")])
        if not out:
            return
        with open(out, "w", encoding="utf-8-sig") as f:
            f.write(build_diff_txt(self.diff_rows, self.diff_stats,
                                   self.diff_names[0], self.diff_names[1]))
        self.status_var.set(tr("已导出：{}").format(out))
        self.show_info(tr("已导出：\n{}").format(out))

    def _export_diff_csv(self):
        if not self.diff_rows:
            return
        out = self.filedialog.asksaveasfilename(
            title=tr("保存对比 CSV"), defaultextension=".csv",
            initialfile=os.path.splitext(self.diff_names[1])[0] + "_对比结果.csv",
            filetypes=[(tr("CSV 文件"), "*.csv")])
        if not out:
            return
        write_diff_csv(self.diff_rows, out)
        self.status_var.set(tr("已导出：{}").format(out))
        self.show_info(tr("已导出：\n{}").format(out))

    # ==================================================
    # 对比 → 重定向 联动
    # ==================================================
    def do_fill_remap(self):
        """把对比出的「路径变化」填进重定向页。

        两件事：
          ① 逐条精确指定 —— A 里的每个旧路径配上 B 里的新路径，100% 准确；
          ② 可选：顺带提炼成前缀规则，留给以后新增的素材用。
        """
        if not self.diff_rows:
            self.show_info(tr("先点「开始对比」"))
            return
        mapping = path_mapping(self.diff_rows)
        if not mapping:
            self.show_info(tr("这次对比里没有「路径变化」的条目，没什么可填的。\n\n"
                              "如果只是新增或删除了素材，重定向页用不上。"))
            return

        fa = self.v_diff_a.get().strip().strip('"')

        # 重定向页还没加载任何项目 → 把 A（旧项目）填进去，让用户先加载
        if not self.rm_records:
            self.v_rm_src.set(fa)
            self.nb.select(self.page_remap)
            self.status_var.set(
                tr("已把 A（旧项目）填进重定向页　点「加载全部」，再回来点一次「填到重定向表」"))
            self.show_info(tr("已把 A（旧项目）填进重定向页。\n\n"
                              "先点「加载全部」把素材列出来，再回来点一次「填到重定向表」，"
                              "就会把这 {} 条新路径逐条填进去。").format(len(mapping)))
            return

        # 重定向页加载的必须是 A（旧项目），否则路径对不上
        cur = self.v_rm_src.get().strip().strip('"')
        if cur and os.path.normcase(os.path.abspath(cur)) != \
                os.path.normcase(os.path.abspath(fa)):
            if not self.messagebox.askyesno(
                    tr(self.APP_TITLE),
                    tr("重定向页现在加载的是：\n{}\n\n对比的 A（旧项目）是：\n{}\n\n"
                       "两边不是同一个项目，路径可能对不上。仍要按 A 的路径填吗？").format(
                           os.path.basename(cur), os.path.basename(fa)),
                    parent=self.root):
                return

        lut = {path_key(a): b for a, b in mapping.items()}
        targets = []
        for r in self.rm_records:
            new = lut.get(path_key(r["old_path"]))
            if new and path_key(new) != path_key(r["old_path"]):
                targets.append((r, new))
        if not targets:
            self.show_info(tr("重定向表里没有和这些旧路径对得上的条目。\n\n"
                              "多半是加载的项目不是对比里的 A（旧项目）。"))
            return

        # 已有手动指定会被覆盖 —— 那是用户一条条点出来的，必须先问
        had = sum(1 for r, _ in targets if r["manual"])
        if had and not self.messagebox.askyesno(
                tr(self.APP_TITLE),
                tr("其中 {} 条已经有手动指定的新位置，会被这次对比的结果覆盖。\n\n继续吗？").format(had),
                parent=self.root):
            return

        for r, new in targets:
            r["manual"] = new
        recompute_remap(self.rm_records, list(self.rules))

        added = 0
        if self.v_diff_rules.get():
            sug = suggest_rules(self.diff_rows)
            for rule in sug["rules"]:
                if rule not in self.rules:
                    self.rules.append(rule)
                    added += 1
            if added:
                self._refresh_rules()

        self._render_remap()
        self.nb.select(self.page_remap)
        msg = tr("已按对比结果指定 {} 条新路径").format(len(targets))
        if added:
            msg += tr("，另添加了 {} 条前缀规则").format(added)
        self.status_var.set(msg)
        self.show_info(
            tr("已按对比结果填好 {} 条新路径。").format(len(targets))
            + (tr("\n\n另外把这次变化提炼成 {} 条前缀规则，放在「规则表…」里，"
                  "以后新增的素材也能自动套用。").format(added) if added else "")
            + tr("\n\n检查无误后，在重定向页点「导出新文件」生成改写后的工程。"))
