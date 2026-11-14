"""Similitud entre celdas de la Tierra y un sitio de Marte, y elección de sitios."""

from __future__ import annotations

import numpy as np

EARTH_RADIUS_KM = 6371.0088


def similarity(earth, mars: float, sigma: float) -> np.ndarray:
    """exp(-0.5 * ((tierra - marte) / sigma)^2): 1 si coinciden, cae hacia 0 al alejarse.

    sigma es la dispersión de la variable; usamos el desvío de todo Marte.
    """
    return np.exp(-0.5 * ((np.asarray(earth, dtype=float) - mars) / sigma) ** 2)


def total_score(scores: dict[str, np.ndarray], weights: dict[str, float] | None = None) -> np.ndarray:
    """Promedio ponderado de los puntajes por variable. Sin pesos, todas valen lo mismo."""
    w = {v: 1.0 if weights is None else weights[v] for v in scores}
    return sum(w[v] * scores[v] for v in scores) / sum(w.values())


def distance_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Distancia sobre la esfera entre puntos en grados (haversine)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlat, dlon = p2 - p1, np.radians(lon2) - np.radians(lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def pick_sites(lat: np.ndarray, lon: np.ndarray, score: np.ndarray, n: int, min_km: float) -> list[int]:
    """Índices de las n celdas de mayor puntaje, separadas entre sí al menos min_km."""
    alive = np.isfinite(score)
    chosen: list[int] = []
    while len(chosen) < n and alive.any():
        i = int(np.argmax(np.where(alive, score, -np.inf)))
        chosen.append(i)
        alive[i] = False
        alive &= distance_km(lat, lon, lat[i], lon[i]) >= min_km
    return chosen


def percentile_of(value: float, sorted_scores: np.ndarray, cum_weight: np.ndarray) -> float:
    """Porcentaje del área (peso acumulado) con puntaje menor o igual a value."""
    i = np.searchsorted(sorted_scores, value, side="right")
    return 0.0 if i == 0 else float(100.0 * cum_weight[i - 1] / cum_weight[-1])
