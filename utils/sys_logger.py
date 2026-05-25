# utils/sys_logger.py
import logging, os, re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

_current_log_file = None

class CustomFormatter(logging.Formatter):
    def format(self, record):
        icon = "ℹ️"
        if record.levelno == logging.WARNING: icon = "⚠️"
        elif record.levelno >= logging.ERROR: icon = "❌"
        elif record.levelno == logging.DEBUG: icon = "✅"
        time_str = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]
        module_name = getattr(record, 'module_name', record.module) 
        return f"[{time_str}] {icon} [{module_name}] {record.getMessage()}"

def init_logger(log_filename):
    global _current_log_file
    _current_log_file = log_filename
    logger = logging.getLogger("AliveWorld")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(log_filename, encoding='utf-8')
    handler.setFormatter(CustomFormatter())
    logger.addHandler(handler)
    logger.propagate = False 
    return logger

def get_logger(): return logging.getLogger("AliveWorld")

def read_logs_parsed():
    global _current_log_file
    if _current_log_file and os.path.exists(_current_log_file):
        try:
            with open(_current_log_file, 'r', encoding='utf-8') as f: lines = f.readlines()
            parsed = []
            pattern = r"^\[(.*?)\]\s+(.*?)\s+\[(.*?)\]\s+(.*)$"
            for line in lines:
                match = re.match(pattern, line.strip())
                if match: parsed.append({"time": match.group(1), "icon": match.group(2), "module": match.group(3), "message": match.group(4)})
                else:
                    if parsed: parsed[-1]["message"] += f"<br>{line.strip()}"
            return parsed
        except Exception as e: return [{"time": "", "icon": "❌", "module": "Sys", "message": f"日志解析失败: {e}"}]
    return [{"time": "", "icon": "⚠️", "module": "Sys", "message": "暂无日志"}]