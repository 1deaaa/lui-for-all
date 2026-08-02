"""Matchbox GUI 启动流程回归测试。"""

from types import SimpleNamespace

from app.llm.agent_matchbox.gui.main_window import LLMConfigGUI


class _FakeManager:
    """记录 GUI 启动时调用的管理器初始化方法。"""

    def __init__(self, events):
        self._events = events

    def ensure_database_schema(self):
        self._events.append("ensure_database_schema")

    def initialize_defaults(self):
        self._events.append("initialize_defaults")


def test_bootstrap_startup_uses_current_manager_initialization_api():
    """启动应先检查主密钥，再初始化管理器，最后加载数据库配置。"""
    events = []
    startup = SimpleNamespace(
        root=SimpleNamespace(),
        ai_manager=_FakeManager(events),
    )
    startup._ensure_master_key_ready_on_startup = lambda: events.append("master_key") or True
    startup.load_config_from_db = lambda: events.append("load_config")

    LLMConfigGUI._bootstrap_startup(startup)

    assert events == [
        "ensure_database_schema",
        "master_key",
        "initialize_defaults",
        "load_config",
    ]


def test_set_default_mgr_home_updates_runtime_paths(tmp_path, monkeypatch):
    """宿主切换默认运行目录后，数据库和 .env 路径应同步切换。"""
    from app.llm.agent_matchbox import paths

    monkeypatch.delenv("AGENT_MATCHBOX_HOME", raising=False)

    try:
        resolved_home = paths.set_default_mgr_home(tmp_path)

        assert resolved_home == tmp_path.resolve()
        assert paths.get_mgr_home() == tmp_path.resolve()
        assert paths.get_db_file_path() == tmp_path.resolve() / "llm_config.db"
        assert paths.get_env_file_path() == tmp_path.resolve() / ".env"
    finally:
        paths.set_default_mgr_home(None)


def test_env_cache_follows_default_mgr_home_changes(tmp_path, monkeypatch):
    """切换默认运行目录后，.env 缓存不得继续复用旧目录内容。"""
    from app.llm.agent_matchbox import env_utils, paths

    first_home = tmp_path / "first"
    second_home = tmp_path / "second"
    monkeypatch.delenv("AGENT_MATCHBOX_HOME", raising=False)
    monkeypatch.delenv("MATCHBOX_TEST_VALUE", raising=False)

    try:
        paths.set_default_mgr_home(first_home)
        env_utils._ensure_env_file().write_text(
            "MATCHBOX_TEST_VALUE=first\n",
            encoding="utf-8",
        )
        assert env_utils.get_env_var("MATCHBOX_TEST_VALUE") == "first"

        paths.set_default_mgr_home(second_home)
        assert env_utils.get_env_path() == second_home / ".env"
        assert env_utils.get_env_var("MATCHBOX_TEST_VALUE") is None
    finally:
        paths.set_default_mgr_home(None)
