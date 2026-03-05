# AI Resume Assessor（AI 简历评估系统）

一个基于 AI 的智能简历分析系统，支持 PDF 简历上传、关键信息提取、岗位匹配评分，后端部署在阿里云函数计算（FC），前端部署在 GitHub Pages。

## 在线体验

- **前端页面**：`https://friksd.github.io/resume-assessor/frontend`

---

## 项目架构

```
resume-assessor/
├── backend/
│   ├── app.py           # Flask 主应用 + 阿里云 FC WSGI 入口
│   ├── parser.py        # PDF 解析与文本清洗（pdfplumber）
│   ├── extractor.py     # AI 关键信息提取（通义千问 qwen-plus）
│   ├── scorer.py        # AI 简历 × 岗位匹配评分
│   ├── cache.py         # 内存缓存（MD5 键）
│   ├── requirements.txt
│   └── s.yaml           # Serverless Devs 部署配置
├── frontend/
│   └── index.html       # 单文件前端（Tailwind CDN + 原生 JS）
└── README.md
```

### 技术选型

| 层次 | 技术 |
|------|------|
| 后端框架 | Python 3.10 + Flask 3.0 |
| PDF 解析 | pdfplumber |
| AI 模型 | 通义千问 qwen-plus（阿里云 DashScope） |
| 缓存 | 进程内字典（MD5 键，FIFO 淘汰） |
| 运行环境 | 阿里云函数计算 FC（HTTP 触发器） |
| 前端 | HTML5 + Tailwind CSS CDN + 原生 JS |
| 前端托管 | GitHub Pages |

---

## API 接口说明

### `GET /health`
健康检查。

**响应：** `{"status": "ok"}`

---

### `POST /parse`
上传 PDF 简历，提取文本与关键信息。

**请求：** `multipart/form-data`，字段名 `file`（PDF 文件）

**响应：**
```json
{
  "file_hash": "d41d8cd98f00b204e9800998ecf8427e",
  "cache_hit": false,
  "raw_text": "张伟\n...",
  "extracted": {
    "name": "张伟",
    "phone": "138-0000-0000",
    "email": "zhangwei@example.com",
    "address": "北京市海淀区",
    "job_intent": "后端工程师",
    "expected_salary": "25k-30k",
    "work_years": "5年",
    "education": "清华大学 计算机科学 本科 2015-2019",
    "project_experience": ["电商平台后端开发 (2020-2022)", "实时数据管道 (2022-至今)"],
    "skills": ["Python", "Java"]
  }
}
```

---

### `POST /score`
将已解析简历与岗位需求进行 AI 匹配评分。

**请求：** `application/json`
```json
{
  "file_hash": "d41d8cd98f00b204e9800998ecf8427e",
  "job_description": "招聘 Python 后端工程师，要求 Flask、Redis、云平台经验…"
}
```

**响应：**
```json
{
  "score": 82,
  "matched_keywords": ["Python", "Flask", "Redis"],
  "missing_keywords": ["Kubernetes", "Kafka"],
  "summary": "候选人核心技能与岗位高度匹配，缺少容器编排和消息队列相关经验。"
}
```


---

## 缓存设计

- **缓存键**：PDF 文件内容的 MD5 哈希
- **缓存内容**：`{raw_text, extracted}`（解析结果）
- **存储位置**：FC 实例进程内存（dict）
- **淘汰策略**：超过 500 条时 FIFO 移除最早条目
- **生命周期**：与 FC 实例同生命周期（实例回收即清除）
- **生产升级路径**：将 `cache.py` 中的 `get_cache` / `set_cache` 替换为阿里云 Redis 调用即可

---


