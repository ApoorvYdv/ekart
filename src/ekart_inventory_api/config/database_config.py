from typing import Optional

from sqlalchemy import URL

from .settings.config import settings


class DatabaseConfig:
    db_username: Optional[str]
    db_password: Optional[str]
    db_engine: str
    db_host: Optional[str]
    db_port: Optional[str]
    db_name: Optional[str]

    def __init__(self, conf: dict = {}) -> None:
        conf_src = conf or settings

        self.db_username = conf_src.get("DB_USERNAME", "") or conf_src.get("PGUSER", "")
        self.db_password = conf_src.get("DB_PASSWORD", "") or conf_src.get(
            "PGPASSWORD", ""
        )
        self.db_engine = conf_src.get("DB_ENGINE", "postgresql")
        self.db_host = conf_src.get("DB_HOST", "") or conf_src.get("PGHOST", "")
        self.db_port = conf_src.get("DB_PORT", "") or conf_src.get("PGPORT", "5432")
        self.db_name = conf_src.get("DB_NAME", "") or conf_src.get("PGDATABASE", "")

        if self.db_engine == "postgres":
            # Handle default engine string from SSM
            self.db_engine = "postgresql"

    def build_db_url(
        self, async_driver: bool = False, use_test_db: bool = False
    ) -> URL:
        driver: str
        if not async_driver:
            driver = "postgresql+psycopg2"
        else:
            driver = "postgresql+asyncpg"
        url_object = URL.create(
            drivername=driver,
            username=self.db_username,
            password=self.db_password,
            host=self.db_host,
            port=int(self.db_port) if self.db_port else None,
            database=self.db_name if not use_test_db else "pems_api_test",
        )
        return url_object

    def build_url_as_string(self) -> str:
        return self.build_db_url().render_as_string(hide_password=False)
