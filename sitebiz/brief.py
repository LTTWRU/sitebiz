"""Сбор контент-брифа по организации: всё, из чего можно собрать сайт."""

from . import twogis, website
from .leads import normalize


def build(item: dict, reviews_limit: int = 30) -> dict:
    """Карточка 2ГИС + отзывы → структурированный бриф для генерации сайта."""
    lead = normalize(item)
    contacts = website.extract_contacts(item)
    item_id = item.get("id", "")

    try:
        review_data = twogis.get_reviews(item_id, limit=reviews_limit)
    except Exception as exc:  # отзывы — приятный бонус, а не блокер
        review_data = {"meta": {}, "reviews": [], "error": str(exc)}

    reviews = [_review(r) for r in review_data.get("reviews") or []]
    # Сначала хвалебные и залайканные — из них и собирается блок отзывов на сайте,
    # негатив оставляем в хвосте: он показывает слабые места, которые стоит закрыть текстом.
    reviews.sort(key=lambda r: (-(r["rating"] or 0), -r["likes"], -len(r["text"])))
    photos = _photos(item, review_data.get("reviews") or [])

    return {
        "business": {
            "name": lead["name"],
            "full_name": lead["full_name"],
            "legal_name": (item.get("org") or {}).get("name", ""),
            "tagline_source": (item.get("name_ex") or {}).get("extension", ""),
            "description": item.get("description") or "",
            "categories": [r.get("name") for r in item.get("rubrics") or []],
            "primary_category": next(
                (r.get("name") for r in item.get("rubrics") or []
                 if r.get("kind") == "primary"),
                (lead["categories"].split(", ") or [""])[0],
            ),
            "branch_count": lead["branch_count"],
            "url_2gis": lead["url_2gis"],
            "id": item_id,
        },
        "contacts": {
            "phones": contacts["phones"],
            "emails": contacts["emails"],
            "websites": contacts["sites"],
            "socials": contacts["socials"],
            "website_status": lead["website_status"],
            "website_note": lead["website_note"],
        },
        "location": {
            "address": lead["address"],
            "address_comment": lead["address_comment"],
            "city": _city(item),
            "district": _district(item),
            "lat": lead["lat"],
            "lon": lead["lon"],
            "floors": item.get("floors") or [],
        },
        "schedule": {
            "human": lead["schedule"],
            "raw": twogis.item_schedule(item),
        },
        "reputation": {
            "rating": lead["rating"],
            "reviews_count": lead["reviews_count"],
            "reviews_with_text": len([r for r in reviews if r["text"]]),
            "photos_count": lead["photos"],
        },
        "offering": _attributes(item),
        "reviews": reviews,
        "photos": photos,
        "lead": lead,
    }


def _city(item: dict) -> str:
    for div in item.get("adm_div") or []:
        if div.get("type") == "city":
            return div.get("name", "")
    return ""


def _district(item: dict) -> str:
    names = [
        d.get("name", "")
        for d in item.get("adm_div") or []
        if d.get("type") in ("district", "district_area", "settlement")
    ]
    return ", ".join(n for n in names if n)


def _attributes(item: dict) -> list:
    """attribute_groups 2ГИС — это готовый список услуг, удобств и фишек бизнеса."""
    groups = []
    for group in item.get("attribute_groups") or []:
        values = [a.get("name") for a in group.get("attributes") or [] if a.get("name")]
        if values:
            groups.append({"group": group.get("name", ""), "values": values})
    return groups


def _review(raw: dict) -> dict:
    user = raw.get("user") or {}
    answer = raw.get("official_answer") or {}
    return {
        "author": user.get("name") or "Гость",
        "rating": raw.get("rating"),
        "date": (raw.get("date_created") or "")[:10],
        "text": (raw.get("text") or "").strip(),
        "likes": raw.get("likes_count", 0),
        "owner_reply": (answer.get("text") or "").strip(),
        "photos": [
            (p.get("preview_urls") or {}).get("1920x", "")
            for p in raw.get("photos") or []
        ],
    }


def _photos(item: dict, raw_reviews: list) -> list:
    """Ссылки на реальные фото: обложки альбомов + фото из отзывов."""
    photos = []
    for block in item.get("external_content") or []:
        url = block.get("main_photo_url")
        if url:
            photos.append({"url": f"{url}?w=1920", "source": block.get("subtype", "2gis")})
    for raw in raw_reviews:
        for photo in raw.get("photos") or []:
            url = (photo.get("preview_urls") or {}).get("1920x")
            if url:
                photos.append({"url": url, "source": "review"})
    # Без дублей, порядок сохраняем.
    seen, unique = set(), []
    for photo in photos:
        if photo["url"] not in seen:
            seen.add(photo["url"])
            unique.append(photo)
    return unique


def to_markdown(data: dict) -> str:
    """Бриф в читаемом виде — его же можно просто вставить в чат."""
    biz = data["business"]
    loc = data["location"]
    con = data["contacts"]
    rep = data["reputation"]

    lines = [
        f"## Бриф: {biz['full_name'] or biz['name']}",
        "",
        f"- **Название:** {biz['name']}",
        f"- **Юрлицо / бренд:** {biz['legal_name'] or '—'}",
        f"- **Сфера:** {biz['primary_category'] or '—'} "
        f"({', '.join(biz['categories']) or '—'})",
        f"- **Город:** {loc['city'] or '—'}"
        + (f", район: {loc['district']}" if loc["district"] else ""),
        f"- **Адрес:** {loc['address'] or '—'}"
        + (f" ({loc['address_comment']})" if loc["address_comment"] else ""),
        f"- **Координаты:** {loc['lat']}, {loc['lon']}",
        f"- **Режим работы:** {data['schedule']['human'] or '—'}",
        f"- **Телефоны:** {', '.join(con['phones']) or '—'}",
        f"- **Почта:** {', '.join(con['emails']) or '—'}",
        f"- **Соцсети:** "
        + (", ".join(f"{s['type']}: {s['url']}" for s in con["socials"]) or "—"),
        f"- **Сайт:** {', '.join(con['websites']) or 'нет'} "
        f"({website.STATUS_LABELS[con['website_status']]}: {con['website_note']})",
        f"- **Рейтинг:** {rep['rating'] or '—'} на {rep['reviews_count']} отзывов",
        f"- **Карточка 2ГИС:** {biz['url_2gis']}",
    ]

    if biz["description"]:
        lines += ["", "### Описание от бизнеса", biz["description"]]

    if data["offering"]:
        lines += ["", "### Услуги, удобства и особенности (из карточки 2ГИС)"]
        for group in data["offering"]:
            lines.append(f"- **{group['group']}:** {', '.join(group['values'])}")

    texts = [r for r in data["reviews"] if r["text"]]
    if texts:
        lines += [
            "",
            f"### Отзывы клиентов ({len(texts)} с текстом, сначала лучшие)",
            "_На сайт ставь отзывы на 4–5★ дословно; отзывы на 1–2★ читай как список"
            " слабых мест, которые нужно закрыть текстом и блоками доверия._",
        ]
        for review in texts:
            stars = "★" * int(review["rating"] or 0)
            lines.append(
                f"\n**{review['author']}** · {stars} · {review['date']}\n> "
                + review["text"].replace("\n", "\n> ")
            )
            if review["owner_reply"]:
                lines.append(
                    "\n_Ответ владельца:_ "
                    + review["owner_reply"].replace("\n", " ")[:600]
                )

    if data["photos"]:
        lines += ["", "### Фото бизнеса (реальные, с 2ГИС)"]
        lines += [f"- {p['url']}" for p in data["photos"][:20]]

    return "\n".join(lines) + "\n"
