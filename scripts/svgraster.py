#!/usr/bin/env python3
"""Rasteriza SVGs que envuelven imagenes embebidas, usando solo Pillow.

No es un renderer completo: cubre el patron que dejan los exportadores de
"quitar fondo" (Inkscape, Vector Magic, GIMP), donde el SVG es un <image> con
la foto en base64 y un <mask> con otro <image> que aporta la transparencia.
Soporta transform, mask y <use>; ignora paths, texto y filtros.

Los filtros de ese patron (feColorMatrix luminance-to-alpha) no hacen falta:
la mascara se evalua por luminancia, que es justo lo que esos filtros calculan.

    python scripts/svgraster.py yo.svg -o yo.png
"""

from __future__ import annotations

import argparse
import base64
import binascii
import io
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageChops

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
HREF = f"{{{XLINK_NS}}}href"

# Identidad como matriz SVG (a, b, c, d, e, f).
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

_NUMBER = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
_TRANSFORM_RE = re.compile(rf"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")
_URL_RE = re.compile(r"url\(\s*#([^)\s]+)\s*\)")
_DATA_URI_RE = re.compile(r"^data:(?P<mime>[^,;]*)(?P<b64>;base64)?,(?P<data>.*)$", re.S)


class SVGError(ValueError):
    """El SVG no se puede rasterizar con este modulo."""


# --- algebra de matrices afines -------------------------------------------


def mat_mul(m1: tuple, m2: tuple) -> tuple:
    """Devuelve m1 despues de m2 (o sea: primero se aplica m2)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def mat_invert(m: tuple) -> tuple:
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        raise SVGError("transform degenerada (determinante cero)")
    return (
        d / det,
        -b / det,
        -c / det,
        a / det,
        (c * f - d * e) / det,
        (b * e - a * f) / det,
    )


# --- parsing de atributos --------------------------------------------------


def parse_length(value: str | None, default: float | None = None) -> float | None:
    """Longitud en px. Solo unidades absolutas; los % no se resuelven."""
    if value is None:
        return default
    text = value.strip()
    if not text or text.endswith("%"):
        return default
    match = re.match(rf"^({_NUMBER})\s*(px|pt|pc|mm|cm|in)?$", text)
    if not match:
        return default
    factor = {
        None: 1.0, "px": 1.0, "pt": 96 / 72, "pc": 16.0,
        "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0,
    }[match.group(2)]
    return float(match.group(1)) * factor


def parse_transform(value: str | None) -> tuple:
    """Convierte el atributo transform en una sola matriz."""
    if not value:
        return IDENTITY
    result = IDENTITY
    for kind, raw_args in _TRANSFORM_RE.findall(value):
        args = [float(n) for n in re.findall(_NUMBER, raw_args)]
        if kind == "matrix" and len(args) == 6:
            step = tuple(args)
        elif kind == "translate" and args:
            step = (1.0, 0.0, 0.0, 1.0, args[0], args[1] if len(args) > 1 else 0.0)
        elif kind == "scale" and args:
            sy = args[1] if len(args) > 1 else args[0]
            step = (args[0], 0.0, 0.0, sy, 0.0, 0.0)
        elif kind == "rotate" and args:
            from math import cos, radians, sin

            angle = radians(args[0])
            step = (cos(angle), sin(angle), -sin(angle), cos(angle), 0.0, 0.0)
            if len(args) >= 3:  # rotate(a, cx, cy) gira alrededor de un punto
                cx, cy = args[1], args[2]
                step = mat_mul((1.0, 0.0, 0.0, 1.0, cx, cy), step)
                step = mat_mul(step, (1.0, 0.0, 0.0, 1.0, -cx, -cy))
        elif kind in ("skewX", "skewY") and args:
            from math import radians, tan

            t = tan(radians(args[0]))
            step = (1.0, 0.0, t, 1.0, 0.0, 0.0) if kind == "skewX" else (1.0, t, 0.0, 1.0, 0.0, 0.0)
        else:
            continue
        result = mat_mul(result, step)
    return result


def parse_viewbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parts = [float(n) for n in re.findall(_NUMBER, value)]
    if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def fit_matrix(
    box: tuple[float, float, float, float],
    src_w: float,
    src_h: float,
    preserve: str | None,
) -> tuple:
    """Matriz que encaja un rect de origen (src) dentro de box, tipo viewBox."""
    x, y, w, h = box
    mode = (preserve or "xMidYMid meet").split()
    align = mode[0]
    slice_ = len(mode) > 1 and mode[1] == "slice"

    if align == "none":
        return (w / src_w, 0.0, 0.0, h / src_h, x, y)

    scale = max(w / src_w, h / src_h) if slice_ else min(w / src_w, h / src_h)
    free_x, free_y = w - src_w * scale, h - src_h * scale
    tx = x + (free_x / 2 if "xMid" in align else free_x if "xMax" in align else 0.0)
    ty = y + (free_y / 2 if "YMid" in align else free_y if "YMax" in align else 0.0)
    return (scale, 0.0, 0.0, scale, tx, ty)


def decode_href(href: str | None, base_dir: Path) -> Image.Image | None:
    """Decodifica el bitmap de un <image>: data URI o archivo vecino."""
    if not href:
        return None
    href = href.strip()
    match = _DATA_URI_RE.match(href)
    if match:
        payload = match.group("data")
        try:
            raw = (
                base64.b64decode(payload, validate=False)
                if match.group("b64")
                else urllib.parse.unquote_to_bytes(payload)
            )
        except (binascii.Error, ValueError) as exc:
            raise SVGError(f"data URI ilegible en <image>: {exc}") from exc
        return Image.open(io.BytesIO(raw))
    if "://" in href:  # nada de red: el pipeline es local
        return None
    path = (base_dir / urllib.parse.unquote(href)).resolve()
    return Image.open(path) if path.exists() else None


# --- render ----------------------------------------------------------------


def _tag(element: ET.Element) -> str:
    tag = element.tag
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) and "}" in tag else str(tag)


def _warp(source: Image.Image, matrix: tuple, size: tuple[int, int]) -> Image.Image:
    """Aplica una matriz SVG a una imagen y la deja sobre un lienzo del tamano dado."""
    inv = mat_invert(matrix)
    a, b, c, d, e, f = inv
    return source.convert("RGBA").transform(
        size, Image.AFFINE, (a, c, e, b, d, f), resample=Image.BICUBIC
    )


class _Renderer:
    def __init__(self, root: ET.Element, base_dir: Path, size: tuple[int, int]):
        self.base_dir = base_dir
        self.size = size
        self.defs: dict[str, ET.Element] = {}
        for element in root.iter():
            node_id = element.get("id")
            if node_id and node_id not in self.defs:
                self.defs[node_id] = element
        self.used_images = 0

    def blank(self) -> Image.Image:
        return Image.new("RGBA", self.size, (0, 0, 0, 0))

    def draw(self, element: ET.Element, ctm: tuple, canvas: Image.Image) -> None:
        name = _tag(element)
        if name in ("defs", "clipPath", "mask", "symbol", "title", "desc", "metadata", "style"):
            return
        if element.get("display") == "none":
            return

        ctm = mat_mul(ctm, parse_transform(element.get("transform")))

        mask_ref = _URL_RE.search(element.get("mask") or "")
        if mask_ref:
            # Lo enmascarado se pinta aparte para poder multiplicar su alfa.
            layer = self.blank()
            self._draw_children(element, name, ctm, layer)
            self._apply_mask(layer, mask_ref.group(1), ctm)
            canvas.alpha_composite(layer)
            return

        self._draw_children(element, name, ctm, canvas)

    def _draw_children(
        self, element: ET.Element, name: str, ctm: tuple, canvas: Image.Image
    ) -> None:
        if name == "image":
            self._draw_image(element, ctm, canvas)
            return
        if name == "use":
            target = self.defs.get((element.get("href") or element.get(HREF) or "").lstrip("#"))
            if target is not None:
                offset = (
                    1.0, 0.0, 0.0, 1.0,
                    parse_length(element.get("x"), 0.0) or 0.0,
                    parse_length(element.get("y"), 0.0) or 0.0,
                )
                self.draw(target, mat_mul(ctm, offset), canvas)
            return
        for child in element:
            self.draw(child, ctm, canvas)

    def _draw_image(self, element: ET.Element, ctm: tuple, canvas: Image.Image) -> None:
        bitmap = decode_href(element.get("href") or element.get(HREF), self.base_dir)
        if bitmap is None:
            return
        with bitmap:
            box = (
                parse_length(element.get("x"), 0.0) or 0.0,
                parse_length(element.get("y"), 0.0) or 0.0,
                parse_length(element.get("width")) or float(bitmap.width),
                parse_length(element.get("height")) or float(bitmap.height),
            )
            placement = fit_matrix(
                box, bitmap.width, bitmap.height, element.get("preserveAspectRatio")
            )
            canvas.alpha_composite(_warp(bitmap, mat_mul(ctm, placement), self.size))
        self.used_images += 1

    def _apply_mask(self, layer: Image.Image, mask_id: str, ctm: tuple) -> None:
        node = self.defs.get(mask_id)
        if node is None or _tag(node) != "mask":
            return
        painted = self.blank()
        for child in node:
            self.draw(child, mat_mul(ctm, parse_transform(node.get("transform"))), painted)

        # Mascara por luminancia (el default de SVG): luma ponderada * alfa.
        luma = painted.convert("RGB").convert("L", matrix=(0.2126, 0.7152, 0.0722, 0.0))
        coverage = Image.new("L", self.size, 0)
        coverage.paste(luma, mask=painted.getchannel("A"))
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), coverage))


def rasterize(path: str | Path, scale: float = 1.0) -> Image.Image:
    """Devuelve el SVG como imagen RGBA, del tamano del viewport por `scale`."""
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise SVGError(f"SVG mal formado: {exc}") from exc
    if _tag(root) != "svg":
        raise SVGError(f"la raiz no es <svg> sino <{_tag(root)}>")
    if scale <= 0:
        raise SVGError("scale debe ser mayor que cero")

    viewbox = parse_viewbox(root.get("viewBox"))
    width = parse_length(root.get("width"), viewbox[2] if viewbox else None)
    height = parse_length(root.get("height"), viewbox[3] if viewbox else None)
    if width is None or height is None:
        raise SVGError("el SVG no declara width/height ni viewBox utilizables")

    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    ctm = (scale, 0.0, 0.0, scale, 0.0, 0.0)
    if viewbox:
        ctm = mat_mul(ctm, fit_matrix((0.0, 0.0, width, height), viewbox[2], viewbox[3],
                                      root.get("preserveAspectRatio")))
        ctm = mat_mul(ctm, (1.0, 0.0, 0.0, 1.0, -viewbox[0], -viewbox[1]))

    renderer = _Renderer(root, path.resolve().parent, size)
    canvas = renderer.blank()
    for child in root:
        renderer.draw(child, ctm, canvas)
    if not renderer.used_images:
        raise SVGError(
            f"{path.name} no trae imagenes embebidas; este rasterizador no dibuja vectores"
        )
    return canvas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rasteriza un SVG con imagenes embebidas.")
    parser.add_argument("svg", type=Path, help="Ruta del SVG")
    parser.add_argument("-o", "--output", type=Path, required=True, help="PNG de salida")
    parser.add_argument("-s", "--scale", type=float, default=1.0, help="Factor de escala (def. 1.0)")
    args = parser.parse_args(argv)

    if not args.svg.exists():
        parser.error(f"no existe el SVG: {args.svg}")

    image = rasterize(args.svg, scale=args.scale)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(f"PNG escrito en {args.output} ({image.width}x{image.height})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
