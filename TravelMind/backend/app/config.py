from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    database_url: str
    checkpoint_database_url: str | None = None
    model_name: str = "qwen3.5-plus"
    model_api_key: SecretStr | None = None
    model_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_api_key: SecretStr | None = None
    amap_api_key: SecretStr | None = None
    amap_timeout_seconds: float = 10
    mcp_config_path: Path = PROJECT_ROOT / "config" / "mcp.json"
    feishu_verification_token: SecretStr | None = None
    feishu_encrypt_key: SecretStr | None = None
    feishu_app_id: str | None = None
    feishu_app_secret: SecretStr | None = None
    feishu_mcp_url: str = "https://mcp.feishu.cn/mcp"
    feishu_mcp_token: SecretStr | None = None

    @field_validator("mcp_config_path")
    @classmethod
    def resolve_mcp_config_path(cls, value: Path) -> Path:
        """Resolve relative MCP config paths from the repository root."""
        return value if value.is_absolute() else PROJECT_ROOT / value

    @property
    def langgraph_database_url(self) -> str:
        """Return the aiomysql-compatible URL used by LangGraph persistence."""
        value = self.checkpoint_database_url or self.database_url
        return value.replace("mysql+pymysql://", "mysql://", 1)


settings = Settings()
