"""Explicit workshop request: evidence to editable character draft, never save."""
import json
from core.ai_engine import robust_json_parse
from core.character_extraction import prepare_character_card

SYSTEM_PROMPT = '''你是人物整理工坊，不续写故事。根据用户选定人物、原人设与公开回合整理可编辑角色卡。
身份ID与别名确定对象，不要合并同名人物。原稿明确设定优先；一次行为不证明永久性格。
短期伤势、情绪、地点不写成人格。示例对白仅作为表达示例，不是新世界已发生的事实。
经历只记录此角色本人经历或明确获知的内容，玩家看到不等于角色知道。不推断幕后秘密。
不确定的人格或知情写入notes供用户审阅，不补造事实。历史关系是来源世界关系，不自动映射目标世界同名人物。
返回JSON：{"profile":{"description":"身份与稳定设定","appearance":"外观","personality":"性格","dialogue_examples":"言行示例","starting_scene":""},"experiences":"可选旧世界经历摘要","notes":"推断与不确定之处"}。
不输出文件路径、API密钥、内部账本或整份原文。经历与人设分开，不把旧回合塞进人设以绕过经历开关。'''


def extract_character(engine, *, subject, profile, evidence, instruction=''):
    payload = dict(subject=subject, profile=profile, evidence=evidence, instruction=instruction)
    raw, error = engine.chat_json(SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False),
                                  temp=0.3, trace_label='角色提取工坊')
    if error or not raw:
        raise ValueError(f'人物整理请求失败：{error or "空返回"}')
    result = robust_json_parse(raw)
    if not isinstance(result, dict) or not isinstance(result.get('profile'), dict):
        raise ValueError('人物整理需要返回人设对象，请重试；来源未修改')
    for key in ('experiences', 'notes'):
        if not isinstance(result.get(key), str):
            raise ValueError(f'人物整理的{key}必须是文本')
    return {'profile': prepare_character_card(result['profile'], subject['name']),
            'experiences': result['experiences'], 'notes': result['notes']}
