# Scripts

Generadores locales del README. Unica dependencia externa: `Pillow`
(`pip install -r ../requirements.txt`). El resto es stdlib.

La idea: **todo se resuelve en tiempo de build**. Los datos se descargan una
vez, se guardan en `data/stats.json`, y lo que se publica es texto y SVG
versionados en el repo. Cuando alguien abre el perfil no se llama a ningun
servicio de terceros.

## Estructura

```
config.json              todo lo editable
data/stats.json          datos descargados de GitHub (regenerado)
profile/README.md        la portada; es lo que GitHub renderiza  (regenerado)
profile/assets/          avatar, ascii.txt y los SVG             (regenerado)
scripts/                 los generadores
```

Los assets viven dentro de `profile/` a proposito: la portada se referencia a
si misma con rutas relativas simples (`assets/languages.svg`), sin `../`, que
es lo unico que resuelve bien cuando GitHub la renderiza fuera del arbol del
repositorio.

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
| `svgraster.py`    | Rasteriza SVG con imagenes embebidas para que `img2ascii` los acepte.     |
| `github_data.py`  | Baja perfil, repos, lenguajes, calendario de contribuciones y logros.     |
| `svgkit.py`       | Dibuja la barra de lenguajes y los badges del stack como SVG locales.     |
| `render.py`       | Arma los bloques de texto: panel tipo neofetch, rachas, logros.           |
| `build_readme.py` | Orquesta todo y reemplaza los bloques marcados de `profile/README.md`.    |

## ASCII art suelto

```bash
python scripts/img2ascii.py profile/assets/yo.svg -w 40 -o profile/assets/ascii.txt
python scripts/img2ascii.py foto.jpg -w 60 --ramp blocks --autocontrast
```

Rampas disponibles: `minimal`, `standard`, `blocks`, `shades`. Estan pensadas
para fondo oscuro; usa `--invert` si el fondo es claro.

## SVG como origen

`img2ascii` acepta `.svg` ademas de los formatos de Pillow. Como Pillow no lee
SVG, `svgraster.py` los rasteriza primero, sin dependencias nuevas.

No es un renderer completo: dibuja los `<image>` embebidos en base64 aplicando
`transform`, `mask` y `use`, que es exactamente lo que exportan las
herramientas de quitar fondo (el caso de `profile/assets/yo.svg`). La parte
transparente del recorte queda como hueco en el ASCII, no como pixel negro. Un
SVG puramente vectorial no se dibuja: el build avisa y cae al ASCII por
defecto.

```bash
python scripts/svgraster.py profile/assets/yo.svg -o /tmp/preview.png -s 2
```

## Configuracion

Todo lo editable vive en `config.json`:

- `github_user` — de quien se sacan las estadisticas.
- `repo` — nombre del repositorio, solo para armar los enlaces del pie.
- `ascii` — imagen de origen, ancho, rampa y ajustes de contraste. Admite png,
  jpg, webp y svg. Si no existe el archivo se descarga el avatar publico de
  GitHub (salvo que la ruta sea `.svg`, que es raster y no aplica).
- `identity` — los datos personales que salen al lado del ASCII. Los campos
  vacios simplemente no se muestran.
- `tech` — categorias y tecnologias de los badges.
- `tech_colors` — sobrescribe el color de un badge puntual.
- `languages` — cuantos lenguajes mostrar, cuales excluir, si contar forks.

## Bloques de la portada

`build_readme.py` reemplaza el contenido entre marcadores de
`profile/README.md`, asi que se puede escribir lo que sea fuera de ellos sin
que se pierda:

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
