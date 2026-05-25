# sys_logger.py
import logging
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

current_log_file = None
_logger_initialized = False

class CustomFormatter(logging.Formatter):
    """自定义专业级日志格式 (类 ReaDreamAI 风格)"""
    def format(self, record):
        # 根据日志级别分配图标
        icon = "ℹ️"
        if record.levelno == logging.WARNING: icon = "⚠️"
        elif record.levelno >= logging.ERROR: icon = "❌"
        elif record.levelno == logging.DEBUG: icon = "✅"
        
        # 格式：[18:58:25.959] ℹ️ [模块名] 消息内容
        time_str = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]
        return f"[{time_str}] {icon} [{record.module}] {record.getMessage()}"

def get_logger():
    global current_log_file, _logger_initialized
    logger = logging.getLogger("AliveWorld")
    
    if not _logger_initialized:
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_log_file = os.path.join(LOG_DIR, f"run_{current_time}.log")
        
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        handler = logging.FileHandler(current_log_file, encoding='utf-8')
        handler.setFormatter(CustomFormatter())
        logger.addHandler(handler)
        logger.propagate = False # 防止控制台重复打印
        _logger_initialized = True
        
    return logger

def read_logs(lines=100):
    """供 UI 实时调取的读取接口"""
    if current_log_file and os.path.exists(current_log_file):
        try:
            with open(current_log_file, 'r', encoding='utf-8') as f:
                return "".join(f.readlines()[-lines:])
        except Exception as e:
            return f"读取日志失败: {str(e)}"
    return "系统启动中，暂无日志产生..."