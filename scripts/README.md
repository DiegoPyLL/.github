# Scripts

Generadores locales del README. Unica dependencia externa: `Pillow`
(`pip install -r ../requirements.txt`). El resto es stdlib.

La idea: **todo se resuelve en tiempo de build**. Los datos se descargan una
vez, se guardan en `data/stats.json`, y lo que se publica es texto y SVG
versionados en el repo. Cuando alguien abre el perfil no se llama a ningun
servicio de terceros.

## Uso

```bash
python scripts/build_readme.py            # descarga datos y regenera todo
python scripts/build_readme.py --no-fetch # reusa data/stats.json (sin red)
```

Opcionalmente exporta `GITHUB_TOKEN` para subir el limite de la API de 60 a
5000 peticiones por hora. Sin token igual funciona.

## Archivos

| Script            | Que hace                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `img2ascii.py`    | Convierte una imagen a ASCII art. Sirve suelto como CLI.                  |
| `github_data.py`  | Baja perfil, repos, lenguajes, calendario de contribuciones y logros.     |
| `svgkit.py`       | Dibuja la barra de lenguajes y los badges del stack como SVG locales.     |
| `render.py`       | Arma los bloques de texto: panel tipo neofetch, rachas, logros.           |
| `build_readme.py` | Orquesta todo y reemplaza los bloques marcados del `README.md`.           |

## ASCII art suelto

```bash
python scripts/img2ascii.py assets/avatar.png --width 40 -o assets/ascii.txt
python scripts/img2ascii.py foto.jpg -w 60 --ramp blocks --autocontrast
```

Rampas disponibles: `minimal`, `standard`, `blocks`, `shades`. Estan pensadas
para fondo oscuro; usa `--invert` si el fondo es claro.

## Configuracion

Todo lo editable vive en `config.json`:

- `github_user` — de quien se sacan las estadisticas.
- `ascii` — imagen de origen, ancho, rampa y ajustes de contraste. Si no
  existe el archivo, se descarga el avatar publico de GitHub.
- `identity` — los datos personales que salen al lado del ASCII. Los campos
  vacios simplemente no se muestran.
- `tech` — categorias y tecnologias de los badges.
- `tech_colors` — sobrescribe el color de un badge puntual.
- `languages` — cuantos lenguajes mostrar, cuales excluir, si contar forks.

## Bloques del README

`build_readme.py` reemplaza el contenido entre marcadores, asi que se puede
escribir lo que sea fuera de ellos sin que se pierda:

```
<!-- BEGIN:hero -->   ...  <!-- END:hero -->
<!-- BEGIN:streaks --> ... <!-- END:streaks -->
<!-- BEGIN:languages --> ... <!-- END:languages -->
<!-- BEGIN:achievements --> ... <!-- END:achievements -->
<!-- BEGIN:tech --> ... <!-- END:tech -->
<!-- BEGIN:footer --> ... <!-- END:footer -->
```

## Actualizacion automatica

`.github/workflows/refresh-readme.yml` corre el build a diario y commitea los
cambios. Usa el `GITHUB_TOKEN` que Actions ya provee.

## Nota sobre las rachas

El calendario de contribuciones se lee de
`https://github.com/users/<user>/contributions`, el mismo endpoint publico que
usa la propia web del perfil. No es una API documentada: si GitHub cambia el
HTML, `_parse_calendar()` en `github_data.py` es lo unico que hay que ajustar.
El build no falla por eso, solo se queda sin la seccion de rachas.
