"""Клиент публичных API 2ГИС: города, поиск организаций, карточка, отзывы."""

from . import config
from .http import ApiError, get_json

WEEKDAYS = [
    ("Mon", "Пн"),
    ("Tue", "Вт"),
    ("Wed", "Ср"),
    ("Thu", "Чт"),
    ("Fri", "Пт"),
    ("Sat", "Сб"),
    ("Sun", "Вс"),
]


def find_regions(city: str) -> list:
    """Найти регион (город) 2ГИС по названию."""
    data = get_json(
        f"{config.CATALOG_URL}/2.0/region/search",
        {"q": city, "key": config.CATALOG_KEY, "locale": "ru_RU"},
    )
    return (data.get("result") or {}).get("items") or []


def resolve_region_id(city: str) -> str:
    """Один регион по названию города, иначе понятная ошибка со списком вариантов."""
    regions = find_regions(city)
    if not regions:
        raise ApiError(
            f"Город «{city}» не найден в 2ГИС. Попробуй другое написание "
            f"или задай --region-id вручную (см. команду `cities`)."
        )
    return str(regions[0]["id"])


def search_page(
    region_id: str,
    query: str = None,
    rubric_id: str = None,
    page: int = 1,
    page_size: int = config.MAX_PAGE_SIZE,
) -> dict:
    """Одна страница выдачи каталога."""
    data = get_json(
        f"{config.CATALOG_URL}/3.0/items",
        {
            "q": query,
            "rubric_id": rubric_id,
            "region_id": region_id,
            "page": page,
            "page_size": min(page_size, config.MAX_PAGE_SIZE),
            "type": "branch",
            "fields": config.ITEM_FIELDS,
            "locale": "ru_RU",
            "key": config.CATALOG_KEY,
        },
    )
    meta = data.get("meta") or {}
    if meta.get("code") not in (200, None):
        message = (meta.get("error") or {}).get("message", "неизвестная ошибка")
        raise ApiError(f"2ГИС вернул код {meta.get('code')}: {message}")
    return data.get("result") or {}


def iter_items(
    region_id: str,
    query: str = None,
    rubric_id: str = None,
    limit: int = 200,
    on_page=None,
):
    """Постранично обойти выдачу и вернуть до `limit` карточек."""
    collected = 0
    page = 1
    total = None

    while collected < limit:
        page_size = min(config.MAX_PAGE_SIZE, limit - collected)
        try:
            result = search_page(region_id, query, rubric_id, page, page_size)
        except ApiError as exc:
            # Каталог обрывает глубокую пагинацию — это не повод терять собранное.
            if page > 1:
                if on_page:
                    on_page(page, collected, total, str(exc))
                break
            raise

        items = result.get("items") or []
        if total is None:
            total = result.get("total")
        if not items:
            break

        for item in items:
            yield item
            collected += 1

        if on_page:
            on_page(page, collected, total, None)

        if len(items) < page_size:
            break
        page += 1


def get_item(item_id: str) -> dict:
    """Карточка организации по её id (полный id с хвостом или числовой)."""
    data = get_json(
        f"{config.CATALOG_URL}/3.0/items/byid",
        {
            "id": item_id,
            "fields": config.ITEM_FIELDS,
            "locale": "ru_RU",
            "key": config.CATALOG_KEY,
        },
    )
    items = (data.get("result") or {}).get("items") or []
    if not items:
        raise ApiError(f"Организация {item_id} не найдена в каталоге 2ГИС")
    return items[0]


def branch_id(item_id: str) -> str:
    """Числовой id филиала — то, что понимает сервис отзывов."""
    return str(item_id).split("_", 1)[0]


def get_reviews(item_id: str, limit: int = 30) -> dict:
    """Тексты отзывов, оценки, фото и ответы владельца."""
    reviews, meta = [], {}
    offset_date = None

    while len(reviews) < limit:
        data = get_json(
            f"{config.REVIEWS_URL}/2.0/branches/{branch_id(item_id)}/reviews",
            {
                "limit": min(50, limit - len(reviews)),
                "is_advertiser": "false",
                "fields": "meta.branch_rating,meta.branch_reviews_count,meta.total_count",
                "without_my_first_review": "false",
                "rated": "true",
                "sort_by": "friends",
                "offset_date": offset_date,
                "locale": "ru_RU",
                "key": config.REVIEWS_KEY,
            },
        )
        meta = data.get("meta") or meta
        batch = data.get("reviews") or []
        if not batch:
            break
        reviews.extend(batch)

        next_link = (data.get("meta") or {}).get("next_link") or ""
        if "offset_date=" not in next_link:
            break
        import urllib.parse

        offset_date = urllib.parse.parse_qs(
            urllib.parse.urlparse(next_link).query
        ).get("offset_date", [None])[0]
        if not offset_date:
            break

    return {"meta": meta, "reviews": reviews[:limit]}


def format_schedule(schedule: dict) -> str:
    """Расписание 2ГИС → человеческая строка."""
    if not schedule:
        return ""
    if schedule.get("everyday"):
        hours = schedule["everyday"].get("working_hours") or []
        if hours:
            return "Ежедневно " + ", ".join(f"{h['from']}–{h['to']}" for h in hours)
        return "Ежедневно, круглосуточно"

    parts = []
    for key, label in WEEKDAYS:
        day = schedule.get(key)
        if not day:
            parts.append(f"{label}: выходной")
            continue
        hours = day.get("working_hours") or []
        if not hours:
            parts.append(f"{label}: круглосуточно")
        else:
            parts.append(f"{label}: " + ", ".join(f"{h['from']}–{h['to']}" for h in hours))
    return "; ".join(parts)


def item_schedule(item: dict) -> dict:
    """Расписание лежит либо в корне карточки, либо внутри группы контактов."""
    if item.get("schedule"):
        return item["schedule"]
    for group in item.get("contact_groups") or []:
        if group.get("schedule"):
            return group["schedule"]
    return {}


def public_url(item_id: str) -> str:
    return f"https://2gis.ru/firm/{branch_id(item_id)}"
