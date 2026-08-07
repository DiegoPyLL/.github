#!/usr/bin/env python3
"""Genera SVG locales: el hero en color, la barra de lenguajes y los badges.

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
    "emailbars": "#F7931E",
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

# Ancho comun de los paneles que van uno debajo del otro. El hero conserva su
# ancho natural (lo fija la grilla del ASCII); el README los escala al 100%.
PANEL_WIDTH = 860

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


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - len(text))


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


def _svg(
    width: float, height: float, body: str, *, extra_css: str = "", theme: bool = True
) -> str:
    """Envoltorio comun. Con theme=False el dibujo se pinta sus propios colores."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img">\n'
        f"  <style>\n"
        f'    text {{ font-family: "Segoe UI", Ubuntu, "Helvetica Neue", Helvetica, Arial, sans-serif; }}\n'
        f"{_THEME_CSS if theme else ''}{extra_css}"
        f"  </style>\n"
        f"{body}"
        f"</svg>\n"
    )


# ------------------------------------------------------------- hero en color

MONO_FAMILY = (
    'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, '
    '"Liberation Mono", "Courier New", monospace'
)


# Paleta de las tarjetas. Va oscura en los dos temas: en el hero la rampa asigna
# los glifos densos a los pixeles claros, asi que sobre fondo blanco el retrato se
# leeria en negativo. Los demas paneles la comparten para que la pagina se lea como
# un solo bloque.
_CARD_CSS = (
    "    .card { fill: #0D1117; stroke: #30363D; }\n"
    "    .val { fill: #E6EDF3; }\n"
    "    .key { fill: #7D8590; }\n"
    "    .head { fill: #58A6FF; }\n"
    "    .rule { stroke: #30363D; }\n"
    "    .track { fill: #21262D; }\n"
)

CARD_RADIUS = 10


def _card_rect(x: float, y: float, w: float, h: float) -> str:
    """Fondo de tarjeta. El medio pixel deja el trazo dentro del viewBox."""
    return (
        f'  <rect class="card" x="{x + 0.5:.1f}" y="{y + 0.5:.1f}" '
        f'width="{w - 1:.1f}" height="{h - 1:.1f}" rx="{CARD_RADIUS}"/>\n'
    )


def _hero_css(font_size: float) -> str:
    """La tarjeta comun mas la tipografia monoespaciada de la grilla ASCII."""
    return (
        f"    text {{ font-family: {MONO_FAMILY}; font-size: {font_size:g}px; "
        f"white-space: pre; }}\n"
    ) + _CARD_CSS


# Cuantizar el color junta celdas vecinas en una sola corrida: mismo aspecto,
# bastante menos SVG. El retrato tiene degradados suaves, no bordes duros.
_COLOR_STEP = 12

# Ancho de avance de una celda monoespaciada, en ems. Cada fila ademas lleva
# textLength, asi que la grilla cuadra aunque el visor use otra fuente.
_ADVANCE_EM = 0.6


def _quantized(rgb: tuple[int, int, int]) -> str:
    half = _COLOR_STEP // 2
    r, g, b = (min(255, (c // _COLOR_STEP) * _COLOR_STEP + half) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def _art_runs(row: list[tuple[str, tuple[int, int, int] | None]]) -> list[tuple[str, str]]:
    """Agrupa celdas contiguas del mismo color en corridas (texto, atributo).

    Los espacios no pintan nada, asi que se pegan a la corrida en curso en vez
    de cortarla: menos elementos y el hueco conserva su avance igual.
    """
    runs: list[tuple[str, str]] = []
    buffer: list[str] = []
    current = ""
    for char, rgb in row:
        attr = current if char == " " else (f' fill="{_quantized(rgb)}"' if rgb else "")
        if buffer and attr != current:
            runs.append(("".join(buffer), current))
            buffer = []
        current = attr
        buffer.append(char)
    if buffer:
        runs.append(("".join(buffer), current))
    return runs


def _row(runs: list[tuple[str, str]], x: float, y: float, advance: float) -> str:
    """Una fila de la grilla como <text> con textLength exacto."""
    cols = sum(len(text) for text, _ in runs)
    body = "".join(
        escape(text) if not attr else f"<tspan{attr}>{escape(text)}</tspan>" for text, attr in runs
    )
    return (
        f'  <text x="{x:.1f}" y="{y:.1f}" textLength="{cols * advance:.1f}" '
        f'lengthAdjust="spacingAndGlyphs" xml:space="preserve">{body}</text>\n'
    )


def _info_lines(
    email: str,
    identity: list[tuple[str, str]],
    stats: list[tuple[str, str]],
    heading: str,
) -> tuple[list[list[tuple[str, str]] | None], int]:
    """Panel de datos: etiqueta apagada, valor destacado.

    Los dos bloques (lo fijo y lo que se refresca a diario) van separados por un
    titulo con su propia regla. Un None en la lista es una regla horizontal: se
    dibuja como <line> y no repitiendo ─, que en algun visor sale con costuras.
    """
    key_w = max((len(label) for label, _ in identity + stats), default=0)
    lines: list[list[tuple[str, str]] | None] = [[(email, ' class="val"')], None]

    def rows_to_lines(rows: list[tuple[str, str]]) -> None:
        for label, value in rows:
            # Fila sin etiqueta ni valor: separador. Se deja como lista vacia
            # para que ocupe su alto de linea sin dibujar un <text> de espacios.
            # (Una continuacion de _wrap_rows viene sin etiqueta pero con valor.)
            if not label and not value:
                lines.append([])
                continue
            lines.append(
                [(_pad(label, key_w) + "   ", ' class="key"'), (value, ' class="val"')]
            )

    rows_to_lines(identity)
    if identity and stats:
        lines += [[], [(heading, ' class="head"')], None]
    rows_to_lines(stats)

    width = max(sum(len(text) for text, _ in line) for line in lines if line)
    return lines, width


def ascii_hero(
    art: list[list[tuple[str, tuple[int, int, int] | None]]],
    email: str,
    identity: list[tuple[str, str]],
    stats: list[tuple[str, str]],
    *,
    heading: str = "Estadísticas",
    font_size: float = 13.0,
    char_aspect: float = 0.5,
    gutter: int = 3,
) -> str:
    """Dos tarjetas lado a lado: el retrato ASCII y el panel de datos.

    char_aspect tiene que ser el mismo con que se genero el ASCII: define el
    alto de linea y es lo que evita que el retrato salga estirado o aplastado.
    """
    advance = font_size * _ADVANCE_EM
    line_h = advance / char_aspect
    pad_x = advance * 2
    pad_y = line_h * 0.9

    art_w = max((len(row) for row in art), default=0)
    info_lines, info_w = _info_lines(email, identity, stats, heading)
    rule_cols = max(len(email), len(heading), 28)
    info_w = max(info_w, rule_cols)

    # Cada tarjeta se mide sola; la mas corta se estira al alto de la otra para
    # que el par quede parejo.
    art_h = pad_y * 2 + len(art) * line_h
    info_h = pad_y * 2 + len(info_lines) * line_h
    height = max(art_h, info_h)

    art_card_w = pad_x * 2 + art_w * advance
    info_card_w = pad_x * 2 + info_w * advance
    gap = gutter * advance
    width = art_card_w + gap + info_card_w

    def card(x: float, w: float) -> str:
        return _card_rect(x, 0, w, height)

    def baseline(index: int, count: int) -> float:
        # Cada bloque se centra vertical dentro de su tarjeta.
        top = (height - count * line_h) / 2
        return top + index * line_h + line_h / 2 + font_size * 0.35

    parts = [card(0, art_card_w), card(art_card_w + gap, info_card_w)]

    for i, row in enumerate(art):
        if row:
            parts.append(_row(_art_runs(row), pad_x, baseline(i, len(art)), advance))

    info_x = art_card_w + gap + pad_x
    for i, line in enumerate(info_lines):
        y = baseline(i, len(info_lines))
        if line:
            parts.append(_row(line, info_x, y, advance))
        elif line is None:
            parts.append(
                f'  <line class="rule" x1="{info_x:.1f}" y1="{y - font_size * 0.35:.1f}" '
                f'x2="{info_x + rule_cols * advance:.1f}" y2="{y - font_size * 0.35:.1f}"/>\n'
            )

    return _svg(width, height, "".join(parts), extra_css=_hero_css(font_size), theme=False)


# ------------------------------------------------------------------- rachas

# Padding interno de los paneles con tarjeta.
CARD_PAD_X = 28.0
CARD_PAD_Y = 24.0


def streak_panel(cards: list[list[str]], *, width: int = PANEL_WIDTH) -> str:
    """Tarjeta con una columna por racha, separadas por una regla vertical.

    Cada columna llega como [valor, etiqueta, detalle] ya formateado por
    render.py: aqui solo se dibuja.
    """
    if not cards:
        return _svg(width, 24, '  <text class="key" x="0" y="16" font-size="13">Sin datos</text>\n',
                    extra_css=_CARD_CSS, theme=False)

    value_size = 34.0
    label_size = 14.0
    detail_size = 12.0

    # Las tres lineas se miden por linea base. El alto arranca en la altura de
    # mayuscula del numero y termina bajo el trazo descendente del detalle: asi
    # el aire de arriba y el de abajo quedan iguales de verdad.
    y_value = CARD_PAD_Y + value_size * 0.72
    y_label = y_value + 24.0
    y_detail = y_label + 22.0
    # Redondeado para que el rect de la tarjeta y el viewBox coincidan al pixel.
    height = round(y_detail + detail_size * 0.28 + CARD_PAD_Y)

    parts = [_card_rect(0, 0, width, height)]
    col_w = width / len(cards)

    for i, (value, label, detail) in enumerate(cards):
        cx = col_w * (i + 0.5)
        if i:
            # La regla no llega a los bordes: deja respirar la esquina redondeada.
            parts.append(
                f'  <line class="rule" x1="{col_w * i:.1f}" y1="{CARD_PAD_Y:.1f}" '
                f'x2="{col_w * i:.1f}" y2="{height - CARD_PAD_Y:.1f}"/>\n'
            )
        parts.append(
            f'  <text class="val" x="{cx:.1f}" y="{y_value:.1f}" font-size="{value_size:g}" '
            f'font-weight="700" text-anchor="middle">{escape(value)}</text>\n'
            f'  <text class="head" x="{cx:.1f}" y="{y_label:.1f}" font-size="{label_size:g}" '
            f'font-weight="600" text-anchor="middle">{escape(label)}</text>\n'
            f'  <text class="key" x="{cx:.1f}" y="{y_detail:.1f}" font-size="{detail_size:g}" '
            f'text-anchor="middle">{escape(detail)}</text>\n'
        )

    return _svg(width, height, "".join(parts), extra_css=_CARD_CSS, theme=False)


# --------------------------------------------------------- barra de lenguajes


def language_bar(
    languages: list[dict],
    *,
    width: int = PANEL_WIDTH,
    columns: int = 3,
    overrides: dict[str, str] | None = None,
) -> str:
    """Barra apilada con la distribucion de lenguajes + leyenda, sobre tarjeta."""
    if not languages:
        return _svg(width, 24, '  <text class="key" x="0" y="16" font-size="13">Sin datos</text>\n',
                    extra_css=_CARD_CSS, theme=False)

    bar_h = 14
    legend_top = bar_h + 22
    row_h = 24
    rows = -(-len(languages) // columns)
    inner_w = width - CARD_PAD_X * 2
    height = CARD_PAD_Y * 2 + legend_top + rows * row_h - (row_h - 13)
    col_w = inner_w / columns

    parts = [
        _card_rect(0, 0, width, height),
        f'  <g transform="translate({CARD_PAD_X:.1f},{CARD_PAD_Y:.1f})">\n',
        '  <clipPath id="round"><rect x="0" y="0" '
        f'width="{inner_w:.1f}" height="{bar_h}" rx="{bar_h / 2}"/></clipPath>\n',
        f'  <rect class="track" x="0" y="0" width="{inner_w:.1f}" height="{bar_h}" '
        f'rx="{bar_h / 2}"/>\n',
        '  <g clip-path="url(#round)">\n',
    ]

    total = sum(lang["percent"] for lang in languages) or 100.0
    x = 0.0
    for i, lang in enumerate(languages):
        color = _color_for(lang["name"], LANGUAGE_COLORS, overrides)
        seg = inner_w * lang["percent"] / total
        # El ultimo segmento cierra la barra para evitar un hueco por redondeo.
        if i == len(languages) - 1:
            seg = inner_w - x
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
            f'  <text class="val" x="{cx + 20:.1f}" y="{cy + 11:.1f}" font-size="13" '
            f'font-weight="600">{escape(lang["name"])}</text>\n'
        )
        parts.append(
            f'  <text class="key" x="{cx + 26 + _text_width(lang["name"], 13):.1f}" '
            f'y="{cy + 11:.1f}" font-size="13">{lang["percent"]}%</text>\n'
        )

    parts.append("  </g>\n")
    return _svg(width, height, "".join(parts), extra_css=_CARD_CSS, theme=False)


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


# ---------------------------------------------------------- repos pinneados

def _wrap_text(text: str, max_width: float, font_size: float = 12.0) -> list[str]:
    """Parte texto en lineas que caben en un ancho dado, sin limite de lineas."""
    if not text:
        return []

    lines = []
    current_line = ""

    for word in text.split():
        test_line = f"{current_line} {word}".strip()
        if current_line and _text_width(test_line, font_size) > max_width:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line

    if current_line:
        lines.append(current_line)

    return lines


def pinned_repos_panel(
    repos: list[dict],
    *,
    width: int = PANEL_WIDTH,
    columns: int = 2,
    overrides: dict[str, str] | None = None,
) -> str:
    """Panel con tarjetas de repos pinneados.

    Cada tarjeta muestra: nombre, descripcion completa, lenguajes y estrellas.
    La altura de cada tarjeta se ajusta al texto que tenga, y la fila crece
    hasta la tarjeta mas alta para que las columnas sigan alineadas.
    """
    if not repos:
        return _svg(width, 24, '  <text class="key" x="0" y="16" font-size="13">Sin repos pinneados</text>\n',
                    extra_css=_CARD_CSS, theme=False)

    card_pad = 14
    gap = 16
    name_offset = 36  # distancia del top de la tarjeta al inicio de la descripcion
    line_h = 16
    gap_after_desc = 14
    badge_h = 20
    inner_w = width - CARD_PAD_X * 2
    col_w = (inner_w - gap * (columns - 1)) / columns

    # Primera pasada: arma las lineas de descripcion y la altura que necesita
    # cada tarjeta segun su propio contenido.
    laid_out = []
    for repo in repos:
        desc = (repo.get("description") or "").strip()
        desc_lines = _wrap_text(desc, col_w - card_pad * 2, 11)
        desc_block_h = len(desc_lines) * line_h
        langs_y = card_pad + name_offset + desc_block_h + (gap_after_desc if desc_lines else 0)
        card_h = langs_y + badge_h + card_pad
        laid_out.append({"repo": repo, "desc_lines": desc_lines, "langs_y": langs_y, "card_h": card_h})

    # Segunda pasada: cada fila toma la altura de su tarjeta mas alta.
    rows = -(-len(laid_out) // columns)
    row_h = [0.0] * rows
    for i, item in enumerate(laid_out):
        r = i // columns
        row_h[r] = max(row_h[r], item["card_h"])

    row_y = [0.0] * rows
    for r in range(1, rows):
        row_y[r] = row_y[r - 1] + row_h[r - 1] + gap

    height = CARD_PAD_Y * 2 + sum(row_h) + gap * (rows - 1)

    parts = [
        _card_rect(0, 0, width, height),
        f'  <g transform="translate({CARD_PAD_X:.1f},{CARD_PAD_Y:.1f})">\n',
    ]

    for i, item in enumerate(laid_out):
        repo = item["repo"]
        row, col = i // columns, i % columns
        x = col * (col_w + gap)
        y = row_y[row]
        card_h = row_h[row]

        # Fondo de la tarjeta del repo
        parts.append(
            f'  <rect x="{x:.1f}" y="{y:.1f}" width="{col_w:.1f}" height="{card_h:.1f}" '
            f'rx="6" fill="#161B22" stroke="#30363D" stroke-width="1"/>\n'
        )

        # Nombre del repo (clickeable con href)
        repo_name = repo.get("name", "")
        repo_url = repo.get("url", "")
        parts.append(
            f'  <a href="{escape(repo_url)}">\n'
            f'    <text class="head" x="{x + card_pad:.1f}" y="{y + card_pad + 15:.1f}" '
            f'font-size="16" font-weight="700">{escape(repo_name)}</text>\n'
            f'  </a>\n'
        )

        # Descripcion completa
        desc_y = y + card_pad + name_offset
        for line in item["desc_lines"]:
            parts.append(
                f'  <text class="key" x="{x + card_pad:.1f}" y="{desc_y:.1f}" '
                f'font-size="11">{escape(line)}</text>\n'
            )
            desc_y += line_h

        # Lenguajes como badges pequeños
        langs = repo.get("languages", [])[:3]
        langs_y = y + item["langs_y"]
        lang_x = x + card_pad
        for lang in langs:
            color = _color_for(lang, LANGUAGE_COLORS, overrides)
            fg = _readable_text(color)
            lang_w = _text_width(lang, 10) + 10
            parts.append(
                f'  <rect x="{lang_x:.1f}" y="{langs_y:.1f}" width="{lang_w:.1f}" '
                f'height="{badge_h}" rx="4" fill="{color}"/>\n'
                f'  <text x="{lang_x + lang_w / 2:.1f}" y="{langs_y + 14:.1f}" '
                f'font-size="11" font-weight="600" fill="{fg}" text-anchor="middle">{escape(lang)}</text>\n'
            )
            lang_x += lang_w + 6

        # Estrellas, alineadas con la fila de badges
        stars = repo.get("stars", 0)
        stars_text = f"⭐ {stars}" if stars > 0 else ""
        parts.append(
            f'  <text class="key" x="{x + col_w - card_pad:.1f}" y="{langs_y + 14:.1f}" '
            f'font-size="13" text-anchor="end">{escape(stars_text)}</text>\n'
        )

    parts.append("  </g>\n")
    return _svg(width, height, "".join(parts), extra_css=_CARD_CSS, theme=False)
