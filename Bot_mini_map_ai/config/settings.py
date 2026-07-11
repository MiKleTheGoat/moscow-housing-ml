from pathlib import Path
from typing import List, Any
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Telegram ──────────────────────────────────────────────────────────
    MAIN_BOT_TOKEN: str
    SUPPORT_BOT_TOKEN: str
    ADMIN_ID: int
    MINI_APP_URL: str


    PARSER_HEADLESS: bool = True
    PARSER_MAX_CONCURRENT: int = 5
    PARSER_MAX_PAGES: int = 50
    PARSER_START_PAGE: int = 1
    PARSER_COOKIE_FILE: str = "data/cian_cookies.json"

    ML_API_URL: str = "http://localhost:8001"

    DATABASE_URL: str
    CSV_PATH: str = "data/csv/house_cian.csv"
    MODEL_PATH: str = "data/model.pkl"


    REDIS_URL: str
    CELERY_RESULT_BACKEND: str

    MLFLOW_TRACKING_URI: str
    MLFLOW_EXPERIMENT_NAME: str = "moscow_housing"

    # ── Admin ────────────────────────────────────────────────────────────────
    ADMIN_PASSWORD: str
    ADMIN_JWT_SECRET: str
    ADMIN_TOTP_SECRET: str
    ADMIN_JWT_TTL_MINUTES: int = 1000
    ADMIN_IP_WHITELIST: str

     # ── Url Parser Proxy  ────────────────────────────────────────────────────────────────
    URL_PARSER_PROXY: str = ""
    PARSER_PROXY_POOL: str = ""


    @staticmethod
    def _to_pw_proxy(raw: str) -> str:
        url = urlparse(raw)
        proxy = {"server": f"{url.scheme}://{url.netloc}:{url.port}"}
        if url.username:
            proxy["username"] = url.username
        if url.password:
            proxy["password"] = url.password
        return proxy

    @property
    def playwright_url(self) -> dict | None:
        return self._to_pw_proxy(self.URL_PARSER_PROXY) if self.URL_PARSER_PROXY else None

    @property
    def proxy_pool(self) -> list[dict] | list[Any]:
        if not self.PARSER_PROXY_POOL:
            return []
        return [self._to_pw_proxy(p.strip())
                for p in self.PARSER_PROXY_POOL.split(",") if p.strip()]


    # --- Paths ---
    ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent

    @model_validator(mode='after')
    def resolve_paths(self) -> 'Settings':
        csv_path = Path(self.CSV_PATH)
        if not csv_path.is_absolute():
            abs_csv = (self.ROOT_DIR / csv_path).resolve()
            abs_csv.parent.mkdir(parents=True, exist_ok=True)
            self.CSV_PATH = str(abs_csv)

        model_path = Path(self.MODEL_PATH)
        if not model_path.is_absolute():
            abs_model = (self.ROOT_DIR / model_path).resolve()
            abs_model.parent.mkdir(parents=True, exist_ok=True)
            self.MODEL_PATH = str(abs_model)

        cookie_path = Path(self.PARSER_COOKIE_FILE)
        if not cookie_path.is_absolute():
            abs_cookie = (self.ROOT_DIR / cookie_path).resolve()
            abs_cookie.parent.mkdir(parents=True, exist_ok=True)
            self.PARSER_COOKIE_FILE = str(abs_cookie)

        return self

    @property
    def ip_whitelist(self) -> List[str]:
        if not self.ADMIN_IP_WHITELIST:
            return []
        return [ip.strip() for ip in self.ADMIN_IP_WHITELIST.split(",") if ip.strip()]


settings = Settings()

