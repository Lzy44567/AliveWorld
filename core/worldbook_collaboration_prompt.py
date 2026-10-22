"""Optional, compact contract for conflicts found during normal settlement."""

CONFLICT_INSTRUCTION = """【多世界书协作】
主世界书规定世界规则，补充知识书不能覆盖它；不同区域/条件的规则可共存，不因题材不同就判冲突。
仅当本次给出的资料在同一适用范围有互斥规则时，正文按主书推进，并在JSON中附worldbook_conflicts数组（最多8项）。
每项：{"keep":"主书资料的引用ID","disable":"次书具体条目的引用ID","keep_quote":"主书原文片段","disable_quote":"次书原文片段","scope":"重叠的具体适用范围","reason":"为什么不能同时成立"}。
只能引用本次提供的ID和原文，不报告未检索内容；不能停用概述、公理或主书条目。同书区域差异按适用范围处理，不输出停用。
没有明确冲突就省略此字段。程序负责本局处理，你不删除资产、不改写历史，也不在叙事中暴露隐藏设定。"""
