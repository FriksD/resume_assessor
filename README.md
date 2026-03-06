# AI 简历洞察系统（Resume AI Analytics）

一个基于 AI 的智能简历洞察与分析系统。系统支持无缝上传 PDF 简历、智能提取核心关键档案信息，并能够基于自定义或目标岗位需求（JD）提供深度的双向匹配度综合评估。

目前项目采用极简、云原生的 Serverless 架构：后端无框架且零依赖部署在**阿里云函数计算（FC 3.0）**，前端则是采用现代化视觉设计、基于 Tailwind CSS 原生构建的单页面应用，托管于 **GitHub Pages**。

## 🌟 在线体验

- **前端访问地址**：[`https://friksd.github.io/resume-assessor/frontend`](https://friksd.github.io/resume-assessor/frontend)

---

## 🏗 项目架构与体系

系统整体结构极具轻量化，并在近期经历了深度的重构升级：

```text
resume-assessor/
├── backend/
│   ├── app.py           # 阿里云 FC3 裸函数入口 & 本地原生 HTTP 开发服务器
│   ├── parser.py        # PDF 解析与文本清洗（依赖 pdfplumber）
│   ├── extractor.py     # AI 高级关键信息提取（接入通义千问 qwen-plus）
│   ├── scorer.py        # 提供基于大模型的 AI 简历 × 岗位（JD）匹配评分体系
│   ├── cache.py         # 内存轻量级缓存（基于 MD5 Hash 文件指纹）
│   ├── requirements.txt # 去除了 Flask 等冗余依赖，仅保留核心 AI 库
│   └── s.yaml           # Serverless Devs 一键部署配置文件
├── frontend/
│   └── index.html       # 极致美感的前端单文件（基于 Tailwind CSS CDN + 原生 JS，新增交互动效与圆环进度反馈）
└── README.md
```

### 💻 核心技术栈

| 层次 | 技术选型 |
|------|------|
| **后端运行层** | Python 3.10 原生 |
| **PDF 解析引擎** | pdfplumber |
| **AI 大语言模型** |  **MiniMax-M2.5**  |
| **缓存机制** | 进程内原生大字典（文件 MD5 Hash 键，FIFO 淘汰，上限 500） |
| **云端基础设施** | 阿里云函数计算 FC 3.0（HTTP 无服务器触发器） |
| **前端应用化** | HTML5 + Tailwind CSS CDN + 原生原生 JavaScript ES6 |
| **前端静态托管** | GitHub Pages CDN |

---

## ⚡ API 接口说明

> API 采用 FC Native HTTP Handler 协议进行响应与路由分发。

### `GET /health`
系统存活探针与健康检查，极速返回可用状态。

**响应：** `{"status": "ok"}`

---

### `POST /parse`
上传并解码 PDF 格式简历，通过 AI 引擎结构化其核心经历和技能。

**请求类型：** `multipart/form-data`，携带表单字段 `file`（传入 PDF 附件）。

**响应示例：**
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
    "project_experience": [
       {"project_name": "电商平台后端开发", "duration": "2020-2022", "details": ["负责订单系统微服务拆分"]}
    ],
    "internship_experience": [
       {"project_name": "某一线大厂实习", "duration": "2019-2020", "details": ["参与基础架构组件开发"]}
    ],
    "campus_experience": [
       {"project_name": "校学生会技术部理事", "duration": "2016-2018", "details": ["负责校园官网维护"]}
    ],
    "skills": ["Python", "Java", "Docker"],
    "awards": ["优秀员工", "蓝桥杯一等奖"]
  }
}
```

---

### `POST /score`
引入已缓存的被解析简历内容，结合目标公司/岗位的真实痛点进行全方位 AI 评分诊断。

**请求类型：** `application/json`
```json
{
  "file_hash": "d41d8cd98f00b204e9800998ecf8427e",
  "job_description": "招聘 Python 后端工程师，要求 Flask、Redis、云平台经验…"
}
```

**响应示例：**
```json
{
  "score": 82,
  "matched_keywords": ["Python", "Flask", "Redis"],
  "missing_keywords": ["Kubernetes", "Kafka"],
  "summary": "候选人核心技能与岗位高度匹配，基础扎实，但在容器编排和消息队列底层原理相关经验略显薄弱。"
}
```

---

## 🚀 性能与缓存设计升级

本项目在最近一次迭代去除了重型 Web 框架的支持，并优化内存交互逻辑：
- **缓存追踪键**：被提取 PDF 文件的纯净文件流 `MD5 哈希`
- **生命周期机制**：伴随 FC 进程的生成与实例回收，确保冷热数据的自然更替
- **降本增效**：原生函数处理降低了服务冷启动加载的内存损耗与时间延长

---

## 🛠 后续优化方向

- **多模态与多格式支持**：扩展支持解析 Word (.docx)、图片类简历及扫描件 PDF（引入 OCR 能力），覆盖更多样化的简历投递场景。
- **前端工程化升级**：将现有单页面前端重构为 **React** 工程化项目，便于进行组件化开发与复杂交互逻辑的后续拓展。

