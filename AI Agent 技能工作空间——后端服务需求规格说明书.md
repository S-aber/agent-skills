# AI Agent 技能工作空间——后端服务需求规格说明书

**版本**：2.1
**日期**：2026-05-09
**状态**：已确认，可进入详细设计

> 本版本为基于 claude-code-ts 架构分析后的全面修订版。新增内容主要包括：工具系统重构（3→17工具）、权限体系、上下文管理、记忆系统、任务管理、SSE 事件扩充、容错重试机制。模型为本地部署，不涉及第三方 API 成本与配额管理。

---

## 目录

- [1. 项目背景与目标](#1-项目背景与目标)
- [2. 术语定义](#2-术语定义)
- [3. 用户与身份认证](#3-用户与身份认证)
- [4. 工作空间与权限隔离](#4-工作空间与权限隔离)
- [5. Skill 定义与来源](#5-skill-定义与来源)
- [6. 工具系统](#6-工具系统)
- [7. 权限系统](#7-权限系统)
- [8. Agent 行为与会话引擎](#8-agent-行为与会话引擎)
- [9. 大模型接入](#9-大模型接入)
- [10. 流式输出规范](#10-流式输出规范)
- [11. 错误处理与容错](#11-错误处理与容错)
- [12. 记忆系统](#12-记忆系统)
- [13. 任务管理](#13-任务管理)
- [14. 数据模型概要](#14-数据模型概要)
- [15. API 端点设计](#15-api-端点设计)
- [16. 非功能需求](#16-非功能需求)
- [17. 待确定及后续优化项](#17-待确定及后续优化项)

---

## 1. 项目背景与目标

本项目是一个较大 Web 系统的**独立后端模块**，核心能力是让用户在自己的私密工作空间中管理符合 Claude Agent Skills 规范的技能（Skill），并与大语言模型进行连续对话，由模型自主决策调用合适的 Skill 及内置工具完成复杂任务。

**关键目标**：
- 提供高效、隔离的个人 Skill 管理
- 实现基于 Tool Use 的 Agent 自动编排
- 支持公共 Skill 仓库，促进复用
- 兼容 OpenAI 兼容接口，灵活切换模型
- 提供流式交互体验
- 提供完整的权限、上下文管理体系

**设计原则**（参考 claude-code-ts）：
- **工具是一等公民**：所有能力通过统一的工具接口暴露，Skill 直接注册为工具
- **失败可恢复**：错误分级处理，支持重试与降级，不因单次失败中断整个会话
- **上下文是有限资源**：自动压缩（compaction）和 token 预算强制执行是必需的
- **安全深度防御**：多层权限控制，从模式到规则到分类器
- **模型本地部署**：无第三方 API 调用，无需成本追踪与外部配额管理

---

## 2. 术语定义

| 术语 | 定义 |
|------|------|
| **工作空间 (Workspace)** | 用户的私密操作区域，与用户一对一绑定，包含 Skill、会话、记忆等所有数据 |
| **Skill** | 符合 Claude Agent Skills 规范的技能定义，核心为 `SKILL.md` 文件，包含 YAML 头和 Markdown 指令 |
| **工具 (Tool)** | Agent 可调用的能力单元，包括内置工具（如文件读写、代码执行）和 Skill 工具（由 Skill 注册而来） |
| **Agent** | 大模型 + 工具系统组成的自主决策实体，根据用户输入选择并调用工具完成复杂任务 |
| **会话 (Conversation/Session)** | 一次完整的对话生命周期，绑定激活的 Skill 集合、权限模式、token 预算 |
| **上下文窗口 (Context Window)** | 模型能处理的最大 token 数量，超出需要压缩或截断 |
| **压缩 (Compaction)** | 当对话历史超过上下文窗口阈值时，自动摘要/裁剪历史消息的过程 |
| **权限模式 (Permission Mode)** | 控制工具调用审批行为的策略：默认、接受编辑、计划、绕过、自动 |
| **Token 预算 (Token Budget)** | 每个会话可消耗的最大输出 token 数量，超过则强制压缩或终止 |

---

## 3. 用户与身份认证

### 3.1 认证方式

- 每个用户拥有唯一账号，通过 **JWT** 进行鉴权。
- 系统提供基础注册、登录接口（后续可集成至主系统统一认证）。
- 本阶段**不设管理员角色**，所有用户权限平等。

### 3.2 Token 生命周期

- Access Token 有效期：**2 小时**
- Refresh Token 有效期：**7 天**
- 支持 token 刷新，旧 refresh token 轮换作废

---

## 4. 工作空间与权限隔离

### 4.1 基本关系

- 用户与工作空间为 **一对一** 关系，注册时自动创建。
- 用户上传的所有私有 Skill 均存储在其工作空间内。
- 用户**只能访问、修改、删除自己的私有 Skill**。

### 4.2 公共资源

- 公共 Skill 仓库独立于任何用户空间，所有用户只读引用。
- 公共 Skill 记录上传者信息，但无单独所有者。

### 4.3 工作空间配置

每个工作空间拥有独立配置，会话创建时生效：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `default_permission_mode` | 默认权限模式 | `default` |
| `default_model` | 默认模型 ID | 系统配置 |
| `max_token_budget` | 单会话输出 token 上限 | 200,000 |
| `allowed_tools` | 允许使用的工具列表（白名单，空=全部） | `[]`（全部） |
| `auto_memory_enabled` | 是否启用自动记忆 | `true` |
| `auto_compact_enabled` | 是否启用自动压缩 | `true` |

---

## 5. Skill 定义与来源

### 5.1 Skill 标准

Skill 严格遵循 **Claude Agent Skills 开放规范**：
- 每个 Skill 是一个文件夹，核心文件为 `SKILL.md`。
- `SKILL.md` 包含 YAML 头（必填 `name`、`description`）和 Markdown 指令。
- 可选包含 `resources/`、`scripts/` 等辅助文件。

**SKILL.md 示例**：

```markdown
---
name: pdf-generator
description: Generate PDF documents from HTML or Markdown content. Use when the user asks to create, export, or download a PDF file.
when_to_use: User wants to create a PDF document
model: default
is_readonly: false
is_destructive: false
allowed_tools: [read_file, write_file, execute_bash]
---

# PDF Generator

## Instructions
1. Accept HTML or Markdown content from the user
2. Use `execute_bash` to run wkhtmltopdf or weasyprint
3. Save the output PDF to the path specified by the user
...
```

**YAML 头字段说明**：

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | Skill 唯一标识名 |
| `description` | 是 | 供模型理解 Skill 用途的描述，会作为工具的 `description` |
| `when_to_use` | 否 | 触发条件提示，帮助模型判断何时调用 |
| `model` | 否 | 指定执行该 Skill 的模型（`default` 使用当前模型） |
| `is_readonly` | 否 | 该 Skill 是否只读，影响权限评估 |
| `is_destructive` | 否 | 该 Skill 是否执行破坏性操作 |
| `allowed_tools` | 否 | 该 Skill 可调用的工具白名单（空=继承当前工具集） |
| `timeout_ms` | 否 | Skill 执行超时（毫秒） |

### 5.2 Skill 分类

| 类型 | 归属 | 可见性 | 管理方式 |
|------|------|--------|----------|
| **私有 Skill** | 单个用户 | 仅创建者可见 | 用户可增删改查 |
| **公共 Skill** | 仓库（记录上传者） | 所有用户可见 | 所有用户可上传；当前阶段暂不允许修改或删除 |

### 5.3 Skill 注册为工具（关键设计决策）

**本系统采用直接注册模式**：每个激活的 Skill 在会话初始化时被注册为一个独立的 `Tool` 实例，而非通过单一 `use_skill` 工具间接加载。

**设计理由**（参考 claude-code-ts `SkillTool` 实现）：
1. **减少 round-trip**：模型直接通过 tool name 调用 Skill，无需先用 `use_skill` 查询再调用
2. **独立的权限控制**：每个 Skill 可以有自己的 `isReadOnly`、`isDestructive`、`checkPermissions` 配置
3. **独立的输入 Schema**：Skill 可以在 YAML 头中声明参数，模型直接传递结构化输入
4. **更好的缓存命中**：工具定义在 system prompt 中是稳定的，不随 Skill 激活集变化而重建整个 prompt

**渐进式加载流程**：

```
会话创建 → 加载激活 Skill 的元数据（name + description）
  → 每个 Skill 注册为独立 Tool → 注入 system prompt
  → 用户发送消息 → 模型选择调用 Skill Tool
  → 后端加载完整 SKILL.md 内容 → 作为 tool result 返回
  → 模型基于完整指令继续推理或调用其他工具
```

### 5.4 Skill 激活集合

- 用户创建会话时，选择一个 **Skill 激活集合**，来源包括私有 Skill 和公共 Skill。
- **激活集合在会话创建后可以追加，但不可移除**（防止已加载的 Skill 指令在上下文中产生断裂）。
- 不同会话可以拥有完全不同的激活组合。
- 对话过程中，Agent 只能调用本会话已激活的 Skill。
- 激活 Skill 数量建议上限：**20 个**（与模型 context window 中的 tool 定义开销相关）。

### 5.5 公共 Skill 使用规则

- 所有用户均可上传公共 Skill，**暂不审核**（后续可引入审核机制）。
- 用户在使用公共 Skill 时采用**直接引用**方式，无需复制到私有空间。
- 公共 Skill 与私有 Skill 在激活后对于 Agent 行为**完全一致**，仅 `source` 字段不同。

---

## 6. 工具系统

> 本章参考 claude-code-ts `src/Tool.ts` 的工具接口设计和 `src/tools.ts` 的工具注册模式。

### 6.1 统一工具接口

所有工具（内置工具、Skill 工具、未来扩展的 MCP 工具）必须实现统一的 `Tool` 接口：

```
Tool {
  // === 标识与元数据 ===
  name: string                    // 工具唯一名称（模型通过此名称调用）
  aliases?: string[]              // 别名（向后兼容）
  searchHint?: string             // 关键词搜索提示（3-10词）
  description(input, options): Promise<string>
    → 返回工具用途描述（供模型理解）
  prompt(options): Promise<string>
    → 返回注入 system prompt 的工具说明

  // === Schema ===
  inputSchema: JSONSchema         // 输入参数的 JSON Schema 定义
  outputSchema?: JSONSchema       // 输出格式（可选，用于结构化输出）

  // === 执行 ===
  call(input, context, canUseTool, onProgress): Promise<ToolResult>
    → 核心执行方法
  isEnabled(): boolean            // 当前环境是否可用
  isConcurrencySafe(input): boolean
    → 是否支持并发调用（默认 false）
  interruptBehavior(): 'cancel' | 'block'
    → 用户发送新消息时的行为（默认 'block'）

  // === 安全与权限 ===
  isReadOnly(input): boolean      // 是否只读（默认 false）
  isDestructive?(input): boolean  // 是否破坏性（默认 false）
  validateInput(input, context): Promise<ValidationResult>
    → 输入参数验证
  checkPermissions(input, context): Promise<PermissionResult>
    → 工具级权限检查

  // === 分类器 ===
  toAutoClassifierInput(input): unknown
    → 为自动模式安全分类器提供摘要（返回 '' 表示跳过）

  // === 渲染（供前端使用） ===
  getToolUseSummary(input): string | null
    → 工具调用简短摘要
  getActivityDescription(input): string | null
    → 执行中的活动描述（如 "正在读取 src/foo.ts"）

  // === 限制 ===
  maxResultSizeChars: number      // 结果最大字符数（超出则持久化到文件）
  shouldDefer?: boolean           // 是否延迟加载（需 ToolSearch 后才能使用）
  strict?: boolean                // 是否启用严格模式

  // === 进度 ===
  renderProgressMessage?(progressData, options): ProgressUI
    → 自定义进度展示
}
```

### 6.2 工具工厂

提供 `buildTool(def)` 工厂函数，自动填充安全默认值：

| 方法 | 默认值 | 说明 |
|------|--------|------|
| `isEnabled()` | `true` | 默认启用 |
| `isConcurrencySafe()` | `false` | 默认不安全 |
| `isReadOnly()` | `false` | 默认非只读 |
| `isDestructive()` | `false` | 默认非破坏性 |
| `checkPermissions()` | `{ behavior: 'allow' }` | 默认允许，委托给通用权限系统 |
| `toAutoClassifierInput()` | `''` | 默认跳过分类器 |

### 6.3 MVP 内置工具列表

> 以下工具清单参考 claude-code-ts `src/tools.ts` `getAllBaseTools()` 并按 Web 场景筛选。

#### 6.3.1 文件操作

| 工具名 | 功能 | 关键参数 | 风险 |
|--------|------|----------|------|
| `read_file` | 读取文件内容，支持分页 | `file_path`, `offset?`, `limit?` | 低 |
| `write_file` | 创建或覆盖文件 | `file_path`, `content` | 中 |
| `edit_file` | 精确字符串替换（单个/全部） | `file_path`, `old_string`, `new_string`, `replace_all?` | 中 |
| `glob` | 文件模式匹配搜索 | `pattern`, `path?` | 低 |

#### 6.3.2 搜索

| 工具名 | 功能 | 关键参数 | 风险 |
|--------|------|----------|------|
| `grep` | 内容搜索（正则匹配） | `pattern`, `path?`, `include?` | 低 |
| `web_search` | 网络搜索 | `query`, `allowed_domains?`, `blocked_domains?` | 低 |
| `web_fetch` | 获取 URL 内容 | `url`, `prompt?` | 中 |

#### 6.3.3 执行

| 工具名 | 功能 | 关键参数 | 风险 |
|--------|------|----------|------|
| `execute_python` | 在沙箱中执行 Python | `code`, `timeout?`（默认 30s） | 高 |
| `execute_bash` | 在沙箱中执行 Shell 命令 | `command`, `timeout?`, `workdir?` | 高 |

#### 6.3.4 任务管理

| 工具名 | 功能 | 关键参数 | 风险 |
|--------|------|----------|------|
| `task_create` | 创建任务 | `subject`, `description`, `activeForm?` | 低 |
| `task_list` | 列出所有任务 | — | 低 |
| `task_get` | 获取任务详情 | `taskId` | 低 |
| `task_update` | 更新任务状态 | `taskId`, `status`, `subject?`, `description?` | 低 |
| `task_stop` | 停止后台任务 | `taskId` | 中 |

#### 6.3.5 记忆

| 工具名 | 功能 | 关键参数 | 风险 |
|--------|------|----------|------|
| `memory_read` | 读取工作空间记忆 | `query?`, `type?` | 低 |
| `memory_write` | 写入/更新记忆 | `type`, `name`, `description`, `content` | 低 |

#### 6.3.6 交互与控制

| 工具名 | 功能 | 关键参数 | 风险 |
|--------|------|----------|------|
| `ask_user` | 向用户提问 | `questions[]`（每项含 question, header, options） | 低 |
| `enter_plan_mode` | 进入计划模式 | — | 低 |
| `set_config` | 修改会话配置 | `key`, `value` | 中 |

> **总计 MVP 内置工具：17 个**。后续可按需通过插件/MCP 方式扩展。

### 6.4 Skill 工具

每个激活的 Skill 自动注册为一个 `Tool` 实例：

- `name` 来自 SKILL.md 的 `name` 字段
- `description` 来自 SKILL.md 的 `description` 字段
- `call()` 加载完整 SKILL.md 内容并返回
- `isReadOnly()` / `isDestructive()` 来自 SKILL.md YAML 头
- Skill 工具与内置工具在模型视角**完全平等**

### 6.5 工具执行上下文

每个工具被调用时接收以下上下文对象（参考 claude-code-ts `ToolUseContext`）：

```
ToolUseContext {
  sessionId: string              // 会话 ID
  workspaceId: string            // 工作空间 ID
  workingDirectory: string       // 当前工作目录（沙箱路径）
  permissionMode: PermissionMode // 当前权限模式
  messages: Message[]            // 当前对话消息历史
  abortController: AbortController  // 取消信号
  tools: Tool[]                  // 所有可用工具
  setProgress(data): void        // 报告执行进度
  appendSystemMessage(msg): void // 注入系统消息
}
```

### 6.6 工具执行结果

```
ToolResult<T> {
  data: T                        // 工具返回数据
  newMessages?: Message[]        // 注入到对话中的附加消息
  mcpMeta?: {                    // MCP 协议元数据
    structuredContent?: object
    _meta?: object
  }
}
```

### 6.7 工具链式调用

- 模型可在一次响应中同时调用多个工具（并行）或顺序调用（串行）。
- 工具调用结果追加到对话上下文，模型可基于结果继续调用其他工具。
- 支持 Skill 工具与内置工具的混合链式调用。
- 最大连续调用轮次：**50 turns**（超过则终止，发送 `error_max_turns`）。

---

## 7. 权限系统

> 本章参考 claude-code-ts `src/Tool.ts` 的 `checkPermissions()`/`isReadOnly()`/`isDestructive()` 接口以及权限模式设计。

### 7.1 权限模式

会话级别的权限模式，决定工具调用的默认审批行为：

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| `default` | 只读工具自动批准，写入/破坏性工具需要用户确认 | 日常开发 |
| `acceptEdits` | 文件读写自动批准，Shell/网络/破坏操作需要确认 | 信任的编辑场景 |
| `plan` | 所有工具调用均需用户确认 | 需求分析阶段 |
| `bypassPermissions` | 全部自动批准（仅限沙箱/Docker 环境 + 无外网） | CI/CD、自动化测试 |
| `auto` | 由安全分类器自动评估，低风险自动批准 | 高级用法（后续实现） |

权限模式在**会话创建时设定**，可在会话中途通过 `PATCH /sessions/{id}/mode` 更改。

### 7.2 权限检查流程

每次工具调用前执行以下检查链（参考 claude-code-ts 权限系统）：

```
工具调用请求
  ↓
1. validateInput() → 参数是否合法？
  ↓ 通过
2. 检查 alwaysDenyRules → 匹配 → deny
  ↓ 不匹配
3. 检查 alwaysAllowRules → 匹配 → allow
  ↓ 不匹配
4. 工具级 checkPermissions() → 有自定义逻辑？
  ↓ 无
5. 模式默认策略：
   - bypassPermissions → allow
   - plan → ask
   - default → isReadOnly? → allow : ask
   - acceptEdits → isDestructive? → ask : allow
   - auto → 分类器评估
  ↓
6. 返回 PermissionResult { behavior: 'allow' | 'deny' | 'ask', ... }
```

### 7.3 权限规则

```
PermissionRule {
  source: 'userSettings' | 'workspaceSettings' | 'sessionSettings' | 'cliArg'
  behavior: 'allow' | 'deny' | 'ask'
  toolName: string               // 工具名
  ruleContent?: string           // 匹配模式（如 "git *" 匹配 Bash(git ...)）
}
```

权限规则优先级：`sessionSettings` > `workspaceSettings` > `userSettings` > `cliArg`。

### 7.4 风险等级

每个工具声明风险等级，影响默认权限策略和自动分类器行为：

| 等级 | 说明 | 示例工具 |
|------|------|----------|
| **LOW** | 只读操作，无副作用 | `read_file`, `glob`, `grep`, `web_search` |
| **MEDIUM** | 写入操作，可逆或范围受限 | `write_file`, `edit_file`, `web_fetch` |
| **HIGH** | 执行任意代码或系统级操作 | `execute_python`, `execute_bash` |

### 7.5 拒绝追踪

- 记录每次权限拒绝（工具名、输入摘要、时间戳）。
- 同一会话中同一工具的拒绝次数超过阈值后，自动将其加入 `alwaysDenyRules`。
- 防止模型反复尝试被用户拒绝的操作。

---

## 8. Agent 行为与会话引擎

> 本章参考 claude-code-ts `src/query.ts` 的查询循环和 `src/QueryEngine.ts` 的会话生命周期。

### 8.1 会话生命周期

```
1. 用户发送消息 → submitMessage()
2. 加载工作空间上下文（记忆、system prompt、激活的 Skill）
3. 构建消息列表（system prompt + 历史 + attachments + 新消息）
4. 调用 LLM API（携带所有工具定义）
5. 流式接收响应（assistant message → tool_use → tool_result 循环）
6. 每次 assistant 响应后检查是否需要压缩
7. 返回最终响应（result 事件）
```

### 8.2 上下文窗口管理

- 每次 Assistant 响应后，计算当前上下文 token 总数。
- 当 token 数达到模型上下文窗口的 **80%** 时，触发自动压缩。
- 当 token 数达到 **95%** 时，强制压缩（即使压缩失败也要丢弃旧消息）。

### 8.3 自动压缩（Auto-Compaction）

> 参考 claude-code-ts `src/services/compact/compact.ts`

**压缩策略（按优先级）**：

| 优先级 | 策略 | 说明 | 效果 |
|--------|------|------|------|
| 1 | **微压缩 (Micro-compact)** | 移除 tool_result 的完整内容，仅保留摘要 | 减少 30-50% |
| 2 | **摘要压缩 (Snip-compact)** | 使用 LLM 将较早的对话轮次总结为简短摘要 | 减少 60-80% |
| 3 | **记忆转存** | 将关键信息写入记忆系统，从对话中移除 | 减少 10-20% |

**压缩流程**：
1. 触发压缩 → 发送 `compact_progress` SSE 事件
2. 执行 Pre-compact hooks
3. 执行压缩策略
4. 标记 `compact_boundary` 消息（压缩前后的分界线）
5. 发送压缩后的消息列表
6. 执行 Post-compact hooks
7. 继续对话

**压缩边界消息**（`compact_boundary`）是一个特殊系统消息，标记哪些消息已被压缩。客户端可据此调整 UI 显示（如折叠压缩部分）。

### 8.4 Token 预算

- 每个会话有输出 token 预算上限（默认 200,000 tokens），用于控制上下文窗口占用。
- 累计消耗达到 **80%** 时发送进度事件，提醒前端。
- 预算耗尽时终止会话，返回 `error_max_budget`。
- 非计费目的——模型为本地部署，仅用于防止单会话无限膨胀。

### 8.5 结构化输出

- 支持 JSON Schema 约束的模型输出（通过 `SyntheticOutputTool` 模式）。
- 当请求指定 `jsonSchema` 时，注入结构化输出工具。
- 最多重试 **5 次**（`MAX_STRUCTURED_OUTPUT_RETRIES`）以获取有效 JSON。

---

## 9. 大模型接入

### 9.1 本地部署模型

- 模型为**本地部署**，服务端直接调用本地推理服务的 API 端点。
- 无需外部 API Key 管理，无需成本计费。
- 系统兼容 **OpenAI 兼容 API** 格式（`/v1/chat/completions`），适配主流本地推理框架（vLLM、Ollama、LocalAI 等）。

### 9.2 模型配置

- 模型中预设了可用的本地模型列表及其能力参数。
- 每个模型记录：
  - `model_id`：唯一标识
  - `display_name`：展示名称
  - `api_endpoint`：本地推理服务地址
  - `context_window`：上下文窗口大小
  - `max_output_tokens`：最大输出 token 数
  - 能力标记：是否支持 tool calling / streaming / JSON mode
- 客户端在发起对话时通过 `model_id` 指定模型，服务端根据配置路由到对应的本地推理端点。

### 9.3 模型降级

当主模型不可用时（推理服务宕机或超时）：
1. 尝试同一级别的**备用模型**（预设于工作空间配置中）
2. 仍不可用时返回 `MODEL_NOT_AVAILABLE` 错误

---

## 10. 流式输出规范

> 参考 claude-code-ts `src/query.ts` 的 yield 事件体系。

### 10.1 协议

- 采用 **Server-Sent Events (SSE)** 协议。
- 连接端点：`POST /conversations/{id}/messages`（请求头 `Accept: text/event-stream`）。
- 服务端每 **30 秒**发送 `ping` 心跳事件，防止连接超时。

### 10.2 事件格式

```
event: <event_type>
data: <JSON payload>
```

### 10.3 事件类型

| 事件类型 | 含义 | 数据结构 |
|----------|------|----------|
| `stream_request_start` | API 调用开始 | `{"type":"stream_request_start","request_id":"..."}` |
| `assistant` | 模型响应消息（含增量更新） | `{"type":"assistant","uuid":"...","message":{"content":[...]}, "delta?":{...}}` |
| `tool_use` | 模型发起工具调用 | `{"type":"tool_use","tool_use_id":"...","tool_name":"...","input":{...}}` |
| `tool_progress` | 工具执行进度 | `{"type":"tool_progress","tool_use_id":"...","data":{...}}` |
| `tool_result` | 工具执行完成 | `{"type":"tool_result","tool_use_id":"...","output":...,"is_error":false}` |
| `attachment` | 附件注入（如结构化输出） | `{"type":"attachment","attachment":{"type":"...","data":{...}}}` |
| `compact_progress` | 压缩进行中 | `{"type":"compact_progress","stage":"hooks_start\|compact_start\|compact_end"}` |
| `compact_boundary` | 压缩边界标记 | `{"type":"system","subtype":"compact_boundary","compact_metadata":{...}}` |
| `tombstone` | 消息已被压缩移除 | `{"type":"tombstone","message":{"uuid":"..."}}` |
| `error` | 错误（可恢复） | `{"type":"error","code":"...","message":"...","retryable":true}` |
| `done` | 本轮回复结束 | `{"type":"done","turn_id":"...","usage":{...}}` |
| `ping` | 心跳 | `:ping` |

### 10.4 工具进度事件

每种工具可定义类型化的进度数据：

```
// Bash 执行进度
BashProgress: {
  type: 'bash_progress'
  stdout_lines: string[]
  stderr_lines: string[]
  exit_code?: number
}

// 文件读取进度
FileReadProgress: {
  type: 'file_read_progress'
  bytes_read: number
  total_bytes: number
}

// 网络搜索进度
WebSearchProgress: {
  type: 'web_search_progress'
  query: string
  results_count: number
}
```

### 10.5 done 事件数据结构

```
{
  "type": "done",
  "turn_id": "uuid",
  "stop_reason": "end_turn" | "max_tokens" | "tool_use" | "stop_sequence",
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "cache_read_input_tokens": 100,
    "cache_creation_input_tokens": 50
  },
  "num_turns": 5
}
```

---

## 11. 错误处理与容错

> 参考 claude-code-ts `src/services/api/errors.ts` 和 `src/services/api/withRetry.ts`。

### 11.1 错误分类

```
APIError（基类）
  ├── AuthError              // 401/403 — 不重试，直接返回
  ├── RateLimitError         // 429 — 重试，指数退避
  ├── ServerError            // 529/5xx — 重试，指数退避
  ├── ConnectionError        // 网络不可达 — 重试
  ├── ConnectionTimeoutError // 连接超时 — 重试
  ├── PromptTooLongError     // 上下文超限 — 触发压缩后重试
  └── ClientError            // 4xx（非429）— 不重试
```

### 11.2 重试策略

- **退避算法**：指数退避 + 随机抖动（`delay = min(500ms × 2^n, 30s) + random(0, delay×0.3)`）
- **可重试错误**：
  - 速率限制 (429/529)：最多 **3 次**
  - 连接/超时错误：最多 **10 次**
  - 上下文超限：自动压缩后重试，最多 **2 次压缩**
- **不可重试错误**：认证错误、客户端参数错误（直接返回给调用方）
- **用户取消**：不重试，立即传播中止信号

### 11.3 降级策略

| 场景 | 降级方案 |
|------|----------|
| 主模型持续不可用 | 切换到预设降级模型 |
| 压缩失败 | 丢弃最旧的消息（FIFO） |
| 权限系统不可用 | 破坏性工具 → deny；只读工具 → allow |
| 工具执行失败 | 返回 `is_error: true` 的 tool_result，不中断会话 |

### 11.4 错误响应格式

**非流式接口**：
```json
{
  "error": {
    "code": "SKILL_PARSE_ERROR",
    "message": "SKILL.md 格式错误：缺少 name 字段",
    "detail": "在文件 /skills/my-skill/SKILL.md 中未找到 name 字段",
    "request_id": "req_abc123"
  }
}
```

**流式接口**（不关闭连接）：
```
event: error
data: {"type":"error","code":"RATE_LIMITED","message":"请求过于频繁","retryable":true,"retry_after_ms":5000}
```

**致命错误**（关闭连接）：
```
event: error
data: {"type":"error","code":"AUTH_FAILED","message":"认证已过期","retryable":false}
```

### 11.5 常见错误码

| 错误码 | 说明 | 可重试 |
|--------|------|--------|
| `AUTH_FAILED` | 认证失败 | 否 |
| `PERMISSION_DENIED` | 权限不足 | 否 |
| `SKILL_NOT_FOUND` | Skill 不存在 | 否 |
| `SKILL_PARSE_ERROR` | SKILL.md 解析失败 | 否 |
| `MODEL_NOT_AVAILABLE` | 模型不可用 | 是 |
| `RATE_LIMITED` | 速率限制 | 是 |
| `CONTEXT_TOO_LONG` | 上下文超限 | 是（压缩后） |
| `MAX_TURNS_REACHED` | 达到最大轮次 | 否 |
| `MAX_BUDGET_REACHED` | 达到预算上限 | 否 |
| `EXECUTION_TIMEOUT` | 工具执行超时 | 否 |
| `TOOL_CALL_FAILED` | 工具调用失败 | 否 |
| `INTERNAL_ERROR` | 内部错误 | 否 |

---

## 12. 记忆系统

> 参考 claude-code-ts `src/memdir/` 记忆文件系统。

### 13.1 记忆模型

工作空间记忆以 Markdown 文件形式存储，包含 YAML 头：

```markdown
---
name: user-preferences
description: 用户偏好设置，包括代码风格、语言偏好
type: user
---

用户偏好使用 TypeScript，缩进为 2 空格，使用 Prettier 格式化。
```

**记忆类型**（参考 claude-code-ts 的分类）：

| 类型 | 用途 |
|------|------|
| `user` | 用户角色、偏好、知识背景 |
| `project` | 项目决策、目标、截止日期 |
| `feedback` | 用户对协作方式的反馈 |
| `reference` | 外部资源指针 |

### 13.2 记忆工具

| 工具 | 功能 |
|------|------|
| `memory_read` | 搜索/列出工作空间记忆，支持按 `type` 过滤和关键词搜索 |
| `memory_write` | 写入或更新一条记忆（通过 `name` 去重） |

### 13.3 自动记忆

- 会话开始时，将工作空间 `MEMORY.md` 的内容注入 system prompt。
- 若启用 `auto_memory`，模型可以在对话中自行决定写入记忆。
- 记忆文件 token 上限：**25KB / 200 行**，超出部分截断并附警告。

### 13.4 记忆相关性

- 每轮对话开始前，扫描记忆文件列表。
- 将最近修改的活跃记忆作为 attachment 预加载。

---

## 13. 任务管理

> 参考 claude-code-ts `src/tools/TodoWriteTool/` 和 `src/tools/TaskCreateTool/`。

### 14.1 任务模型

```
Task {
  id: string                // 唯一标识
  subject: string           // 任务标题（祈使句，如 "修复登录 bug"）
  description: string       // 任务详细描述
  status: 'pending' | 'in_progress' | 'completed' | 'deleted'
  activeForm?: string       // 进行中时态描述（如 "正在修复登录 bug"）
  blockedBy?: string[]      // 前置依赖任务 ID
  metadata?: Record<string, unknown>
  createdAt: timestamp
  updatedAt: timestamp
}
```

### 14.2 任务状态流转

```
pending → in_progress → completed
  ↓                       ↓
deleted                (可回退到 in_progress)
```

### 14.3 任务工具

| 工具 | 功能 |
|------|------|
| `task_create` | 创建新任务，可指定依赖 |
| `task_list` | 列出所有任务（按状态和 ID 排序） |
| `task_get` | 获取单个任务详情 |
| `task_update` | 更新任务状态/描述（支持批量更新依赖关系） |
| `task_stop` | 停止正在运行的后台任务 |

---

## 14. 数据模型概要

### 14.1 核心实体

**User**
```
User {
  id: UUID
  username: string
  email: string
  password_hash: string
  created_at: timestamp
  updated_at: timestamp
}
```

**Workspace**
```
Workspace {
  id: UUID
  user_id: UUID (UNIQUE, FK → User)
  settings: WorkspaceSettings (JSON)
  created_at: timestamp
  updated_at: timestamp
}
```

**Skill**
```
Skill {
  id: UUID
  workspace_id: UUID? (FK → Workspace, null = public)
  source: 'private' | 'public'
  uploader_id: UUID (FK → User)
  name: string (from SKILL.md)
  description: string (from SKILL.md)
  yaml_metadata: JSON (完整 YAML 头数据)
  folder_path: string (服务器存储路径)
  file_count: int
  size_bytes: bigint
  created_at: timestamp
  updated_at: timestamp
}
```

**Conversation**
```
Conversation {
  id: UUID
  workspace_id: UUID (FK → Workspace)
  title: string
  activated_skill_ids: UUID[]
  permission_mode: PermissionMode
  model_id: string
  token_budget: int
  status: 'active' | 'completed' | 'timed_out'
  started_at: timestamp
  last_activity_at: timestamp
}
```

**Session**（运行时会话状态，关联 Conversation）
```
Session {
  id: UUID
  conversation_id: UUID (FK → Conversation)
  status: 'active' | 'paused' | 'completed'
  token_budget_used: int
  api_duration_ms: bigint
  tool_duration_ms: bigint
  started_at: timestamp
  last_activity_at: timestamp
}
```

**Message**
```
Message {
  id: UUID
  conversation_id: UUID (FK → Conversation)
  role: 'system' | 'user' | 'assistant'
  content: text | ContentBlock[]  (文本或结构化内容块)
  tool_calls: ToolCall[]?         (assistant 消息中的工具调用)
  tool_use_result: object?          (user 消息中的工具返回结果)
  usage: {                          (assistant 消息的 token 用量)
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int?
    cache_creation_tokens: int?
  }?
  compacted: boolean               (是否已被压缩)
  compacted_summary: string?        (压缩后的摘要)
  is_meta: boolean?                 (是否为系统辅助消息)
  uuid: UUID
  created_at: timestamp
}
```

**ToolCall**
```
ToolCall {
  id: UUID
  message_id: UUID (FK → Message)
  tool_name: string
  tool_use_id: string
  input: JSON
  output: JSON?
  is_error: boolean
  permission_decision: 'allow' | 'deny' | 'ask'
  started_at: timestamp
  completed_at: timestamp?
}
```

**Memory**
```
Memory {
  id: UUID
  workspace_id: UUID (FK → Workspace)
  name: string
  type: 'user' | 'project' | 'feedback' | 'reference'
  description: string
  content: string
  token_count: int
  active: boolean
  created_at: timestamp
  updated_at: timestamp
}
```

### 14.2 模型配置数据库（本地）

服务端根据 `model_id` 从已有模型配置数据库中查询：

```
ModelConfig {
  id: string (model_id)
  display_name: string
  provider: string (如 openai, anthropic, minimax)
  api_endpoint: string (完整 API URL)
  api_key: string (加密存储)
  actual_model_name: string (如 gpt-4o)
  context_window: int
  max_output_tokens: int
  supports_tool_calling: boolean
  supports_streaming: boolean
  supports_json_mode: boolean
  is_active: boolean
}
```

---

## 15. API 端点设计

所有 API 前缀：`/api/v1/`。

### 15.1 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/auth/register` | 注册 |
| `POST` | `/auth/login` | 登录，返回 JWT |
| `POST` | `/auth/refresh` | 刷新令牌 |

### 15.2 工作空间

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/workspace` | 获取我的工作空间信息 |
| `PATCH` | `/workspace/settings` | 更新工作空间配置 |

### 15.3 私有 Skill 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/skills` | 列出我的私有 Skill |
| `POST` | `/skills/upload` | 上传 Skill（multipart/form-data，字段 `file` 为 ZIP/TAR 包） |
| `GET` | `/skills/{id}` | 查看 Skill 详情（含公开 Skill，返回元数据 + 文件树） |
| `PUT` | `/skills/{id}` | 更新私有 Skill（覆盖上传） |
| `DELETE` | `/skills/{id}` | 删除私有 Skill（含关联文件） |
| `GET` | `/skills/{id}/files` | 获取 Skill 文件树 |
| `GET` | `/skills/{id}/files/{path}` | 读取 Skill 资源文件内容 |

### 15.4 公共 Skill 仓库

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/skills/public` | 列出所有公共 Skill（分页、可搜索） |
| `POST` | `/skills/public/upload` | 上传公共 Skill |

### 15.5 会话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/conversations` | 创建会话<br>Body: `{ title, activated_skill_ids[], model_id, permission_mode?, token_budget? }` |
| `GET` | `/conversations` | 我的会话列表（分页） |
| `GET` | `/conversations/{id}` | 会话详情（含激活 Skill 列表、权限模式） |
| `PATCH` | `/conversations/{id}` | 更新会话（追加激活 Skill、修改权限模式等） |
| `DELETE` | `/conversations/{id}` | 删除会话 |
| `POST` | `/conversations/{id}/compact` | 手动触发上下文压缩 |

### 15.6 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/conversations/{id}/messages` | 发送消息<br>Body: `{ content, model_id }`<br>支持 SSE：请求头 `Accept: text/event-stream` |
| `GET` | `/conversations/{id}/messages` | 历史消息分页（`?before=uuid&limit=50`） |
| `POST` | `/conversations/{id}/messages/{msg_id}/abort` | 中止正在生成的回复 |

### 15.7 记忆

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/workspace/memories` | 列出记忆（按 type 过滤） |
| `POST` | `/workspace/memories` | 创建记忆 |
| `PUT` | `/workspace/memories/{id}` | 更新记忆 |
| `DELETE` | `/workspace/memories/{id}` | 删除记忆 |

### 15.8 Skill 发现

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/workspace/skills/discover` | 触发 Skill 目录扫描，更新可用 Skill 列表 |

### 15.9 模型

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/models` | 列出可用模型（含上下文窗口、能力标记） |

---

## 16. 非功能需求

### 16.1 安全

- 所有查询严格通过 `user_id` 或 `workspace_id` 过滤，禁止跨用户数据泄漏。
- 文件上传校验：ZIP/TAR 格式，单文件最大 10MB，总量最大 50MB。
- Skill 上传后进行 YAML 解析校验，拒绝包含恶意内容的 SKILL.md。
- 沙箱执行：`execute_python` 和 `execute_bash` 在隔离环境中运行（Docker/gVisor），限制 CPU、内存、网络、文件系统。
- 敏感信息（API Key、密码哈希）不得出现在日志中。

### 16.2 性能

- 流式响应首字节延迟（TTFT）：**p95 < 2 秒**（正常负载）。
- 工具执行开销（不含 LLM）：**p99 < 500ms**。
- 压缩操作：**< 5 秒**（会话 < 500k tokens）。
- Skill 元数据使用缓存（TTL 5 分钟），避免每次会话创建时重复解析。

### 16.3 缓存策略

| 缓存对象 | 策略 | TTL | 失效条件 |
|----------|------|-----|----------|
| Skill 元数据 | 内存 LRU | 5 min | 手动 discover / Skill 上传 |
| 工具定义 | 会话级 | 会话生命周期 | 权限模式变更 |
| 记忆文件 | 内存 LRU（10 条） | — | 记忆写入时淘汰 |
| 模型配置 | 内存 | 10 min | — |
| 文件状态 | 会话级 | 会话生命周期 | 文件写入时更新 |

### 16.4 速率限制

| 维度 | 限制 |
|------|------|
| 全局 API | 100 req/s 每用户 |
| Token 输入 | 1,000,000 tokens/min 每工作空间 |
| SSE 连接 | 5 个并发连接每用户 |
| Skill 上传 | 20 次/小时 每用户 |

### 16.5 并发

- SSE 流使用 async generator（`yield` 模式），单个连接不阻塞其他请求。
- 工具执行默认串行（同一 turn 内），`isConcurrencySafe()` 标记的工具可并行。
- 每工作空间最多 3 个活跃会话。

### 16.6 数据保留

| 数据类型 | 保留策略 |
|----------|----------|
| 对话/消息 | 90 天，之后自动归档 |
| 记忆 | 永久（直到显式删除） |
| 会话状态 | 最后活动后 24 小时自动清理 |
| Skill 文件 | 永久（直到显式删除） |

### 16.7 可观测性

- 关键操作记录结构化日志，包含：`request_id`、`user_id`、`workspace_id`、`session_id`、操作类型、耗时、错误上下文。
- SSE 连接生命周期事件记录（连接建立、异常断开、心跳超时）。
- 工具调用记录完整的 input/output/permission_decision。
- API 调用记录 token 用量。

---

## 17. 待确定及后续优化项

### 17.1 本版本不实现

- 公共 Skill 的修改、删除权限及审核流
- 多用户协作工作空间
- MCP 协议集成（工具通过 MCP 服务器动态扩展）
- 多 Agent 协作（Team/Coordinator 模式）
- 自动模式下的 LLM 安全分类器
- 语音输入/输出
- 与主系统的统一认证集成

### 17.2 待决策项

- 沙箱具体实现方案（Docker / gVisor / Firecracker）
- 模型使用白名单
- Skill 市场的评分/评论机制
- 对话模板系统（一键创建特定场景的会话）

---

## 附录 A：与 claude-code-ts 的映射关系

| 本系统概念 | claude-code-ts 对应 | 文件位置 |
|-----------|-------------------|----------|
| 工具接口 (Tool) | `Tool` 接口 | `src/Tool.ts` |
| 工具注册 | `getAllBaseTools()` | `src/tools.ts` |
| Skill 工具 | `SkillTool` | `src/tools/SkillTool/` |
| 权限模式 | `PermissionMode` | `src/types/permissions.ts` |
| 权限检查 | `checkPermissions()` | `src/Tool.ts:500-503` |
| 会话引擎 | `QueryEngine` | `src/QueryEngine.ts` |
| 查询循环 | `query()` | `src/query.ts` |
| 上下文压缩 | `compact.ts` | `src/services/compact/compact.ts` |
| 自动压缩 | `autoCompact.ts` | `src/services/compact/autoCompact.ts` |
| 记忆系统 | `memdir/` | `src/memdir/` |
| 任务管理 | `TodoWriteTool`, `TaskCreateTool` | `src/tools/TodoWriteTool/`, `src/tools/TaskCreateTool/` |
| 错误重试 | `withRetry.ts` | `src/services/api/withRetry.ts` |

---

## 附录 B：修订记录

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2026-05-09 | 初始版本 |
| 2.0 | 2026-05-09 | 基于 claude-code-ts 架构全面修订：工具系统 3→17、新增权限体系、上下文管理、成本追踪、记忆系统、任务管理、SSE 事件 4→12、容错重试、API 扩充 |
| 2.1 | 2026-05-09 | 调整为本地部署模型：移除成本追踪章节、移除 cost 相关 API、精简 ModelConfig 数据模型、调整大模型接入描述 |
