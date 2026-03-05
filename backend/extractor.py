"""AI key-information extraction using DashScope (Tongyi Qianwen)."""
import json
import os

from dashscope import Generation

_PROMPT = """你是一名专业的简历解析器。请从下面的简历文本中提取关键信息。
只返回一个合法的 JSON 对象，不要有任何其他文字，包含以下字段（找不到的字段填 null）：
{{
  "name": "姓名",
  "phone": "电话",
  "email": "邮箱",
  "address": "地址",
  "job_intent": "求职意向",
  "expected_salary": "期望薪资",
  "work_years": "工作年限",
  "education": "学历背景（学校/专业/学历/时间）",
  "skills": ["技能1", "技能2"],
  "project_experience": ["项目1简述", "项目2简述"]
}}

简历文本：
{resume_text}
"""


def extract_key_info(resume_text: str) -> dict:
    """Call qwen-plus to extract structured resume fields."""
    api_key = os.environ.get("ALI_API_KEY", "")
    if not api_key:
        return {"error": "ALI_API_KEY 环境变量未设置", "parse_error": True}

    prompt = _PROMPT.format(resume_text=resume_text[:4000])
    response = Generation.call(
        api_key=api_key,
        model="qwen-plus",
        messages=[{"role": "user", "content": prompt}],
        result_format="message",
    )

    # Check for API errors
    if response.status_code != 200:
        return {
            "error": f"DashScope API 错误: {response.status_code} - {response.code or ''}",
            "message": response.message or "",
            "parse_error": True,
        }

    if not response.output or not response.output.choices:
        return {"error": "DashScope 返回空响应", "parse_error": True}

    content = response.output.choices[0].message.content.strip()
    content = _strip_fences(content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_response": content, "parse_error": True}


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that LLMs sometimes add."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()
