#!/usr/bin/env python3
"""Добавляет бизнес в registry.json, не переформатируя остальной файл.

Почему не json.dump: он переписывает весь файл своим форматированием, и
добавление одной записи превращается в диф на четыре тысячи строк, в котором
не видно, что именно изменилось. Здесь запись вставляется текстом перед
закрывающей скобкой, а остальные 100+ записей остаются нетронутыми.

    python3 tools/registry_add.py new.json      # один объект или список
    cat new.json | python3 tools/registry_add.py -

Поля записи:
    slug     — папка в docs/ и часть адреса
    name     — как называется бизнес
    headline — «Название — адрес»
    meta     — «Район район · 4.8 ★ по N отзывам»
    phones   — список телефонов в виде «+7 913 000-00-00»
    email    — строка, часто пустая
    url2gis  — ссылка на карточку
    tags     — первый тег всегда про состояние сайта («сайта нет вообще»)
    made     — дата в виде ГГГГ-ММ-ДД
    status   — новый | позвонил | думает | перезвонить | согласовал | отказ
    message  — текст первого сообщения владельцу, {URL} подставится при сборке
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry.json"

REQUIRED = ["slug", "name", "headline", "meta", "phones", "url2gis", "tags",
            "made", "status", "message"]
STATUSES = {"новый", "позвонил", "думает", "перезвонить", "согласовал", "отказ"}


def add(entry: dict) -> int:
    missing = [f for f in REQUIRED if f not in entry]
    if missing:
        sys.exit(f"в записи не хватает полей: {', '.join(missing)}")
    if entry["status"] not in STATUSES:
        sys.exit(f"статус «{entry['status']}» не из списка: {', '.join(sorted(STATUSES))}")
    if "{URL}" not in entry["message"]:
        sys.exit("в message нет плейсхолдера {URL} — ссылка на сайт не подставится")

    raw = REGISTRY.read_text(encoding="utf-8")
    if f'"slug": "{entry["slug"]}"' in raw:
        sys.exit(f"{entry['slug']} уже есть в registry.json")

    site_dir = ROOT / "docs" / entry["slug"]
    if not site_dir.is_dir():
        print(f"  внимание: папки docs/{entry['slug']}/ ещё нет")

    anchor = raw.rindex("\n  }\n ]")
    block = json.dumps(entry, ensure_ascii=False, indent=2)
    block = "\n".join("  " + line for line in block.split("\n"))
    cut = anchor + len("\n  }")
    REGISTRY.write_text(raw[:cut] + ",\n" + block + raw[cut:], encoding="utf-8")

    return len(json.loads(REGISTRY.read_text(encoding="utf-8"))["sites"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = sys.stdin.read() if sys.argv[1] == "-" else Path(sys.argv[1]).read_text(encoding="utf-8")
    data = json.loads(src)
    total = 0
    for item in data if isinstance(data, list) else [data]:
        total = add(item)
        print(f"  + {item['slug']}")
    print(f"в registry.json теперь записей: {total}")
