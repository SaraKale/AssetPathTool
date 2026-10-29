# -*- coding: utf-8 -*-
"""「查找缺失…」弹窗：在指定目录里按文件名前缀找可能的新位置。

单独放一个文件，是因为它自己就是一个完整的窗口（200 多行），
塞在页面③里会把重定向的主流程冲淡。
"""
import os
import queue
import subprocess
import threading

from ..i18n import tr
from ..theme import C
from ..core.fsinfo import file_info, fmt_mtime, fmt_size
from ..core.matching import MEDIA_EXTS, match_missing, norm_stem, scan_media_index
from ..core.remap import recompute_remap
from ..platform_utils import WindowsDropTarget


class FinderMixin:
    def _open_finder(self):
        """
        给「路径不存在」的素材，在指定目录里按文件名（前缀）匹配出可能的新位置。
        范围：表格里选中的行优先，没选就取全部缺失行。
        """
        tk, ttk = self.tk, self.ttk
        if not self.rm_records:
            self.show_info(tr("请先点「加载全部」"))
            return

        # 上一次开的窗口还开着就先关掉：范围（勾选 / 选中行）可能已经变了，
        # 复用旧窗口会按旧范围扫描，容易误操作
        old = getattr(self, "_finder", None)
        if old:
            try:
                w = old.get("win")
                if w is not None and w.winfo_exists():
                    old["drop"] = None
                    w.destroy()
            except Exception:
                pass

        sel = [self.rm_iid[i] for i in self.rm_tree.selection() if i in self.rm_iid]
        checked = [r for r in self.rm_records if r.get("_chk")]
        # 优先级：勾选的行 → 选中的行 → 全部缺失行
        base = checked or sel or self.rm_records
        pool = [r for r in base if r["path"] and not r["exists"]]
        if not pool:
            if checked or sel:
                self.show_info(tr("勾选 / 选中的行里没有「路径不存在」的素材。\n\n"
                                  "取消勾选，或把「只看」切到「缺失」再试。"))
            else:
                self.show_info(tr("当前没有「路径不存在」的素材。\n\n"
                                  "把右上角「只看」切到「缺失」，就能看到这些条目。"))
            return
        if len(pool) > 300 and not self.messagebox.askyesno(
                tr(self.APP_TITLE),
                tr("要处理 {} 条缺失素材，数量较多，扫描和匹配会比较慢。\n"
                   "建议先在表格里选中几行再点「查找缺失…」。\n\n仍要继续吗？").format(len(pool))):
            return

        win = tk.Toplevel(self.root)
        win.title(tr("查找缺失素材"))
        win.configure(bg=C["bg"])
        win.geometry(f"{self.px(1000)}x{self.px(650)}")
        win.minsize(self.px(780), self.px(500))
        win.transient(self.root)

        top, top_in = self.card(win)
        top.pack(fill="x", padx=self.px(14), pady=(self.px(14), self.px(10)))

        if checked:
            scope = tr("（范围：已勾选的 {} 条）").format(len(pool))
        elif sel:
            scope = tr("（范围：已选中的 {} 条）").format(len(pool))
        else:
            scope = tr("（范围：全部缺失素材 {} 条）").format(len(pool))
        self.note_label(
            top_in,
            tr("在下面的目录里按文件名找这些缺失素材，比的是文件名前缀，"
               "后缀不同也能认出来。") + scope,
            bg=C["card"]).pack(fill="x", pady=(0, self.px(10)))

        v_dir = tk.StringVar()
        ent = self.file_row(top_in, "搜索目录", v_dir,
                            lambda: self._pick_finder_dir(v_dir))
        self.add_placeholder(ent, v_dir, "点「浏览…」选一个目录（会递归扫描子目录）")

        opt = tk.Frame(top_in, bg=C["card"])
        opt.pack(fill="x", pady=(0, self.px(6)))
        self.form_label(opt, "相似度", bg=C["card"]).pack(
            side="left", padx=(0, self.px(6)))
        v_thr = tk.StringVar(value="标准")
        self.segmented(opt, ["宽松", "标准", "严格"], v_thr).pack(side="left")
        self.form_label(opt, "搜索深度", bg=C["card"]).pack(
            side="left", padx=(self.px(16), self.px(6)))
        v_depth = tk.StringVar(value="6 层")
        self.segmented(opt, ["3 层", "6 层", "不限"], v_depth).pack(side="left")
        self.form_label(opt, "后缀", bg=C["card"]).pack(
            side="left", padx=(self.px(16), self.px(6)))
        v_ext = tk.StringVar(value="忽略")
        self.segmented(opt, ["忽略", "相同"], v_ext).pack(side="left")

        # 一个素材可能匹配出好几个候选（名字短的尤其容易），默认只留最高分的那个，
        # 否则表格里同一素材连着出现好几行，看着像重复。想看全部就取消勾选。
        v_best = tk.BooleanVar(value=True)
        self.checkbox(opt, "每个素材只留最佳候选", v_best, bg=C["card"],
                      command=lambda: refill()).pack(side="right")

        act = tk.Frame(top_in, bg=C["card"])
        act.pack(fill="x", pady=(0, self.px(2)))
        self.note_label(act, "按文件名前缀比对；后缀选「忽略」时 flv/mp4/mov 互相认。",
                        bg=C["card"]).pack(side="left")
        btn_scan = ttk.Button(act, text="开始扫描", style="Primary.TButton")
        btn_scan.pack(side="right")
        btn_apply = ttk.Button(act, text="应用到重定向表", style="Ghost.TButton",
                               state="disabled")
        btn_apply.pack(side="right", padx=(0, self.px(8)))

        wrap, tbl, empty = self.make_table(win, [
            ("name", "素材名", 180, "w", False),
            ("cand", "建议文件", 230, "w", True),
            ("score", "相似度", 60, "center", False),
            ("size", "大小", 80, "e", False),
            ("mtime", "修改时间", 118, "center", False),
            ("folder", "所在目录", 230, "w", True),
        ], height=10, selectmode="extended",
            empty_text="选好目录和相似度后点「开始扫描」\n\n"
                       "不选任何行直接点「应用到重定向表」= 全部应用")
        wrap.pack(fill="both", expand=True,
                  padx=self.px(14), pady=(0, self.px(8)))

        lbl = self.note_label(
            win, "提示：相似度 ≥85% 的结果会自动选中；不选任何行点「应用到重定向表」= 全部应用。",
            bg=C["bg"])
        lbl.pack(fill="x", padx=self.px(16), pady=(0, self.px(12)))

        # 右键菜单：单行操作比「先选中再点按钮」顺手
        ctx = {"iid": ""}
        menu = tk.Menu(win, tearoff=0)
        menu.add_command(label="采用这个建议", command=lambda: ctx_apply())
        menu.add_command(label="选择新位置…", command=lambda: ctx_pick())
        menu.add_separator()
        menu.add_command(label="在资源管理器中定位", command=lambda: ctx_reveal())
        for idx, key in ((0, "采用这个建议"), (1, "选择新位置…"),
                         (3, "在资源管理器中定位")):
            self._i18n_menu.append((menu, idx, key))

        def on_right_click(event):
            iid = tbl.identify_row(event.y)
            if not iid or iid not in res_map:
                return
            # 右键点在多选范围内就保留整片选择，否则只选这一行
            if iid not in tbl.selection():
                tbl.selection_set(iid)
            tbl.focus(iid)
            ctx["iid"] = iid
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        tbl.bind("<Button-3>", on_right_click)

        def ctx_apply():
            """只应用右键点中的那一行，不要连带整片选择"""
            iid = ctx["iid"]
            if iid:
                do_apply([iid])

        def ctx_pick():
            """不走建议，直接给这条素材挑一个新文件"""
            item = res_map.get(ctx["iid"])
            if not item:
                return
            rec = item[0]
            self._pick_new_for(rec)        # 内部会刷新主表并写状态栏
            lbl.configure(text=tr("已为「{}」单独指定新位置").format(rec["name"]))

        def ctx_reveal():
            item = res_map.get(ctx["iid"])
            if not item:
                return
            rec, suggest, _score = item
            for p in (suggest, rec["manual"], rec["path"], rec["old_path"]):
                if p and os.path.exists(p):
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
                    return
            self.show_info(tr("这个文件现在不存在，无法定位。"), parent=win)

        # 弹窗是建完主界面之后才出现的，得单独登记一遍再翻译
        self._i18n_title.append((win, "查找缺失素材"))
        prev = self.status_var.get()
        self._collect_i18n(win)
        self._apply_i18n()
        self.status_var.set(prev)

        res_map = {}          # iid -> (record, 建议路径, 分数)
        state = {"busy": False, "last": None}

        def do_scan():
            if state["busy"]:
                return
            root_dir = v_dir.get().strip().strip('"')
            if not root_dir or not os.path.isdir(root_dir):
                self.show_warn(tr("请先选一个存在的搜索目录"), parent=win)
                return
            thr = {"宽松": 0.50, "标准": 0.65, "严格": 0.80}[v_thr.get()]
            depth = {"3 层": 3, "6 层": 6, "不限": None}[v_depth.get()]
            own = {os.path.splitext(r["old_path"])[1].lower() for r in pool}
            own.discard("")
            if v_ext.get() == "相同":
                exts = own
            else:
                # 忽略后缀：索引所有常见媒体扩展名，flv/mp4/mov 才能互相认出来；
                # 再并上素材原本的后缀，防止 .prtl / .aep 这类冷门格式被漏掉
                exts = MEDIA_EXTS | own
            targets = []
            for i, r in enumerate(pool):
                base = os.path.basename(r["old_path"]) or r["name"]
                targets.append({
                    "key": str(i),
                    "stem": norm_stem(base),
                    "ext": os.path.splitext(base)[1].lower(),
                })

            state["busy"] = True
            btn_scan.configure(state="disabled")
            btn_apply.configure(state="disabled")
            tbl.delete(*tbl.get_children())
            res_map.clear()
            empty.place_forget()
            lbl.configure(text=tr("正在扫描目录…"))

            q = queue.Queue()

            def work():
                try:
                    idx, truncated = scan_media_index(
                        [root_dir], exts=exts, max_depth=depth,
                        progress=lambda m: q.put(("msg", m)))
                    q.put(("msg", tr("索引 {} 个文件，开始匹配…").format(len(idx))))
                    res = match_missing(targets, idx, min_score=thr,
                                        progress=lambda m: q.put(("msg", m)))
                    # 顺手把候选的大小 / 修改时间查出来。同名不同版本太常见，
                    # 光看文件名和相似度判断不了是不是同一个东西。
                    # 放在后台线程里 stat，主线程铺表时就不用等。
                    q.put(("msg", tr("读取候选文件信息…")))
                    info = {}
                    for lst in res.values():
                        for c in lst:
                            p = c["path"]
                            got = info.get(p)
                            if got is None:
                                got = info[p] = file_info(p)
                            c["size"], c["mtime"] = got
                    q.put(("done", (res, truncated, len(idx))))
                except Exception as ex:
                    q.put(("err", f"{type(ex).__name__}: {ex}"))

            def poll():
                try:
                    while True:
                        kind, payload = q.get_nowait()
                        if kind == "msg":
                            lbl.configure(text=payload)
                        elif kind == "err":
                            state["busy"] = False
                            btn_scan.configure(state="normal")
                            lbl.configure(text=tr("出错：{}").format(payload))
                            return
                        else:
                            fill(*payload)
                            state["busy"] = False
                            btn_scan.configure(state="normal")
                            return
                except queue.Empty:
                    pass
                win.after(120, poll)

            threading.Thread(target=work, daemon=True).start()
            poll()

        def fill(res, truncated, n_index):
            """把匹配结果铺进表格。

            同一个缺失素材可能命中好几个候选文件（名字越短越容易，比如都带
            「仙剑3外传」这种系列前缀）。这不是重复行，是同一素材的备选。
            所以：素材名只在第一行写全，后面的候选写「└ 备选」；
            默认「每个素材只留最佳候选」勾着，低分备选根本不显示。
            """
            state["last"] = (res, truncated, n_index)
            tbl.delete(*tbl.get_children())
            res_map.clear()
            best_only = v_best.get()
            n_cand = n_asset = n_auto = 0
            for i, r in enumerate(pool):
                cands = res.get(str(i), [])
                if best_only:
                    cands = cands[:1]
                if cands:
                    n_asset += 1
                for j, c in enumerate(cands):
                    # 同素材的第 2 条起缩进一下，一眼看出是备选而不是重复
                    label = r["name"] if j == 0 else tr("　└ 备选")
                    iid = tbl.insert("", "end", values=(
                        label, os.path.basename(c["path"]),
                        f"{c['score'] * 100:.0f}%",
                        fmt_size(c.get("size")), fmt_mtime(c.get("mtime")),
                        c["folder"]))
                    res_map[iid] = (r, c["path"], c["score"])
                    n_cand += 1
                    # 每个素材只自动勾最佳那条 —— 勾一堆备选会让人以为会应用多行
                    if j == 0 and c["score"] >= 0.85:
                        tbl.selection_add(iid)
                        n_auto += 1
            btn_apply.configure(state="normal" if n_cand else "disabled")
            msg = tr("索引 {} 个文件，命中 {} 条素材 / {} 条候选，已自动选中 {} 条（相似度 ≥85%）").format(
                n_index, n_asset, n_cand, n_auto)
            if truncated:
                msg += tr("　⚠ 已达文件数上限，建议缩小搜索目录或降低深度")
            lbl.configure(text=msg)
            if not n_cand:
                empty.configure(text=tr("这个目录里没找到相似的文件\n\n"
                                        "试试放宽相似度、加大搜索深度，或换一个目录"))
                empty.place(relx=0.5, rely=0.5, anchor="center")
            else:
                empty.place_forget()

        def refill():
            """切换「只留最佳候选」时重铺表格，不用重新扫描"""
            if state["last"]:
                fill(*state["last"])

        def do_apply(picked=None):
            """应用到重定向表。

            picked 给了就只处理这些行（右键「采用这个建议」走这条）；
            没给就看表格里选了什么，**什么都没选就全部应用** ——
            以前这里没选会直接弹提示，用户得先手动圈一遍才能全改，太别扭。
            """
            whole = False
            if picked is None:
                picked = tbl.selection()
                if not picked:
                    picked = list(res_map.keys())
                    whole = True
            picked = [i for i in picked if i in res_map]
            if not picked:
                self.show_info(tr("表格里还没有候选，先点「开始扫描」"), parent=win)
                return
            best = {}
            for iid in picked:
                rec, path, sc = res_map[iid]
                k = id(rec)
                if k not in best or sc > best[k][1]:
                    best[k] = (rec, sc, path)
            if whole and len(best) > 50 and not self.messagebox.askyesno(
                    tr(self.APP_TITLE),
                    tr("要把 {} 条素材的建议路径全部填进重定向表吗？\n\n"
                       "填完可以在主表里逐条复核，改错了用「清空手动指定」撤回。").format(
                           len(best)),
                    parent=win):
                return
            for rec, _sc, path in best.values():
                rec["manual"] = path
                recompute_remap([rec], [])
            self._render_remap()
            n = len(best)
            lbl.configure(text=tr("已把 {} 条建议填进重定向表").format(n))
            self.status_var.set(tr("已为 {} 条缺失素材填上建议路径").format(n))

        btn_scan.configure(command=do_scan)
        btn_apply.configure(command=do_apply)

        def _close():
            # 拖放目标子类化了窗口过程；窗口销毁前先把引用摘掉，
            # 免得下次打开 finder 时旧回调还挂在被复用的 hwnd 上。
            # 只清属于自己这个窗口的那份引用，别误清新开的窗口。
            try:
                f = getattr(self, "_finder", None)
                if f and f.get("win") is win:
                    f["drop"] = None
            except Exception:
                pass
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _close)
        win.bind("<Escape>", lambda e: _close())

        # 留一份引用：既方便调试/自动化测试驱动，也避免窗口被 GC 提前回收
        self._finder = {
            "win": win, "dir": v_dir, "thr": v_thr, "depth": v_depth,
            "ext": v_ext, "scan": btn_scan, "apply": btn_apply, "tree": tbl,
            "label": lbl, "res": res_map, "busy": state, "best": v_best,
            "fill": fill, "refill": refill, "do_apply": do_apply,
            # 右键三项：菜单是 tk_popup 弹出的，自动化点不到，直接留句柄
            "ctx": {"cur": ctx, "apply": ctx_apply,
                    "pick": ctx_pick, "reveal": ctx_reveal},
        }

        # 拖文件夹进「搜索目录」。
        # 主窗口的拖放只认自己的句柄，收不到拖到这个 Toplevel 上的东西，
        # 所以得给弹窗单独注册一个。
        def on_dir_drop(paths):
            dirs = [p for p in paths if os.path.isdir(p)]
            if not dirs:
                lbl.configure(text=tr("拖进来的是文件，不是文件夹。请拖一个目录过来。"))
                return
            v_dir.set(os.path.normpath(dirs[0]))
            lbl.configure(text=tr("已拖入搜索目录：{}　点「开始扫描」").format(
                os.path.normpath(dirs[0])))
            self.status_var.set(tr("已把文件夹填进搜索目录"))

        try:
            self._finder["drop"] = WindowsDropTarget(win, on_dir_drop)
        except Exception:
            self._finder["drop"] = None

    def _pick_finder_dir(self, var):
        p = self.filedialog.askdirectory(title=tr("选择要搜索的目录"))
        if p:
            var.set(os.path.normpath(p))
