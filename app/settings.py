from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ENV_FILE = Path(__file__).resolve().with_name(".env")


class Settings(BaseSettings):
    """主应用配置。

    这里只保留 API 与 agent 编排真正使用的设置项。
    主应用默认从 `app/.env` 读取环境变量。
    """

    model_config = SettingsConfigDict(
        env_file=APP_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="Enterprise Data Agent Demo", alias="APP_NAME")

    dashscope_api_key: str | None = Field(default=None, alias="DASHSCOPE_API_KEY")
    bailian_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="BAILIAN_BASE_URL",
    )
    bailian_model: str = Field(default="qwen-plus", alias="BAILIAN_MODEL")
    llm_log_payloads: bool = Field(default=True, alias="LLM_LOG_PAYLOADS")
    agent_recursion_limit: int = Field(default=25, alias="AGENT_RECURSION_LIMIT")
    summary_trigger_messages: int = Field(default=40, alias="SUMMARY_TRIGGER_MESSAGES")
    summary_trigger_tokens: int = Field(default=6000, alias="SUMMARY_TRIGGER_TOKENS")
    summary_keep_messages: int = Field(default=20, alias="SUMMARY_KEEP_MESSAGES")

    mcp_timeout_seconds: float = Field(default=10.0, alias="MCP_TIMEOUT_SECONDS")
    skills_dir: str = Field(default="app/skills", alias="SKILLS_DIR")
    mcp_services_config: str = Field(default="app/config/mcp_services.yaml", alias="MCP_SERVICES_CONFIG")

    def resolve_path(self, relative_or_absolute: str) -> Path:
        return Path(relative_or_absolute).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
