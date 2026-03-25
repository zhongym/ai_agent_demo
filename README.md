# ✨ Enterprise Data Agent

一个基于 **FastAPI + LangGraph + LangChain + MCP** 的企业数据 Agent 示例工程。它的核心目标很直接：  
让 LLM 先读取 **Markdown Skill**，再按 Skill 约束去调用 **本地工具** 和 **MCP 工具**，最后输出结构化、可解释的回答。

当前项目已经不是“写死业务逻辑的 demo”，而是一个相对清晰的通用骨架 🧩

- 📄 Skill 用 Markdown 管理
- 🛠️ 本地工具用 `@tool` 定义
- 🔌 MCP 工具由服务端暴露元数据并动态发现
- 🧠 会话历史由 LangGraph checkpoint 管理
- 🗜️ 长对话支持 `SummarizationMiddleware` 自动摘要
- 🧾 API 返回最终答案和本轮工具调用摘要

---

## 🌟 当前内置能力

当前仓库自带 4 个业务 Skill：

- `kpi_query`：查询销售额、订单量、客单价等指标
- `inventory_analysis`：查询库存排行、仓库库存情况
- `product_recommend`：按品牌、价格、品类和场景推荐商品
- `sales_inventory_snapshot`：组合查询销售指标和库存排行，输出经营概览

常见问题示例：

- `我这个月销售额多少`
- `华东一仓库存最高的商品`
- `推荐 500 元以内的李宁鞋`
- `给我看下本月销售额和库存最高的前 3 个商品`

---

## 🧭 整体执行链路

```text
用户问题
  -> FastAPI /query
  -> AgentOrchestrator
  -> LangGraph checkpoint 按 thread_id 恢复历史
  -> SummarizationMiddleware 在阈值触发时压缩旧消息
  -> LLM 判断是否先调用 run_skill
  -> run_skill 返回 Markdown Skill 正文
  -> LLM 再调用本地工具 / MCP 工具
  -> 汇总最终回答
  -> 返回 answer + message_summary.tool_calls
```

这条链路里，最重要的约束是：

- 🥇 如果某个 Skill 明显匹配当前任务，LLM 必须先调用 `run_skill`
- 📅 如果用户说“本月 / 上个月 / 今日 / 近30天”，LLM 应先调用 `get_time`
- 🚫 不允许在没有工具结果的情况下编造真实数据

---

## 🗂️ 目录结构

```text
app/
  main.py                  # FastAPI 入口
  bootstrap.py             # 装配 orchestrator / model / registry
  orchestrator.py          # 主编排逻辑
  settings.py              # 主应用配置，读取 app/.env
  llm/
    factory.py             # LLM 构建
    prompts.py             # system prompt
  local_tools/
    __init__.py            # 本地工具聚合出口
    run_skill.py           # 动态本地工具：run_skill
    time.py                # 静态本地工具：get_time
  runtime/
    skill_registry.py      # Skill 加载与索引
    local_tool_registry.py # 本地工具注册
    mcp_tool_registry.py   # MCP 工具注册
    tool_registry.py       # 多工具来源聚合
  schemas/
    api.py                 # API 请求/响应 schema
  skills/
    sales/kpi_query.md
    inventory/inventory_analysis.md
    catalog/product_recommend.md
    operations/sales_inventory_snapshot.md
  config/
    mcp_services.yaml      # MCP 客户端配置

mcp_server/
  server.py                # data center MCP server 入口
  settings.py              # MCP server 配置，读取 mcp_server/.env
  tools/                   # data center MCP tools

tests/
  test_api.py
  test_orchestrator.py
  test_runtime.py
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp app/.env.example app/.env
cp mcp_server/.env.example mcp_server/.env
```

### 2. 启动 API

```bash
.venv/bin/uvicorn app.main:app --reload
```

启动后可访问：

- `GET /`：简单说明
- `GET /health`：健康检查
- `POST /query`：主查询接口

### 3. 发起请求

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"product-thread","question":"推荐500元以内李宁鞋"}'
```

一个典型响应大致像这样：

```json
{
  "thread_id": "product-thread",
  "question": "推荐500元以内李宁鞋",
  "answer": "我为你筛出几款 500 元以内的李宁鞋……",
  "llm_provider": "bailian-langchain",
  "mcp_transport": "data_center:stdio",
  "message_summary": {
    "tool_calls": [
      {
        "name": "run_skill",
        "kind": "skill",
        "arguments": {
          "skill": "product_recommend",
          "args": "品牌=李宁 价格上限=500 类目=鞋"
        },
        "response": {
          "skill_name": "product_recommend"
        }
      }
    ]
  }
}
```

---

## ⚙️ 配置说明

### `app/.env`

主应用配置，主要包含：

- `APP_NAME`
- `DASHSCOPE_API_KEY`
- `BAILIAN_BASE_URL`
- `BAILIAN_MODEL`
- `LLM_LOG_PAYLOADS`
- `AGENT_RECURSION_LIMIT`
- `SUMMARY_TRIGGER_MESSAGES`
- `SUMMARY_TRIGGER_TOKENS`
- `SUMMARY_KEEP_MESSAGES`
- `MCP_TIMEOUT_SECONDS`
- `SKILLS_DIR`
- `MCP_SERVICES_CONFIG`

### `mcp_server/.env`

MCP 服务配置，主要包含：

- `MCP_HOST`
- `MCP_PORT`
- `MCP_PATH`

### `app/config/mcp_services.yaml`

这是 **agent 侧** 的 MCP 客户端配置。目前支持两种接入方式：

- `stdio`：agent 自己拉起本地 `mcp_server` 子进程
- `http`：你先独立启动 `mcp_server`，agent 再通过 URL 连接过去

#### 方式 1：`stdio` 启动 `mcp_server` 🌿

这是当前默认方式，配置如下：

```yaml
services:
  data_center:
    enabled: true
    transport: stdio
    command: /Users/zhongym/ai_agent/.venv/bin/python
    args:
      - -m
      - mcp_server.server
    cwd: /Users/zhongym/ai_agent
    env:
      MCP_TRANSPORT: stdio
    timeout_seconds: 10
```

这种模式下，不需要你手动先启动 `mcp_server`。

#### 方式 2：HTTP 启动 `mcp_server` 🌐

如果你希望把 `mcp_server` 作为独立 HTTP 服务运行，可以这样配置：

先设置 `mcp_server/.env`：

```env
MCP_HOST=127.0.0.1
MCP_PORT=9001
MCP_PATH=/mcp
```

然后单独启动服务：

```bash
.venv/bin/python -m mcp_server.server
```

这里有一个关键点：

- 不要给这个进程设置 `MCP_TRANSPORT=stdio`
- 只要没有这个环境变量，`mcp_server` 就会自动走 HTTP 模式

如果使用默认配置，服务地址就是：

```text
http://127.0.0.1:9001/mcp
```

对应地，把 `app/config/mcp_services.yaml` 改成：

```yaml
services:
  data_center:
    enabled: true
    transport: http
    url: http://127.0.0.1:9001/mcp
    timeout_seconds: 10
```

在 HTTP 模式下，这些字段就不需要了：

- `command`
- `args`
- `cwd`
- `env`

---

## 🧠 Skill 机制

Skill 文件位于 `app/skills/**/*.md`，每个文件都包含：

- YAML front matter
- `name`
- `description`
- 正文执行说明

例如：

- `app/skills/sales/kpi_query.md`
- `app/skills/inventory/inventory_analysis.md`
- `app/skills/catalog/product_recommend.md`

`SkillRegistry` 会负责：

- 📚 扫描目录
- 🔍 解析 front matter
- ✅ 校验字段
- 🧷 以 `name` 建立索引

LLM 不直接读取这些 Markdown 文件；它是通过本地工具 `run_skill` 获取 Skill 正文的。

---

## 🛠️ 本地工具机制

本地工具在 `app/local_tools/` 下维护，目前有两类：

### 1. 动态工具

由 `build_local_tools(...)` 构建，例如：

- `run_skill`

这类工具通常需要依赖注入，比如注入 `SkillRegistry`。

### 2. 静态工具

直接在模块级定义并导出，例如：

- `get_time`

`get_time` 走的就是 `LocalToolRegistry._collect_static_tools()` 这条静态收集路径，用于处理相对日期，不再依赖 MCP 服务 ✍️

本地工具统一使用 LangChain 的 `@tool` 定义，并通过 `extras.local_tool` 声明运行时信息，例如：

- `kind`
  - `skill`
  - `local`
- `tool_result`
  - `json`
  - `identity`

---

## 🔌 MCP 工具机制

`mcp_server` 当前注册了 3 个 data center MCP tools：

- `query_metric`
- `top_products`
- `search_products`

在 agent 侧，通过 `MultiServerMCPClient` 加载后会暴露为：

- `data_center_query_metric`
- `data_center_top_products`
- `data_center_search_products`

这样做的好处是：

- 🏷️ tool 名能区分来源服务
- 📦 schema、description、tags 都直接来自 MCP 服务
- 🧾 agent 侧不需要再维护一份本地 metadata 文件

---

## 🧪 测试

运行全量测试：

```bash
.venv/bin/pytest
```

如果只想看核心回归：

```bash
.venv/bin/pytest tests/test_api.py
.venv/bin/pytest tests/test_orchestrator.py
.venv/bin/pytest tests/test_runtime.py
```

测试主要覆盖：

- ✅ API 请求/响应
- ✅ `thread_id` 多轮记忆
- ✅ `run_skill -> MCP tool -> final answer`
- ✅ 自动摘要
- ✅ 本地工具静态/动态收集
- ✅ MCP tool 发现与结果归一化

---

## 🧱 当前设计边界

- `run_skill` 仍然是一个本地工具，而不是特殊旁路
- 当前 `mcp_server` 是仓库内 data center 示例服务，但已经按独立服务边界整理
- 当前默认使用内存 checkpoint：适合本地开发与测试，不适合生产持久化
- 当前场景更偏查询、分析、推荐；复杂工作流后续可以继续外扩

---

## 🧩 如何扩展

### 新增 Skill

1. 在 `app/skills/` 下新增一个 `.md`
2. 写好 `name`、`description` 和正文
3. 重启服务

### 新增静态本地工具

1. 在 `app/local_tools/` 下新增一个模块级 `@tool`
2. 在 `app/local_tools/__init__.py` 中导出它
3. 让 `LocalToolRegistry._collect_static_tools()` 自动收集

### 新增动态本地工具

1. 写一个返回 `StructuredTool` 的工厂函数
2. 在 `build_local_tools(...)` 里挂进去
3. 需要记录额外行为时，通过 `extras.local_tool` 声明

### 新增 MCP 服务

1. 在 `app/config/mcp_services.yaml` 增加服务配置
2. 确保服务端返回完整的 tool 元数据
3. 在 Skill 中写明何时调用这些工具

---

## 💡 适合先看的文件

- `app/orchestrator.py`
- `app/bootstrap.py`
- `app/runtime/local_tool_registry.py`
- `app/runtime/mcp_tool_registry.py`
- `app/runtime/skill_registry.py`
- `app/local_tools/run_skill.py`
- `mcp_server/server.py`

如果你刚接手这个项目，建议阅读顺序是：

1. `app/main.py`
2. `app/bootstrap.py`
3. `app/orchestrator.py`
4. `app/runtime/*_registry.py`
5. `app/local_tools/run_skill.py`
6. `app/skills/**/*.md`

这样最快 🪄
