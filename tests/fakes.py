from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict, PrivateAttr


class ScriptedAgentChatModel(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    responses: list[Any]
    _bound_tools: list[Any] = PrivateAttr(default_factory=list)
    _calls: list[list[BaseMessage]] = PrivateAttr(default_factory=list)
    _response_index: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted-agent-chat-model"

    @property
    def calls(self) -> list[list[BaseMessage]]:
        return self._calls

    @property
    def bound_tool_names(self) -> list[str]:
        result: list[str] = []
        for tool in self._bound_tools:
            name = getattr(tool, "name", None)
            if isinstance(name, str):
                result.append(name)
        return result

    def bind_tools(self, tools: list[Any], *, tool_choice: str | None = None, **kwargs: Any) -> "ScriptedAgentChatModel":
        _ = tool_choice
        _ = kwargs
        self._bound_tools = list(tools)
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        _ = stop
        _ = run_manager
        _ = kwargs
        self._calls.append(list(messages))
        response: Any = self.responses[self._response_index]
        self._response_index += 1
        message = response(list(messages)) if callable(response) else response
        return ChatResult(generations=[ChatGeneration(message=message)])
