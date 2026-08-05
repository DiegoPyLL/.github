#!/usr/bin/env python3
"""Genera SVG locales: la barra de lenguajes y los badges del stack.

Reemplaza a shields.io y compania: los archivos quedan versionados en el repo
y el README los referencia con rutas relativas.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

# Colores de github/linguist para los lenguajes mas comunes.
LANGUAGE_COLORS = {
    "python": "#3572A5",
    "kotlin": "#A97BFF",
    "java": "#B07219",
    "javascript": "#F1E05A",
    "typescript": "#3178C6",
    "html": "#E34C26",
    "css": "#663399",
    "scss": "#C6538C",
    "shell": "#89E051",
    "powershell": "#012456",
    "c": "#555555",
    "c++": "#F34B7D",
    "c#": "#178600",
    "go": "#00ADD8",
    "rust": "#DEA584",
    "ruby": "#701516",
    "php": "#4F5D95",
    "swift": "#F05138",
    "dart": "#00B4AB",
    "vue": "#41B883",
    "svelte": "#FF3E00",
    "astro": "#FF5D01",
    "mdx": "#FCB32C",
    "handlebars": "#F7931E",
    "ejs": "#A91E50",
    "nix": "#7E7EFF",
    "zig": "#EC915C",
    "perl": "#0298C3",
    "objective-c": "#438EFF",
    "batchfile": "#C1F12E",
    "cmake": "#DA3434",
    "vim script": "#199F4B",
    "tex": "#3D6117",
    "jupyter notebook": "#DA5B0B",
    "r": "#198CE7",
    "sql": "#E38C00",
    "plpgsql": "#336790",
    "dockerfile": "#384D54",
    "makefile": "#427819",
    "hcl": "#844FBA",
    "lua": "#000080",
    "elixir": "#6E4A7E",
    "scala": "#C22D40",
    "haskell": "#5E5086",
    "otros": "#8B949E",
}

# Colores de marca para el stack.
BRAND_COLORS = {
    "kotlin": "#7F52FF",
    "python": "#3670A0",
    "java": "#ED8B00",
    "typescript": "#3178C6",
    "javascript": "#F7DF1E",
    "sql": "#E38C00",
    "spring": "#6DB33F",
    "fastapi": "#009688",
    "flask": "#000000",
    "django": "#092E20",
    "node.js": "#339933",
    "react": "#61DAFB",
    "next.js": "#000000",
    "astro": "#FF5D01",
    "tailwind css": "#06B6D4",
    "html5": "#E34F26",
    "css3": "#1572B6",
    "pandas": "#150458",
    "numpy": "#013243",
    "matplotlib": "#11557C",
    "jupyter": "#F37626",
    "scikit-learn": "#F7931E",
    "pytorch": "#EE4C2C",
    "tensorflow": "#FF6F00",
    "postgresql": "#4169E1",
    "mysql": "#4479A1",
    "mongodb": "#47A248",
    "supabase": "#3ECF8E",
    "redis": "#DC382D",
    "sqlite": "#003B57",
    "aws": "#FF9900",
    "docker": "#2496ED",
    "kubernetes": "#326CE5",
    "terraform": "#7B42BC",
    "vercel": "#000000",
    "git": "#F05032",
    "github": "#181717",
    "gitlab": "#FC6D26",
    "linux": "#FCC624",
    "nginx": "#009639",
    "postman": "#FF6C37",
    "figma": "#F24E1E",
}

FALLBACK = "#6E7681"

# Anchos relativos aproximados para una sans-serif de 12px en negrita.
_NARROW = set("ijltfrI.,:;'\"|!()[]{}-")
_WIDE = set("mwMW@")


def _text_width(text: str, size: float = 12.0) -> float:
    units = 0.0
    for ch in text:
        if ch in _NARROW:
            units += 0.36
        elif ch in _WIDE:
            units += 0.92
        elif ch.isupper() or ch.isdigit():
            units += 0.66
        else:
            units += 0.58
    return units * size


def _color_for(name: str, table: dict[str, str], overrides: dict[str, str] | None = None) -> str:
    key = name.strip().lower()
    if overrides and key in {k.lower() for k in overrides}:
        return {k.lower(): v for k, v in overrides.items()}[key]
    return table.get(key, FALLBACK)


def _readable_text(bg: str) -> str:
    """Negro o blanco segun la luminancia del fondo."""
    r, g, b = (int(bg[i : i + 2], 16) / 255 for i in (1, 3, 5))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#0D1117" if lum > 0.6 else "#FFFFFF"


_THEME_CSS = """
    .fg { fill: #1F2328; }
    .muted { fill: #59636E; }
    .track { fill: #D1D9E0; }
    @media (prefers-color-scheme: dark) {
      .fg { fill: #E6EDF3; }
      .muted { fill: #9198A1; }
      .track { fill: #30363D; }
    }
"""


def _svg(width: float, height: float, body: str, *, extra_css: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img">\n'
        f"  <style>\n"
        f'    text {{ font-family: "Segoe UI", Ubuntu, "Helvetica Neue", Helvetica, Arial, sans-serif; }}\n'
        f"{_THEME_CSS}{extra_css}"
        f"  </style>\n"
        f"{body}"
        f"</svg>\n"
    )


# --------------------------------------------------------- barra de lenguajes


def language_bar(
    languages: list[dict],
    *,
    width: int = 860,
    columns: int = 3,
    overrides: dict[str, str] | None = None,
) -> str:
    """Barra apilada con la distribucion de lenguajes + leyenda."""
    if not languages:
        return _svg(width, 24, '  <text class="muted" x="0" y="16" font-size="13">Sin datos</text>\n')

    bar_h = 14
    legend_top = bar_h + 22
    row_h = 24
    rows = -(-len(languages) // columns)
    height = legend_top + rows * row_h
    col_w = width / columns

    parts = [
        '  <clipPath id="round"><rect x="0" y="0" '
        f'width="{width}" height="{bar_h}" rx="{bar_h / 2}"/></clipPath>\n',
        f'  <rect class="track" x="0" y="0" width="{width}" height="{bar_h}" rx="{bar_h / 2}"/>\n',
        '  <g clip-path="url(#round)">\n',
    ]

    total = sum(lang["percent"] for lang in languages) or 100.0
    x = 0.0
    for i, lang in enumerate(languages):
        color = _color_for(lang["name"], LANGUAGE_COLORS, overrides)
        seg = width * lang["percent"] / total
        # El ultimo segmento cierra la barra para evitar un hueco por redondeo.
        if i == len(languages) - 1:
            seg = width - x
        parts.append(f'    <rect x="{x:.2f}" y="0" width="{seg:.2f}" height="{bar_h}" fill="{color}"/>\n')
        x += seg
    parts.append("  </g>\n")

    for i, lang in enumerate(languages):
        col, row = i % columns, i // columns
        cx = col * col_w
        cy = legend_top + row * row_h
        color = _color_for(lang["name"], LANGUAGE_COLORS, overrides)
        parts.append(f'  <circle cx="{cx + 6:.1f}" cy="{cy + 6:.1f}" r="6" fill="{color}"/>\n')
        parts.append(
            f'  <text class="fg" x="{cx + 20:.1f}" y="{cy + 11:.1f}" font-size="13" '
            f'font-weight="600">{escape(lang["name"])}</text>\n'
        )
        parts.append(
            f'  <text class="muted" x="{cx + 26 + _text_width(lang["name"], 13):.1f}" '
            f'y="{cy + 11:.1f}" font-size="13">{lang["percent"]}%</text>\n'
        )

    return _svg(width, height, "".join(parts))


# ------------------------------------------------------------------- badges


def tech_badges(
    groups: dict[str, list[str]],
    *,
    width: int = 860,
    overrides: dict[str, str] | None = None,
) -> str:
    """Badges redondeados agrupados por categoria, con etiqueta por grupo."""
    badge_h = 28
    gap = 8
    pad = 12
    label_h = 22
    group_gap = 14

    parts: list[str] = []
    y = 0.0

    for title, items in groups.items():
        if not items:
            continue
        parts.append(
            f'  <text class="muted" x="0" y="{y + 13:.1f}" font-size="12" '
            f'font-weight="700" letter-spacing="0.6">{escape(title.upper())}</text>\n'
        )
        y += label_h

        x = 0.0
        for item in items:
            w = _text_width(item) + pad * 2
            if x and x + w > width:
                x = 0.0
                y += badge_h + gap
            bg = _color_for(item, BRAND_COLORS, overrides)
            fg = _readable_text(bg)
            parts.append(
                f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{badge_h}" '
                f'rx="6" fill="{bg}"/>\n'
                f'  <text x="{x + w / 2:.1f}" y="{y + badge_h / 2 + 4:.1f}" font-size="12" '
                f'font-weight="600" fill="{fg}" text-anchor="middle">{escape(item)}</text>\n'
            )
            x += w + gap
        y += badge_h + group_gap

    height = max(y - group_gap, badge_h)
    return _svg(width, height, "".join(parts))
