# AI Resume Assessor（AI 简历评估系统）

一个基于 AI 的智能简历分析系统，支持 PDF 简历上传、关键信息提取、岗位匹配评分，后端部署在阿里云函数计算（FC），前端部署在 GitHub Pages。

## 在线体验

- **前端页面**：`https://<your-username>.github.io/resume-assessor/`
- **API 地址**：`https://<your-fc-domain>/`

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

## 本地运行

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 设置 DashScope API Key
export DASHSCOPE_API_KEY=sk-xxxxx

# 3. 启动 Flask 开发服务器
python app.py
# 服务运行在 http://localhost:5000

# 4. 打开前端页面（本地验证）
# 修改 frontend/index.html 中的 API_BASE 为 http://localhost:5000
# 然后直接用浏览器打开 frontend/index.html
```

---

## 部署说明

### A. 后端 → 阿里云函数计算 FC

**前提条件：**
- 阿里云账号，已开通函数计算服务
- RAM 用户，具备 FC、OSS 相关权限
- [通义千问 DashScope API Key](https://dashscope.aliyun.com/)

```bash
# 1. 安装 Serverless Devs CLI
npm install -g @serverless-devs/s

# 2. 配置阿里云凭据
s config add \
  --AccountID <your-account-id> \
  --AccessKeyID <your-access-key-id> \
  --AccessKeySecret <your-access-key-secret> \
  -a default

# 3. 设置 DashScope API Key（部署时注入为环境变量）
export DASHSCOPE_API_KEY=sk-xxxxx
# Windows: set DASHSCOPE_API_KEY=sk-xxxxx

# 4. 部署
cd backend
s deploy --use-local -y

# 5. 部署成功后记录输出的自定义域名，例如：
#    http://resume-assessor.cn-hangzhou.fcapp.run

# 6. 验证
curl http://resume-assessor.cn-hangzhou.fcapp.run/health
# 预期：{"status":"ok"}
```

---

### B. 前端 → GitHub Pages

```bash
# 1. 修改 frontend/index.html 第 96 行的 API_BASE：
#    const API_BASE = 'http://resume-assessor.cn-hangzhou.fcapp.run';

# 2. 在 GitHub 创建公开仓库（名称如 resume-assessor）

# 3. 推送前端文件
cd frontend
git init
git add index.html
git commit -m "feat: initial frontend deploy"
git branch -M main
git remote add origin https://github.com/<your-username>/resume-assessor.git
git push -u origin main

# 4. 开启 GitHub Pages
#    仓库 Settings → Pages → Source: Deploy from branch
#    Branch: main，文件夹: / (root) → Save

# 5. 约 1-2 分钟后访问：
#    https://<your-username>.github.io/resume-assessor/
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

## 错误处理

| 情形 | HTTP 状态 | 说明 |
|------|-----------|------|
| 未上传文件 | 400 | `{"error": "No file provided"}` |
| 非 PDF 格式 | 400 | `{"error": "Only PDF files are supported"}` |
| 扫描件/无文字 PDF | 422 | `{"error": "Could not extract text from PDF"}` |
| AI 返回非 JSON | 200 | 降级返回 `{"raw_response": "...", "parse_error": true}` |
| `file_hash` 不在缓存 | 404 | 提示用户重新上传解析 |

---

## Git 提交规范

本项目使用 Conventional Commits 规范：

```
feat:   新增功能
fix:    Bug 修复
docs:   文档更新
refactor: 代码重构（不影响功能）
chore:  构建/工具相关
```
