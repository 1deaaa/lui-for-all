import os

import pytest

import app.config as config
from app.api import settings as settings_api


@pytest.mark.asyncio
async def test_save_runtime_settings_persists_demo_mode(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"

    def ensure_env_file():
        env_path.touch(exist_ok=True)
        return env_path

    monkeypatch.setattr(settings_api, "_ensure_env_file", ensure_env_file)
    monkeypatch.setattr(config, "ENV_FILE_PATH", env_path)
    monkeypatch.setattr(config.settings, "demo_mode", config.settings.demo_mode)

    for env_name in (
        "LUI_DEMO_MODE",
        "LUI_MCP_API_TOKEN",
        "LUI_SAFETY_DEFAULT_ACTION",
        "LUI_JWT_SECRET",
    ):
        if env_name in os.environ:
            monkeypatch.setenv(env_name, os.environ[env_name])
        else:
            monkeypatch.delenv(env_name, raising=False)

    monkeypatch.setenv("LUI_JWT_SECRET", config.settings.jwt_secret)

    response = await settings_api.save_runtime_settings(
        settings_api.SettingsPayload(
            mcp_api_token="demo-token",
            safety_default_action="confirm",
            demo_mode=True,
        )
    )

    assert response.demo_mode is True
    assert "LUI_DEMO_MODE=true" in env_path.read_text(encoding="utf-8")

    preserved_response = await settings_api.save_runtime_settings(
        settings_api.SettingsPayload(
            mcp_api_token="demo-token",
            safety_default_action="confirm",
        )
    )

    assert preserved_response.demo_mode is True
