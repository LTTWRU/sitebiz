#!/usr/bin/env python3
"""Фото-конвейер: качает снимки из брифа, приводит их к единому виду,
замазывает то, что публиковать нельзя, и собирает контрольный лист.

Зачем нужен единый вид: фотографии в карточках 2ГИС сняты десятком разных
телефонов в разном свете. Если поставить их на страницу как есть, сайт
рассыпается на пёстрые куски. Лёгкая приглушка цвета и общий контраст
делают из них один ряд.

    # 1. скачать и обработать все фото из брифа
    python3 tools/photos.py fetch brief.md docs/<slug>/photo

    # 2. посмотреть их одним листом с подписями и решить, что оставить
    python3 tools/photos.py sheet docs/<slug>/photo out/sheet.png

    # 3. замазать номер / лицо / телефон (координаты — доли ширины и высоты)
    python3 tools/photos.py blur docs/<slug>/photo/07.jpg 0.66,0.55,0.80,0.64

    # 4. срезать водяной знак 2ГИС снизу
    python3 tools/photos.py crop docs/<slug>/photo/00.jpg

    # 5. переименовать по смыслу
    python3 tools/photos.py rename docs/<slug>/photo 19=hero 14=sklad 15=diski

После blur обязательно проверяйте попадание: `python3 tools/photos.py peek`
вырезает область вокруг замазки и показывает, накрыла ли она цель.
Промахнуться легко, а опубликованный госномер — это уже персональные данные.
"""
from __future__ import annotations

import os
import re
import sys
import urllib.request

try:
    from PIL import Image, ImageEnhance, ImageFilter
except ModuleNotFoundError:
    sys.exit("нужен Pillow: python3 -m pip install -r requirements-dev.txt")

UA = {"User-Agent": "Mozilla/5.0"}
MAXSIDE = 1400
QUALITY = 82
WATERMARK_KEEP = 0.93  # 2ГИС ставит подпись в нижних ~7% кадра


def grade(im: Image.Image) -> Image.Image:
    """Общая цветокоррекция: чуть приглушить цвет, добавить контраст,
    подмешать тёплый свет и подрезать под 1400px по длинной стороне."""
    im = im.convert("RGB")
    im = ImageEnhance.Color(im).enhance(0.66)
    im = ImageEnhance.Contrast(im).enhance(1.09)
    im = ImageEnhance.Brightness(im).enhance(1.04)
    im = Image.blend(im, Image.new("RGB", im.size, (255, 240, 220)), 0.05)
    im = im.filter(ImageFilter.UnsharpMask(1.4, 52, 3))
    im.thumbnail((MAXSIDE, MAXSIDE))
    return im


def _box(im: Image.Image, ratio: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    w, h = im.size
    x0, y0, x1, y1 = ratio
    return int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)


def cmd_fetch(brief: str, outdir: str) -> None:
    """Скачивает все ссылки на фото из брифа и складывает как 00.jpg, 01.jpg…
    Уже скачанные индексы пропускает, так что команду можно повторять."""
    text = open(brief, encoding="utf-8").read()
    urls = re.findall(r"^- (https://\S+)$", text, re.M)
    os.makedirs(outdir, exist_ok=True)
    have = {f[:2] for f in os.listdir(outdir) if f.endswith(".jpg")}
    added = 0
    for i, url in enumerate(urls):
        if f"{i:02d}" in have:
            continue
        try:
            req = urllib.request.Request(url, headers=UA)
            data = urllib.request.urlopen(req, timeout=45).read()
            tmp = os.path.join(outdir, ".tmp")
            open(tmp, "wb").write(data)
            grade(Image.open(tmp)).save(os.path.join(outdir, f"{i:02d}.jpg"), quality=QUALITY)
            os.remove(tmp)
            added += 1
        except Exception as exc:  # сеть, битый файл, удалённое фото
            print(f"  пропуск {i:02d}: {exc}")
    print(f"{outdir}: +{added}, всего {len(os.listdir(outdir))}")


def cmd_sheet(photodir: str, out: str, cols: int = 5, cell: int = 380) -> None:
    """Контрольный лист: все фото одной картинкой, каждое подписано именем файла.
    Нужен, чтобы за один взгляд отобрать годные и заметить чужие лица,
    госномера, заказ-наряды и каталожные снимки с чужих сайтов."""
    from PIL import ImageDraw

    files = sorted(f for f in os.listdir(photodir) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    if not files:
        sys.exit(f"в {photodir} нет фотографий")
    rows = (len(files) + cols - 1) // cols
    pad = 16
    sheet = Image.new("RGB", (cols * cell, rows * cell), (26, 26, 28))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(files):
        im = Image.open(os.path.join(photodir, name)).copy()
        im.thumbnail((cell - pad, cell - pad - 14))
        x = (i % cols) * cell + pad // 2
        y = (i // cols) * cell + pad // 2 + 14
        sheet.paste(im, (x, y))
        draw.text((x, y - 13), name, fill=(240, 190, 90))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    sheet.save(out)
    print(f"{out}  ({len(files)} шт.)")


def cmd_blur(path: str, *specs: str) -> None:
    """Замазывает прямоугольники. Координаты — доли ширины и высоты:
    x0,y0,x1,y1 или x0,y0,x1,y1,радиус."""
    im = Image.open(path)
    for spec in specs:
        nums = [float(v) for v in spec.split(",")]
        radius = int(nums[4]) if len(nums) > 4 else 13
        box = _box(im, tuple(nums[:4]))  # type: ignore[arg-type]
        im.paste(im.crop(box).filter(ImageFilter.GaussianBlur(radius)), box)
    im.save(path, quality=QUALITY)
    print(f"{path}: замазано областей — {len(specs)}")


def cmd_peek(path: str, spec: str, out: str = "out/peek.jpg") -> None:
    """Вырезает область вокруг замазки, чтобы проверить попадание."""
    im = Image.open(path)
    x0, y0, x1, y1 = (float(v) for v in spec.split(",")[:4])
    m = 0.08
    box = _box(im, (max(0, x0 - m), max(0, y0 - m), min(1, x1 + m), min(1, y1 + m)))
    crop = im.crop(box)
    crop = crop.resize((640, max(1, int(640 * crop.height / crop.width))))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    crop.save(out)
    print(out)


def cmd_crop(path: str, keep: float = WATERMARK_KEEP) -> None:
    """Срезает низ кадра — там водяной знак 2ГИС."""
    im = Image.open(path)
    w, h = im.size
    im.crop((0, 0, w, int(h * keep))).save(path, quality=QUALITY)
    print(f"{path}: срезано снизу {round((1 - keep) * 100)}%")


def cmd_rename(photodir: str, *pairs: str) -> None:
    """Переименовывает по смыслу: 19=hero 14=sklad. Осмысленные имена
    потом читаются в alt-текстах и в истории git."""
    for pair in pairs:
        src, dst = pair.split("=")
        a = os.path.join(photodir, f"{src}.jpg" if not src.endswith(".jpg") else src)
        b = os.path.join(photodir, f"{dst}.jpg" if not dst.endswith(".jpg") else dst)
        os.rename(a, b)
        print(f"  {os.path.basename(a)} → {os.path.basename(b)}")


COMMANDS = {
    "fetch": cmd_fetch, "sheet": cmd_sheet, "blur": cmd_blur,
    "peek": cmd_peek, "crop": cmd_crop, "rename": cmd_rename,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]](*sys.argv[2:])  # type: ignore[operator]
