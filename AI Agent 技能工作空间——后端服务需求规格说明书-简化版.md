# AI Agent 技能工作空间——后端服务需求规格说明书（简化版 · Demo）

**版本**：1.0  
**日期**：2026-05-09  
**状态**：Demo 开发用 · 仅核心功能

> 本文档是[完整版需求规格说明书]的精简版本，仅包含 Demo 阶段所需的核心功能：工作空间、Skill 管理、工具调用、Agent 对话。权限系统、上下文压缩、记忆系统、任务管理、成本控制等高级功能不在本版本范围内。

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 术语定义](#2-术语定义)
- [3. 用户与认证](#3-用户与认证)
- [4. 工作空间](#4-工作空间)
- [5. Skill 系统](#5-skill-系统)
- [6. 工具系统](#6-工具系统)
- [7. Agent 对话引擎](#7-agent-对话引擎)
- [8. 大模型接入](#8-大模型接入)
- [9. 流式输出](#9-流式输出)
- [10. 错误处理](#10-错误处理)
- [11. 数据模型](#11-数据模型)
- [12. API 端点](#12-api-端点)
- [13. 实施建议](#13-实施建议)

---

## 1. 项目概述

### 1.1 目标

构建一个 AI Agent 技能工作空间的 **Demo 后端服务**，实现以下核心流程：

```
用户注册/登录 → 上传 Skill → 创建会话 → 发送消息
  → 后端加载 Skill + 工具 → 调用 LLM → LLM 自主选择调用工具
  → 流式返回结果
```

### 1.2 Demo 范围

| 包含 | 不包含（后续版本） |
|------|-------------------|
| 用户注册/登录（JWT） | 权限系统（所有调用自动允许） |
| 私有/公共 Skill 管理 | 上下文压缩 |
| 会话与 Skill 激活 | 记忆系统 |
| 6 个内置工具 + Skill 工具 | 任务管理 |
| SSE 流式对话 | 成本控制/配额 |
| 基本错误处理 | 结构化输出 / 重试机制 |

### 1.3 技术选型建议

| 层面 | 建议技术 |
|------|----------|
| 运行时 | Node.js + TypeScript 或 Python (FastAPI) |
| 数据库 | PostgreSQL 或 SQLite (Demo 够用) |
| LLM 调用 | 直接 HTTP 调用本地推理服务（OpenAI 兼容 API） |
| 流式 | SSE (Server-Sent Events) |
| Skill 存储 | 文件系统（每个 Skill 一个文件夹） |

---

## 2. 术语定义

| 术语 | 定义 |
|------|------|
| **工作空间** | 用户的数据隔离区，1:1 绑定用户 |
| **Skill** | 包含 `SKILL.md` 的文件夹，定义一项可被 Agent 调用的技能 |
| **工具** | Agent 可调用的能力单元，包括内置工具和 Skill 注册的工具 |
| **Agent** | LLM + 工具系统的自主决策体 |
| **会话** | 一次完整对话，绑定激活的 Skill 集合 |

---

## 3. 用户与认证

- JWT 鉴权，所有 API（除注册/登录外）需携带 `Authorization: Bearer <token>`
- 注册：`POST /auth/register`（`username` + `password`）
- 登录：`POST /auth/login`，返回 `access_token` + `refresh_token`
- Access Token 有效期 2 小时

---

## 4. 工作空间

- 用户注册时自动创建工作空间，1:1 绑定。
- 工作空间下包含：私有 Skill、会话、对话历史。

---

## 5. Skill 系统

### 5.1 Skill 格式

每个 Skill 是一个文件夹，核心文件为 `SKILL.md`：

```markdown
---
name: code-reviewer
description: Review code for bugs, security issues, and style problems. Use when the user asks to review or check code.
---

# Code Reviewer

## Instructions
1. Read the target file(s)
2. Check for: bugs, security issues, style problems, performance concerns
3. Report findings with severity levels
4. Suggest fixes
```

- `name`（必填）— Skill 唯一标识
- `description`（必填）— 供 LLM 理解何时调用此 Skill
- Markdown 正文 — 完整指令

### 5.2 Skill 分类

| 类型 | 归属 | 可见性 |
|------|------|--------|
| 私有 Skill | 单个用户 | 仅创建者 |
| 公共 Skill | 无所有者（记录上传者） | 所有人 |

### 5.3 Skill 注册为工具

会话创建时，所有激活的 Skill 被注册为独立工具：

- 工具名 = Skill 的 `name`
- 工具描述 = Skill 的 `description`
- 调用时加载完整 `SKILL.md` 内容返回给 LLM

---

## 6. 工具系统

### 6.1 工具接口

所有工具遵循统一接口：

```
Tool {
  name: string               // 唯一名称（LLM 通过此名调用）
  description: string        // LLM 可读的用途说明
  inputSchema: object        // 输入参数 JSON Schema
  execute(input, context): Promise<ToolResult>
    → 执行工具并返回结果
}

ToolResult {
  content: string | object   // 返回给 LLM 的内容
  isError?: boolean          // 是否执行失败
}
```

### 6.2 Demo 阶段内置工具

| 工具名 | 功能 | 关键参数 |
|--------|------|----------|
| `read_file` | 读取文件 | `file_path`, `offset?`, `limit?` |
| `write_file` | 写入/创建文件 | `file_path`, `content` |
| `execute_python` | 执行 Python 代码 | `code`, `timeout?` |
| `execute_bash` | 执行 Shell 命令 | `command`, `timeout?` |
| `web_fetch` | 获取 URL 内容 | `url` |
| `web_search` | 网络搜索 | `query` |

> Demo 阶段不实现沙箱隔离，`execute_python` 和 `execute_bash` 直接在服务端执行。生产环境必须加沙箱。

### 6.3 工具调用流程

```
1. LLM 响应包含 tool_use 块
2. 后端解析 tool_use → 匹配工具 → 校验参数
3. 执行工具 → 获取结果
4. 将 tool_result 追加到消息历史
5. 再次调用 LLM（带工具结果）
6. 重复直到 LLM 返回纯文本（无 tool_use）
```

---

## 7. Agent 对话引擎

### 7.1 会话创建

- 用户创建会话时指定 `title` 和 `activated_skill_ids`
- 激活的 Skill 在创建后不可变更（Demo 简化）

### 7.2 消息处理流程

```
POST /conversations/{id}/messages
  { content: "帮我用 code-reviewer 检查 src/app.ts" }

→ 1. 构建消息列表: system_prompt + history + 新消息
→ 2. 构建工具列表: 内置工具 + 激活 Skill 工具
→ 3. POST /v1/chat/completions（携带 tools 定义）
→ 4. 流式读取响应（SSE 转发给前端）
→ 5. 检测 tool_use → 执行工具 → 追加 tool_result → 回到步骤 3
→ 6. LLM 返回最终文本 → 发送 done 事件
```

### 7.3 System Prompt 构建

```
你是 AI Agent，可以调用工具完成用户的任务。

当前可用的工具由系统提供，你可以根据需要选择合适的工具。

Skill 工具对应特定的技能，调用后会返回技能指令，请严格遵循。
```

### 7.4 工具调用上限

- 单轮对话最多 20 次工具调用（防止死循环）
- 超过上限返回 `MAX_TOOL_CALLS_REACHED`

---

## 8. 大模型接入

- 模型为**本地部署**（vLLM / Ollama / 其他兼容框架）
- 调用格式：**OpenAI 兼容 API**（`/v1/chat/completions`）
- 支持 `tools` 参数（tool calling）
- 支持 `stream: true`（SSE 流式）
- 模型列表配置在服务端，前端通过 `model_id` 选择

---

## 9. 流式输出

### 9.1 协议

- **SSE** (Server-Sent Events)
- 连接：`POST /conversations/{id}/messages`（`Accept: text/event-stream`）

### 9.2 事件类型

| 事件 | 说明 | 示例 Payload |
|------|------|-------------|
| `assistant` | LLM 文本块 | `{"type":"assistant","content":"我来帮你..."}` |
| `tool_use` | LLM 调用工具 | `{"type":"tool_use","tool_name":"read_file","input":{...}}` |
| `tool_result` | 工具执行完成 | `{"type":"tool_result","tool_name":"read_file","content":"..."}` |
| `error` | 错误 | `{"type":"error","code":"SKILL_NOT_FOUND","message":"..."}` |
| `done` | 本轮结束 | `{"type":"done","usage":{"input":123,"output":456}}` |

### 9.3 示例流

```
event: assistant
data: {"type":"assistant","content":"我先检查目标文件"}

event: tool_use
data: {"type":"tool_use","tool_name":"read_file","input":{"file_path":"src/app.ts"}}

event: tool_result
data: {"type":"tool_result","tool_name":"read_file","content":"import ...\n..."}

event: assistant
data: {"type":"assistant","content":"发现以下问题:\n1. ..."}

event: done
data: {"type":"done","usage":{"input_tokens":500,"output_tokens":200}}
```

---

## 10. 错误处理

### 10.1 非流式接口错误格式

```json
{
  "error": {
    "code": "SKILL_NOT_FOUND",
    "message": "Skill 不存在"
  }
}
```

### 10.2 流式接口错误

```
event: error
data: {"type":"error","code":"MODEL_UNAVAILABLE","message":"模型推理服务不可达"}
```

### 10.3 常见错误码

| 错误码 | 说明 |
|--------|------|
| `AUTH_FAILED` | 认证失败 |
| `SKILL_NOT_FOUND` | Skill 不存在 |
| `SKILL_PARSE_ERROR` | SKILL.md 解析失败 |
| `MODEL_UNAVAILABLE` | 模型服务不可达 |
| `MAX_TOOL_CALLS_REACHED` | 超过最大工具调用次数 |
| `INTERNAL_ERROR` | 服务端内部错误 |

---

## 11. 数据模型

> 以下使用伪代码描述，实际建表可根据技术栈调整。

### User

```
User {
  id: UUID (PK)
  username: string (UNIQUE)
  password_hash: string
  created_at: timestamp
}
```

### Skill

```
Skill {
  id: UUID (PK)
  workspace_id: UUID? (FK → Workspace, NULL = public)
  uploader_id: UUID (FK → User)
  source: 'private' | 'public'
  name: string            // 来自 SKILL.md
  description: string     // 来自 SKILL.md
  folder_path: string     // 服务器存储路径
  created_at: timestamp
}
```

### Conversation

```
Conversation {
  id: UUID (PK)
  workspace_id: UUID (FK → Workspace)
  title: string
  activated_skill_ids: UUID[]  // 激活的 Skill ID 列表
  model_id: string
  created_at: timestamp
}
```

### Message

```
Message {
  id: UUID (PK)
  conversation_id: UUID (FK → Conversation)
  role: 'user' | 'assistant' | 'system'
  content: text
  tool_calls?: [{
    tool_name: string
    input: object
    output?: string
    is_error?: boolean
  }]
  created_at: timestamp
}
```

### ModelConfig（配置表）

```
ModelConfig {
  id: string (PK, model_id)
  display_name: string
  api_endpoint: string           // 推理服务地址
  context_window: int
  max_output_tokens: int
  supports_tool_calling: boolean
  is_active: boolean
}
```

---

## 12. API 端点

所有 API 前缀：`/api/v1`

### 12.1 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/auth/register` | 注册 `{ username, password }` |
| `POST` | `/auth/login` | 登录，返回 `{ access_token, refresh_token }` |

### 12.2 Skill 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/skills` | 列出我的私有 Skill |
| `POST` | `/skills/upload` | 上传 Skill（multipart: `file` = SKILL.md, 可选 `resources` 为 zip） |
| `GET` | `/skills/{id}` | Skill 详情 |
| `DELETE` | `/skills/{id}` | 删除私有 Skill |
| `GET` | `/skills/public` | 列出所有公共 Skill |
| `POST` | `/skills/public/upload` | 上传公共 Skill |
| `GET` | `/skills/{id}/content` | 获取 SKILL.md 完整内容 |

### 12.3 会话

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/conversations` | 创建会话 `{ title, activated_skill_ids[], model_id }` |
| `GET` | `/conversations` | 我的会话列表 |
| `GET` | `/conversations/{id}` | 会话详情 |
| `DELETE` | `/conversations/{id}` | 删除会话 |

### 12.4 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/conversations/{id}/messages` | 发送消息 `{ content }`<br>请求头 `Accept: text/event-stream` 启用 SSE |
| `GET` | `/conversations/{id}/messages` | 历史消息（`?limit=50&before=uuid`） |

### 12.5 模型

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/models` | 列出可用模型 |

---

## 13. 实施建议

### 13.1 推荐开发顺序

```
第1步: 项目脚手架 + 数据库建表 + JWT 认证
第2步: Skill 上传/解析/CRUD API
第3步: 会话 + 消息 API（先实现简单文本回复，不走工具调用）
第4步: 内置工具实现（read_file, write_file, execute_python, execute_bash）
第5步: Skill 注册为工具 + LLM Tool Calling 集成
第6步: SSE 流式输出
第7步: web_fetch + web_search 工具
第8步: 前端对接 + 联调
```

### 13.2 关键技术点

**1. LLM Tool Calling 循环**

```
async function handleMessage(convId, userMsg):
  messages = [systemPrompt, ...history, userMsg]
  tools = buildTools(activatedSkills)

  loop (max 20 times):
    response = await llm.chat(messages, tools, stream=true)
    if response has tool_use:
      result = await executeTool(tool_use)
      messages.push(tool_result)
    else:
      return response.text
```

**2. Skill 解析**

```
function parseSkill(folderPath):
  content = readFile(folderPath + "/SKILL.md")
  match content with /^---\n(.*?)\n---/s
  yaml = parseYAML(match)
  return {
    name: yaml.name,
    description: yaml.description,
    body: content
  }
```

**3. SSE 流式转发**

```
async function* streamResponse(convId, messages, tools):
  stream = await fetch(llmEndpoint, { body: { messages, tools, stream: true } })
  for chunk of stream:
    if chunk is text:
      yield { event: "assistant", data: { content: chunk } }
    if chunk is tool_use:
      yield { event: "tool_use", data: { tool_name, input } }
      result = await executeTool(...)
      yield { event: "tool_result", data: { content: result } }
      // 将 tool_result 追加到 messages，继续循环
  yield { event: "done", data: { usage } }
```

### 13.3 Demo 简化说明

相比完整版，Demo 做了以下简化：

| 完整版 | Demo 版 | 原因 |
|--------|---------|------|
| 权限模式 + 规则系统 | 无权限检查，全部自动允许 | Demo 信任用户 |
| 17 个内置工具 | 6 个 | 核心流程够用 |
| 12 种 SSE 事件 | 5 种 | 覆盖核心交互 |
| 上下文压缩 (compaction) | 无 | 对话较短，暂不需要 |
| Token 预算管理 | 无 | Demo 阶段无需限制 |
| 记忆系统 (MEMORY.md) | 无 | 后续版本 |
| 任务管理 (5 个工具) | 无 | 后续版本 |
| 重试/降级机制 | 无 | 出错直接返回 |
| 30+ API 端点 | ~15 个 | 满足核心流程 |

---

## 附录：与完整版文档的对应关系

| 简化版章节 | 完整版对应 | 简化程度 |
|-----------|-----------|----------|
| §5 Skill 系统 | §5 + §6.4 | 保留核心格式和注册机制，去掉渐进式加载细节 |
| §6 工具系统 | §6 | 6 个工具，去掉统一接口的 15+ 方法，只保留核心 3 个 |
| §7 Agent 对话引擎 | §8 | 保留基本流程，去掉压缩/预算/结构化输出 |
| §9 流式输出 | §10 | 5 种事件，去掉 progress/compact/tombstone 等 |
| §10 错误处理 | §11 | 保留错误码，去掉分类树/重试/降级 |
| §11 数据模型 | §14 | 精简字段 |
| §12 API 端点 | §15 | ~15 个端点 |
| 无 | §7 权限系统 | 完全移除 |
| 无 | §12 记忆系统 | 完全移除 |
| 无 | §13 任务管理 | 完全移除 |
| 无 | §16 非功能需求 | 完全移除 |
