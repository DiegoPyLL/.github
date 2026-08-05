#!/usr/bin/env python3
"""Renderiza los bloques de texto del README a partir de data/stats.json.

Todo sale como texto plano dentro de bloques de codigo, asi que se ve igual en
cualquier cliente que muestre markdown y no depende de ningun servicio.

Los tres cuadros comparten ancho para que la pagina se lea como un panel.
"""

from __future__ import annotations

from datetime import date

MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Los cuadros se estiran hasta el contenido mas ancho, dentro de estos limites.
WIDTH_MIN = 74
WIDTH_MAX = 108

FALLBACK_ASCII = """\
        ▄▄▄▄▄▄▄▄▄▄▄
     ▄█████████████████▄
   ███████████████████████
  ████████▀▀     ▀▀████████
 ███████▀           ▀███████
 ██████     ▄▄▄▄▄     ██████
 ██████    ███████    ██████
 ███████▄  ▀█████▀  ▄███████
  ████████▄▄     ▄▄████████
   ███████████████████████
     ▀█████████████████▀
        ▀▀▀▀▀▀▀▀▀▀▀"""


# ------------------------------------------------------------------- utilidades


def _num(value: int | float | None) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", ".")


def _short_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return "—"
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - len(text))


def _center(text: str, width: int) -> str:
    space = max(0, width - len(text))
    left = space // 2
    return " " * left + text + " " * (space - left)


def _fence(lines: list[str]) -> str:
    return "```text\n" + "\n".join(lines) + "\n```"


def _frame(lines: list[str], width: int) -> list[str]:
    """Envuelve el contenido en un cuadro de esquinas redondeadas.

    El bloque se centra como una unidad: se conserva la alineacion interna de
    las columnas y el aire sobrante queda repartido a ambos lados.
    """
    inner = width - 4  # "│ " + " │"
    block = max((len(line) for line in lines), default=0)
    indent = " " * max(0, (inner - block) // 2)
    body = ["│ " + _pad(indent + line if line else "", inner) + " │" for line in ["", *lines, ""]]
    return ["╭" + "─" * (width - 2) + "╮", *body, "╰" + "─" * (width - 2) + "╯"]


def _columns(cards: list[list[str]], width: int) -> list[str]:
    """Cuadro dividido en columnas, con conectores en los bordes."""
    n = len(cards)
    base, extra = divmod(width - 2 - (n - 1), n)
    widths = [base + (1 if i < extra else 0) for i in range(n)]

    def row(cells: list[str]) -> str:
        return "│" + "│".join(_center(c, w) for c, w in zip(cells, widths)) + "│"

    blank = row([""] * n)
    rows = [row([card[i] for card in cards]) for i in range(len(cards[0]))]
    return [
        "╭" + "┬".join("─" * w for w in widths) + "╮",
        blank,
        *rows,
        blank,
        "╰" + "┴".join("─" * w for w in widths) + "╯",
    ]


def _bar(level: int, max_level: int, cells: int = 12) -> str:
    filled = round(cells * level / max_level) if max_level else 0
    return "█" * filled + "░" * (cells - filled)


def _clamp_width(natural: int) -> int:
    return max(WIDTH_MIN, min(WIDTH_MAX, natural))


# ----------------------------------------------------------------- hero (perfil)


def _info_rows(stats: dict, config: dict) -> list[tuple[str, str]]:
    identity = config.get("identity", {})
    profile = stats.get("profile", {})
    repos = stats.get("repos", {})
    streaks_data = stats.get("streaks", {})
    counts = stats.get("counts", {})

    rows: list[tuple[str, str]] = []

    def add(label: str, value) -> None:
        if value not in (None, "", 0, "—"):
            rows.append((label, str(value)))

    add("Nombre", identity.get("name") or profile.get("name"))
    add("Rol", identity.get("role"))
    add("Ubicación", identity.get("location") or profile.get("location"))
    add("Trabajando en", identity.get("working_on"))
    add("Aprendiendo", identity.get("learning"))
    add("Pregúntame de", identity.get("ask_me_about"))
    add("Colaboro en", identity.get("collaborate_on"))
    add("Dato random", identity.get("fun_fact"))

    if rows:
        rows.append(("", ""))

    add("Repos", _num(repos.get("own_repos")))
    add("Estrellas", _num(repos.get("stars")))
    add("Seguidores", _num(profile.get("followers")))
    add("Contribuciones", _num(streaks_data.get("total")))
    if counts.get("pull_requests"):
        add("Pull requests", _num(counts["pull_requests"]))
    if streaks_data.get("current"):
        add("Racha", f"{streaks_data['current']} días")
    if stats.get("years_on_github"):
        years = stats["years_on_github"]
        add("En GitHub", f"{years} año{'s' if years != 1 else ''}")

    return rows


def _hero_lines(stats: dict, config: dict, ascii_art: str | None) -> list[str]:
    art_lines = (ascii_art or FALLBACK_ASCII).rstrip("\n").split("\n")
    art_width = max((len(line) for line in art_lines), default=0)

    handle = config.get("identity", {}).get("handle") or stats.get("profile", {}).get("login", "")
    rows = _info_rows(stats, config)
    label_width = max((len(label) for label, _ in rows), default=0)

    info = [handle, "─" * max(len(handle), 28)]
    info += ["" if not label else f"{_pad(label, label_width)}   {value}" for label, value in rows]

    # El bloque de datos se centra respecto al dibujo cuando este es mas alto.
    offset = max(0, (len(art_lines) - len(info)) // 2)
    info = [""] * offset + info

    gutter = "    "
    total = max(len(art_lines), len(info))
    out = []
    for i in range(total):
        left = art_lines[i] if i < len(art_lines) else ""
        right = info[i] if i < len(info) else ""
        out.append((_pad(left, art_width) + gutter + right).rstrip())
    return out


# --------------------------------------------------------------------- rachas


def _streak_cards(stats: dict) -> list[list[str]] | None:
    data = stats.get("streaks") or {}
    if not data.get("days_tracked"):
        return None

    total = _num(data.get("total"))
    if not data.get("exact_counts", True):
        total = f"{_num(data.get('active_days'))}+"

    current_range = (
        f"{_short_date(data.get('current_start'))} → hoy"
        if data.get("current")
        else "sin racha activa"
    )
    longest_range = (
        f"{_short_date(data.get('longest_start'))} → {_short_date(data.get('longest_end'))}"
        if data.get("longest")
        else "—"
    )

    return [
        [total, "Contribuciones totales", f"desde {_short_date(data.get('first_day'))}"],
        [str(data.get("current", 0)), "Racha actual · días", current_range],
        [str(data.get("longest", 0)), "Racha más larga · días", longest_range],
    ]


# --------------------------------------------------------------------- logros


def _achievement_lines(stats: dict) -> list[str] | None:
    items = stats.get("achievements") or []
    if not items:
        return None

    name_w = max(len(i["title"]) for i in items)
    value_w = max(len(_num(i["value"])) for i in items)

    lines = []
    for item in items:
        if item.get("next"):
            goal = f"faltan {_num(item['next'] - item['value'])} para {item.get('next_tier', '—')}"
        else:
            goal = "rango máximo"
        lines.append(
            f"{_pad(item['title'], name_w)}   "
            f"{_num(item['value']).rjust(value_w)}   "
            f"[ {item['tier'].center(3)} ]   "
            f"{_bar(item['level'], item['max_level'])}   {goal}"
        )
    return lines


# ---------------------------------------------------------------------- footer


def footer(stats: dict) -> str:
    when = _short_date(stats.get("generated_at", ""))
    return (
        f"<sub>Actualizado automáticamente el {when} por "
        f"<a href=\".github/workflows/refresh-readme.yml\">GitHub Actions</a> — "
        f"generado con los scripts de <a href=\"scripts/\">scripts/</a>, "
        f"sin servicios externos en el render.</sub>"
    )


# ----------------------------------------------------------------------- build


def build_blocks(stats: dict, config: dict, ascii_art: str | None) -> dict[str, str]:
    """Renderiza los tres cuadros con un ancho comun."""
    hero_lines = _hero_lines(stats, config, ascii_art)
    ach_lines = _achievement_lines(stats)
    cards = _streak_cards(stats)

    natural = max(
        [len(line) for line in hero_lines]
        + [len(line) for line in (ach_lines or [])]
        # Cada tarjeta necesita su texto mas ancho, mas aire a los lados.
        + [max(len(line) for card in (cards or [[""]]) for line in card) * 3 + 8]
    )
    width = _clamp_width(natural + 4)

    return {
        "hero": _fence(_frame(hero_lines, width)),
        "streaks": _fence(_columns(cards, width)) if cards else "_Sin datos de contribuciones._",
        "achievements": _fence(_frame(ach_lines, width)) if ach_lines else "_Sin logros._",
        "footer": footer(stats),
    }
