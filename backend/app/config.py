from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    secret_key: str = ""
    admin_password: str = ""
    # 环境变量 DB_PATH（pydantic-settings 对字段名大小写不敏感）
    db_path: str = Field(default="")
    public_token_ttl: int = 3600
    session_ttl: int = 86400 * 7
    # 同域部署（Docker 内静态 + API）可留空
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # 经 HTTPS 反代时设 true，管理 Cookie 带 Secure
    cookie_secure: bool = False
    host: str = "0.0.0.0"
    port: int = 8080

    @field_validator("cookie_secure", mode="before")
    @classmethod
    def _parse_bool(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on"}
        return bool(v)

    def resolve_db_path(self) -> str:
        if self.db_path:
            p = Path(self.db_path)
            if p.is_absolute():
                return str(p)
            # 相对路径：优先相对仓库根，其次 backend/
            repo_root = Path(__file__).resolve().parent.parent.parent
            backend_dir = Path(__file__).resolve().parent.parent
            for base in (repo_root, backend_dir, Path.cwd()):
                candidate = (base / p).resolve()
                if candidate.parent.exists():
                    return str(candidate)
            return str((repo_root / p).resolve())

        default = Path(__file__).resolve().parent.parent / "data" / "mail.db"
        return str(default)

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # allow_origins=["*"] 配合 allow_credentials=True 时，Starlette 会
        # 回显调用方的 Origin —— 任意站点都能带着管理 Cookie 驱动后台接口。
        # 直接拒绝，而不是留个安静的脚枪。
        if "*" in origins:
            raise ValueError(
                "CORS_ORIGINS 不能为 *（会与 Cookie 凭据一起构成 CSRF 通道）；"
                "同域部署请留空，跨域请写明确的来源"
            )
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
