"""Командный интерфейс sitebiz."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import brief as brief_mod
from . import export, leads as leads_mod, links, twogis, website
from .http import ApiError

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
DEFAULT_TEMPLATE = PROMPTS_DIR / "website_builder.md"


def _err(message: str) -> int:
    print(f"Ошибка: {message}", file=sys.stderr)
    return 1


def _slug(text: str) -> str:
    keep = [c if c.isalnum() else "-" for c in (text or "").lower()]
    return "".join(keep).strip("-").replace("--", "-")[:40] or "all"


# --------------------------------------------------------------------------- cities

def cmd_cities(args) -> int:
    regions = twogis.find_regions(args.query)
    if not regions:
        return _err(f"город «{args.query}» не найден")
    for region in regions:
        print(f"{region['id']:>6}  {region['name']}  ({region.get('type', '')})")
    return 0


# ----------------------------------------------------------------------------- scan

def cmd_scan(args) -> int:
    region_id = args.region_id or twogis.resolve_region_id(args.city)
    city_name = args.city or f"регион {region_id}"
    statuses = {s.strip() for s in args.status.split(",") if s.strip()}
    categories = args.category or [None]

    collected, seen = [], set()

    for category in categories:
        label = category or f"рубрика {args.rubric_id}"
        if not args.quiet:
            print(f"→ Сканирую «{label}» в городе {city_name}…", file=sys.stderr)

        def progress(page, count, total, error):
            if args.quiet:
                return
            tail = f" из ~{total}" if total else ""
            note = f"  [{error[:60]}]" if error else ""
            print(f"   страница {page}: собрано {count}{tail}{note}", file=sys.stderr)

        try:
            for item in twogis.iter_items(
                region_id,
                query=category,
                rubric_id=args.rubric_id,
                limit=args.limit,
                on_page=progress,
            ):
                # id карточки содержит меняющийся хвост — сверяем по id филиала,
                # а по умолчанию схлопываем ещё и филиалы одной организации:
                # сайт продаётся бизнесу один раз, а не каждой точке.
                key = twogis.branch_id(item.get("id", ""))
                if not args.all_branches:
                    key = (item.get("org") or {}).get("id") or key
                if key in seen:
                    continue
                seen.add(key)
                lead = leads_mod.normalize(item)
                lead["query"] = label
                collected.append(lead)
        except ApiError as exc:
            return _err(str(exc))

    total_found = len(collected)

    if args.check_sites:
        collected = _check_live_sites(collected, quiet=args.quiet)

    result = [
        lead
        for lead in collected
        if lead["website_status"] in statuses
        and int(lead["reviews_count"] or 0) >= args.min_reviews
        and lead["score"] >= args.min_score
        and not (args.no_chains and int(lead["branch_count"] or 1) > 3)
    ]
    result.sort(key=lambda x: (-x["score"], -int(x["reviews_count"] or 0)))

    if not result:
        print(
            f"Просмотрено {total_found} организаций, подходящих под фильтры нет.\n"
            "Попробуй ослабить фильтры: --min-reviews 0 --min-score 0 "
            "или увеличить --limit.",
            file=sys.stderr,
        )
        return 0

    out = args.out or (
        f"leads-{_slug(city_name)}-{_slug(categories[0] or args.rubric_id)}"
        f"-{date.today():%Y%m%d}.csv"
    )
    title = f"{', '.join(c for c in categories if c) or 'все'} · {city_name}"
    path = export.write(result, out, title)

    _print_table(result[: args.show])
    print(
        f"\nПросмотрено: {total_found} · подходит: {len(result)}"
        f"\nФайл: {path}"
        f"\nДальше: python -m sitebiz prompt {result[0]['url_2gis']}",
        file=sys.stderr,
    )
    return 0


def _check_live_sites(leads: list, quiet: bool = False) -> list:
    """Открыть сайты тех, у кого они «есть», и понизить статус мёртвым и заглушкам."""
    from . import sitecheck

    targets = {}
    for lead in leads:
        if lead["website_status"] == website.HAS and lead["sites"]:
            targets.setdefault(lead["sites"].split(",")[0].strip(), []).append(lead)

    if not targets:
        return leads

    if not quiet:
        print(f"→ Проверяю {len(targets)} сайтов на живость…", file=sys.stderr)

    def progress(done, total, res):
        if not quiet and (done % 20 == 0 or done == total):
            print(f"   проверено {done}/{total}", file=sys.stderr)

    checked = sitecheck.check_many(list(targets), on_done=progress)
    broken = 0

    for url, res in checked.items():
        for lead in targets[url]:
            lead["live_status"] = res["status"]
            lead["live_label"] = res["label"]
            lead["live_title"] = res.get("title", "")
            if res["status"] in (sitecheck.DEAD, sitecheck.STUB, sitecheck.PARKED):
                # Сайт формально есть, но по факту его нет — это тёплый лид.
                lead["website_status"] = website.WEAK
                lead["website_status_label"] = website.STATUS_LABELS[website.WEAK]
                lead["website_note"] = f"{res['label']}: {website.host_of(url)}"
                lead["score"] = leads_mod.score(lead)
                broken += 1

    for lead in leads:
        lead.setdefault("live_status", "")
        lead.setdefault("live_label", "")
        lead.setdefault("live_title", "")

    if not quiet:
        print(f"   мёртвых сайтов и заглушек: {broken}", file=sys.stderr)
    return leads


def _print_table(rows: list) -> None:
    if not rows:
        return
    head = f"{'СКОР':>4}  {'НАЗВАНИЕ':<34} {'СТАТУС':<22} {'★':<5} {'ОТЗ':>4}  ТЕЛЕФОН"
    print(head)
    print("-" * len(head))
    for lead in rows:
        name = lead["name"][:33]
        status = lead["website_note"][:21]
        phone = (lead["phones"].split(",")[0] or "—").strip()
        rating = str(lead["rating"] or "—")
        print(
            f"{lead['score']:>4}  {name:<34} {status:<22} "
            f"{rating:<5} {lead['reviews_count']:>4}  {phone}"
        )


# ---------------------------------------------------------------------------- brief

def _resolve_brief(args) -> dict:
    resolved = links.resolve(args.link, city=getattr(args, "city", None))
    if resolved["note"]:
        print(f"! {resolved['note']}", file=sys.stderr)
    return brief_mod.build(resolved["item"], reviews_limit=args.reviews)


def cmd_brief(args) -> int:
    data = _resolve_brief(args)

    if args.download_photos:
        saved = _download_photos(data, args.download_photos)
        print(f"Скачано фото: {saved} → {args.download_photos}", file=sys.stderr)

    text = (
        json.dumps(data, ensure_ascii=False, indent=2)
        if args.format == "json"
        else brief_mod.to_markdown(data)
    )

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Бриф сохранён: {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


def _download_photos(data: dict, directory: str) -> int:
    import urllib.request

    from . import config

    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    saved = 0
    for index, photo in enumerate(data.get("photos") or [], start=1):
        name = target / f"photo-{index:02d}.jpg"
        try:
            request = urllib.request.Request(
                photo["url"], headers={"User-Agent": config.USER_AGENT}
            )
            with urllib.request.urlopen(request, timeout=config.TIMEOUT) as response:
                name.write_bytes(response.read())
            photo["local"] = str(name)
            saved += 1
        except Exception as exc:  # одно битое фото не должно ронять команду
            print(f"  не скачалось {photo['url']}: {exc}", file=sys.stderr)
    return saved


# --------------------------------------------------------------------------- prompt

def cmd_prompt(args) -> int:
    template_path = Path(args.template) if args.template else DEFAULT_TEMPLATE
    if not template_path.exists():
        return _err(f"шаблон промпта не найден: {template_path}")

    data = _resolve_brief(args)
    template = template_path.read_text(encoding="utf-8")
    body = template.split("---\n", 1)[-1] if args.template is None else template
    text = body.replace("{{BRIEF}}", brief_mod.to_markdown(data))

    out = args.out
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
        print(f"Промпт готов: {out}\nСкопируй его целиком в чат с Claude.", file=sys.stderr)
    else:
        print(text)
    return 0


# ----------------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sitebiz",
        description="Ищет в 2ГИС бизнесы без сайта и готовит данные для генерации сайта.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_cities = sub.add_parser("cities", help="найти id города в 2ГИС")
    p_cities.add_argument("query", help="название города, например «Казань»")
    p_cities.set_defaults(func=cmd_cities)

    p_scan = sub.add_parser("scan", help="просканировать категорию в городе")
    p_scan.add_argument("--city", help="город, например «Москва»")
    p_scan.add_argument("--region-id", help="id региона 2ГИС вместо названия города")
    p_scan.add_argument(
        "-c", "--category", action="append",
        help="категория/запрос, можно повторять: -c стоматология -c ортодонт",
    )
    p_scan.add_argument("--rubric-id", help="точный id рубрики 2ГИС")
    p_scan.add_argument("-n", "--limit", type=int, default=200,
                        help="сколько карточек смотреть на категорию (по умолчанию 200)")
    p_scan.add_argument(
        "--status", default=f"{website.NONE},{website.WEAK}",
        help="какие статусы оставить: none,weak,has (по умолчанию none,weak)",
    )
    p_scan.add_argument("--min-reviews", type=int, default=0,
                        help="минимум отзывов — отсекает мёртвые точки")
    p_scan.add_argument("--min-score", type=int, default=0, help="минимальный скор лида")
    p_scan.add_argument("--no-chains", action="store_true",
                        help="убрать сети (больше 3 филиалов)")
    p_scan.add_argument("--all-branches", action="store_true",
                        help="показывать все филиалы, а не одну точку на организацию")
    p_scan.add_argument("--check-sites", action="store_true",
                        help="открыть найденные сайты и поймать мёртвые, заглушки и парковки")
    p_scan.add_argument("-o", "--out", help="файл: .csv, .xlsx→csv, .json, .md, .html")
    p_scan.add_argument("--show", type=int, default=20, help="сколько строк вывести в консоль")
    p_scan.add_argument("-q", "--quiet", action="store_true")
    p_scan.set_defaults(func=cmd_scan)

    p_brief = sub.add_parser("brief", help="собрать контент-бриф по одной организации")
    p_brief.add_argument("link", help="ссылка 2ГИС / Яндекс.Карт или id филиала")
    p_brief.add_argument("--city", help="город — если в ссылке Яндекса нет координат")
    p_brief.add_argument("--format", choices=["md", "json"], default="md")
    p_brief.add_argument("--reviews", type=int, default=30, help="сколько отзывов тянуть")
    p_brief.add_argument("--download-photos", metavar="DIR",
                         help="скачать фото бизнеса в папку")
    p_brief.add_argument("-o", "--out")
    p_brief.set_defaults(func=cmd_brief)

    p_prompt = sub.add_parser(
        "prompt", help="готовый промпт для генерации сайта по ссылке"
    )
    p_prompt.add_argument("link", help="ссылка 2ГИС / Яндекс.Карт или id филиала")
    p_prompt.add_argument("--city", help="город — если в ссылке Яндекса нет координат")
    p_prompt.add_argument("--reviews", type=int, default=25)
    p_prompt.add_argument("--template", help="свой шаблон промпта вместо стандартного")
    p_prompt.add_argument("-o", "--out", help="сохранить промпт в файл")
    p_prompt.set_defaults(func=cmd_prompt)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ApiError as exc:
        return _err(str(exc))
    except KeyboardInterrupt:
        print("\nПрервано.", file=sys.stderr)
        return 130
