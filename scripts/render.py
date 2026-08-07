#!/usr/bin/env python3
"""Renderiza los bloques de texto del README a partir de data/stats.json.

Todo sale como texto plano dentro de bloques de codigo, asi que se ve igual en
cualquier cliente que muestre markdown y no depende de ningun servicio.

Los tres cuadros comparten ancho para que la pagina se lea como un panel.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

MONTHS =["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Los cuadros se estiran hasta el contenido mas ancho. Solo hay piso, no techo:
# un techo recortaria el marco sin recortar el texto y las lineas se saldrian
# de la caja. Para achicar el panel hay que bajar "ascii.width" en config.json.
WIDTH_MIN = 74

# Los valores largos (estudios, "trabajando en") se parten aqui para que el
# panel no se estire a lo ancho por una sola fila.
VALUE_WRAP = 30

# Titulo del segundo bloque del panel: lo que el workflow refresca a diario.
STATS_HEADING = "Estadísticas · al día de hoy"

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


def _clamp_width(natural: int) -> int:
    return max(WIDTH_MIN, natural)


# ----------------------------------------------------------------- hero (perfil)


def _wrap_rows(rows: list[tuple[str, str]], width: int = VALUE_WRAP) -> list[tuple[str, str]]:
    """Parte los valores largos en varias filas; la continuacion va sin etiqueta."""
    out: list[tuple[str, str]] = []
    for label, value in rows:
        line = ""
        first = True
        for word in value.split():
            candidate = f"{line} {word}".strip()
            if line and len(candidate) > width:
                out.append((label if first else "", line))
                first = False
                line = word
            else:
                line = candidate
        out.append((label if first else "", line))
    return out


def _time_on_github(profile: dict) -> str | None:
    """Antiguedad de la cuenta en años y meses, no solo el año redondeado."""
    created = profile.get("created_at")
    if not created:
        return None
    try:
        start = date.fromisoformat(created[:10])
    except ValueError:
        return None

    today = date.today()
    months = (today.year - start.year) * 12 + (today.month - start.month)
    if today.day < start.day:
        months -= 1
    months = max(0, months)
    years, rest = divmod(months, 12)

    parts = []
    if years:
        parts.append(f"{years} año{'s' if years != 1 else ''}")
    if rest or not years:
        parts.append(f"{rest} mes{'es' if rest != 1 else ''}")
    return " y ".join(parts)


def _identity_rows(config: dict, stats: dict) -> list[tuple[str, str]]:
    """Datos fijos: los que solo cambian cuando se edita config.json."""
    identity = config.get("identity", {})
    profile = stats.get("profile", {})
    rows: list[tuple[str, str]] = []

    def add(label: str, value) -> None:
        if value not in (None, "", 0, "—"):
            rows.append((label, str(value)))

    add("Nombre", identity.get("name") or profile.get("name"))
    add("\nEstudios", identity.get("studies") or identity.get("role"))
    add("\nUbicación", identity.get("location") or profile.get("location"))
    add("\nTrabajando en", identity.get("working_on"))
    add("\nAprendiendo", identity.get("learning"))
    add("\nPregúntame de", identity.get("ask_me_about"))
    add("\nColaboro en", identity.get("collaborate_on"))
    add("\nDato random", identity.get("fun_fact"))

    return _wrap_rows(rows)


def _stat_rows(stats: dict) -> list[tuple[str, str]]:
    """Datos vivos: los que el workflow diario vuelve a bajar de la API."""
    profile = stats.get("profile", {})
    repos = stats.get("repos", {})
    streaks_data = stats.get("streaks", {})
    counts = stats.get("counts", {})
    rows: list[tuple[str, str]] = []

    def add(label: str, value) -> None:
        if value not in (None, "", 0, "—"):
            rows.append((label, str(value)))

    add("Repositorios Públicos", _num(repos.get("own_repos")))
    add("Estrellas", _num(repos.get("stars")))
    add("Seguidores", _num(profile.get("followers")))
    add("Contribuciones", _num(streaks_data.get("total")))
    add("Pull requests", _num(counts.get("pull_requests")))
    add("Issues", _num(counts.get("issues")))
  # if streaks_data.get("current"):
  #     add("Racha actual", f"{streaks_data['current']} días")
  # if streaks_data.get("longest"):
  #     add("Racha más larga", f"{streaks_data['longest']} días")
  # add("Miembro desde", _short_date(profile.get("created_at")))
    add("Tiempo en GitHub", _time_on_github(profile))

    return rows


def hero_panel(stats: dict, config: dict) -> tuple[str, list[tuple[str, str]], list[tuple[str, str]]]:
    """email, datos fijos y estadisticas del hero: los usan la version texto y la SVG."""
    email = config.get("identity", {}).get("email") or stats.get("profile", {}).get("login", "")
    return email, _identity_rows(config, stats), _stat_rows(stats)


def _rows_to_lines(rows: list[tuple[str, str]], label_width: int) -> list[str]:
    return [f"{_pad(label, label_width)}   {value}" for label, value in rows]


def _hero_lines(stats: dict, config: dict, ascii_art: str | None) -> list[str]:
    art_lines = (ascii_art or FALLBACK_ASCII).rstrip("\n").split("\n")
    art_width = max((len(line) for line in art_lines), default=0)

    email, identity, live = hero_panel(stats, config)
    label_width = max((len(label) for label, _ in identity + live), default=0)

    info = [email, "─" * max(len(email), 28)]
    info += _rows_to_lines(identity, label_width)
    if identity and live:
        info += ["", STATS_HEADING, "─" * max(len(STATS_HEADING), 28)]
    info += _rows_to_lines(live, label_width)

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


def streak_cards(stats: dict) -> list[list[str]] | None:
    """Tarjetas de racha: [valor, etiqueta, detalle].

    El total de contribuciones no va aqui: ya aparece en el panel del hero.
    """
    data = stats.get("streaks") or {}
    if not data.get("days_tracked"):
        return None

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
        [str(data.get("current", 0)), "Racha actual · días", current_range],
        [str(data.get("longest", 0)), "Racha más larga · días", longest_range],
    ]


# ----------------------------------------------------------------------- quote


QUOTE_HINT = (
    '<!-- Tu cita va aqui: escribela en config.json, en "quote": '
    '{ "1": [ { "text": "...", "author": "..." } ], ... }, una clave por dia '
    "ISO (1 = lunes ... 7 = domingo). Editar este bloque a mano no sirve, "
    "el build lo reescribe. -->"
)

# Cada dia puede tener varias citas: la lista avanza una posicion cada tantos
# dias de calendario, asi que la del lunes no es la misma todas las semanas.
ROTATION_DAYS = 3

# El cron corre de madrugada UTC, donde la fecha ya coincide con la de Chile,
# pero un workflow_dispatch o un push al mediodia caen en otro dia UTC. La zona
# la fija el mismo huso que usa github_data para "generated_at".
TIMEZONE = ZoneInfo("America/Santiago")


def _today() -> date:
    return datetime.now(TIMEZONE).date()


def _pick_quote(data: dict, today: date) -> dict:
    """Cita que toca hoy dentro del mapa por dia de config.json."""
    if not isinstance(data, dict):
        return {}

    # Forma antigua: un solo { "text": ..., "author": ... } sin dias.
    if "text" in data:
        return data

    entries = data.get(str(today.isoweekday())) or []
    if isinstance(entries, dict):
        entries = [entries]
    entries = [
        item
        for item in entries
        if isinstance(item, dict) and (item.get("text") or "").strip()
    ]
    if not entries:
        return {}

    return entries[(today.toordinal() // ROTATION_DAYS) % len(entries)]


def quote(config: dict) -> str:
    """Cita del final, editable en config.json.

    Sin texto se deja el hueco con una pista: el bloque se regenera en cada
    build, asi que el contenido tiene que salir de config.json.
    """
    data = _pick_quote(config.get("quote") or {}, _today())
    text = (data.get("text") or "").strip()
    if not text:
        return QUOTE_HINT

    # Las comillas se ponen aca, asi que las que ya traiga el texto sobran.
    text = text.strip("\"'“”«»").strip()

    body = text.splitlines()
    body[0] = f"*“{body[0]}"
    body[-1] = f"{body[-1]}”*"
    lines = [f"> {line}" for line in body]

    author = (data.get("author") or "").strip()
    if author:
        # El markdown no alinea a la derecha; el <p align> si, y GitHub lo
        # acepta dentro de la cita.
        lines += [">", f'> <p align="right">— <b>{author}</b></p>']
    return "\n".join(lines)


# -------------------------------------------------------------- repos principales

def raw_asset_base(config: dict) -> str:
    """URL base de raw.githubusercontent.com para los assets de profile/.

    La portada del perfil resuelve las rutas relativas de las imagenes
    contra la raiz del repo, no contra profile/, asi que una ruta relativa
    simple como "assets/hero.svg" queda rota ahi (aunque funcione al ver
    profile/README.md como blob normal). Usar URLs absolutas evita el problema
    en cualquier contexto de render.
    """
    user = config.get("github_user", "")
    repo = config.get("repo", ".github")
    return f"https://raw.githubusercontent.com/{user}/{repo}/main/profile/assets"


def pinned_repos(stats: dict, config: dict) -> str:
    """Devuelve el marcador de imagen (el SVG se genera en build_readme.py)."""
    # El SVG se genera en build_readme.py y se embebe aqui.
    # Esta funcion solo devuelve un placeholder.
    repos = stats.get("pinned_repos") or []
    if not repos:
        return "_Sin repos pinneados._"
    base = raw_asset_base(config)
    return f'<img src="{base}/pinned-repos.svg" alt="Repositorios pinneados" width="100%">'

# ---------------------------------------------------------------------- footer


def footer(stats: dict, config: dict) -> str:
    """Pie con enlaces absolutos.

    La portada del perfil se renderiza fuera del arbol del repo, asi que las
    rutas relativas a scripts/ no resolverian desde ahi.
    """
    when = _short_date(stats.get("generated_at", ""))
    base = f"https://github.com/{config.get('github_user', '')}/{config.get('repo', '.github')}"
    workflow = f"{base}/blob/main/.github/workflows/refresh-readme.yml"
    return (
        f"<sub>Actualizado automáticamente el {when} por "
        f"<a href=\"{workflow}\">GitHub Actions</a> — "        
        f"sin servicios externos en el render.</sub>"
    )


# ----------------------------------------------------------------------- build


def build_blocks(stats: dict, config: dict, ascii_art: str | None) -> dict[str, str]:
    """Bloques de texto del README.

    Rachas y lenguajes salen como SVG (los arma build_readme.py); aqui
    solo queda el hero en texto, que es el respaldo para cuando no hay imagen.
    """
    hero_lines = _hero_lines(stats, config, ascii_art)
    width = _clamp_width(max(len(line) for line in hero_lines) + 4)

    return {
        "hero": _fence(_frame(hero_lines, width)),
        "repos": pinned_repos(stats, config),
        "quote": quote(config),
        "footer": footer(stats, config),
    }
