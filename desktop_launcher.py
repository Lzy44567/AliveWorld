"""Windows desktop entry point for the packaged AliveWorld server."""

from __future__ import annotations

import ctypes
import json
import os
import socket
import sys
import threading
import time
import urllib.request
import urllib.parse
import webbrowser

from desktop_shell import show_desktop_window
from core.update_runtime import UPDATE_EXIT_EVENT
from utils.runtime_paths import PATHS
from utils.sys_logger import get_logger
from utils.version import APP_VERSION


MUTEX_NAME = "Local\\AliveWorldDesktopLauncher"
PORT_FILE = PATHS.user_root / "aliveworld.port"


class SingleInstance:
    def __init__(self) -> None:
        self.handle = None
        self.already_running = False
        if os.name == "nt":
            kernel32 = ctypes.windll.kernel32
            self.handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
            self.already_running = kernel32.GetLastError() == 183

    def close(self) -> None:
        if self.handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None


def choose_port(preferred: int = 8000, attempts: int = 100) -> int:
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("无法找到可用的本地端口（8000-8099）")


def read_running_url() -> str | None:
    try:
        port = int(PORT_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return f"http://127.0.0.1:{port}/"


def versioned_url(base_url: str) -> str:
    """Force WebView/browser navigation to revalidate the frontend after upgrades."""

    return f"{base_url}?app_version={urllib.parse.quote(APP_VERSION, safe='')}"


def wait_until_healthy(url: str, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    health_url = f"{url.rstrip('/')}/api/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.2)
    get_logger().error("启动超时：本地服务未能在 %.0f 秒内就绪。", timeout)
    return False


def activate_existing_window() -> bool:
    if os.name != "nt":
        return False
    user32 = ctypes.windll.user32
    handle = user32.FindWindowW(None, "AliveWorld")
    if not handle:
        return False
    user32.ShowWindow(handle, 9)
    user32.SetForegroundWindow(handle)
    return True


def show_control_window(url: str, server, server_thread: threading.Thread) -> None:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title(f"AliveWorld {APP_VERSION}")
    root.geometry("420x190")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="AliveWorld is running", font=("Segoe UI", 15, "bold")).pack(anchor="w")
    ttk.Label(
        frame,
        text="The game opens in your browser. Keep this window open while playing.",
        wraplength=370,
    ).pack(anchor="w", pady=(8, 18))

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x")
    ttk.Button(buttons, text="Open AliveWorld", command=lambda: webbrowser.open(url, new=1)).pack(
        side="left"
    )

    def stop() -> None:
        server.should_exit = True
        root.destroy()

    ttk.Button(buttons, text="Exit AliveWorld", command=stop).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", stop)

    def monitor_server() -> None:
        if not server_thread.is_alive():
            root.destroy()
            return
        root.after(1000, monitor_server)

    root.after(1000, monitor_server)
    root.mainloop()


def create_server(app, port: int):
    # Keep Uvicorn's relatively heavy import behind the already-visible loading
    # window so a double-click receives feedback as early as possible.
    import uvicorn

    # PyInstaller windowed executables have sys.stdout/sys.stderr set to None.
    # Uvicorn's default color formatter calls isatty() and crashes before startup.
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
        log_config=None,
    )
    return uvicorn.Server(config)


def set_loading_status(window, message: str) -> None:
    try:
        window.evaluate_js(
            f"window.setAliveWorldStatus({json.dumps(message, ensure_ascii=False)})"
        )
    except Exception:
        # Loading status is cosmetic and must never prevent the backend startup.
        pass


def confirm_successful_update() -> None:
    confirmation = os.environ.get("ALIVEWORLD_UPDATE_CONFIRM_PATH")
    token = os.environ.get("ALIVEWORLD_UPDATE_TOKEN")
    expected = os.environ.get("ALIVEWORLD_EXPECTED_VERSION")
    if not confirmation or not token or expected != APP_VERSION:
        return
    try:
        target = os.path.abspath(confirmation)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        temporary = f"{target}.tmp-{os.getpid()}"
        with open(temporary, "w", encoding="utf-8") as output:
            json.dump({"token": token, "version": APP_VERSION, "pid": os.getpid()}, output)
        os.replace(temporary, target)
    except OSError as exc:
        get_logger().warning("无法写入更新健康确认：%s", exc)


def monitor_update_exit(window, server) -> None:
    UPDATE_EXIT_EVENT.wait()
    # Let the install endpoint return so the player sees the restart message.
    time.sleep(1.0)
    server.should_exit = True
    time.sleep(0.3)
    try:
        window.destroy()
    except Exception:
        pass


def monitor_browser_update_exit(server) -> None:
    UPDATE_EXIT_EVENT.wait()
    time.sleep(1.0)
    server.should_exit = True


def run_browser_fallback(url: str, port: int) -> None:
    from main import app

    server = create_server(app, port)
    server_thread = threading.Thread(target=server.run, name="aliveworld-server", daemon=True)
    server_thread.start()
    if not wait_until_healthy(url):
        raise RuntimeError("本地服务未能完成健康检查")
    confirm_successful_update()
    threading.Thread(
        target=monitor_browser_update_exit,
        args=(server,),
        name="aliveworld-browser-update-exit",
        daemon=True,
    ).start()
    if os.environ.get("ALIVEWORLD_NO_BROWSER") != "1":
        webbrowser.open(versioned_url(url), new=1)
    show_control_window(url, server, server_thread)
    server.should_exit = True
    server_thread.join(timeout=10)


def stop_runtime(runtime: dict[str, object]) -> None:
    server = runtime.get("server")
    server_thread = runtime.get("thread")
    if server is not None and hasattr(server, "should_exit"):
        server.should_exit = True
    if isinstance(server_thread, threading.Thread):
        server_thread.join(timeout=10)


def run() -> int:
    instance = SingleInstance()
    if instance.already_running:
        url = read_running_url()
        if not activate_existing_window() and url and os.environ.get("ALIVEWORLD_NO_BROWSER") != "1":
            webbrowser.open(versioned_url(url), new=1)
        instance.close()
        return 0

    preferred = int(os.environ.get("ALIVEWORLD_PORT", "8000"))
    port = choose_port(preferred)
    PORT_FILE.write_text(str(port), encoding="utf-8")
    url = f"http://127.0.0.1:{port}/"

    try:
        runtime: dict[str, object] = {}

        def bootstrap(window) -> None:
            try:
                set_loading_status(window, "正在加载游戏核心……")
                from main import app

                set_loading_status(window, "正在启动本地服务……")
                server = create_server(app, port)
                server_thread = threading.Thread(
                    target=server.run,
                    name="aliveworld-server",
                    daemon=True,
                )
                runtime["server"] = server
                runtime["thread"] = server_thread
                server_thread.start()
                if not wait_until_healthy(url):
                    raise RuntimeError("本地服务未能完成健康检查")
                confirm_successful_update()
                threading.Thread(
                    target=monitor_update_exit,
                    args=(window, server),
                    name="aliveworld-update-exit",
                    daemon=True,
                ).start()
                set_loading_status(window, "世界已经就绪，正在打开……")
                window.load_url(versioned_url(url))
            except Exception as exc:
                get_logger().error(
                    "桌面后端启动失败：%s: %s",
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )
                window.load_html(
                    "<body style='background:#0f172a;color:#fecaca;font:16px sans-serif;padding:40px'>"
                    "<h2>AliveWorld 启动失败</h2>"
                    "<p>请查看 AliveWorld.exe 旁 UserData\\logs 中的最新日志。</p></body>"
                )

        try:
            show_desktop_window(
                bootstrap,
                storage_path=PATHS.user_root / "webview",
            )
        except Exception as exc:
            stop_runtime(runtime)
            get_logger().warning(
                "WebView2 启动失败，已回退到系统浏览器：%s: %s",
                type(exc).__name__,
                exc,
            )
            run_browser_fallback(url, port)

        stop_runtime(runtime)
        return 0
    except Exception as exc:
        get_logger().error(
            "AliveWorld 启动失败：%s: %s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        return 1
    finally:
        try:
            if PORT_FILE.read_text(encoding="utf-8").strip() == str(port):
                PORT_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        instance.close()


if __name__ == "__main__":
    raise SystemExit(run())
