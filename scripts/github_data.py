#!/usr/bin/env python3
"""Descarga estadisticas publicas de GitHub y las deja en data/stats.json.

Se ejecuta en tiempo de build, no cuando alguien mira el README: lo que se
publica es el JSON y el markdown ya renderizado. Solo usa la stdlib.

Si existe la variable de entorno GITHUB_TOKEN se usa para subir el limite de
peticiones (60/h anonimo -> 5000/h autenticado), pero no es obligatoria.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

API = "https://api.github.com"
UA = "readme-builder (local build script)"
TIMEOUT = 30
SEARCH_DELAY = 3  # segundos entre consultas al search API


# --------------------------------------------------------------------------- red


def _request(url: str, *, accept: str = "application/vnd.github+json") -> str:
    headers = {"User-Agent": UA, "Accept": accept}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and url.startswith(API):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _get_json(url: str) -> Any:
    return json.loads(_request(url))


def _graphql_query(query: str) -> Any:
    """Ejecuta una query GraphQL contra la API de GitHub."""
    url = f"{API}/graphql"
    body = json.dumps({"query": query}).encode("utf-8")
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json", "Content-Type": "application/json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        result = json.loads(resp.read().decode("utf-8", errors="replace"))
    if "errors" in result:
        raise ValueError(f"GraphQL error: {result.get('errors')}")
    return result.get("data", {})


def _warn(msg: str) -> None:
    print(f"  ! {msg}", file=sys.stderr)


# ------------------------------------------------------------------------ perfil


def fetch_user(user: str) -> dict:
    u = _get_json(f"{API}/users/{user}")
    return {
        "login": u["login"],
        "name": u.get("name"),
        "bio": u.get("bio"),
        "company": u.get("company"),
        "location": u.get("location"),
        "blog": u.get("blog"),
        "avatar_url": u.get("avatar_url"),
        "followers": u.get("followers", 0),
        "following": u.get("following", 0),
        "public_repos": u.get("public_repos", 0),
        "created_at": u.get("created_at"),
    }


def fetch_repos(user: str) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        batch = _get_json(f"{API}/users/{user}/repos?per_page=100&page={page}&type=owner")
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def fetch_pinned_repos(user: str) -> list[dict]:
    """Obtiene los repositorios pinneados en el perfil."""
    query = f"""
    query {{
      user(login: "{user}") {{
        pinnedItems(first: 6, types: REPOSITORY) {{
          nodes {{
            ... on Repository {{
              name
              description
              url
              languages(first: 5) {{
                nodes {{
                  name
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    try:
        result = _graphql_query(query)
        items = result.get("user", {}).get("pinnedItems", {}).get("nodes", [])
        repos = []
        for item in items:
            if not item:
                continue
            repo = {
                "name": item.get("name"),
                "description": item.get("description"),
                "url": item.get("url"),
                "languages": [lang.get("name") for lang in item.get("languages", {}).get("nodes", [])],
                "stars": 0,
            }
            # Intenta obtener estrellas via REST API como fallback
            if repo.get("name"):
                try:
                    rest_url = f"{API}/repos/{user}/{repo['name']}"
                    rest_data = _get_json(rest_url)
                    repo["stars"] = rest_data.get("stargazers_count", 0)
                except (ValueError, urllib.error.URLError):
                    pass
            repos.append(repo)
        return repos
    except (ValueError, urllib.error.URLError) as exc:
        _warn(f"no se pudieron obtener repos pinneados: {exc}")
        return []


def summarize_repos(repos: list[dict]) -> dict:
    own = [r for r in repos if not r.get("fork")]
    return {
        "public_repos": len(repos),
        "own_repos": len(own),
        "forks_owned": len(repos) - len(own),
        "stars": sum(r.get("stargazers_count", 0) for r in repos),
        "forks_received": sum(r.get("forks_count", 0) for r in repos),
        "watchers": sum(r.get("watchers_count", 0) for r in repos),
        "top_repos": [
            {"name": r["name"], "stars": r.get("stargazers_count", 0), "url": r.get("html_url")}
            for r in sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:5]
            if r.get("stargazers_count", 0) > 0
        ],
    }


# --------------------------------------------------------------------- lenguajes


def fetch_languages(
    repos: list[dict], *, include_forks: bool = False, exclude: list[str] | None = None
) -> dict[str, int]:
    """Suma los bytes por lenguaje de todos los repos.

    Cuesta una peticion por repo. Si se agota el limite anonimo se degrada al
    lenguaje principal que ya viene en el listado de repos.
    """
    exclude_lower = {e.lower() for e in (exclude or [])}
    targets = [r for r in repos if include_forks or not r.get("fork")]
    totals: dict[str, int] = {}
    degraded = False

    for repo in targets:
        if degraded:
            break
        url = repo.get("languages_url")
        if not url:
            continue
        try:
            for lang, size in _get_json(url).items():
                totals[lang] = totals.get(lang, 0) + size
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                _warn("limite de peticiones alcanzado; usando solo el lenguaje principal")
                degraded = True
                totals.clear()
            else:
                _warn(f"no se pudo leer {url}: {exc}")

    if degraded or not totals:
        for repo in targets:
            lang = repo.get("language")
            if lang:
                totals[lang] = totals.get(lang, 0) + max(repo.get("size", 1), 1)

    return {k: v for k, v in totals.items() if k.lower() not in exclude_lower}


def language_shares(totals: dict[str, int], max_shown: int = 8) -> list[dict]:
    grand = sum(totals.values())
    if not grand:
        return []
    ordered = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    top, rest = ordered[:max_shown], ordered[max_shown:]
    shares = [{"name": n, "bytes": b, "percent": round(b * 100 / grand, 1)} for n, b in top]
    if rest:
        other = sum(b for _, b in rest)
        shares.append(
            {"name": "Otros", "bytes": other, "percent": round(other * 100 / grand, 1)}
        )
    return shares


# ------------------------------------------------------------- contribuciones


_TD_RE = re.compile(r"<td\b[^>]*>", re.I)
_TOOLTIP_RE = re.compile(r"<tool-tip\b[^>]*\bfor=\"([^\"]+)\"[^>]*>(.*?)</tool-tip>", re.I | re.S)


def _parse_calendar(html: str) -> tuple[dict[str, int], bool]:
    """Extrae {fecha: contribuciones} del HTML del calendario.

    Devuelve tambien si los conteos son exactos (dependen de los tool-tips).
    """
    days: dict[str, int] = {}
    levels: dict[str, int] = {}
    ids: dict[str, str] = {}

    for match in _TD_RE.finditer(html):
        tag = match.group(0)
        date_m = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        if not date_m:
            continue
        day = date_m.group(1)
        level_m = re.search(r'data-level="(\d+)"', tag)
        levels[day] = int(level_m.group(1)) if level_m else 0
        id_m = re.search(r'id="([^"]+)"', tag)
        if id_m:
            ids[id_m.group(1)] = day

    for match in _TOOLTIP_RE.finditer(html):
        day = ids.get(match.group(1))
        if not day:
            continue
        text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        num = re.match(r"([\d,]+)\s+contribution", text)
        days[day] = int(num.group(1).replace(",", "")) if num else 0

    exact = bool(days)
    if not exact:
        # Sin tool-tips solo sabemos si hubo actividad, no cuanta.
        days = {d: (1 if lvl > 0 else 0) for d, lvl in levels.items()}
    else:
        for day, lvl in levels.items():
            days.setdefault(day, 1 if lvl > 0 else 0)

    return days, exact


def fetch_contributions(user: str, since_year: int | None = None) -> tuple[dict[str, int], bool]:
    """Lee el calendario de contribuciones publico, ano por ano."""
    today = date.today()
    start = since_year or today.year - 1
    days: dict[str, int] = {}
    exact = True

    for year in range(start, today.year + 1):
        url = (
            f"https://github.com/users/{user}/contributions"
            f"?from={year}-01-01&to={year}-12-31"
        )
        try:
            html = _request(url, accept="text/html")
        except urllib.error.URLError as exc:
            _warn(f"no se pudo leer el calendario {year}: {exc}")
            continue
        year_days, year_exact = _parse_calendar(html)
        days.update(year_days)
        exact = exact and year_exact

    return days, exact


def compute_streaks(days: dict[str, int]) -> dict:
    """Racha actual, racha mas larga y total, a partir del calendario."""
    if not days:
        return {}

    today = date.today()
    ordered = sorted(d for d in days if date.fromisoformat(d) <= today)
    if not ordered:
        return {}

    longest = current = 0
    longest_end: str | None = None
    run_end: str | None = None

    for day in ordered:
        if days[day] > 0:
            current += 1
            run_end = day
            if current > longest:
                longest, longest_end = current, run_end
        else:
            current = 0

    # Racha actual: se cuenta hacia atras. Que hoy este en cero no la corta,
    # el dia todavia no termina.
    cursor = today
    if days.get(cursor.isoformat(), 0) == 0:
        cursor -= timedelta(days=1)
    current_streak = 0
    while days.get(cursor.isoformat(), 0) > 0:
        current_streak += 1
        cursor -= timedelta(days=1)

    current_start = (cursor + timedelta(days=1)).isoformat() if current_streak else None
    longest_start = (
        (date.fromisoformat(longest_end) - timedelta(days=longest - 1)).isoformat()
        if longest_end
        else None
    )

    return {
        "total": sum(days.values()),
        "current": current_streak,
        "current_start": current_start,
        "current_end": today.isoformat() if current_streak else None,
        "longest": longest,
        "longest_start": longest_start,
        "longest_end": longest_end,
        "days_tracked": len(ordered),
        "active_days": sum(1 for d in ordered if days[d] > 0),
        # Primer dia con actividad real, no el primero del calendario descargado.
        "first_day": next((d for d in ordered if days[d] > 0), ordered[0]),
    }


def fetch_counts(user: str) -> dict:
    """PRs e issues via search API.

    La busqueda tiene un limite propio y muy bajo sin token, asi que se espera
    entre consultas y se reintenta una vez si devuelve 403.
    """
    out: dict[str, int] = {}
    queries = {
        "pull_requests": f"type:pr+author:{user}",
        "merged_prs": f"type:pr+author:{user}+is:merged",
        "issues": f"type:issue+author:{user}",
    }
    for i, (key, query) in enumerate(queries.items()):
        if i:
            time.sleep(SEARCH_DELAY)
        url = f"{API}/search/issues?q={query}&per_page=1"
        for attempt in range(2):
            try:
                out[key] = _get_json(url).get("total_count", 0)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 429) and attempt == 0:
                    time.sleep(SEARCH_DELAY * 3)
                    continue
                _warn(f"no se pudo contar {key}: {exc}")
                break
    return out


# ------------------------------------------------------------------------ logros


TIERS = ("C", "B", "A", "S", "SS", "SSS")


def _rank(value: int, thresholds: list[int]) -> tuple[str, int, int | None]:
    """Devuelve (tier, nivel alcanzado, siguiente umbral) para un valor dado."""
    level = sum(1 for limit in thresholds if value >= limit)
    tier = TIERS[min(level - 1, len(TIERS) - 1)] if level else "-"
    nxt = thresholds[level] if level < len(thresholds) else None
    return tier, level, nxt


ACHIEVEMENTS = [
    ("Commits", "contributions", [10, 100, 500, 1000, 2000, 4000]),
    ("Repos", "own_repos", [1, 5, 10, 25, 50, 100]),
    ("Estrellas", "stars", [1, 10, 50, 100, 500, 1000]),
    ("Seguidores", "followers", [1, 10, 50, 100, 500, 1000]),
    ("Pull requests", "pull_requests", [1, 10, 50, 100, 300, 500]),
    ("Issues", "issues", [1, 10, 25, 50, 100, 300]),
    ("Experiencia", "years", [1, 2, 3, 5, 8, 10]),
]


def compute_achievements(metrics: dict) -> list[dict]:
    out = []
    for title, key, thresholds in ACHIEVEMENTS:
        value = metrics.get(key)
        if value is None:
            continue
        tier, level, nxt = _rank(int(value), thresholds)
        out.append(
            {
                "title": title,
                "value": int(value),
                "tier": tier,
                "level": level,
                "max_level": len(thresholds),
                "next": nxt,
                "next_tier": TIERS[min(level, len(TIERS) - 1)] if nxt else None,
            }
        )
    return out


# ------------------------------------------------------------------------- build


def collect(config: dict) -> dict:
    user = config["github_user"]
    lang_cfg = config.get("languages", {})

    print(f"> perfil de {user}", file=sys.stderr)
    profile = fetch_user(user)

    print("> repositorios", file=sys.stderr)
    repos = fetch_repos(user)
    repo_stats = summarize_repos(repos)

    print("> repositorios pinneados", file=sys.stderr)
    pinned_repos = fetch_pinned_repos(user)

    print("> lenguajes", file=sys.stderr)
    totals = fetch_languages(
        repos,
        include_forks=lang_cfg.get("include_forks", False),
        exclude=lang_cfg.get("exclude"),
    )
    languages = language_shares(totals, lang_cfg.get("max_shown", 8))

    print("> calendario de contribuciones", file=sys.stderr)
    created = profile.get("created_at") or ""
    since = int(created[:4]) if created[:4].isdigit() else None
    days, exact = fetch_contributions(user, since)
    streaks = compute_streaks(days)
    streaks["exact_counts"] = exact

    print("> pull requests e issues", file=sys.stderr)
    counts = fetch_counts(user)

    years = 0
    if created:
        started = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
        years = (date.today() - started).days // 365

    metrics = {
        "contributions": streaks.get("total", 0),
        "own_repos": repo_stats["own_repos"],
        "stars": repo_stats["stars"],
        "followers": profile["followers"],
        "years": years,
        **counts,
    }

    return {
        "generated_at": datetime.now(ZoneInfo("America/Santiago")).isoformat(timespec="seconds"),
        "profile": profile,
        "repos": repo_stats,
        "pinned_repos": pinned_repos,
        "languages": languages,
        "streaks": streaks,
        "counts": counts,
        "years_on_github": years,
        "achievements": compute_achievements(metrics),
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))

    data = collect(config)

    out = root / "data" / "stats.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Estadisticas escritas en {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
