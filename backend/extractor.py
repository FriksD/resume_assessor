import json
import os
from typing import Any

from dashscope import Generation

_PROMPT = """你是一个专业的简历解析器。请从下面的简历文本中提取关键信息。只返回一个合法的 JSON 对象，不要有任何其他文字，包含以下字段（找不到的字段填 null）：
{{
  "name": "姓名",
  "phone": "电话",
  "email": "邮箱",
  "address": "地址",
  "job_intent": "求职意向",
  "expected_salary": "期望薪资",
  "work_years": "工作年限",
  "education": "教育背景（学校/专业/学历/时间）",
  "skills": ["技能1", "技能2"],
  "awards": ["所获奖项1"],
  "project_experience": [
    {{
      "project_name": "项目名称",
      "duration": "持续时间",
      "details": ["具体经历1", "具体经历2"]
    }}
  ],
  "internship_experience": [
    {{
      "project_name": "实习公司/岗位名称",
      "duration": "持续时间",
      "details": ["具体经历1", "具体经历2"]
    }}
  ],
  "campus_experience": [
    {{
      "project_name": "在校经历名称",
      "duration": "持续时间",
      "details": ["具体经历1", "具体经历2"]
    }}
  ]
}}

要求：
- `project_experience`、`internship_experience`、`campus_experience` 必须是数组。
- 每条经历必须包含 `project_name`、`duration`、`details` 三个字段。
- `details` 可以是字符串，也可以是字符串数组（优先数组）。
- 所获奖项不算校园经历，校园经历指的是在校期间的社团、学生会、班委等经历。

简历文本：
{resume_text}
"""


def extract_key_info(resume_text: str) -> dict:
    """调用千问，传入简历文本，返回提取的关键信息"""
    api_key = os.environ.get("ALI_API_KEY", "")
    if not api_key:
        return {"error": "ALI_API_KEY 环境变量未设置", "parse_error": True}

    prompt = _PROMPT.format(resume_text=resume_text[:4000])
    response = Generation.call(
        api_key=api_key,
        model="MiniMax-M2.5",
        messages=[{"role": "user", "content": prompt}],
        result_format="message",
    )

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
        data = json.loads(content)
        if isinstance(data, dict):
            return _normalize_experience_fields(data)
        return data
    except json.JSONDecodeError:
        return {"raw_response": content, "parse_error": True}


def _strip_fences(text: str) -> str:
    """移除文本中的md格式符号，如果有的话"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _normalize_experience_fields(data: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "project_experience": ["projects", "project", "项目经历"],
        "internship_experience": ["intern_experience", "internship", "实习经历"],
        "campus_experience": ["school_experience", "on_campus_experience", "在校经历"],
    }

    for field, field_aliases in aliases.items():
        raw_value = data.get(field)
        if raw_value is None:
            for alias in field_aliases:
                if data.get(alias) is not None:
                    raw_value = data.get(alias)
                    break
        data[field] = _normalize_experience_list(raw_value)

    raw_awards = None
    for field in ("awards", "award", "honors", "honours", "所获奖项", "获奖情况"):
        if data.get(field) is not None:
            raw_awards = data.get(field)
            break
    data["awards"] = _normalize_text_list(raw_awards)

    return data


def _normalize_experience_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []

    if isinstance(value, (str, dict)):
        value = [value]
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in value:
        record = _normalize_experience_item(item)
        if record:
            normalized.append(record)
    return normalized


def _normalize_experience_item(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        details = item.strip()
        if not details:
            return None
        return {"project_name": "", "duration": "", "details": details}

    if not isinstance(item, dict):
        return None

    project_name = (
        item.get("project_name")
        or item.get("name")
        or item.get("title")
        or item.get("project")
        or item.get("项目名称")
        or ""
    )
    duration = (
        item.get("duration")
        or item.get("period")
        or item.get("time")
        or item.get("持续时间")
        or ""
    )
    details = _normalize_details(
        item.get("details")
        or item.get("experience")
        or item.get("description")
        or item.get("content")
        or item.get("具体经历")
        or item.get("职责")
    )

    if not project_name and not duration and not details:
        return None
    return {
        "project_name": str(project_name).strip(),
        "duration": str(duration).strip(),
        "details": details,
    }


def _normalize_details(value: Any) -> str | list[str]:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return str(value).strip()


def _normalize_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
