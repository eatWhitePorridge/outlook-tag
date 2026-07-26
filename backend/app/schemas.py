from pydantic import BaseModel, Field


class LoginBody(BaseModel):
    password: str


class AccountCreate(BaseModel):
    raw: str | None = None
    email: str = ""
    password: str = ""
    client_id: str = ""
    refresh_token: str = ""
    note: str = ""


class AccountUpdate(BaseModel):
    email: str | None = None
    password: str | None = None
    client_id: str | None = None
    refresh_token: str | None = None
    note: str | None = None


class BatchImportBody(BaseModel):
    lines: str = Field(..., description="每行: email----password----client_id----refresh_token")


class BatchIdsBody(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)


class AliasCreate(BaseModel):
    tag: str = ""


class LookupBody(BaseModel):
    email: str


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)


class ApiKeyUpdate(BaseModel):
    enabled: bool


class SystemSettingsUpdate(BaseModel):
    probe_enabled: bool | None = None
    probe_interval_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    probe_batch_size: int | None = Field(default=None, ge=1, le=200)
    probe_workers: int | None = Field(default=None, ge=1, le=16)
    probe_stale_hours: int | None = Field(default=None, ge=1, le=168)
