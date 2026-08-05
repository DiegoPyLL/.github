#!/usr/bin/env python3
"""Convierte una imagen a ASCII art.

Todo el procesamiento es local: la unica dependencia es Pillow.

    python scripts/img2ascii.py assets/avatar.png --width 40 -o assets/ascii.txt

Acepta lo que abra Pillow (png, jpg, webp, ...) y ademas SVG con imagenes
embebidas, que se rasterizan con svgraster.

La unidad de trabajo es la celda: caracter + color de la imagen original. El
texto plano descarta el color; el hero en SVG lo usa para pintar cada caracter.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

import svgraster

# Las rampas van del pixel mas oscuro (indice 0) al mas claro (ultimo indice),
# pensadas para leerse sobre fondo oscuro. Usa --invert para fondo claro.
RAMPS = {
    "minimal": " .:-=+*#%@",
    "standard": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "blocks": " ░▒▓█",
    "shades": " .:░▒▓█",
}

# Una celda es el caracter elegido y el color de la imagen en ese punto. Las
# celdas transparentes van sin color: son hueco, no pixel negro.
Cell = tuple[str, tuple[int, int, int] | None]
Row = list[Cell]


def _stretch(gray: Image.Image, hist: list[int]) -> Image.Image:
    """Lleva el rango util del histograma a 0..255 (autocontrast con mascara)."""
    used = [i for i, count in enumerate(hist) if count]
    if len(used) < 2:
        return gray
    lo, hi = used[0], used[-1]
    scale = 255.0 / (hi - lo)
    return gray.point([min(255, max(0, round((v - lo) * scale))) for v in range(256)])


def _apply_contrast(gray: Image.Image, factor: float, hist: list[int]) -> Image.Image:
    """Separa los tonos alrededor de la media, calculada sobre el histograma dado."""
    total = sum(hist)
    if not total:
        return gray
    mean = sum(i * count for i, count in enumerate(hist)) / total
    return gray.point(
        [min(255, max(0, round(mean + (v - mean) * factor))) for v in range(256)]
    )


def _clamp(value: float) -> int:
    return min(255, max(0, round(value)))


def _tint(
    rgb: tuple[int, int, int],
    base: int,
    toned: int,
    saturation: float,
    min_brightness: int,
) -> tuple[int, int, int]:
    """Color de la imagen llevado al tono que le toco al caracter.

    El caracter sale de la luminancia ya ajustada (autocontrast, contrast,
    invert), asi que el color se reescala con la misma razon: conserva el matiz
    de la foto y acompana al glifo en vez de contradecirlo.

    min_brightness comprime ese rango hacia arriba en vez de recortarlo. La
    sombra ya la dibuja la densidad del glifo; si ademas el color se va a negro
    el trazo desaparece contra el panel oscuro y el retrato se deshace.
    """
    target = min_brightness + toned * (255 - min_brightness) / 255.0
    r, g, b = rgb
    if base:
        scale = target / base
        r, g, b = _clamp(r * scale), _clamp(g * scale), _clamp(b * scale)
    else:
        # Negro puro no tiene matiz que escalar; queda gris del tono destino.
        r = g = b = _clamp(target)
    if saturation != 1.0:
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        r, g, b = (_clamp(lum + (c - lum) * saturation) for c in (r, g, b))
    return r, g, b


def image_to_cells(
    image: Image.Image,
    width: int = 40,
    ramp: str = RAMPS["standard"],
    *,
    invert: bool = False,
    autocontrast: bool = False,
    contrast: float = 1.0,
    char_aspect: float = 0.5,
    alpha_threshold: int = 32,
    saturation: float = 1.0,
    min_brightness: int = 0,
) -> list[Row]:
    """Devuelve la imagen como filas de celdas (caracter + color).

    char_aspect compensa que las celdas de texto son mas altas que anchas.
    """
    image = ImageOps.exif_transpose(image)
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    src_w, src_h = image.size
    height = max(1, round(src_h * (width / src_w) * char_aspect))
    image = image.resize((width, height), Image.LANCZOS)

    alpha = image.getchannel("A")
    gray = image.convert("L")

    # Los ajustes se miden solo sobre lo que se va a dibujar. En un recorte con
    # fondo transparente el RGB de afuera suele ser negro, y si entra al
    # histograma corre la media y termina aclarando al sujeto en vez de
    # separarlo. Sin canal alfa la mascara cubre todo y no cambia nada.
    visible = alpha.point([255 if v >= alpha_threshold else 0 for v in range(256)]).convert("1")
    toned = gray
    if autocontrast:
        toned = _stretch(toned, toned.histogram(mask=visible))
    if contrast != 1.0:
        toned = _apply_contrast(toned, contrast, toned.histogram(mask=visible))
    if invert:
        toned = ImageOps.invert(toned)

    lum = toned.load()
    base = gray.load()
    color = image.convert("RGB").load()
    mask = alpha.load()
    last = len(ramp) - 1

    rows: list[Row] = []
    for y in range(height):
        row: Row = []
        for x in range(width):
            # Lo transparente queda como hueco, no como pixel negro.
            if mask[x, y] < alpha_threshold:
                row.append((" ", None))
            else:
                char = ramp[lum[x, y] * last // 255]
                row.append(
                    (
                        char,
                        _tint(color[x, y], base[x, y], lum[x, y], saturation, min_brightness),
                    )
                )
        while row and row[-1][0] == " ":
            row.pop()
        rows.append(row)
    return rows


def cells_to_text(rows: list[Row]) -> str:
    return "\n".join("".join(char for char, _ in row) for row in rows)


def image_to_ascii(
    image: Image.Image, width: int = 40, ramp: str = RAMPS["standard"], **kwargs
) -> str:
    """Devuelve la imagen renderizada como texto, sin color."""
    return cells_to_text(image_to_cells(image, width, ramp, **kwargs))


def load_image(path: str | Path) -> Image.Image:
    """Abre la imagen; los SVG pasan primero por el rasterizador local."""
    path = Path(path)
    if path.suffix.lower() == ".svg":
        return svgraster.rasterize(path)
    return Image.open(path)


def render_cells(path: str | Path, **kwargs) -> list[Row]:
    with load_image(path) as img:
        return image_to_cells(img, **kwargs)


def render_file(path: str | Path, **kwargs) -> str:
    return cells_to_text(render_cells(path, **kwargs))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convierte una imagen a ASCII art (local).")
    parser.add_argument("image", type=Path, help="Ruta de la imagen (png, jpg, webp, svg, ...)")
    parser.add_argument("-w", "--width", type=int, default=40, help="Ancho en caracteres (def. 40)")
    parser.add_argument(
        "-r", "--ramp", default="standard", choices=sorted(RAMPS), help="Set de caracteres"
    )
    parser.add_argument("-o", "--output", type=Path, help="Archivo de salida (def. stdout)")
    parser.add_argument("--invert", action="store_true", help="Invierte para fondo claro")
    parser.add_argument("--autocontrast", action="store_true", help="Normaliza el histograma")
    parser.add_argument("--contrast", type=float, default=1.0, help="Factor de contraste (def. 1.0)")
    parser.add_argument(
        "--char-aspect", type=float, default=0.5, help="Alto/ancho de la celda (def. 0.5)"
    )
    args = parser.parse_args(argv)

    if not args.image.exists():
        parser.error(f"no existe la imagen: {args.image}")

    try:
        art = render_file(
            args.image,
            width=args.width,
            ramp=RAMPS[args.ramp],
            invert=args.invert,
            autocontrast=args.autocontrast,
            contrast=args.contrast,
            char_aspect=args.char_aspect,
        )
    except svgraster.SVGError as exc:
        parser.error(str(exc))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(art + "\n", encoding="utf-8")
        print(f"ASCII escrito en {args.output}", file=sys.stderr)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(art)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
