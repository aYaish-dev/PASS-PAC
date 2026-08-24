import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_mode: str = "simulator"
    reports_dir: str = "reports"
    mock_data_dir: str = "mock-data"
    simulator_card_file: str = "flipper-imported-cards.json"
    proxmark_bridge_url: str | None = None
    proxmark_client_path: str | None = None
    proxmark_port: str | None = None
    proxmark_command_timeout_seconds: int = 10

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    timeout_value = os.getenv("PROXMARK_COMMAND_TIMEOUT_SECONDS", "10")
    try:
        timeout_seconds = int(timeout_value)
    except ValueError:
        timeout_seconds = 10

    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql://pass_pac_user:pass_pac_password@localhost:5432/pass_pac",
        ),
        app_mode=os.getenv("APP_MODE", "simulator"),
        reports_dir=os.getenv("REPORTS_DIR", "reports"),
        mock_data_dir=os.getenv("MOCK_DATA_DIR", "mock-data"),
        simulator_card_file=os.getenv(
            "SIMULATOR_CARD_FILE",
            "flipper-imported-cards.json",
        ),
        proxmark_bridge_url=_empty_to_none(os.getenv("PROXMARK_BRIDGE_URL")),
        proxmark_client_path=_empty_to_none(os.getenv("PROXMARK_CLIENT_PATH")),
        proxmark_port=_empty_to_none(os.getenv("PROXMARK_PORT")),
        proxmark_command_timeout_seconds=max(1, timeout_seconds),
    )


def _empty_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()
