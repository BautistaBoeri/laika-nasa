"""
Parámetros del rol Tierra. Todo lo que se puede ajustar está acá.
puntuar.py guarda una copia de estos valores en earth/parametros_usados.json
cada vez que corre, para tenerlos a mano en la presentación.
"""

PROYECTO = "laika-nasa"

# --- Grilla ---
CELDA_GRADOS = 0.05   # tamaño de celda de salida (~5,5 km en el ecuador)
SUBCELDAS = 12        # 0.05° / 12 = 0.004167° ≈ 463 m: resolución a la que se
                      # degrada el modelo de elevación ANTES de pendiente y relieve

# [lon_min, lat_min, lon_max, lat_max]; tienen que ser múltiplos de CELDA_GRADOS
REGIONES = {
    "noa": [-70.0, -28.0, -64.0, -21.0],      # noroeste argentino (paso 2)
    "mundo": [-180.0, -80.0, 180.0, 84.0],
}

TILE_GRADOS = 10      # tamaño de cada pedido a Earth Engine
HILOS = 6             # pedidos en paralelo

# --- Datos ---
DEM_COLECCION = "COPERNICUS/DEM/GLO30_2024_1"   # reemplazo de la obsoleta
DEM_RESPALDO = "COPERNICUS/DEM/GLO30"           # se usa si la de arriba no carga
DEM_BANDA = "DEM"

ALBEDO_ANIOS = [2021, 2022, 2023]
ALBEDO_CADA_DIAS = 8      # el producto es diario pero cada imagen ya resume 16 días

NDVI_DESDE, NDVI_HASTA = "2022-01-01", "2024-01-01"
COBERTURA_ANIO = 2022    # año del mapa de cobertura (MCD12Q1)
TEMP_DESDE, TEMP_HASTA = "2022-01-01", "2024-01-01"   # segunda tanda
ARIDEZ_DESDE, ARIDEZ_HASTA = "1991-01-01", "2021-01-01"   # normal climática de 30 años

NODATA = -9999.0

# --- Máscara ---
RANGOS_VALIDOS = {"albedo": (0.0, 1.0), "ndvi": (-0.2, 1.0)}   # fuera de esto es relleno
NDVI_MAX = 0.15       # percentil 90 del NDVI por debajo de esto = sin vegetación
AGUA_MAX = 0.10       # fracción máxima de agua dentro de la celda
EXCLUIR_HIELO = True
HIELO_MAX = 0.10      # fracción máxima de hielo permanente dentro de la celda

# --- Similitud ---
# desvio_m (medir_extra.py) es el desvío estándar de la elevación en la celda, la
# misma definición de "roughness" que usa Marte. La alternativa vieja es relieve_m
# (máximo - mínimo) dividido por RELIEVE_A_DESVIO.
#
# Desde el 15/11 se suman tres (medir_extra.py baja "aridez"; las otras dos se
# calculan en puntuar.py). Para volver al ranking de tres variables alcanza con
# dejar solo las tres primeras.
#   pendiente_var, desvio_var   desvío de pendiente_deg y desvio_m entre las celdas
#                               del círculo de SUAVIZADO_KM. Marte: el "std" del sitio.
#   aridez                      lluvia / evapotranspiración potencial (TerraClimate)
VARIABLES = ["pendiente_deg", "desvio_m", "albedo",
             "pendiente_var", "desvio_var", "aridez"]

# Variables que son el desvío de otra dentro del círculo: {variable: de cuál}.
DISPERSION = {"pendiente_var": "pendiente_deg", "desvio_var": "desvio_m"}

# Variables que Marte no mide en targets.json: valor fijo para todos los sitios.
# Aridez 0 = no llueve nada.
VALOR_EN_MARTE = {"aridez": 0.0}

# Variables informativas: se calculan y se guardan en cada sitio de sites.json junto
# con el valor de Marte, pero con peso 0: no cambian score ni ranking.
#
# "termica" = inercia térmica aparente, (1 - albedo) / (LST día - LST noche), pasada
# a percentil (0 a 1, ponderado por área) dentro del suelo desnudo (las celdas que
# pasan la máscara), para comparar con "thermal" de Marte, que es el percentil de la
# inercia térmica dentro de Marte. Necesita earth/datos/<region>_extra/.
# Decisión del 14/11: NO entra al puntaje. La amplitud día-noche en la Tierra depende
# también de la altura, la humedad y las nubes, no solo del suelo. Las pruebas están
# en earth/analisis_termica.json. Para que puntúe: pasarla de INFORMATIVAS a VARIABLES.
INFORMATIVAS = ["termica"]
TERMICA_AMPLITUD_MIN_C = 1.0   # con menos diferencia día-noche el cociente no es confiable

PESOS = {"pendiente_deg": 1.0, "relieve_m": 1.0, "desvio_m": 1.0, "albedo": 1.0,
         "termica": 1.0, "pendiente_var": 1.0, "desvio_var": 1.0, "aridez": 1.0}

# De dónde salió el mars/targets.json que hay en disco. puntuar.py guarda esta línea
# en parametros_usados.json junto con el sha256 del archivo (calculado con fin de
# línea LF, para que dé lo mismo en Windows y en Linux).
TARGETS_ORIGEN = ("con seguimiento en git, traído de main (merge fab0bff); "
                  "mismo contenido que el commit 5db5995 de marte-targets")

# Cómo se llama cada variable nuestra en mars/targets.json
NOMBRE_EN_MARTE = {"pendiente_deg": "slope", "relieve_m": "roughness",
                   "desvio_m": "roughness", "albedo": "albedo", "termica": "thermal",
                   "pendiente_var": "slope_std", "desvio_var": "roughness_std",
                   "aridez": "aridity"}

# Tolerancia (sigma) de la similitud. Por defecto es el desvío global de Marte que
# trae targets.json (para una de DISPERSION, el de su variable de origen); acá van
# las variables que usan una propia. Para un percentil el desvío global es 0,29
# (distribución uniforme) y casi no discrimina.
# Aridez: 0,05 es el límite de "hiperárido" (UNEP); ahí el puntaje vale 0,61, lo
# mismo que estar a 1 desvío del sitio marciano en las otras variables.
SIGMA_PROPIA = {"termica": 0.15, "aridez": 0.05}

# mars/targets.json define "roughness" como el DESVÍO ESTÁNDAR de la elevación en
# la celda; nuestro relieve_m es máximo - mínimo. puntuar.py divide relieve_m por
# este factor para estimar el desvío. OJO: el factor está medido SOLO en NOA
# (16.695 celdas: mediana 4,24; 90% entre 3,5 y 5,4; correlación 0,983).
# Solo se aplica si "relieve_m" está en VARIABLES. Desde que se usa desvio_m vale
# 1.0; para volver a la estimación vieja: VARIABLES con "relieve_m" y factor 4.24.
RELIEVE_A_DESVIO = 1.0

# Nombre y unidad que muestra la página (lista "variables" de web/data/sites.json)
ETIQUETAS = {
    "pendiente_deg": ("Pendiente", "°"),
    "relieve_m": ("Relieve local", "m"),
    "desvio_m": ("Relieve local", "m"),
    "albedo": ("Albedo", ""),
    "termica": ("Inercia térmica, percentil (informativa, no puntúa)", ""),
    "pendiente_var": ("Variación de la pendiente", "°"),
    "desvio_var": ("Variación del relieve local", "m"),
    "aridez": ("Aridez (lluvia / evaporación potencial)", ""),
}

# --- Selección de sitios ---
N_SITIOS = 15
SEPARACION_KM = 300       # distancia mínima entre sitios elegidos
RADIO_CONOCIDOS_KM = 300  # zona alrededor de un análogo conocido que se saca de la búsqueda
RADIO_VALIDACION_KM = 25  # radio para puntuar un análogo conocido

# Desempate: el puntaje de un sitio es el promedio de las celdas en un círculo de
# este radio (el mismo con que Marte describe cada sitio objetivo). Las celdas
# enmascaradas cuentan como 0. Con 0 se apaga y se puntúa celda por celda.
SUAVIZADO_KM = 25
SUAVIZADO_MIN_FRAC = 0.5  # fracción mínima de celdas válidas en el círculo para
                          # que un lugar pueda salir como sitio nuevo

# Los sitios nuevos solo se buscan entre -LAT_MAX_BUSQUEDA y +LAT_MAX_BUSQUEDA: más
# cerca de los polos la celda de 0.05° se angosta (a 60° mide la mitad de ancho) y
# el relieve queda subestimado. Los análogos conocidos se puntúan igual, con nota.
LAT_MAX_BUSQUEDA = 60

# --- Capa PNG ---
PNG_LIMITES = [-180.0, -85.0, 180.0, 85.0]   # [O, S, E, N] que fija docs/contratos.md
PNG_ANCHO_MAX = 4096
PNG_UMBRAL = 0.30         # por debajo de este puntaje la capa es transparente
