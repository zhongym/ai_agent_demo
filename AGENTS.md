# Repository Guidelines

## 项目结构与模块组织
- `app/` 是主应用目录：`main.py` 暴露 FastAPI 入口，`bootstrap.py` 负责装配，`orchestrator.py` 串联路由、工具执行与追踪。
- `app/runtime/` 放运行时核心逻辑，如 `skill_registry.py`、`skill_executor.py`、`tool_registry.py`；`app/llm/` 放模型适配；`app/schemas/` 放 API 与意图数据结构。
- `app/config/` 保存 `mcp_services.yaml`；`app/skills/` 按业务域维护 Markdown Skill，例如 `catalog/product_recommend.md`。
- `mcp_server/` 提供本地 mock MCP 服务；`tests/` 放接口、编排与运行时测试。

## 构建、测试与开发命令
- `python3 -m venv .venv`：创建本地虚拟环境。
- `.venv/bin/pip install -r requirements.txt`：安装 FastAPI、pytest、fastmcp 等依赖。
- `cp .env.example .env`：初始化本地配置，提交前不要提交真实密钥。
- `.venv/bin/uvicorn app.main:app --reload`：启动开发 API，默认访问 `http://127.0.0.1:8000/docs`。
- `.venv/bin/pytest`：运行全部测试；如需聚焦回归，可先跑 `.venv/bin/pytest tests/test_api.py`。

## 编码风格与命名约定
- 使用 Python 3.13 风格，4 空格缩进，保持类型标注，优先沿用现有 `from __future__ import annotations`。
- 模块、函数、测试文件统一使用 `snake_case`；类名使用 `PascalCase`；Skill 文件名与 `skill_name` 保持一致，如 `kpi_query.md`。
- 代码仓库未配置独立格式化工具；提交前请至少保证导入分组清晰、无未使用符号，并与现有文件风格一致。

## 测试要求
- 测试框架为 `pytest`，异步流程使用 `@pytest.mark.anyio`，HTTP 接口使用 `fastapi.testclient.TestClient`。
- 新增或修改编排、Skill 绑定、MCP 工具逻辑时，优先补充对应的 `tests/test_orchestrator.py`、`tests/test_runtime.py` 或 `tests/test_api.py`。
- 测试文件命名遵循 `test_*.py`；断言优先覆盖意图名、结构化结果与关键回答文本。

## 提交与 Pull Request 规范
- 当前仓库尚无历史提交；建议从现在开始使用简洁的祈使句或 Conventional Commits，例如 `feat: add inventory skill`、`fix: sync mcp tool metadata`。
- PR 应包含：变更摘要、测试命令与结果、涉及的配置项、必要时附上 `/docs` 页面或响应示例截图。
- 若变更影响 `.env`、`app/config/` 或 Skill 行为，请在描述中明确迁移步骤与回滚方式。

## 安全与配置提示
- 使用 `.env.example` 维护必填变量说明，真实凭证只保留在本地 `.env`。
- 不要提交 `.venv/`、缓存文件、IDE 配置或追踪输出；新增本地生成物时同步更新 `.gitignore`。
