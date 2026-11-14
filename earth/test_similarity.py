"""Prueba mínima de la similitud, de la elección de sitios y del promedio por zona.

    .venv/bin/python earth/test_similarity.py
"""

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from similarity import distance_km, percentile_of, pick_sites, similarity, total_score


def test_iguales_dan_uno():
    assert similarity(2.6, 2.6, 2.5) == 1.0
    assert np.all(similarity(np.array([0.18, 0.18]), 0.18, 0.06) == 1.0)


def test_muy_distintos_dan_casi_cero():
    assert similarity(40.0, 2.6, 2.5) < 1e-6
    assert similarity(0.9, 0.18, 0.06) < 1e-6


def test_a_un_sigma_y_simetria():
    assert math.isclose(similarity(5.0, 3.0, 2.0), math.exp(-0.5))
    assert math.isclose(similarity(1.0, 3.0, 2.0), similarity(5.0, 3.0, 2.0))
    assert similarity(3.5, 3.0, 2.0) > similarity(5.0, 3.0, 2.0) > similarity(9.0, 3.0, 2.0)


def test_total_es_el_promedio():
    scores = {"a": np.array([1.0, 0.0]), "b": np.array([0.5, 1.0])}
    assert np.allclose(total_score(scores), [0.75, 0.5])
    assert np.allclose(total_score(scores, {"a": 3.0, "b": 1.0}), [0.875, 0.25])


def test_distancia():
    assert math.isclose(distance_km(0.0, 0.0, 0.0, 1.0), 111.195, rel_tol=1e-4)
    assert distance_km(-34.6, -58.4, -34.6, -58.4) == 0.0


def test_sitios_separados():
    lat = np.array([0.0, 0.1, 0.0, 10.0])
    lon = np.array([0.0, 0.0, 5.0, 0.0])
    score = np.array([0.99, 0.98, 0.90, 0.80])
    # la segunda mejor está a 11 km de la mejor: se saltea
    assert pick_sites(lat, lon, score, 3, 300.0) == [0, 2, 3]
    assert pick_sites(lat, lon, score, 2, 0.0) == [0, 1]


def test_percentil():
    s = np.array([0.1, 0.2, 0.3, 0.4])
    cw = np.cumsum(np.ones(4))
    assert percentile_of(0.4, s, cw) == 100.0
    assert percentile_of(0.25, s, cw) == 50.0
    assert percentile_of(0.05, s, cw) == 0.0


def test_promedio_por_zona():
    import measure as m
    from zones import zone_means

    # un bloque de 9 x 9 celdas en una franja cerca del ecuador
    band = m.bands()[45]
    r, c = (a.ravel() for a in np.meshgrid(np.arange(10, 19), np.arange(100, 109), indexing="ij"))
    cells = {"band": np.full(r.size, band.k), "row": r, "col": c, "w": np.ones(r.size), "lat": band.lats()[r]}
    centre = int(np.nonzero((r == 14) & (c == 104))[0][0])
    spike = np.zeros(r.size)
    spike[centre] = 1.0
    means, coverage = zone_means(cells, {"constante": np.full(r.size, 7.0), "pico": spike}, 25.0)
    assert np.allclose(means["constante"], 7.0)  # el promedio de una constante es la constante
    assert math.isclose(coverage[centre], 1.0)  # el círculo del centro está completo: 69 celdas
    assert math.isclose(means["pico"][centre], 1 / 69, rel_tol=1e-5)
    assert coverage[0] < 0.5  # una esquina del bloque tiene menos de la mitad del círculo


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for f in tests:
        f()
        print("ok ", f.__name__)
    print(f"{len(tests)} pruebas pasaron")
