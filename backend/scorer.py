"""AI-powered resume-vs-job-description scoring using DashScope."""
import json
import os

from dashscope import Generation

_PROMPT = """你是一名专业招聘顾问。请根据下方岗位需求和简历内容，分析候选人与岗位的匹配程度。
只返回一个合法的 JSON 对象，不要有任何其他文字：
{{
  "score": 整数(0-100),
  "matched_keywords": ["岗位要求中简历已具备的技能/关键词"],
  "missing_keywords": ["岗位要求中简历缺少的技能/关键词"],
  "summary": "2-3句话的总结评价"
}}

岗位需求：
{job_description}

简历内容：
{resume_text}
"""


def score_resume(resume_text: str, job_description: str) -> dict:
    """Call qwen-plus to score a resume against a job description."""
    prompt = _PROMPT.format(
        job_description=job_description[:2000],
        resume_text=resume_text[:3000],
    )
    response = Generation.call(
        api_key=os.environ.get("ALI_API_KEY", ""),
        model="qwen-plus",
        messages=[{"role": "user", "content": prompt}],
        result_format="message",
    )
    content = response.output.choices[0].message.content.strip()
    content = _strip_fences(content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "score": 0,
            "matched_keywords": [],
            "missing_keywords": [],
            "summary": content,
        }


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()
