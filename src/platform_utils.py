# -*- coding: utf-8 -*-
"""平台相关的小工具：DPI、控制台接管、文件拖放、换解释器重启。

都是「Windows 上才有效、其他平台安静跳过」的东西，集中放这里。
"""
import os
import sys
import traceback

try:
    import ctypes
    from ctypes import wintypes
    WIN = sys.platform == "win32"
except ImportError:      # 非 Windows 平台没有 wintypes
    ctypes = None
    wintypes = None
    WIN = False


# ---------------------------------------------------------------- DPI
def detect_dpi():
    """
    取系统真实 DPI。
    注意：tkinter 的 winfo_fpixels("1i") 在设置 scaling 之前恒返回 96，
    不能用来判断缩放比例，必须问 Windows 自己。
    """
    if sys.platform == "win32":
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
            if dpi and dpi > 0:
                return float(dpi)
        except Exception:
            pass
        try:
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, hdc)
            if dpi and dpi > 0:
                return float(dpi)
        except Exception:
            pass
    return 96.0


# ---------------------------------------------------------------- 拖放
class WindowsDropTarget:
    """
    把顶层窗口注册成文件拖放目标。
    做法：DragAcceptFiles 打开接收，再子类化窗口过程拦截 WM_DROPFILES。
    """

    WM_DROPFILES = 0x0233
    GWL_WNDPROC = -4
    GA_ROOT = 2

    def __init__(self, root, on_drop):
        self.ok = False
        self.hwnd = None
        self.error = ""
        self.on_drop = on_drop
        self._proc = None
        self._old = None
        if not WIN:
            self.error = "仅支持 Windows"
            return
        try:
            LRESULT = ctypes.c_ssize_t
            WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                                         wintypes.WPARAM, wintypes.LPARAM)
            u = ctypes.WinDLL("user32", use_last_error=True)
            s = ctypes.WinDLL("shell32", use_last_error=True)

            u.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            u.GetAncestor.restype = wintypes.HWND
            u.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND,
                                          wintypes.UINT, wintypes.WPARAM,
                                          wintypes.LPARAM]
            u.CallWindowProcW.restype = LRESULT

            if ctypes.sizeof(ctypes.c_void_p) == 8:
                setter = u.SetWindowLongPtrW
            else:
                setter = u.SetWindowLongW
            setter.argtypes = [wintypes.HWND, ctypes.c_int, WNDPROC]
            setter.restype = ctypes.c_void_p

            s.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
            s.DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT,
                                         ctypes.c_wchar_p, wintypes.UINT]
            s.DragQueryFileW.restype = wintypes.UINT
            s.DragFinish.argtypes = [ctypes.c_void_p]

            hwnd = u.GetAncestor(root.winfo_id(), self.GA_ROOT)
            if not hwnd:
                self.error = "取不到窗口句柄"
                return

            s.DragAcceptFiles(hwnd, True)
            self._u, self._s = u, s
            self._WNDPROC = WNDPROC
            self.hwnd = hwnd
            self._proc = WNDPROC(self._wndproc)   # 必须留引用，否则回调被回收会崩
            self._old = setter(hwnd, self.GWL_WNDPROC, self._proc)
            self.ok = bool(self._old)
            if not self.ok:
                self.error = "子类化窗口过程失败"
        except Exception as ex:
            self.error = f"{type(ex).__name__}: {ex}"
            self.ok = False

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == self.WM_DROPFILES:
            try:
                self.on_drop(self._read_paths(wparam))
            except Exception:
                traceback.print_exc()
            finally:
                try:
                    self._s.DragFinish(wparam)
                except Exception:
                    pass
            return 0
        return self._u.CallWindowProcW(self._old, hwnd, msg, wparam, lparam)

    def _read_paths(self, hdrop):
        n = self._s.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        paths = []
        for i in range(n):
            ln = self._s.DragQueryFileW(hdrop, i, None, 0)
            if ln <= 0:
                continue
            buf = ctypes.create_unicode_buffer(ln + 1)
            self._s.DragQueryFileW(hdrop, i, buf, ln + 1)
            if buf.value:
                paths.append(buf.value)
        return paths


# ---------------------------------------------------------------- 控制台
def attach_console():
    """
    打包成「无控制台窗口」的 exe 之后，sys.stdout 是 None，--cli 模式的
    print 会全部丢失。这里分两种情况接回去：

      ① 启动时 stdout 已经被重定向到文件 / 管道（`exe --cli a.prproj > out.txt`）
         → 直接复用那个句柄，重定向照常有效；
      ② 在 cmd / PowerShell 里直接跑（没有重定向）
         → AttachConsole(-1) 挂到调用它的控制台窗口。

    双击启动（既没重定向、也没有父控制台）时两样都失败，安静返回，
    不会莫名弹出黑框。

    注意：Git Bash / MinTTY 是 pty 而不是 Win32 控制台，AttachConsole 挂不上，
    想测输出请用 cmd，或者直接用 --out 写文件。
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    try:
        import msvcrt
        k32 = ctypes.windll.kernel32

        # Windows 控制台默认是 GBK 代码页，中文 print 会变乱码，先切 UTF-8
        try:
            k32.SetConsoleOutputCP(65001)
        except Exception:
            pass

        def wrap(std_id):
            h = k32.GetStdHandle(std_id)
            if not h or h == -1:
                return None
            fd = msvcrt.open_osfhandle(h, os.O_WRONLY)
            return os.fdopen(fd, "w", encoding="utf-8", buffering=1,
                             errors="replace", closefd=False)

        out, err = wrap(-11), wrap(-12)
        if out is not None:
            sys.stdout = out
            if err is not None:
                sys.stderr = err
            return

        # 没有可用句柄 → 挂到调用者的控制台
        if not k32.AttachConsole(-1):
            return
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1,
                          errors="replace")
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1,
                          errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------- 缺 tkinter 时自救
def entry_script():
    """入口脚本的绝对路径（打包后返回 exe 自己）"""
    if getattr(sys, "frozen", False):
        return sys.executable
    # 本文件在 <root>/src/ 下，入口在 <root>/AssetPathToolMain.py
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("AssetPathToolMain.py",):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            return p
    return os.path.abspath(sys.argv[0])


def relaunch_with_tk():
    """当前解释器缺 tkinter 时，自动换一个能用的重新启动"""
    import subprocess
    import shutil

    me = entry_script()
    cands = [r"C:\Python314\pythonw.exe", r"C:\Python314\python.exe",
             shutil.which("pythonw"), shutil.which("python")]
    for p in cands:
        if not p or not os.path.isfile(p):
            continue
        if os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(sys.executable)):
            continue
        try:
            r = subprocess.run([p, "-c", "import tkinter"], capture_output=True, timeout=20)
            if r.returncode == 0:
                subprocess.Popen([p, me])
                return True
        except Exception:
            continue
    try:
        r = subprocess.run(["py", "-c", "import tkinter"], capture_output=True, timeout=20)
        if r.returncode == 0:
            subprocess.Popen(["py", me])
            return True
    except Exception:
        pass
    return False
