# sys_logger.py
import logging
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

current_log_file = None
_logger_initialized = False

class CustomFormatter(logging.Formatter):
    """自定义专业级日志格式 (完美适配 UI 渲染)"""
    def format(self, record):
        icon = "ℹ️"
        if record.levelno == logging.WARNING: icon = "⚠️"
        elif record.levelno >= logging.ERROR: icon = "❌"
        elif record.levelno == logging.DEBUG: icon = "✅"
        
        time_str = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]
        # 支持通过 extra={'module_name': '自定义模块'} 传入模块名
        module_name = getattr(record, 'module_name', record.module) 
        return f"[{time_str}] {icon} [{module_name}] {record.getMessage()}"

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
        logger.propagate = False 
        _logger_initialized = True
        
    return logger

def read_logs_parsed():
    """将文本日志反向解析为字典列表，供全屏日志 UI 渲染"""
    if current_log_file and os.path.exists(current_log_file):
        try:
            with open(current_log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            parsed = []
            # 正则匹配形如: [18:58:25.959] ℹ️ [模块名] 消息内容
            pattern = r"^\[(.*?)\]\s+(.*?)\s+\[(.*?)\]\s+(.*)$"
            for line in lines:
                match = re.match(pattern, line.strip())
                if match:
                    parsed.append({
                        "time": match.group(1),
                        "icon": match.group(2),
                        "module": match.group(3),
                        "message": match.group(4)
                    })
                else:
                    # 处理带换行符的长日志 (如 JSON 或报错堆栈)
                    if parsed:
                        parsed[-1]["message"] += f"<br>{line.strip()}"
            return parsed
        except Exception as e:
            return [{"time": "", "icon": "❌", "module": "Sys", "message": f"日志解析失败: {e}"}]
    return []