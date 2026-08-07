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

Los assets viven dentro de `profile/` para mantener todo junto, pero la
portada los referencia con URLs absolutas de `raw.githubusercontent.com`
(`render.raw_asset_base`), no con rutas relativas: cuando GitHub renderiza
`profile/README.md` como pagina de perfil, resuelve las rutas relativas de
imagenes contra la raiz del repo (no contra `profile/`), asi que
`assets/languages.svg` termina apuntando a `<repo>/assets/languages.svg`, que
no existe.

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
| `img2ascii.py`    | Convierte una imagen a celdas de ASCII con color. Sirve suelto como CLI.  |
| `svgraster.py`    | Rasteriza SVG con imagenes embebidas para que `img2ascii` los acepte.     |
| `github_data.py`  | Baja perfil, repos, lenguajes, calendario de contribuciones y logros.     |
| `svgkit.py`       | Dibuja el hero en color, la barra de lenguajes y los badges, como SVG.    |
| `render.py`       | Arma los bloques de texto: panel tipo neofetch, rachas, logros.           |
| `build_readme.py` | Orquesta todo y reemplaza los bloques marcados de `profile/README.md`.    |

## ASCII art suelto

```bash
python scripts/img2ascii.py profile/assets/yo.svg -w 40 -o profile/assets/ascii.txt
python scripts/img2ascii.py foto.jpg -w 60 --ramp blocks --autocontrast
```

Rampas disponibles: `minimal`, `standard`, `blocks`, `shades`. Estan pensadas
para fondo oscuro; usa `--invert` si el fondo es claro.

## El hero en color

Un bloque de codigo en markdown se pinta de un solo color, asi que el hero se
publica como `profile/assets/hero.svg`: la misma grilla de caracteres, pero
cada uno con el color que tenia ese punto de la foto.

Son dos tarjetas separadas: a la izquierda el retrato, a la derecha el panel de
datos. El panel a su vez va partido en dos bloques, con el titulo
`Estadisticas · al dia de hoy` y su regla como separador:

- **Arriba, lo fijo** (`render._identity_rows`): nombre, estudios, ubicacion y
  demas campos de `identity` en `config.json`. Solo cambian si se edita el
  archivo. Los valores largos se parten solos a `render.VALUE_WRAP` columnas.
- **Abajo, lo vivo** (`render._stat_rows`): repos, estrellas, seguidores,
  contribuciones, PRs, issues, rachas y tiempo en GitHub. Esto
  lo vuelve a bajar de la API el workflow diario de las 06:00 UTC.

Detalles que importan si se toca:

- **El panel va oscuro en los dos temas.** La rampa da glifos densos a los
  pixeles claros; sobre fondo blanco el retrato se leeria en negativo.
- **`min_brightness` levanta el piso del color.** La sombra ya la dibuja la
  densidad del glifo. Si ademas el color se va a negro, el trazo desaparece
  contra el panel y el retrato se deshace.
- **`char_aspect` tiene que ser el mismo** con que se genero el ASCII: define
  el alto de linea del SVG y es lo que evita que la cara salga estirada.
- **Cada fila lleva `textLength`**, asi que las columnas cuadran aunque el
  visor resuelva otra monoespaciada.

Con `"color": false` el hero vuelve al cuadro de texto, que es el unico formato
donde el ASCII sigue siendo texto seleccionable. `ascii.txt` se escribe igual
en los dos casos.

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
  GitHub (salvo que la ruta sea `.svg`, que es raster y no aplica). Ademas:
  `color` publica el hero como SVG en vez de texto, `saturation` sube el matiz
  de la foto, `min_brightness` (0-255) evita que los caracteres oscuros se
  pierdan contra el panel y `font_size` fija el tamano de la grilla.
- `identity` — los datos personales del bloque de arriba del panel (`email`,
  `name`, `studies`, `location`, `working_on`, `learning`, `ask_me_about`,
  `collaborate_on`, `fun_fact`). Los campos vacios simplemente no se muestran.
- `tech` — categorias y tecnologias de los badges.
- `quote` — la cita de la portada, agrupada por dia de la semana ISO: `"1"` es
  lunes y `"7"` domingo. Cada dia es una lista de `{ "text", "author" }` y el
  build elige la que toca segun la fecha en `America/Santiago`. Con varias
  citas en un mismo dia la lista avanza una posicion cada 3 dias, asi que el
  lunes no repite siempre la misma. Un dia sin citas deja el hueco con una
  pista en vez del bloque.
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
<!-- BEGIN:quote --> ... <!-- END:quote -->
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
