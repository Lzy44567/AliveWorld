# schemas/api_models.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ActionRequest(BaseModel):
    action: str = Field(..., description="玩家本回合的行动文本")
    # 热插拔参数预留坑位
    override_style: Optional[str] = Field(None, description="临时替换文风卡")
    override_worldbook: Optional[str] = Field(None, description="临时替换世界书")

class TurnResultResponse(BaseModel):
    status: str = "success"
    message: str = "推演完成"
    chat_messages: List[Dict[str, Any]] = Field(default_factory=list, description="本次推演产生的新对话流")
    state_deltas: Dict[str, int] = Field(default_factory=dict, description="生命/灵力等变化量，供前端飘字")
    undercurrent_events: List[str] = Field(default_factory=list, description="暗流弹窗警告")
    triggered_entries: List[str] = Field(default_factory=list, description="触发的世界记忆词条")
    is_game_over: bool = False