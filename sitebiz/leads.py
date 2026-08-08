"""Приведение карточки 2ГИС к строке лида + оценка «насколько это горячий клиент»."""

import math

from . import twogis, website


def normalize(item: dict) -> dict:
    """Карточка каталога → плоский словарь лида."""
    contacts = website.extract_contacts(item)
    reviews = item.get("reviews") or {}
    org = item.get("org") or {}

    sites = list(contacts["sites"])
    hidden = website.find_domain_in_text(item.get("description") or "")
    if hidden and hidden not in sites:
        sites.append(hidden)

    status, reason = website.classify(sites, contacts["socials"])

    rubrics = [r.get("name") for r in item.get("rubrics") or [] if r.get("name")]
    point = item.get("point") or {}

    lead = {
        "id": item.get("id", ""),
        "name": item.get("name_ex", {}).get("primary") or item.get("name", ""),
        "full_name": item.get("name", ""),
        "categories": ", ".join(rubrics),
        "address": item.get("address_name") or "",
        "address_comment": item.get("address_comment") or "",
        "phones": ", ".join(contacts["phones"]),
        "emails": ", ".join(contacts["emails"]),
        "sites": ", ".join(sites),
        "socials": ", ".join(s["url"] for s in contacts["socials"]),
        "website_status": status,
        "website_status_label": website.STATUS_LABELS[status],
        "website_note": reason,
        "rating": reviews.get("org_rating") or reviews.get("general_rating") or "",
        "reviews_count": reviews.get("org_review_count")
        or reviews.get("general_review_count")
        or 0,
        "branch_count": org.get("branch_count") or 1,
        "schedule": twogis.format_schedule(twogis.item_schedule(item)),
        "lat": point.get("lat", ""),
        "lon": point.get("lon", ""),
        "url_2gis": twogis.public_url(item.get("id", "")),
        "photos": sum(
            block.get("count", 0)
            for block in item.get("external_content") or []
            if block.get("type") == "photo_album"
        ),
    }
    lead["score"] = score(lead)
    return lead


def score(lead: dict) -> int:
    """0–100: чем выше, тем интереснее лид для продажи сайта.

    Логика простая: живой бизнес с отзывами и телефоном, но без сайта — золото.
    Сетям (много филиалов) сайт обычно уже делают централизованно.
    """
    value = 0.0

    if lead["website_status"] == website.NONE:
        value += 45
    elif lead["website_status"] == website.WEAK:
        value += 35

    count = int(lead.get("reviews_count") or 0)
    value += min(25.0, 9 * math.log10(count + 1))  # 10 отзывов ≈ 9, 100 ≈ 18

    try:
        rating = float(lead.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0.0
    if rating >= 4.5:
        value += 12
    elif rating >= 4.0:
        value += 8
    elif rating >= 3.0:
        value += 3

    if lead.get("phones"):
        value += 8
    if lead.get("emails"):
        value += 4
    if lead.get("socials"):
        value += 4  # соцсети = бизнес уже вкладывается в продвижение
    if int(lead.get("photos") or 0) >= 5:
        value += 4  # есть фото — будет чем наполнить сайт

    branches = int(lead.get("branch_count") or 1)
    if branches > 5:
        value -= 15
    elif branches > 1:
        value -= 5

    return max(0, min(100, round(value)))


COLUMNS = [
    ("score", "Скор"),
    ("name", "Название"),
    ("categories", "Категории"),
    ("website_status_label", "Сайт"),
    ("website_note", "Детали"),
    ("rating", "Рейтинг"),
    ("reviews_count", "Отзывов"),
    ("phones", "Телефоны"),
    ("emails", "Почта"),
    ("address", "Адрес"),
    ("schedule", "Режим"),
    ("socials", "Соцсети"),
    ("sites", "Ссылки"),
    ("branch_count", "Филиалов"),
    ("photos", "Фото"),
    ("url_2gis", "Карточка 2ГИС"),
    ("lat", "Широта"),
    ("lon", "Долгота"),
    ("id", "ID"),
]
