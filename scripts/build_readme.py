#!/usr/bin/env python3
"""Construye el README completo.

    python scripts/build_readme.py              # descarga datos y regenera todo
    python scripts/build_readme.py --no-fetch   # reusa data/stats.json

Pasos: estadisticas -> ASCII del avatar -> SVG locales -> reemplazo de los
bloques marcados en README.md. Nada de esto ocurre cuando alguien abre el
README: ahi solo hay texto y archivos del repo.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import github_data
import render
import svgkit
import svgraster
from img2ascii import RAMPS, render_file

ROOT = Path(__file__).resolve().parent.parent

# GitHub renderiza profile/README.md como portada del perfil de la organizacion.
# Los assets viven dentro de esa misma carpeta para poder referenciarlos con
# rutas relativas simples, sin "../", que es lo que aguanta ese render.
PROFILE_DIR = ROOT / "profile"
ASSETS_DIR = PROFILE_DIR / "assets"

TEMPLATE = """\
<!-- BEGIN:hero -->
<!-- END:hero -->

## 🔥 Rachas

<!-- BEGIN:streaks -->
<!-- END:streaks -->

## 📊 Lenguajes

<!-- BEGIN:languages -->
<!-- END:languages -->

## 🏆 Logros

<!-- BEGIN:achievements -->
<!-- END:achievements -->

## 🛠️ Tecnologías

<!-- BEGIN:tech -->
<!-- END:tech -->

---

<!-- BEGIN:footer -->
<!-- END:footer -->
"""


def replace_block(text: str, name: str, content: str) -> str:
    pattern = re.compile(
        rf"(<!-- BEGIN:{name} -->)(.*?)(<!-- END:{name} -->)", re.S
    )
    if not pattern.search(text):
        raise KeyError(f"falta el marcador BEGIN/END:{name} en el README")
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(3)}", text)


def ensure_avatar(path: Path, stats: dict) -> Path | None:
    """Baja el avatar publico si no hay imagen local todavia."""
    if path.exists():
        return path
    if path.suffix.lower() == ".svg":
        # El avatar de GitHub es raster: escribirlo con nombre .svg confunde mas
        # que ayudar. Si el SVG configurado no esta, se cae al ASCII por defecto.
        return None
    url = stats.get("profile", {}).get("avatar_url")
    if not url:
        return None
    print(f"> descargando avatar en {path.relative_to(ROOT)}", file=sys.stderr)
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": github_data.UA})
    with urllib.request.urlopen(req, timeout=github_data.TIMEOUT) as resp:
        path.write_bytes(resp.read())
    return path


def build_ascii(config: dict, stats: dict) -> str | None:
    cfg = config.get("ascii", {})
    source = ROOT / cfg.get("source", "profile/assets/avatar.png")
    source = ensure_avatar(source, stats)
    if not source or not source.exists():
        print("  ! sin imagen de origen, se usa el ASCII por defecto", file=sys.stderr)
        return None

    try:
        art = render_file(
            source,
            width=cfg.get("width", 34),
            ramp=RAMPS.get(cfg.get("ramp", "standard"), RAMPS["standard"]),
            invert=cfg.get("invert", False),
            autocontrast=cfg.get("autocontrast", True),
            contrast=cfg.get("contrast", 1.0),
            char_aspect=cfg.get("char_aspect", 0.5),
        )
    except svgraster.SVGError as exc:
        # Un SVG que no se puede rasterizar no debe voltear todo el build.
        print(f"  ! {exc}; se usa el ASCII por defecto", file=sys.stderr)
        return None

    out = ROOT / cfg.get("output", "profile/assets/ascii.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(art + "\n", encoding="utf-8")
    return art


def write_svgs(config: dict, stats: dict) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    overrides = config.get("tech_colors") or {}

    (ASSETS_DIR / "languages.svg").write_text(
        svgkit.language_bar(stats.get("languages", []), overrides=overrides), encoding="utf-8"
    )
    (ASSETS_DIR / "tech-stack.svg").write_text(
        svgkit.tech_badges(config.get("tech", {}), overrides=overrides), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera el README a partir de config.json")
    parser.add_argument(
        "--no-fetch", action="store_true", help="Reusa data/stats.json en vez de consultar GitHub"
    )
    args = parser.parse_args(argv)

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    stats_path = ROOT / "data" / "stats.json"

    if args.no_fetch:
        if not stats_path.exists():
            parser.error("no hay data/stats.json; ejecuta sin --no-fetch al menos una vez")
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
    else:
        stats = github_data.collect(config)
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(
            json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    art = build_ascii(config, stats)
    write_svgs(config, stats)

    readme = PROFILE_DIR / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    if "<!-- BEGIN:hero -->" not in text:
        print("> README sin marcadores, se escribe la plantilla base", file=sys.stderr)
        text = TEMPLATE

    blocks = render.build_blocks(stats, config, art)
    blocks["languages"] = (
        '<img src="assets/languages.svg" alt="Distribución de lenguajes" width="100%">'
    )
    blocks["tech"] = '<img src="assets/tech-stack.svg" alt="Stack de tecnologías" width="100%">'

    for name, content in blocks.items():
        text = replace_block(text, name, content)

    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(text, encoding="utf-8")
    print(f"README actualizado: {readme}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
