# core/session_manager.py
from typing import Dict
from core.game_session import GameSession

# 全局存储所有正在运行的沙盒推演实例
active_sessions: Dict[str, GameSession] = {}