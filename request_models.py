"""
request_models.py — Pydantic request schemas for the DB Tool.

All inbound JSON bodies are validated here before touching application logic.
FastAPI will automatically return HTTP 422 with field-level details if validation fails.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=1, max_length=512)


# ---------------------------------------------------------------------------
# Database Connection
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    host: str     = Field(..., min_length=1, max_length=253)
    port: int     = Field(3306, ge=1, le=65535)
    user: str     = Field("", max_length=64)   # Optional: may be blank for hosts stored without username
    password: str = Field("", max_length=512)

    @field_validator('host')
    @classmethod
    def host_no_special_chars(cls, v: str) -> str:
        import re
        if not re.match(r'^[A-Za-z0-9.\-_]{1,253}$', v):
            raise ValueError('Invalid hostname or IP address')
        return v


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

VALID_DUMP_MODES = {'Plain', 'Obscure', 'Service Off', 'Tenant Change', 'Include Structure',
                    'Dump Routines', 'Dump Events', 'Dump Triggers', 'Dump Views'}

class StartExportRequest(BaseModel):
    database:     str           = Field(..., min_length=1, max_length=64)
    dump_modes:   List[str]     = Field(default_factory=lambda: ['Plain'])
    dump_mode:    str           = Field('Plain')
    new_tenant_name: Optional[str] = Field(None, max_length=64)
    host_key:     str           = Field('unknown', max_length=64)

    @field_validator('database', 'new_tenant_name', mode='before')
    @classmethod
    def safe_identifier(cls, v):
        if v is None:
            return v
        import re
        if not re.match(r'^[A-Za-z0-9_\-]{1,64}$', str(v)):
            raise ValueError(f'Value contains invalid characters: {v!r}')
        return v

    @field_validator('dump_modes', mode='before')
    @classmethod
    def validate_modes(cls, v):
        if not isinstance(v, list):
            v = [v]
        for mode in v:
            if mode not in VALID_DUMP_MODES:
                raise ValueError(f'Unknown dump mode: {mode!r}')
        return v


class DownloadRequest(BaseModel):
    database:    str           = Field(..., min_length=1, max_length=64)
    dump_mode:   str           = Field('Plain')
    new_tenant_name: Optional[str] = Field(None, max_length=64)
    host_key:    str           = Field('unknown', max_length=64)

    @field_validator('database', 'new_tenant_name', mode='before')
    @classmethod
    def safe_identifier(cls, v):
        if v is None:
            return v
        import re
        if not re.match(r'^[A-Za-z0-9_\-]{1,64}$', str(v)):
            raise ValueError(f'Value contains invalid characters: {v!r}')
        return v

    @field_validator('dump_mode')
    @classmethod
    def valid_mode(cls, v):
        if v not in VALID_DUMP_MODES:
            raise ValueError(f'Unknown dump mode: {v!r}')
        return v


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------

class AddUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=150)
    password: str = Field(..., min_length=8, max_length=512,
                          description="Minimum 8 characters")

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        import re
        if not re.match(r'^[A-Za-z0-9_.\-@+]{2,150}$', v):
            raise ValueError('Username may only contain letters, digits, and @.+-_')
        return v

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class DeleteUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)


class ResetPasswordRequest(BaseModel):
    username:     str = Field(..., min_length=1, max_length=150)
    new_password: str = Field(..., min_length=8, max_length=512)

    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


# ---------------------------------------------------------------------------
# Export Control / Retry
# ---------------------------------------------------------------------------

class ExportControlRequest(BaseModel):
    action: str = Field(...)

    @field_validator('action')
    @classmethod
    def valid_action(cls, v: str) -> str:
        if v not in ('pause', 'resume', 'cancel'):
            raise ValueError(f'Unknown action: {v!r}. Must be pause, resume, or cancel.')
        return v


class RetryExportRequest(BaseModel):
    job_id:     str = Field(..., min_length=1)
    retry_mode: str = Field(...)

    @field_validator('retry_mode')
    @classmethod
    def valid_retry_mode(cls, v: str) -> str:
        if v not in ('failed', 'full', 'ignore'):
            raise ValueError(f'Unknown retry_mode: {v!r}')
        return v
