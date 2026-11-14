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

NODATA = -9999.0

# --- Máscara ---
RANGOS_VALIDOS = {"albedo": (0.0, 1.0), "ndvi": (-0.2, 1.0)}   # fuera de esto es relleno
NDVI_MAX = 0.15       # percentil 90 del NDVI por debajo de esto = sin vegetación
AGUA_MAX = 0.10       # fracción máxima de agua dentro de la celda
EXCLUIR_HIELO = True
HIELO_MAX = 0.10      # fracción máxima de hielo permanente dentro de la celda

# --- Similitud ---
VARIABLES = ["pendiente_deg", "relieve_m", "albedo"]
PESOS = {"pendiente_deg": 1.0, "relieve_m": 1.0, "albedo": 1.0}

# Cómo se llama cada variable nuestra en mars/targets.json
NOMBRE_EN_MARTE = {"pendiente_deg": "slope", "relieve_m": "roughness", "albedo": "albedo"}

# mars/targets.json define "roughness" como el DESVÍO ESTÁNDAR de la elevación en
# la celda; nuestro relieve_m es máximo - mínimo. puntuar.py divide relieve_m por
# este factor para estimar el desvío. OJO: el factor está medido SOLO en NOA
# (16.695 celdas: mediana 4,24; 90% entre 3,5 y 5,4; correlación 0,983).
# Poner 1.0 cuando relieve_m ya sea un desvío estándar.
RELIEVE_A_DESVIO = 4.24

# Nombre y unidad que muestra la página (lista "variables" de web/data/sites.json)
ETIQUETAS = {
    "pendiente_deg": ("Pendiente", "°"),
    "relieve_m": ("Relieve local", "m"),
    "albedo": ("Albedo", ""),
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
