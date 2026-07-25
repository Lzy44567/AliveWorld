"""Native desktop shell for the local AliveWorld web application."""

from __future__ import annotations

from pathlib import Path
from typing import Callable


LOADING_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      color: #dbeafe; background:
        radial-gradient(circle at 50% 35%, #164e63 0, #0f172a 34%, #020617 78%);
      font: 16px "Microsoft YaHei UI", "Segoe UI", sans-serif;
    }
    main { text-align: center; }
    .world {
      width: 76px; height: 76px; margin: 0 auto 24px; border-radius: 50%;
      border: 4px solid #22d3ee; box-shadow: 0 0 36px #22d3ee55;
      position: relative; animation: pulse 1.8s ease-in-out infinite;
    }
    .world::before, .world::after {
      content: ""; position: absolute; inset: 12px -11px; border: 2px solid #34d399;
      border-radius: 50%; transform: rotate(25deg);
    }
    .world::after { transform: rotate(-25deg); }
    h1 { margin: 0 0 10px; letter-spacing: .16em; color: #5eead4; }
    p { margin: 0; color: #94a3b8; min-height: 24px; }
    .progress {
      width: min(360px, 70vw); height: 7px; margin: 22px auto 0;
      overflow: hidden; border-radius: 999px; background: #1e293b;
      box-shadow: inset 0 0 0 1px #334155;
    }
    .progress::after {
      content: ""; display: block; width: 38%; height: 100%; border-radius: inherit;
      background: linear-gradient(90deg, #22d3ee, #34d399);
      animation: loading 1.25s ease-in-out infinite;
    }
    @keyframes pulse { 50% { transform: scale(1.06); opacity: .78; } }
    @keyframes loading {
      from { transform: translateX(-110%); }
      to { transform: translateX(290%); }
    }
  </style>
</head>
<body><main>
  <div class="world"></div>
  <h1>ALIVEWORLD</h1>
  <p id="status">正在准备用户数据……</p>
  <div class="progress" role="progressbar" aria-label="启动进度"></div>
</main>
<script>
  window.setAliveWorldStatus = function (message) {
    document.getElementById("status").textContent = message;
  };
</script>
</body>
</html>
"""


def show_desktop_window(
    bootstrap: Callable[[object], None],
    *,
    storage_path: Path,
) -> None:
    import webview

    window = webview.create_window(
        "AliveWorld",
        html=LOADING_HTML,
        width=1440,
        height=900,
        min_size=(1024, 720),
        background_color="#0f172a",
    )

    def start_backend() -> None:
        bootstrap(window)

    webview.start(
        start_backend,
        gui="edgechromium",
        debug=False,
        private_mode=False,
        storage_path=str(storage_path),
    )
