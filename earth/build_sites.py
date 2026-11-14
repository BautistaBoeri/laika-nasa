#!/usr/bin/env python3
"""Busca en toda la Tierra las celdas que se parecen a cada sitio de Marte.

Uso (desde la raíz del repo):

    .venv/bin/python earth/build_sites.py                            # mundo entero
    .venv/bin/python earth/build_sites.py --region -69 -27 -65 -22   # prueba en una región

Lee mars/targets.json y content/known_analogs.json. Escribe:

    web/data/sites.json              los sitios (formato en docs/contratos.md)
    web/data/similarity_<id>.png     la capa continua, en Web Mercator
    web/data/img/<sitio>.jpg         imagen Sentinel-2 de cada sitio (se saltea con --sin-imagenes)
    earth/validacion.json            qué puntaje sacan los análogos conocidos
    earth/parametros.json            umbrales, pesos, fechas y datos usados

Con --region no toca web/ ni earth/: deja todo en data/prueba_region/.

La medición en Earth Engine queda en data/earth_cache/. Volver a correr no
gasta cuota mientras no cambien los parámetros de earth/measure.py.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure as m
from similarity import distance_km, percentile_of, pick_sites, similarity, total_score

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent

# Variables que se comparan. Agregar una es agregar una entrada acá, medirla en
# mars/build_targets.py y bajarla en un grupo de earth/measure.py.
VARIABLES = [
    {"id": "slope", "label": "Pendiente", "unit": "°", "decimals": 2},
    {"id": "roughness", "label": "Relieve local", "unit": "m", "decimals": 1},
    {"id": "albedo", "label": "Albedo", "unit": "", "decimals": 3},
]
WEIGHTS = None  # None = todas las variables pesan lo mismo; si no, {"slope": 1, ...}

NDVI_MAX = 0.15  # una celda es candidata si su NDVI medio es menor
LAND_MIN = 0.90  # y si al menos esta fracción es tierra firme (ni agua, ni hielo, ni ciudad)
N_SITES = 15
MIN_SEPARATION_KM = 300.0


# ---------------------------------------------------------------- celdas


def load_cells(todo: list) -> dict[str, np.ndarray]:
    """Todas las celdas medibles de los pedazos bajados, como arreglos planos.

    Medible = tierra firme con todas las variables. La máscara de vegetación
    no se aplica acá: queda en la columna "candidate".
    """
    cols: dict[str, list] = {k: [] for k in ["lat", "lon", "w", "band", "row", "col", "ndvi"] + [v["id"] for v in VARIABLES]}
    for band, c0, n in todo:
        d = m.load_chunk(band, c0)
        ok = d["landfrac"] >= LAND_MIN
        for v in VARIABLES:
            ok &= np.isfinite(d[v["id"]])
        r, c = np.nonzero(ok)
        if not r.size:
            continue
        lat = band.lats()[r]
        cols["lat"].append(lat)
        cols["lon"].append(band.lons(c0, n)[c])
        # peso = área real de la celda respecto de la nominal
        cols["w"].append(np.cos(np.radians(lat)) / np.cos(np.radians(band.lat_c)))
        cols["band"].append(np.full(r.size, band.k, dtype=np.int32))
        cols["row"].append(r.astype(np.int32))
        cols["col"].append((c0 + c).astype(np.int32))
        cols["ndvi"].append(np.nan_to_num(d["ndvi"][r, c], nan=0.0))  # sin dato de NDVI = sin vegetación
        for v in VARIABLES:
            cols[v["id"]].append(d[v["id"]][r, c])
    cells = {k: np.concatenate(a) if a else np.zeros(0) for k, a in cols.items()}
    cells["candidate"] = cells["ndvi"] < NDVI_MAX
    return cells


def within(cells: dict, lat: float, lon: float, radius_km: float) -> np.ndarray:
    """Índices de las celdas a menos de radius_km de un punto."""
    w, s, e, n = m.circle_bbox(lat, lon, radius_km)
    near = np.nonzero((cells["lat"] >= s) & (cells["lat"] <= n) & (cells["lon"] >= w) & (cells["lon"] <= e))[0]
    return near[distance_km(cells["lat"][near], cells["lon"][near], lat, lon) <= radius_km]


# ---------------------------------------------------------------- un sitio objetivo


def site_entry(lat: float, lon: float, known: bool, values: dict, scores: dict, pct) -> dict:
    """Un sitio en el formato de sites.json. values y scores traen un número por variable."""
    total = float(total_score(scores, WEIGHTS))
    return {
        "id": f"{round(lat, 1) + 0.0:.1f}_{round(lon, 1) + 0.0:.1f}",
        "lat": round(float(lat), 4),
        "lon": round(float(lon), 4),
        "known": known,
        "score": round(total, 4),
        "variables": {
            v["id"]: {"score": round(float(scores[v["id"]]), 4), "earth": round(float(values[v["id"]]), v["decimals"])}
            for v in VARIABLES
        },
        "percentile": round(pct(total), 2),
    }


def analyse_target(target: dict, sigma: dict, cells: dict, analogs: list) -> tuple[dict, dict, np.ndarray]:
    """Puntúa todas las celdas contra un sitio de Marte. Devuelve la entrada para
    sites.json, el informe de validación y el puntaje total de cada celda."""
    ids = [v["id"] for v in VARIABLES]
    scores = {vid: similarity(cells[vid], target["values"][vid]["mean"], sigma[vid]) for vid in ids}
    total = total_score(scores, WEIGHTS)
    cand = cells["candidate"]

    # distribución del puntaje entre las celdas candidatas, ponderada por área
    order = np.argsort(total[cand])
    sorted_scores, cum_w = total[cand][order], np.cumsum(cells["w"][cand][order])

    def pct(x: float) -> float:
        return percentile_of(x, sorted_scores, cum_w)

    # --- análogos conocidos: no entran en el cálculo, se miden después.
    # Puntaje de un análogo = promedio de los puntajes de las celdas a menos de
    # radius_km del punto (el mismo círculo con que se midió el sitio marciano).
    # Se usan todas las celdas medibles, tengan o no vegetación.
    known_sites, validation = [], []
    excluded = np.zeros(total.size, dtype=bool)
    for a in analogs:
        region = within(cells, a["lat"], a["lon"], a["radius_km"])
        excluded[region] = True
        if a.get("body", "mars") not in ("mars", "both"):
            continue
        circle = within(cells, a["lat"], a["lon"], target["radius_km"])
        row = {"name": a["name"], "lat": a["lat"], "lon": a["lon"], "radius_km": a["radius_km"]}
        if not circle.size:
            row["note"] = f"sin celdas medibles a menos de {target['radius_km']} km (agua, hielo o sin dato)"
            validation.append(row)
            continue
        w = cells["w"][circle]
        entry = site_entry(
            a["lat"], a["lon"], True,
            {vid: np.average(cells[vid][circle], weights=w) for vid in ids},
            {vid: np.average(scores[vid][circle], weights=w) for vid in ids},
            pct,
        )
        entry["name"], entry["source"] = a["name"], a["source"]
        known_sites.append(entry)
        row.update({
            "score": entry["score"], "percentile": entry["percentile"],
            "variables": entry["variables"],
            "cells_in_circle": int(circle.size),
            "candidate_fraction_in_circle": round(float(cand[circle].mean()), 3),
            "region": {
                "cells": int(region.size),
                "candidate_fraction": round(float(cand[region].mean()), 3),
                "mean_score": round(float(np.average(total[region], weights=cells["w"][region])), 4),
                "median_score": round(float(np.median(total[region])), 4),
                "median_percentile": round(pct(float(np.median(total[region]))), 2),
                "best_score": round(float(total[region].max()), 4),
            },
        })
        validation.append(row)

    # --- sitios nuevos: las mejores celdas candidatas fuera de los análogos conocidos
    pool = np.nonzero(cand & ~excluded)[0]
    chosen = pool[pick_sites(cells["lat"][pool], cells["lon"][pool], total[pool], N_SITES, MIN_SEPARATION_KM)]
    new_sites = [
        site_entry(cells["lat"][i], cells["lon"][i], False, {vid: cells[vid][i] for vid in ids},
                   {vid: scores[vid][i] for vid in ids}, pct)
        for i in chosen
    ]

    known_sites.sort(key=lambda s: -s["score"])
    out = {
        "id": target["id"], "name": target["name"], "lat": target["lat"], "lon": target["lon"],
        "values": {vid: target["values"][vid]["mean"] for vid in ids},
        "layer": f"data/similarity_{target['id']}.png",
        "sites": new_sites + known_sites,
    }
    w_all = cells["w"][cand]
    report = {
        "target": target["id"],
        "candidate_cells": int(cand.sum()),
        "candidate_area_km2": round(float(w_all.sum()) * m.CELL_KM**2),
        "score_quantiles": {f"p{q}": round(float(sorted_scores[min(np.searchsorted(cum_w, cum_w[-1] * q / 100), sorted_scores.size - 1)]), 4)
                            for q in (10, 25, 50, 75, 90, 95, 99)},
        "area_fraction_above": {str(t): round(float(w_all[total[cand] >= t].sum() / w_all.sum()), 4) for t in (0.8, 0.9, 0.95, 0.99)},
        "known_analogs": validation,
    }
    return out, report, np.where(cand, total, np.nan)


# ---------------------------------------------------------------- principal


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region", nargs=4, type=float, metavar=("OESTE", "SUR", "ESTE", "NORTE"),
                    help="medir solo esta región (prueba); no escribe en web/")
    ap.add_argument("--workers", type=int, default=8, help="pedidos simultáneos a Earth Engine")
    ap.add_argument("--solo-bajar", action="store_true", help="solo medir en Earth Engine y guardar en el caché")
    ap.add_argument("--sin-imagenes", action="store_true", help="no bajar la imagen satelital de cada sitio")
    args = ap.parse_args()

    mars = json.loads((ROOT / "mars" / "targets.json").read_text())
    analogs = json.loads((ROOT / "content" / "known_analogs.json").read_text())
    sigma = {vid: g["std"] for vid, g in mars["mars_global"].items()}
    max_radius = max(t["radius_km"] for t in mars["targets"])

    m.init()
    region = tuple(args.region) if args.region else None
    boxes = [m.circle_bbox(a["lat"], a["lon"], max(a["radius_km"], max_radius)) for a in analogs]
    todo = m.plan(boxes, region)
    m.download(todo, args.workers)
    print(f"Cuota de Earth Engine gastada en mediciones hasta ahora: {m.quota_spent_hours():.2f} EECU-h (estimada)")
    if args.solo_bajar:
        return

    cells = load_cells(todo)
    print(f"Celdas medibles: {cells['lat'].size} | candidatas (NDVI < {NDVI_MAX}): {int(cells['candidate'].sum())}")

    out_web = ROOT / "data" / "prueba_region" if region else ROOT / "web" / "data"
    out_meta = ROOT / "data" / "prueba_region" if region else HERE
    out_web.mkdir(parents=True, exist_ok=True)

    from layer import render_layer  # acá para que --solo-bajar no dependa de Pillow

    targets_out, reports = [], []
    for target in mars["targets"]:
        entry, report, cell_score = analyse_target(target, sigma, cells, analogs)
        targets_out.append(entry)
        reports.append(report)
        render_layer(cells, cell_score, out_web / f"similarity_{target['id']}.png")
        print_report(entry, report)
        if not args.sin_imagenes:
            from thumbs import site_image

            print("Imágenes de los sitios ...", flush=True)
            for site in entry["sites"]:
                image = site_image(site, out_web)
                if image:
                    site["image"] = image

    sites = {
        "generated": dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).isoformat(timespec="seconds"),
        "variables": [{k: v[k] for k in ("id", "label", "unit")} for v in VARIABLES],
        "targets": targets_out,
    }
    (out_web / "sites.json").write_text(json.dumps(sites, indent=2, ensure_ascii=False) + "\n")
    (out_meta / "validacion.json").write_text(json.dumps(reports, indent=2, ensure_ascii=False) + "\n")
    params = {
        "ndvi_max": NDVI_MAX, "land_min": LAND_MIN, "n_sites": N_SITES, "min_separation_km": MIN_SEPARATION_KM,
        "weights": WEIGHTS or "iguales", "sigma": sigma, "sigma_source": "desvío global de Marte (mars/targets.json)",
        "cell_km": round(m.CELL_KM, 3), "region": region, "measurement": m.parameters(),
        "screening": {"deg": m.SCREEN_DEG, "ndvi": m.SCREEN_NDVI, "min_pixels": m.SCREEN_MIN},
        "earth_engine_eecu_hours_estimated": round(m.quota_spent_hours(), 2),
    }
    (out_meta / "parametros.json").write_text(json.dumps(params, indent=2, ensure_ascii=False) + "\n")
    print("Escrito:", out_web / "sites.json")


def print_report(entry: dict, report: dict) -> None:
    print(f"\n=== {entry['name']} ===")
    print(f"Celdas candidatas: {report['candidate_cells']} ({report['candidate_area_km2'] / 1e6:.1f} millones de km²)")
    print("Puntaje por percentil de área:", report["score_quantiles"])
    print("Fracción del área candidata por encima de cada puntaje:", report["area_fraction_above"])
    print("\nSitios nuevos:")
    for i, s in enumerate([s for s in entry["sites"] if not s["known"]], 1):
        vals = "  ".join(f"{vid} {x['earth']} ({100 * x['score']:.0f}%)" for vid, x in s["variables"].items())
        print(f"  {i:2d}. {s['lat']:8.3f} {s['lon']:9.3f}  {100 * s['score']:5.1f}%  p{s['percentile']:.1f}  {vals}")
    print("\nAnálogos conocidos (puntaje medio a menos de 25 km | en todo su radio: mediana y mejor celda):")
    for a in report["known_analogs"]:
        if "note" in a:
            print(f"  {a['name'][:44]:44s} {a['note']}")
            continue
        r = a["region"]
        print(f"  {a['name'][:44]:44s} {100 * a['score']:5.1f}%  p{a['percentile']:5.1f} | "
              f"mediana {100 * r['median_score']:5.1f}% (p{r['median_percentile']:.0f})  mejor {100 * r['best_score']:5.1f}%  "
              f"sin vegetación {100 * r['candidate_fraction']:.0f}%")


if __name__ == "__main__":
    main()
