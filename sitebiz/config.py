"""Настройки и ключи доступа к публичным API 2ГИС."""

import os

# Публичный демо-ключ каталога 2ГИС (используется в документации и на сайте 2gis.ru).
# Свой ключ можно получить на https://dev.2gis.ru и положить в переменную окружения.
CATALOG_KEY = os.environ.get("TWOGIS_CATALOG_KEY", "rutnpt3272")

# Публичный ключ сервиса отзывов (тот же, что использует веб-версия 2gis.ru).
REVIEWS_KEY = os.environ.get(
    "TWOGIS_REVIEWS_KEY", "6e7e1929-4ea9-4a5d-8c05-d601860389bd"
)

CATALOG_URL = "https://catalog.api.2gis.com"
REVIEWS_URL = "https://public-api.reviews.2gis.com"

# Сколько ждать ответ API, секунд.
TIMEOUT = int(os.environ.get("SITEBIZ_TIMEOUT", "25"))

# Пауза между запросами, чтобы не упереться в лимиты, секунд.
THROTTLE = float(os.environ.get("SITEBIZ_THROTTLE", "0.35"))

# Максимальный размер страницы, который принимает каталог.
MAX_PAGE_SIZE = 50

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Поля карточки, которые запрашиваем у каталога.
ITEM_FIELDS = ",".join(
    [
        "items.point",
        "items.address",
        "items.adm_div",
        "items.contact_groups",
        "items.external_content",
        "items.rubrics",
        "items.schedule",
        "items.reviews",
        "items.description",
        "items.org",
        "items.name_ex",
        "items.attribute_groups",
        "items.floors",
        "items.links",
        "items.context_rubrics",
    ]
)
