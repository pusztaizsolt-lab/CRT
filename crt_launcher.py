"""
CRT Ajánlatsegéd — asztali launcher
Dupla klikk az ikonon → szerver indul → ablak nyílik
"""
import sys, time, subprocess, urllib.request, threading
from pathlib import Path

ROOT        = Path(__file__).parent
BACKEND_URL = "http://127.0.0.1:8000"
DAEMON_URL  = "http://127.0.0.1:8099"
TIMEOUT_S   = 60   # max várakozás indulásra (s)
WIN_W, WIN_H = 1366, 820
ICO_PATH    = str(ROOT / "crt.ico")


# ── SEGÉDEK ───────────────────────────────────────────────────

def _ping(base: str) -> bool:
    try:
        urllib.request.urlopen(f"{base}/health", timeout=2)
        return True
    except Exception:
        return False


def _start_detached(cmd: str):
    if sys.platform == "win32":
        subprocess.Popen(
            cmd, cwd=ROOT, shell=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    else:
        subprocess.Popen(cmd, cwd=ROOT, shell=True,
                         start_new_session=True)


# ── SPLASH ABLAK (tkinter — mindig elérhető) ─────────────────

def _run_splash(status_var, progress_var, done_event):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("CRT Ajánlatsegéd")
    root.resizable(False, False)
    root.configure(bg="#0d0d14")
    if Path(ICO_PATH).exists():
        try:
            root.iconbitmap(ICO_PATH)
        except Exception:
            pass

    W, H = 420, 200
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

    tk.Label(root, text="CRT Ajánlatsegéd",
             font=("Segoe UI", 16, "bold"),
             fg="#7c6af7", bg="#0d0d14").pack(pady=(30, 4))
    tk.Label(root, text="Civil Rendszertechnika Kft.",
             font=("Segoe UI", 9),
             fg="#5a5a7a", bg="#0d0d14").pack()

    status_lbl = tk.Label(root, textvariable=status_var,
                          font=("Segoe UI", 9),
                          fg="#9898b8", bg="#0d0d14")
    status_lbl.pack(pady=(18, 6))

    style = ttk.Style(root)
    style.theme_use("default")
    style.configure("CRT.Horizontal.TProgressbar",
                    troughcolor="#1a1a2e", background="#7c6af7",
                    bordercolor="#0d0d14", lightcolor="#7c6af7", darkcolor="#7c6af7")
    pb = ttk.Progressbar(root, variable=progress_var, maximum=100,
                         length=340, style="CRT.Horizontal.TProgressbar")
    pb.pack(pady=4)

    def _poll():
        if done_event.is_set():
            root.destroy()
            return
        root.after(200, _poll)

    root.after(200, _poll)
    root.mainloop()


# ── LAUNCHER LOGIKA ───────────────────────────────────────────

def _launch():
    import tkinter as tk

    status_var   = tk.StringVar(value="Szerver ellenőrzése…")
    progress_var = tk.IntVar(value=0)
    done_event   = threading.Event()

    splash_thread = threading.Thread(
        target=_run_splash,
        args=(status_var, progress_var, done_event),
        daemon=True,
    )
    splash_thread.start()

    # Szerver indítás ha nem fut
    if not _ping(BACKEND_URL):
        status_var.set("CRT Backend indítása…")
        _start_detached("py -3.11 main.py")

    if not _ping(DAEMON_URL):
        status_var.set("CRT Daemon indítása…")
        _start_detached("py -3.11 crt_daemon.py")

    # Várakozás — progress bar frissítéssel
    ready = False
    for i in range(TIMEOUT_S):
        if _ping(BACKEND_URL):
            ready = True
            break
        status_var.set(f"Szerver betölt… ({i+1}s)")
        progress_var.set(int(i / TIMEOUT_S * 90))
        time.sleep(1)

    if not ready:
        done_event.set()
        _show_error(
            "A CRT szerver nem indult el.\n\n"
            f"Ellenőrizd: D:\\CRT\\logs\\backend.log\n"
            f"Kézi indítás: {ROOT}\\INDITAS.bat"
        )
        sys.exit(1)

    progress_var.set(95)
    status_var.set("Ablak megnyitása…")
    time.sleep(0.3)
    done_event.set()
    splash_thread.join(timeout=3)

    # WebView ablak
    _open_window()


def _open_window():
    try:
        import webview
        window = webview.create_window(
            title     = "CRT Ajánlatsegéd",
            url       = f"{BACKEND_URL}/ui/fomenu.html",
            width     = WIN_W,
            height    = WIN_H,
            min_size  = (960, 640),
            resizable = True,
        )
        webview.start(
            icon=ICO_PATH if Path(ICO_PATH).exists() else None,
            debug=False,
        )
    except ImportError:
        # Fallback: default browser
        import webbrowser
        webbrowser.open(f"{BACKEND_URL}/ui/fomenu.html")
        _show_info(
            "PyWebView nincs telepítve — böngészőben nyílik meg.\n\n"
            "Ablak módhoz: pip install pywebview"
        )


def _show_error(msg: str):
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("CRT Ajánlatsegéd — Hiba", msg)
        r.destroy()
    except Exception:
        print(f"HIBA: {msg}", file=sys.stderr)


def _show_info(msg: str):
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        messagebox.showinfo("CRT Ajánlatsegéd", msg)
        r.destroy()
    except Exception:
        print(msg)


# ── MAIN ──────────────────────────────────────────────────────

if __name__ == "__main__":
    _launch()
