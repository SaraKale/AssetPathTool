# -*- coding: utf-8 -*-
"""「检查更新」弹窗（mixin）。

单独一个文件，理由跟 finder.py 一样：它自己就是一个完整的小窗口，
塞进 app.py 会把「窗口骨架」的主线冲淡。

流程：
  点按钮 → 后台线程查 tag（GitHub → Gitee 兜底）→ 弹窗列出
  「当前版本 / 最新版本 / 各平台下载地址」。

网络请求走 App._run_task，别自己再开一套线程 + 轮询。
"""
import webbrowser

from ..appinfo import APP_VER
from ..core.update import (DOWNLOAD_SOURCES, SOURCE_LABEL, fetch_latest_version,
                           is_newer, version_label)
from ..i18n import tr
from ..theme import C


class UpdateMixin:
    # ---------------------------------------------------------------- 入口
    def check_update(self):
        """查最新 tag，跟 APP_VER 比大小；结果在弹窗里给。"""
        if getattr(self, "_upd_busy", False):
            return
        self._upd_busy = True

        def work(q):
            # 网络失败不当异常抛：弹窗里显示「无法获取最新版本」比弹个
            # 错误框友好得多（用户只是想看看有没有新版）
            try:
                tag, src = fetch_latest_version()
                q.put(("done", {"tag": tag, "source": src}))
            except Exception as e:
                q.put(("done", {"tag": None, "source": None,
                                "error": "%s: %s" % (type(e).__name__, e)}))

        def done(info):
            self._upd_busy = False
            self._on_update_result(info or {})

        self._run_task(work, done, tr("正在检查更新…（GitHub / Gitee）"),
                       [self.btn_update])

    # ---------------------------------------------------------------- 结果
    def _on_update_result(self, info):
        tag = info.get("tag")
        err = info.get("error", "")
        src = SOURCE_LABEL.get(info.get("source"), "")
        via = tr("通过 {} 获取").format(src) if src else ""

        try:
            if tag and is_newer(tag, APP_VER):
                self.status_var.set(tr("发现新版本 {}（当前 {}）{}").format(
                    version_label(tag), version_label(APP_VER), via))
            elif tag:
                self.status_var.set(tr("已是最新版本（{}）{}").format(
                    version_label(APP_VER), via))
            else:
                self.status_var.set(tr("无法获取最新版本"))
        except Exception:
            pass

        self._show_update_window(tag, err)

    # ---------------------------------------------------------------- 弹窗
    def _show_update_window(self, tag, err=""):
        tk = self.tk
        cur = APP_VER
        newer = bool(tag) and is_newer(tag, cur)
        if newer:
            head, head_fg = tr("发现新版本"), C["accent"]
        elif tag:
            head, head_fg = tr("已是最新版本"), C["ok"]
        else:
            head, head_fg = tr("无法获取最新版本"), C["warn"]

        # 已经开着就先关掉，别叠窗
        old = getattr(self, "_upd_win", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass

        win = tk.Toplevel(self.root)
        self._upd_win = win
        win.title(tr("检查更新"))
        win.configure(bg=C["bg"])
        try:
            win.transient(self.root)
        except Exception:
            pass

        outer, pad = self.card(win)
        outer.pack(fill="both", expand=True,
                   padx=self.px(14), pady=self.px(14))

        tk.Label(pad, text=head, font=self.F_H2, bg=C["card"], fg=head_fg,
                 anchor="w").pack(fill="x")

        self._upd_vrow(pad, tr("当前版本"), version_label(cur) or cur,
                       C["text"])
        self._upd_vrow(pad, tr("最新版本"),
                       version_label(tag) if tag else tr("未知"),
                       head_fg if tag else C["muted"])

        tk.Frame(pad, bg=C["line"], height=max(1, self.px(1))).pack(
            fill="x", pady=(self.px(12), 0))
        tk.Label(pad, text=tr("下载地址"), font=self.F_H2, bg=C["card"],
                 fg=C["text"], anchor="w").pack(fill="x",
                                                pady=(self.px(10), 0))
        for key, url, code in DOWNLOAD_SOURCES:
            self._upd_dlrow(pad, key, url, code)

        if err:
            tk.Label(pad, text=tr("检查更新失败：{}").format(err),
                     font=self.F_SMALL, bg=C["card"], fg=C["warn"],
                     anchor="w", justify="left",
                     wraplength=self.px(560)).pack(fill="x",
                                                   pady=(self.px(10), 0))

        tk.Label(pad,
                 text=tr("版本号取自 GitHub / Gitee 的最新 Release tag。"
                         "下载后解压覆盖即可，配置文件不会丢。"),
                 font=self.F_SMALL, bg=C["card"], fg=C["hint"],
                 anchor="w", justify="left",
                 wraplength=self.px(560)).pack(fill="x",
                                               pady=(self.px(12), 0))

        foot = tk.Frame(pad, bg=C["card"])
        foot.pack(fill="x", pady=(self.px(12), 0))
        self.ttk.Button(foot, text=tr("关闭"), style="Ghost.TButton",
                        command=win.destroy).pack(side="right")

        win.bind("<Escape>", lambda e: win.destroy())
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self._center_on_root(win, min_w=self.px(560))

    # ---------------------------------------------------------------- 行
    def _upd_vrow(self, parent, label, value, color):
        """「当前版本  v1.0.0」这种一行两段。

        标签列用 grid 的 minsize 定宽，不用 Label(width=N) —— 那个 N 是「字符数」，
        英文 "Current version" 15 个字符、日文「現在のバージョン」8 个全角，
        同一个 N 必然有一边被截成 "Current versi"。
        """
        tk = self.tk
        row = tk.Frame(parent, bg=C["card"])
        row.pack(fill="x", pady=(self.px(8), 0))
        row.columnconfigure(0, minsize=self.px(132))
        tk.Label(row, text=label, font=self.F_BODY, bg=C["card"],
                 fg=C["muted"], anchor="w").grid(row=0, column=0, sticky="w")
        tk.Label(row, text=value, font=self.F_H2, bg=C["card"], fg=color,
                 anchor="w").grid(row=0, column=1, sticky="w")

    def _upd_dlrow(self, parent, key, url, code):
        """一行下载地址：平台名 + 可点击链接（+ 提取码）+ 复制按钮"""
        tk = self.tk
        row = tk.Frame(parent, bg=C["card"])
        row.pack(fill="x", pady=(self.px(8), 0))

        # 复制按钮先 pack 到右边，链接才有地方伸展开；留一点间距，
        # 否则 MediaFire 那条长链接会贴到按钮边上
        copy_text = url + (("\n" + code) if code else "")
        btn = self.ttk.Button(row, text=tr("复制"), style="Ghost.TButton",
                              command=lambda t=copy_text: self._copy_text(t))
        btn.pack(side="right", padx=(self.px(12), 0))

        tk.Label(row, text=tr(SOURCE_LABEL.get(key, key)), font=self.F_SMALL,
                 bg=C["card"], fg=C["muted"], anchor="w",
                 width=10).pack(side="left")

        lnk = tk.Label(row, text=url, font=self.F_BODY, bg=C["card"],
                       fg=C["accent"], anchor="w", cursor="hand2")
        lnk.pack(side="left")
        lnk.bind("<Button-1>", lambda e, u=url: self._open_url(u))
        lnk.bind("<Enter>", lambda e: lnk.configure(fg=C["accent_dk"]))
        lnk.bind("<Leave>", lambda e: lnk.configure(fg=C["accent"]))

        if code:
            tk.Label(row, text="%s%s" % (tr("提取码："), code),
                     font=self.F_SMALL, bg=C["card"], fg=C["text"]).pack(
                side="left", padx=(self.px(10), 0))

    # ---------------------------------------------------------------- 工具
    def _copy_text(self, text):
        """复制到剪贴板；顺手在状态栏回一句，免得用户不知道点没点上"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except Exception:
            return
        try:
            self.status_var.set(tr("已复制") + "：" + text.replace("\n", "  "))
        except Exception:
            pass

    def _open_url(self, url):
        try:
            webbrowser.open(url)
        except Exception:
            self._copy_text(url)

    def _center_on_root(self, win, min_w=0):
        """按内容定尺寸，再相对主窗口居中（偏上一点，视觉上更稳）"""
        try:
            win.update_idletasks()
            w = max(win.winfo_reqwidth(), min_w)
            h = win.winfo_reqheight()
            x = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 3
            win.geometry("%dx%d+%d+%d" % (w, h, max(0, x), max(0, y)))
        except Exception:
            pass
        try:
            win.lift()
            win.focus_set()
        except Exception:
            pass
