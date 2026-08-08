"""Разбор ссылок 2ГИС и Яндекс.Карт → карточка организации в каталоге 2ГИС."""

import re
import urllib.error
import urllib.parse
import urllib.request

from . import config, twogis
from .http import ApiError

TWOGIS_HOSTS = ("2gis.ru", "2gis.com", "2gis.kz", "2gis.ae", "2gis.uz", "go.2gis.com")
YANDEX_HOSTS = ("yandex.ru", "yandex.com", "ya.ru", "yandex.com.tr")

_FIRM_RE = re.compile(r"/firm/(\d+)")
_YA_ORG_RE = re.compile(r"/maps/org/([^/]+)/(\d+)")
_YA_PROFILE_RE = re.compile(r"/(?:maps/)?profile/(?:([^/]+)/)?(\d+)")
_LL_RE = re.compile(r"[?&]ll=(-?[\d.]+)%2C(-?[\d.]+)|[?&]ll=(-?[\d.]+),(-?[\d.]+)")


def _follow_redirects(url: str) -> str:
    """Развернуть короткую ссылку (go.2gis.com, yandex.ru/maps/-/…)."""
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": config.USER_AGENT}, method="HEAD"
        )
        with urllib.request.urlopen(request, timeout=config.TIMEOUT) as response:
            return response.geturl()
    except (urllib.error.URLError, TimeoutError, ValueError):
        return url


def _coords(url: str):
    match = _LL_RE.search(url)
    if not match:
        return None
    groups = [g for g in match.groups() if g]
    if len(groups) < 2:
        return None
    return float(groups[0]), float(groups[1])  # lon, lat


def slug_to_query(slug: str) -> str:
    """`kofejnya_zerno` → `kofejnya zerno` (поисковый запрос для каталога)."""
    return urllib.parse.unquote(slug).replace("_", " ").replace("-", " ").strip()


def resolve(link_or_id: str, city: str = None) -> dict:
    """Вернуть {'item': карточка 2ГИС, 'source': '2gis'|'yandex', 'note': ...}.

    Поддерживает: ссылку 2ГИС, короткую go.2gis.com, id филиала,
    ссылку Яндекс.Карт (ищем ту же организацию в 2ГИС по названию и координатам).
    """
    value = (link_or_id or "").strip()
    if not value:
        raise ApiError("Не передана ссылка или id организации")

    # Голый числовой id.
    if value.isdigit():
        return {"item": twogis.get_item(value), "source": "2gis", "note": ""}

    if "://" not in value:
        value = "https://" + value

    host = urllib.parse.urlparse(value).netloc.lower().replace("www.", "")

    if any(host == h or host.endswith("." + h) for h in TWOGIS_HOSTS):
        if host.startswith("go."):
            value = _follow_redirects(value)
        match = _FIRM_RE.search(value)
        if not match:
            raise ApiError(
                "В ссылке 2ГИС не нашёл id организации. "
                "Нужна ссылка вида https://2gis.ru/moscow/firm/70000001112487425"
            )
        return {"item": twogis.get_item(match.group(1)), "source": "2gis", "note": ""}

    if any(host == h or host.endswith("." + h) for h in YANDEX_HOSTS):
        return _resolve_yandex(value, city)

    raise ApiError(
        f"Не понимаю ссылку с домена {host}. Поддерживаются 2ГИС и Яндекс.Карты."
    )


def _resolve_yandex(url: str, city: str = None) -> dict:
    """Яндекс не отдаёт данные организации ботам, поэтому ищем ту же точку в 2ГИС."""
    if "/maps/-/" in url or "/-/" in url:
        url = _follow_redirects(url)

    match = _YA_ORG_RE.search(url) or _YA_PROFILE_RE.search(url)
    slug = match.group(1) if match and match.lastindex and match.group(1) else ""
    query = slug_to_query(slug) if slug else ""

    if not query:
        raise ApiError(
            "Из ссылки Яндекс.Карт не удалось вытащить название организации. "
            "Скинь ссылку вида https://yandex.ru/maps/org/название/123456789/ "
            "или найди этот же бизнес в 2ГИС."
        )

    point = _coords(url)
    params_search = {
        "q": query,
        "fields": config.ITEM_FIELDS,
        "locale": "ru_RU",
        "key": config.CATALOG_KEY,
        "page_size": 5,
        "type": "branch",
    }
    if point:
        params_search["point"] = f"{point[0]},{point[1]}"
        params_search["radius"] = 2000
    elif city:
        params_search["region_id"] = twogis.resolve_region_id(city)
    else:
        raise ApiError(
            "В ссылке Яндекса нет координат. Добавь город: --city «Москва»."
        )

    from .http import get_json

    data = get_json(f"{config.CATALOG_URL}/3.0/items", params_search)
    items = (data.get("result") or {}).get("items") or []
    if not items:
        raise ApiError(
            f"Организацию «{query}» не нашёл в 2ГИС. "
            "Проверь, есть ли она там, и пришли ссылку 2ГИС."
        )

    return {
        "item": items[0],
        "source": "yandex",
        "note": (
            f"Ссылка была на Яндекс.Карты; данные взяты из совпавшей карточки 2ГИС "
            f"«{items[0].get('name')}» ({items[0].get('address_name')}). "
            "Сверь, что это тот же бизнес."
        ),
    }
