import json
import logging
from datetime import datetime
from dataclasses import dataclass, asdict

from Bot_mini_map_ai.config.settings import settings


logger = logging.getLogger(__name__)


@dataclass
class ParseState:
    last_page: int = 0
    offers_collected: int = 0
    parsed_urls: list[str] | None = None
    session_started: str = ""
    cookie_file: str = ""


class ParseResumer:
    STATE_FILE = settings.ROOT_DIR / "data" / "parse_state.json"

    def __init__(self):
        self._state = self._load()

    def _load(self) -> ParseState:
        if not self.STATE_FILE.exists():
            return ParseState()
        try:
            data = json.loads(self.STATE_FILE.read_text())
            return ParseState(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Corrupt state file, starting fresh: %s", e)
            return ParseState()

    def _save(self) -> None:
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.STATE_FILE.write_text(
            json.dumps(asdict(self._state), ensure_ascii=False, indent=2)
        )

    @property
    def last_page(self) -> int:
        return self._state.last_page

    @property
    def offers_collected(self) -> int:
        return self._state.offers_collected

    def has_saved_state(self) -> bool:
        return self._state.last_page > 0

    def update(self, *, page: int, offers: int, urls: list[str] | None = None) -> None:
        self._state.last_page = page
        self._state.offers_collected = offers
        if urls is not None:
            self._state.parsed_urls = urls
        self._state.cookie_file = settings.PARSER_COOKIE_FILE
        self._save()

    def start_session(self) -> None:
        self._state.session_started = datetime.now().isoformat()
        self._state.cookie_file = settings.PARSER_COOKIE_FILE
        self._save()

    def clear(self) -> None:
        self._state = ParseState()
        if self.STATE_FILE.exists():
            self.STATE_FILE.unlink()

    def get_parsed_urls(self) -> set[str]:
        return set(self._state.parsed_urls or [])
