"""Agent 决策辅助：提示词构造、JSON 解析、问题检测。"""

from __future__ import annotations

import json
import re


def is_question(text: str) -> bool:
    """粗略判断一段文本是否为提问，用于决定是否值得回复。"""
    if "?" in text or "？" in text:
        return True
    keywords = ("请问", "请告诉我", "是什么", "怎么", "为什么", "能否", "请确认", "接口", "地址", "参数", "返回结构")
    return any(k in text for k in keywords)


def extract_json(text: str) -> dict | None:
    """从模型输出中尽可能提取一个 JSON 对象。

    优先找代码块 / 方括号包裹的 json，其次尝试全文 json.loads。
    解析失败返回 None（由调用方做兜底）。
    """
    if not text:
        return None
    text = text.strip()
    # 去掉 markdown 代码块围栏
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
    candidates = fenced if fenced else [text]
    for cand in candidates:
        cand = cand.strip()
        try:
            return json.loads(cand)
        except Exception:
            # 尝试截取第一个 { 到最后一个 }
            start, end = cand.find("{"), cand.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(cand[start : end + 1])
                except Exception:
                    continue
    return None


def fail_msg(msg: str) -> str:
    """把 JSON 计划的失败信息转为友好文本。"""
    return f"[规划失败] {msg}"