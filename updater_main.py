"""Independent portable update helper executed from the system temp directory."""

from __future__ import annotations

import json
import ctypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable
import tkinter as tk


def _wait_for_exit(pid: int, timeout: float = 45.0) -> bool:
    if os.name == "nt":
        synchronize = 0x00100000
        wait_object_0 = 0x00000000
        handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
        if not handle:
            return True
        try:
            result = ctypes.windll.kernel32.WaitForSingleObject(handle, int(timeout * 1000))
            return result == wait_object_0
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.25)
    return False


def _move_children(source: Path, destination: Path, *, exclude: set[str] | None = None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    excluded = {name.lower() for name in (exclude or set())}
    for item in source.iterdir():
        if item.name.lower() in excluded:
            continue
        shutil.move(str(item), str(destination / item.name))


def _copy_children(source: Path, destination: Path, *, exclude: set[str] | None = None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    excluded = {name.lower() for name in (exclude or set())}
    for item in source.iterdir():
        if item.name.lower() in excluded:
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def _remove_program_children(install_dir: Path) -> None:
    for item in install_dir.iterdir():
        if item.name.lower() == "userdata":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink(missing_ok=True)


def apply_update(manifest_path: str | Path, status: Callable[[str], None] | None = None) -> None:
    report = status or (lambda _message: None)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    install_dir = Path(manifest["install_dir"]).resolve()
    user_data = Path(manifest["user_data"]).resolve()
    staging_app = Path(manifest["staging_app"]).resolve()
    confirmation = Path(manifest["confirmation"]).resolve()
    version = str(manifest["version"])
    token = str(manifest["token"])
    if not re.fullmatch(r"[0-9A-Za-z.-]{1,80}", version) or not token:
        raise RuntimeError("更新清单中的版本或令牌无效。")
    if user_data != (install_dir / "UserData").resolve():
        raise RuntimeError("用户数据目录不在程序目录的预期位置。")
    update_cache = (user_data / "update-cache").resolve()
    if update_cache not in staging_app.parents:
        raise RuntimeError("更新暂存目录不在受控缓存中。")
    if not staging_app.is_dir() or not (staging_app / "AliveWorld.exe").is_file():
        raise RuntimeError("更新暂存目录无效。")
    if not _wait_for_exit(int(manifest["current_pid"])):
        raise RuntimeError("AliveWorld 未能及时退出，请关闭游戏后重试。")

    backup = user_data / "update-backups" / f"before-{version}"
    if backup.exists():
        shutil.rmtree(backup)
    confirmation.unlink(missing_ok=True)
    report("正在备份当前程序……")
    # Finish a complete rollback copy before touching the running installation.
    _copy_children(install_dir, backup, exclude={"UserData"})
    try:
        report("正在安装新版本……")
        _remove_program_children(install_dir)
        _move_children(staging_app, install_dir)
        executable = install_dir / "AliveWorld.exe"
        env = dict(os.environ)
        env["ALIVEWORLD_UPDATE_TOKEN"] = token
        env["ALIVEWORLD_UPDATE_CONFIRM_PATH"] = str(confirmation)
        env["ALIVEWORLD_EXPECTED_VERSION"] = version
        process = subprocess.Popen([str(executable)], cwd=str(install_dir), env=env)
        report("正在验证新版本启动……")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if confirmation.is_file():
                try:
                    payload = json.loads(confirmation.read_text(encoding="utf-8"))
                    if payload.get("token") == token and payload.get("version") == version:
                        shutil.rmtree(backup, ignore_errors=True)
                        return
                except (OSError, json.JSONDecodeError):
                    pass
            if process.poll() is not None:
                break
            time.sleep(0.5)
        process.terminate()
        try:
            process.wait(timeout=10)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception:
                pass
        raise RuntimeError("新版本未能通过启动验证。")
    except Exception:
        report("更新失败，正在恢复旧版本……")
        _remove_program_children(install_dir)
        if backup.is_dir():
            _move_children(backup, install_dir)
        old_executable = install_dir / "AliveWorld.exe"
        if old_executable.is_file():
            subprocess.Popen([str(old_executable)], cwd=str(install_dir))
        raise


def run_update_ui(manifest_path: str) -> int:
    root = tk.Tk()
    root.title("AliveWorld 更新助手")
    root.geometry("520x210")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=26)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="正在更新 AliveWorld", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
    status_var = tk.StringVar(value="正在等待游戏退出……")
    ttk.Label(frame, textvariable=status_var).pack(anchor="w", pady=(14, 12))
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill="x")
    progress.start(12)

    log_path = None
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        log_dir = Path(manifest["user_data"]) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"update-{manifest.get('version', 'unknown')}.log"
    except Exception:
        pass

    def publish(message: str) -> None:
        root.after(0, status_var.set, message)
        if log_path:
            try:
                with log_path.open("a", encoding="utf-8") as output:
                    output.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
            except OSError:
                pass

    def worker() -> None:
        try:
            apply_update(manifest_path, publish)
            publish("更新成功，新版本已经启动。")
            root.after(0, root.destroy)
        except Exception as exc:
            publish(f"更新失败：{exc}")
            if log_path:
                try:
                    with log_path.open("a", encoding="utf-8") as output:
                        output.write(traceback.format_exc())
                except OSError:
                    pass
            root.after(0, progress.stop)
            root.after(0, messagebox.showerror, "AliveWorld 更新失败", f"{exc}\n\n已尝试恢复旧版本。")
            root.after(0, root.destroy)

    threading.Thread(target=worker, name="aliveworld-updater", daemon=True).start()
    root.mainloop()
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("AliveWorld 更新助手", "请在 AliveWorld 的“关于与更新”中点击一键更新。")
        root.destroy()
        raise SystemExit(0)
    raise SystemExit(run_update_ui(sys.argv[1]))
