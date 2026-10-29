# -*- coding: utf-8 -*-
"""页面④：素材使用统计（时间线分析）。"""
import os

from ..i18n import tr
from ..theme import C
from ..core.fsinfo import fmt_size
from ..core.loader import can_usage, project_kind
from ..core.prproj import extract, load_root
from ..core.usage import (analyze_usage, fmt_duration, group_usage,
                          summarize_usage, write_group_csv, write_usage_csv)


class UsagePageMixin:
    def _build_page_usage(self):
        tk, ttk = self.tk, self.ttk
        page = self.page_usage

        top, top_in = self.card(page)
        top.pack(fill="x", padx=self.px(2), pady=(self.px(12), self.px(10)))

        self.v_usage_src = tk.StringVar()
        self.usage_entry = self.file_row(top_in, "项目文件", self.v_usage_src,
                                         lambda: self._pick_into(self.v_usage_src))
        self.add_placeholder(self.usage_entry, self.v_usage_src,
                             "把 .prproj 拖到这里，或点「浏览…」")
        self.drop_entries.append((self.usage_entry, self.v_usage_src))

        bar = tk.Frame(top_in, bg=C["card"])
        bar.pack(fill="x")
        self.btn_usage = ttk.Button(bar, text="开始统计", style="Primary.TButton",
                                    command=self.do_usage)
        self.btn_usage.pack(side="left")

        self.btn_usage_csv = ttk.Button(bar, text="导出 CSV", style="Ghost.TButton",
                                        command=self._export_usage_csv,
                                        state="disabled")
        self.btn_usage_csv.pack(side="right")

        mid = tk.Frame(page, bg=C["bg"])
        mid.pack(fill="both", expand=True, padx=self.px(2), pady=(0, self.px(12)))

        chips_box, make, self._usage_chip_update = self.stat_chips(mid)
        chips_box.pack(fill="x", pady=(0, self.px(8)))
        make("素材总数", C["text"])
        make("已使用", C["ok"])
        make("从未使用", C["bad"])
        make("序列数", C["text"])
        make("时间线总时长", C["text"])

        filt = tk.Frame(mid, bg=C["bg"])
        filt.pack(fill="x", pady=(0, self.px(10)))
        self.filter_label(filt, "只看").pack(side="left", padx=(0, self.px(10)))
        self.v_usage_filter = tk.StringVar(value="全部")
        self._usage_filter_seg = self.segmented(
            filt, ("全部", "从未使用", "已使用"), self.v_usage_filter,
            command=self._render_usage)
        self._usage_filter_seg.pack(side="left")
        self.note_label(filt, "按使用次数升序排列，没用过的排最前",
                        bg=C["bg"]).pack(side="left", padx=(self.px(14), 0))

        # 视图：逐条 / 按文件夹 / 按类型。汇总视图回答的是
        # 「哪个目录吃了我最多空间、其中多少从来没用过」这种问题。
        self.v_usage_view = tk.StringVar(value="逐条")
        self._usage_view_seg = self.segmented(
            filt, ("逐条", "按文件夹", "按类型"), self.v_usage_view,
            command=self._render_usage)
        self._usage_view_seg.pack(side="right")
        self.form_label(filt, "视图", bg=C["bg"]).pack(
            side="right", padx=(0, self.px(6)))

        self.usage_wrap, self.usage_tree, self.usage_empty = self.make_table(mid, [
            ("name", "素材名", 220, "w", True),
            ("folder", "项目文件夹", 200, "w", False),
            ("count", "使用次数", 80, "center", False),
            ("dur", "累计时长", 90, "center", False),
            ("seqs", "出现在序列", 190, "w", True),
            ("path", "硬盘路径", 260, "w", True),
        ], checkable=True,
            empty_text="选择项目文件后点「开始统计」\n\n"
                      "会读取时间线上每个序列，统计每个素材被用了几次、共多长")

        self.usage_group_wrap, self.usage_group_tree, _grp_empty = self.make_table(mid, [
            # 标题用「文件夹 / 类型」而不是二选一：视图切换时不用改表头，
            # 也就不会和切语言时的表头翻译打架
            ("name", "文件夹 / 类型", 300, "w", True),
            ("total", "素材数", 80, "center", False),
            ("used", "已使用", 80, "center", False),
            ("unused", "从未使用", 90, "center", False),
            ("count", "使用次数", 90, "center", False),
            ("dur", "累计时长", 100, "center", False),
            ("size", "占用空间", 100, "e", False),
        ], empty_text="")

        self.usage_wrap.pack(fill="both", expand=True)

        self.usage_rows = []
        self.usage_seqs = []
        self.usage_groups = []
        self.usage_iid = {}
        self._usage_size_cache = {}
        self.bind_check_column(self.usage_tree, lambda iid: self.usage_iid.get(iid),
                               on_change=self._usage_check_changed)

    def _usage_check_changed(self):
        n = self.count_checked(self.usage_rows)
        self.status_var.set(tr("已勾选 {} 条素材").format(n) if n
                            else tr("已取消全部勾选"))

    def do_usage(self):
        src = self.v_usage_src.get().strip().strip('"')
        if not src or not os.path.isfile(src):
            self.show_warn(tr("请先选择一个存在的项目文件（.prproj / .aep / .sesx / .xml）"))
            return
        if not can_usage(src):
            # AE / AU 工程里没有 PR 那套序列 / 轨道结构，硬解只会得到一堆 0
            if project_kind(src) == "sesx":
                self.show_info(tr("Audition 工程暂不支持时间线统计（.sesx 只做素材路径提取）"))
            else:
                self.show_info(tr("AE 工程暂不支持时间线统计（.aep 只做素材路径提取）"))
            return

        def work(q):
            q.put(("msg", tr("读取项目…")))
            root = load_root(src)
            recs = extract(root, progress=lambda m: q.put(("msg", m)))
            q.put(("msg", tr("分析时间线…")))
            q.put(("done", analyze_usage(root, recs)))

        self._run_task(work=work, on_done=self._usage_done,
                       busy_msg=tr("正在分析时间线…"), buttons=[self.btn_usage])

    def _usage_done(self, payload):
        self.usage_rows, self.usage_seqs = payload
        self._usage_size_cache = {}       # 重新统计后文件可能变过，缓存作废
        self.btn_usage_csv.configure(state="normal")
        self._render_usage()

    def _visible_usage_rows(self):
        want = self.v_usage_filter.get()
        out = []
        for r in self.usage_rows:
            if want == "从未使用" and r["count"] > 0:
                continue
            if want == "已使用" and r["count"] == 0:
                continue
            out.append(r)
        return out

    def _render_usage(self):
        if self.v_usage_view.get() != "逐条":
            self._render_usage_group()
            return

        self.usage_group_wrap.pack_forget()
        # 用 winfo_manager 而不是 winfo_ismapped 判断：这个页不在前台时
        # ismapped 恒为 0，会导致每次重绘都重复 pack
        if not self.usage_wrap.winfo_manager():
            self.usage_wrap.pack(fill="both", expand=True)

        t = self.usage_tree
        t.delete(*t.get_children())
        self.usage_iid = {}

        shown = 0
        for r in self._visible_usage_rows():
            if r["count"] == 0:
                tags = ("muted",)          # 闲置的灰掉，不抢视觉
            elif r["count"] >= 5:
                tags = ("good",)           # 反复使用的标绿
            else:
                tags = ()
            tags = (("even" if shown % 2 else "odd"),) + tags
            chk = self.CHK_ON if r.get("_chk") else self.CHK_OFF
            iid = t.insert("", "end", tags=tags,
                           values=(chk, r["name"], r["folder"], r["count"],
                                   fmt_duration(r["seconds"]) if r["seconds"] else "—",
                                   r["seqs"] or "—", r["path"]))
            self.usage_iid[iid] = r
            shown += 1

        s = summarize_usage(self.usage_rows, self.usage_seqs)
        self._usage_chip_update({
            "素材总数": s["total"], "已使用": s["used"],
            "从未使用": s["unused"], "序列数": s["seqs"],
            "时间线总时长": fmt_duration(s["seconds"]),
        })
        if shown:
            self.usage_empty.place_forget()
        else:
            self.usage_empty.configure(
                text=tr("没有符合条件的素材") if self.usage_rows else
                tr("选择项目文件后点「开始统计」\n\n"
                   "会读取时间线上每个序列，统计每个素材被用了几次、共多长"))
            self.usage_empty.place(relx=0.5, rely=0.5, anchor="center")
        if self.usage_rows:
            self.status_var.set(
                tr("统计完成：{} 个素材，已用 {}，从未使用 {}，共 {} 个序列").format(
                    s["total"], s["used"], s["unused"], s["seqs"]))

    def _render_usage_group(self):
        """汇总视图：按文件夹 / 类型把逐条统计归拢起来"""
        by = "folder" if self.v_usage_view.get() == "按文件夹" else "kind"
        self.usage_wrap.pack_forget()
        if not self.usage_group_wrap.winfo_manager():
            self.usage_group_wrap.pack(fill="both", expand=True)

        t = self.usage_group_tree
        t.delete(*t.get_children())
        self.usage_groups = group_usage(self._visible_usage_rows(), by=by,
                                        size_cache=self._usage_size_cache)

        for i, g in enumerate(self.usage_groups):
            tags = ["even" if i % 2 else "odd"]
            if g["used"] == 0:
                tags.append("muted")       # 整组一个都没用上，最值得注意
            elif g["unused"] == 0:
                tags.append("good")
            t.insert("", "end", tags=tuple(tags), values=(
                g["name"], g["total"], g["used"], g["unused"], g["count"],
                fmt_duration(g["seconds"]) if g["seconds"] else "—",
                fmt_size(g["bytes"]) if g["bytes"] else "—"))

        if self.usage_rows:
            scope = "" if self.v_usage_filter.get() == "全部" else \
                tr("（筛选：{}）").format(tr(self.v_usage_filter.get()))
            self.status_var.set(
                tr("汇总完成：{} 组，共 {} 个素材{}").format(
                    len(self.usage_groups), len(self._visible_usage_rows()), scope))

    def _export_usage_csv(self):
        if not self.usage_rows:
            return
        view = self.v_usage_view.get()
        by = {"按文件夹": "folder", "按类型": "kind"}.get(view)
        src = self.v_usage_src.get().strip()
        stem = os.path.splitext(os.path.basename(src))[0]
        if by:
            tag = tr("按文件夹") if by == "folder" else tr("按类型")
            initial = f"{stem}_使用统计_{tag}.csv"
        else:
            initial = f"{stem}_使用统计.csv"
        out = self.filedialog.asksaveasfilename(
            title=tr("保存使用统计"), defaultextension=".csv",
            initialfile=initial, initialdir=os.path.dirname(src) or None,
            filetypes=[(tr("CSV 文件"), "*.csv")])
        if not out:
            return
        if by:
            groups = self.usage_groups or group_usage(
                self._visible_usage_rows(), by=by, size_cache=self._usage_size_cache)
            write_group_csv(groups, by, out)
        else:
            write_usage_csv(self.usage_rows, out)
        self.status_var.set(tr("已导出：{}").format(out))
        self.show_info(tr("已导出：\n{}").format(out))
