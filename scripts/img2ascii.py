#!/usr/bin/env python3
"""Convierte una imagen a ASCII art.

Todo el procesamiento es local: la unica dependencia es Pillow.

    python scripts/img2ascii.py assets/avatar.png --width 40 -o assets/ascii.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

# Las rampas van del pixel mas oscuro (indice 0) al mas claro (ultimo indice),
# pensadas para leerse sobre fondo oscuro. Usa --invert para fondo claro.
RAMPS = {
    "minimal": " .:-=+*#%@",
    "standard": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "blocks": " ░▒▓█",
    "shades": " .:░▒▓█",
}


def image_to_ascii(
    image: Image.Image,
    width: int = 40,
    ramp: str = RAMPS["standard"],
    *,
    invert: bool = False,
    autocontrast: bool = False,
    contrast: float = 1.0,
    char_aspect: float = 0.5,
    alpha_threshold: int = 32,
) -> str:
    """Devuelve la imagen renderizada como texto.

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
    if autocontrast:
        gray = ImageOps.autocontrast(gray)
    if contrast != 1.0:
        gray = ImageEnhance.Contrast(gray).enhance(contrast)
    if invert:
        gray = ImageOps.invert(gray)

    lum = gray.load()
    mask = alpha.load()
    last = len(ramp) - 1

    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            # Lo transparente queda como hueco, no como pixel negro.
            if mask[x, y] < alpha_threshold:
                row.append(" ")
            else:
                row.append(ramp[lum[x, y] * last // 255])
        rows.append("".join(row).rstrip())
    return "\n".join(rows)


def render_file(path: str | Path, **kwargs) -> str:
    with Image.open(path) as img:
        return image_to_ascii(img, **kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convierte una imagen a ASCII art (local).")
    parser.add_argument("image", type=Path, help="Ruta de la imagen (png, jpg, webp, ...)")
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

    art = render_file(
        args.image,
        width=args.width,
        ramp=RAMPS[args.ramp],
        invert=args.invert,
        autocontrast=args.autocontrast,
        contrast=args.contrast,
        char_aspect=args.char_aspect,
    )

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
