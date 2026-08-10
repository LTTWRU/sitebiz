#!/usr/bin/env python3
"""Собрать папку, которую можно целиком залить на хостинг клиента.

    python tools/build_deploy.py asia-ostrovskogo

На выходе deploy/<slug>/ — самодостаточный сайт: страница, шрифты, фото,
приёмник заявок и инструкция. Отличия от демо-версии в docs/:

* шрифты переезжают из общей папки внутрь сайта (на хостинге нет ../fonts/);
* снимается запрет индексации — демо прятали от поиска, боевой сайт прячут зря;
* форма получает адрес приёмника, то есть начинает работать по-настоящему.
"""

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
RELAY = ROOT / "tools" / "relay"


def used_font_families(html: str) -> list[str]:
    """Какие css-файлы шрифтов подключает страница."""
    return re.findall(r'href="\.\./fonts/([a-z0-9\-]+\.css)"', html)


def copy_fonts(html: str, out: Path) -> int:
    """Перенести только те шрифты, которыми страница действительно пользуется."""
    fonts_out = out / "fonts"
    fonts_out.mkdir(parents=True, exist_ok=True)
    copied = 0
    for css_name in used_font_families(html):
        css_path = DOCS / "fonts" / css_name
        css = css_path.read_text(encoding="utf-8")
        shutil.copy2(css_path, fonts_out / css_name)
        copied += 1
        for woff in re.findall(r"url\(([^)]+\.woff2)\)", css):
            src = DOCS / "fonts" / woff
            if src.exists():
                shutil.copy2(src, fonts_out / woff)
                copied += 1
    return copied


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="папка сайта внутри docs/")
    ap.add_argument("--endpoint", default="send.php",
                    help="адрес приёмника заявок относительно страницы")
    args = ap.parse_args()

    src = DOCS / args.slug
    if not (src / "index.html").exists():
        print(f"нет такого сайта: {src}")
        return 1

    out = ROOT / "deploy" / args.slug
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    html = (src / "index.html").read_text(encoding="utf-8")

    # 1. Шрифты внутрь сайта
    n_fonts = copy_fonts(html, out)
    html = html.replace('href="../fonts/', 'href="fonts/')

    # 2. Снимаем запрет индексации: боевому сайту он не нужен
    html = re.sub(r'\s*<meta name="robots" content="noindex,nofollow">\n?', "\n", html)

    # 3. Включаем приём заявок
    html_new = html.replace('data-endpoint=""', f'data-endpoint="{args.endpoint}"')
    if html_new == html:
        print("ВНИМАНИЕ: в странице нет data-endpoint=\"\" — форма не подключена")
    html = html_new

    (out / "index.html").write_text(html, encoding="utf-8")

    # 4. Фото
    if (src / "photo").exists():
        shutil.copytree(src / "photo", out / "photo")
    if (src / "brand").exists():
        shutil.copytree(src / "brand", out / "brand")

    # 5. Приёмник заявок
    shutil.copy2(RELAY / "send.php", out / "send.php")
    shutil.copy2(RELAY / "config.example.php", out / "config.example.php")
    shutil.copy2(RELAY / "README.md", out / "README.md")
    # Настройки кэша и защиты: без них после правок клиенты видят старую версию
    shutil.copy2(RELAY / ".htaccess", out / ".htaccess")

    # 6. Пускаем поисковики
    (out / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n", encoding="utf-8")

    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    files = sum(1 for f in out.rglob("*") if f.is_file())
    print(f"{out}  —  {files} файлов, {size // 1024} КБ "
          f"(шрифтов: {n_fonts}, индексация разрешена, форма подключена)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
