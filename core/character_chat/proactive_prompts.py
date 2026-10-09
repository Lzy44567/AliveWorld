"""Stable proactive-contact instructions, separate from current-input replies."""
from .prompts import CORE_V3, CONTRACT_V3

CONTACT_CORE = CORE_V3 + '''\n这是一次有限主动联系规划，不是玩家新输入。仅根据正式历史、人设、世界规则和记忆判断是否有自然联系理由；没有理由可返回空计划。不能推测玩家离开原因，不能将闲置时长写成已经发生的剧情，不能伪造玩家回答或现实属性。每次联系可等待真实玩家回复，不以自问自答续写。不能引用其他尚未送达联系。'''

CONTACT_CONTRACT = '''只输出严格JSON对象 {"contacts":[{"delay_seconds":0,"reply":{...}}]}，没有其他根字段。contacts允许0至max_contacts项；delay_seconds为非负整数，按非递减顺序，相对计划保存时点，必须小于max_delay_seconds。所有联系的可见text总计不超过8000字符。reply使用下面的character.reply.v3对象规范，规范中的根字段指每个reply内部；本请求不含current_user_messages，来源仅可用history中的正式message_id和该reply本组bN，dialogue_event不得把旧历史当作本轮新事件。\n''' + CONTRACT_V3
