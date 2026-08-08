"""Минимальный HTTP-клиент на стандартной библиотеке (без внешних зависимостей)."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config


class ApiError(RuntimeError):
    """Ошибка обращения к API 2ГИС."""


_last_call = 0.0


def _throttle() -> None:
    global _last_call
    delta = time.monotonic() - _last_call
    if delta < config.THROTTLE:
        time.sleep(config.THROTTLE - delta)
    _last_call = time.monotonic()


def get_json(url: str, params: dict, retries: int = 3) -> dict:
    """GET с параметрами, ретраями и разбором JSON."""
    clean = {k: v for k, v in params.items() if v is not None}
    full = f"{url}?{urllib.parse.urlencode(clean, doseq=True)}"
    last_error = None

    for attempt in range(retries):
        _throttle()
        request = urllib.request.Request(
            full, headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=config.TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:400]
            # 4xx повторять бессмысленно, кроме 429.
            if exc.code != 429 and 400 <= exc.code < 500:
                raise ApiError(f"HTTP {exc.code} для {url}: {body}") from exc
            last_error = ApiError(f"HTTP {exc.code} для {url}: {body}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = ApiError(f"Сбой запроса к {url}: {exc}")
        time.sleep(2 ** attempt)

    raise last_error or ApiError(f"Не удалось получить данные с {url}")


def fetch_text(url: str, timeout: int | None = None) -> str:
    """Скачать страницу как текст (для разбора ссылок Яндекс.Карт)."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru-RU,ru;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout or config.TIMEOUT) as response:
        return response.read().decode("utf-8", "replace")
