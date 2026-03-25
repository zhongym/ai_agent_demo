from __future__ import annotations

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.bootstrap import build_orchestrator
from app.main import create_app
from app.settings import Settings
from tests.fakes import ScriptedAgentChatModel


def test_query_api_requires_thread_id() -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        response = client.post("/query", json={"question": "推荐500元以内李宁鞋"})

    assert response.status_code == 422


def test_build_orchestrator_initializes_synchronously() -> None:
    settings = Settings(
        skills_dir="/Users/zhongym/ai_agent/app/skills",
        mcp_services_config="/Users/zhongym/ai_agent/app/config/mcp_services.yaml",
    )
    orchestrator = build_orchestrator(
        settings,
        chat_model=ScriptedAgentChatModel(
            responses=[
                AIMessage(content="收到，我会基于这个会话继续处理。"),
            ]
        ),
    )
    assert orchestrator._initialized is True


def test_health_api_returns_llm_provider_and_mcp_transport() -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        response = client.get("/health")
        data = response.json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["llm_provider"] == "bailian-langchain"
    assert data["mcp_transport"] == "data_center:stdio"


def test_demo_questions_api_is_removed() -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        response = client.get("/demo-questions")

    assert response.status_code == 404


def test_query_api_returns_thread_id_and_message_summary() -> None:
    settings = Settings(
        skills_dir="/Users/zhongym/ai_agent/app/skills",
        mcp_services_config="/Users/zhongym/ai_agent/app/config/mcp_services.yaml",
    )
    orchestrator = build_orchestrator(
        settings,
        chat_model=ScriptedAgentChatModel(
            responses=[
                AIMessage(content="收到，我会基于这个会话继续处理。"),
            ]
        ),
    )
    app = create_app(settings, orchestrator=orchestrator)
    with TestClient(app) as client:
        response = client.post("/query", json={"thread_id": "api-thread", "question": "你好"})
        data = response.json()

    assert response.status_code == 200
    assert data["thread_id"] == "api-thread"
    assert data["message_summary"]["tool_calls"] == []
    assert "run_id" not in data
    assert "session_id" not in data
