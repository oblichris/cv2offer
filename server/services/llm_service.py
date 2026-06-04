from __future__ import annotations

import os
from typing import Any

import httpx
from server.config import env_bool, load_environment


class ProviderConfigError(RuntimeError):
    pass


def get_llm_config() -> dict[str, str | bool]:
    load_environment()
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    mock = env_bool("CV2OFFER_MOCK", False)
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not mock and provider == "deepseek" and not api_key:
        raise ProviderConfigError("Missing DEEPSEEK_API_KEY. Set CV2OFFER_MOCK=1 for mock mode.")
    return {
        "provider": provider,
        "api_key": api_key,
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        "mock": mock,
    }


def chat_completion(messages: list[dict[str, str]], max_tokens: int = 700) -> str:
    config = get_llm_config()
    if config["mock"]:
        user_text = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return f"[mock llm] 回答亮点：结构清楚，能贴合岗位。改进建议：补一个量化结果或具体项目例子。\n\n输入摘要：{user_text[:120]}"
    response = httpx.post(
        f"{config['base_url']}/chat/completions",
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        json={
            "model": config["model"],
            "messages": messages,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return payload["choices"][0]["message"]["content"].strip()


def generate_text(prompt: str) -> str:
    return chat_completion([{"role": "user", "content": prompt}])


def review_interview_answer(question: str, answer: str, context: dict[str, str] | None = None) -> str:
    context = context or {}
    messages = [
        {
            "role": "system",
            "content": (
                "你是一位资深面试教练。请基于候选人的目标JD、简历和QA准备，"
                "点评候选人的回答。输出三段：亮点、可改进、建议改写。保持专业友好。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"目标JD：\n{context.get('jd', '')[:2000]}\n\n"
                f"简历：\n{context.get('resume', '')[:2000]}\n\n"
                f"QA准备：\n{context.get('qa', '')[:1500]}\n\n"
                f"面试题：{question}\n\n候选人回答：{answer}"
            ),
        },
    ]
    return chat_completion(messages, max_tokens=600)


def generate_answer_hint(question: str, context: dict[str, str] | None = None) -> str:
    context = context or {}
    messages = [
        {
            "role": "system",
            "content": (
                "你是实时面试辅助助手。请基于候选人的JD、简历和QA，给出可以直接开口说的回答提示。"
                "控制在120-220字，结构清晰，不要编造经历。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"JD：\n{context.get('jd', '')[:1800]}\n\n"
                f"简历：\n{context.get('resume', '')[:1800]}\n\n"
                f"QA：\n{context.get('qa', '')[:1200]}\n\n"
                f"面试官问题：{question}"
            ),
        },
    ]
    return chat_completion(messages, max_tokens=500)
