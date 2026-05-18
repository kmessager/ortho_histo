from collections import defaultdict
import csv
from datetime import datetime
from io import StringIO
import sys
from pathlib import Path

import pandas as pd
import folium
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from config import CRS, GEOREF_MAX_RMS
from core.fetch_wfs import fetch_features
from core.filter_emprise import feature_intersects_emprise
from core.pipeline_download import export_dataset_footprints
from download.tif_downloader import download_image
from georef.georef_runner import run_georef_batch
from georef.simulation import simulate_feature_georef


def get_properties(feature):
    return feature.get("properties", {})


def get_dataset_id(feature):
    return get_properties(feature).get("dataset_identifier")


def get_image_id(feature):
    return get_properties(feature).get("image_identifier")


def parse_year(value):
    if value in (None, ""):
        return None

    text = str(value)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y"):
        try:
            return datetime.strptime(text[:10], fmt).year
        except ValueError:
            continue

    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])

    return None


def feature_year(feature):
    props = get_properties(feature)
    for key in (
        "date_cliche",
        "date",
        "shooting_date",
        "acquisition_date",
        "image_date",
        "date_image",
        "begin_lifespan_version",
    ):
        year = parse_year(props.get(key))
        if year is not None:
            return year

    image_id = get_image_id(feature)
    if image_id:
        parts = str(image_id).split("_")
        for part in parts:
            if len(part) == 4 and part.isdigit():
                year = int(part)
                if 1800 <= year <= 2100:
                    return year

    return None


def group_features_by_dataset(features):
    grouped = defaultdict(list)

    for feature in features:
        dataset_id = get_dataset_id(feature)
        if dataset_id:
            grouped[dataset_id].append(feature)

    return dict(sorted(grouped.items()))


def filter_features_by_year(features, year_min, year_max):
    filtered = []

    for feature in features:
        year = feature_year(feature)
        if year is None:
            continue
        if year < year_min or year > year_max:
            continue
        filtered.append(feature)

    return filtered


def build_map():
    m = folium.Map(
        location=[46.8, 2.4],
        zoom_start=6,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    folium.TileLayer(
        tiles=(
            "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
            "&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&FORMAT=image/jpeg"
            "&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
        ),
        attr="IGN-F/Geoportail",
        name="IGN Orthophotos",
        overlay=False,
        control=True,
        max_zoom=19,
    ).add_to(m)
    Draw(
        export=False,
        draw_options={
            "polyline": False,
            "circle": False,
            "circlemarker": False,
            "marker": False,
            "polygon": True,
            "rectangle": True,
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(m)
    folium.LayerControl(position="topright").add_to(m)
    return m


def extract_bounds(map_state):
    bounds = (map_state or {}).get("bounds")
    if not bounds:
        return None

    if "_southWest" in bounds and "_northEast" in bounds:
        south = bounds["_southWest"]["lat"]
        west = bounds["_southWest"]["lng"]
        north = bounds["_northEast"]["lat"]
        east = bounds["_northEast"]["lng"]
        return west, south, east, north

    if {"south", "west", "north", "east"}.issubset(bounds):
        return bounds["west"], bounds["south"], bounds["east"], bounds["north"]

    return None


def bbox_wgs84_to_projected(bbox_wgs84):
    from osgeo import osr

    west, south, east, north = bbox_wgs84

    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    target = osr.SpatialReference()
    target.ImportFromEPSG(3857)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    transform = osr.CoordinateTransformation(source, target)
    min_x, min_y, _ = transform.TransformPoint(west, south)
    max_x, max_y, _ = transform.TransformPoint(east, north)
    return min(min_x, max_x), min(min_y, max_y), max(min_x, max_x), max(min_y, max_y)


def get_drawn_feature(map_state):
    drawings = (map_state or {}).get("all_drawings") or []
    if not drawings:
        return None

    return drawings[-1]


def drawn_feature_to_projected_geometry(feature):
    import json

    from osgeo import ogr, osr

    geometry_json = (feature or {}).get("geometry")
    if not geometry_json:
        return None

    geometry = ogr.CreateGeometryFromJson(json.dumps(geometry_json))
    if geometry is None or geometry.IsEmpty():
        return None

    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    target = osr.SpatialReference()
    target.ImportFromEPSG(3857)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    geometry.Transform(osr.CoordinateTransformation(source, target))
    return geometry


def geometry_bbox(geometry):
    min_x, max_x, min_y, max_y = geometry.GetEnvelope()
    return min_x, min_y, max_x, max_y


def build_mission_rows(grouped_features):
    rows = []

    for dataset_id, features in grouped_features.items():
        years = sorted(
            year
            for year in (feature_year(feature) for feature in features)
            if year is not None
        )
        rows.append({
            "dataset_id": dataset_id,
            "annee_mission": years[0] if years and years[0] == years[-1] else (
                f"{years[0]}-{years[-1]}" if years else ""
            ),
            "annee_tri": years[0] if years else 9999,
            "nombre_photo": len(features),
        })

    rows.sort(key=lambda row: (row["annee_tri"], row["dataset_id"]))

    for row in rows:
        row.pop("annee_tri", None)

    return rows


def export_and_download_selected(grouped_features, selected_missions):
    selected_missions = [
        mission
        for mission in selected_missions
        if mission in grouped_features
    ]
    selected_features = [
        feature
        for mission in selected_missions
        for feature in grouped_features.get(mission, [])
    ]

    progress = st.progress(0)
    status_text = st.empty()
    total = len(selected_features)
    downloaded = 0
    skipped = 0
    errors = []

    for mission in selected_missions:
        footprint_path = export_dataset_footprints(mission, grouped_features[mission])
        st.write(f"Mission {mission}")
        st.write(f"Photos retenues apres simulation RMQ : {len(grouped_features[mission])}")
        st.write(f"GeoJSON : {footprint_path}")

        for feature in grouped_features[mission]:
            image_id = get_image_id(feature)
            done = downloaded + skipped + len(errors)
            status_text.write(f"Photo {done + 1}/{total} : {image_id}")
            try:
                _, status = download_image(feature, dataset_identifier=mission)
            except Exception as exc:
                errors.append({
                    "mission": mission,
                    "image_id": image_id,
                    "error": str(exc),
                })
                progress.progress((downloaded + skipped + len(errors)) / total)
                continue

            if status == "downloaded":
                downloaded += 1
            else:
                skipped += 1
            progress.progress((downloaded + skipped + len(errors)) / total if total else 1)

    return {
        "downloaded": downloaded,
        "skipped": skipped,
        "errors": errors,
        "total": total,
    }


def run_selected_georef(grouped_features, selected_missions, max_rms):
    summaries = []
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    for mission in selected_missions:
        image_ids = [
            get_image_id(feature)
            for feature in grouped_features.get(mission, [])
            if get_image_id(feature)
        ]
        summaries.append(
            run_georef_batch(
                debug=False,
                overwrite=True,
                dataset_identifier=mission,
                image_ids=image_ids,
                run_source="app",
                run_id=run_id,
                max_rms=max_rms,
            )
        )

    return summaries


def simulate_features(features, max_rms):
    results = []
    georef_features = []
    progress = st.progress(0)
    total = len(features)

    for index, feature in enumerate(features, start=1):
        try:
            result = simulate_feature_georef(feature, max_rms=max_rms)
        except Exception as exc:
            result = {
                "image_id": get_image_id(feature),
                "dataset_id": get_dataset_id(feature),
                "georeferenceable": False,
                "error": str(exc),
            }

        results.append(result)
        if result.get("georeferenceable"):
            georef_features.append(feature)

        progress.progress(index / total if total else 1)

    return results, georef_features


def build_simulation_summary(rows, features):
    years_by_dataset = defaultdict(list)
    for feature in features:
        dataset_id = get_dataset_id(feature)
        year = feature_year(feature)
        if dataset_id and year is not None:
            years_by_dataset[dataset_id].append(year)

    rows_by_dataset = defaultdict(list)
    for row in rows:
        dataset_id = row.get("dataset_id")
        if dataset_id:
            rows_by_dataset[dataset_id].append(row)

    summary_rows = []
    for dataset_id, dataset_rows in sorted(rows_by_dataset.items()):
        years = sorted(years_by_dataset.get(dataset_id, []))
        georef_rows = [row for row in dataset_rows if row.get("georeferenceable")]
        rejected_rows = [
            row
            for row in dataset_rows
            if not row.get("georeferenceable") and not row.get("error")
        ]
        error_rows = [row for row in dataset_rows if row.get("error")]
        accepted_rms_values = [
            row.get("selected_rms_m")
            for row in georef_rows
            if isinstance(row.get("selected_rms_m"), (int, float))
        ]
        rejected_rms_values = [
            row.get("selected_rms_m")
            for row in rejected_rows
            if isinstance(row.get("selected_rms_m"), (int, float))
        ]
        summary_rows.append({
            "dataset_id": dataset_id,
            "annee_mission": years[0] if years and years[0] == years[-1] else (
                f"{years[0]}-{years[-1]}" if years else ""
            ),
            "photos_simulees": len(dataset_rows),
            "photos_georeferencables": len(georef_rows),
            "photos_rejetees": len(rejected_rows),
            "erreurs": len(error_rows),
            "rmq_moyenne_toleree_m": round(
                sum(accepted_rms_values) / len(accepted_rms_values),
                3,
            ) if accepted_rms_values else "",
            "rmq_moyenne_rejetee_m": round(
                sum(rejected_rms_values) / len(rejected_rms_values),
                3,
            ) if rejected_rms_values else "",
        })

    return summary_rows


def build_simulation_csv(rows):
    if not rows:
        return ""

    fieldnames = sorted({key for row in rows for key in row.keys()})
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def clear_downstream_state():
    for key in (
        "simulation_rows",
        "georef_features",
        "download_summary",
        "download_grouped_features",
        "download_selected_missions",
        "simulation_summary_rows",
        "simulation_selected_missions",
        "simulation_max_rms",
    ):
        st.session_state.pop(key, None)

    st.session_state["download_done"] = False


def clear_mission_selection_state():
    for key in list(st.session_state.keys()):
        if key.startswith("mission_download_"):
            st.session_state.pop(key, None)


st.set_page_config(page_title="Ortho Histo", layout="wide")

st.title("Ortho Histo")
st.caption("Filtrage cartographique, simulation Helmert et telechargement IGN PVA")

with st.sidebar:
    st.header("Parametres")
    year_min = st.number_input("Annee minimum", min_value=1800, max_value=2100, value=1800)
    year_max = st.number_input("Annee maximum", min_value=1800, max_value=2100, value=2100)
    max_rms = st.number_input(
        "Seuil RMQ maximum (m)",
        min_value=1.0,
        max_value=1000.0,
        value=float(GEOREF_MAX_RMS),
        step=1.0,
    )
    st.caption(f"Flux WFS en {CRS}. La vue cartographique est reprojetee avant requete.")

if year_min > year_max:
    st.error("L'annee minimum doit etre inferieure ou egale a l'annee maximum.")
    st.stop()

map_state = st_folium(
    build_map(),
    height=560,
    use_container_width=True,
    returned_objects=["bounds", "center", "zoom", "all_drawings"],
    key="map",
)

bbox_wgs84 = extract_bounds(map_state)
drawn_feature = get_drawn_feature(map_state)
drawn_geometry = drawn_feature_to_projected_geometry(drawn_feature)

filter_clicked = st.button(
    "Filtrer l'emprise",
    type="primary",
    disabled=bbox_wgs84 is None and drawn_geometry is None,
)

if bbox_wgs84:
    st.caption(
        "Vue courante WGS84 : "
        f"{bbox_wgs84[0]:.5f}, {bbox_wgs84[1]:.5f}, "
        f"{bbox_wgs84[2]:.5f}, {bbox_wgs84[3]:.5f}"
    )

if drawn_geometry is not None:
    st.caption("Emprise dessinee active : le filtrage utilisera le dernier dessin.")
else:
    st.caption("Aucune emprise dessinee : le filtrage utilisera la vue courante.")

if filter_clicked:
    if drawn_geometry is not None:
        bbox = geometry_bbox(drawn_geometry)
        filter_geometry = drawn_geometry
    else:
        bbox = bbox_wgs84_to_projected(bbox_wgs84)
        filter_geometry = None

    st.session_state.pop("candidate_features", None)
    st.session_state.pop("candidate_grouped_features", None)
    clear_mission_selection_state()
    clear_downstream_state()

    with st.status("Interrogation WFS...", expanded=True) as status:
        st.write(f"Bbox projetee : {bbox}")

        features = fetch_features(bbox=bbox)
        st.write(f"Photos WFS candidates : {len(features)}")

        if filter_geometry is not None:
            features = [
                feature
                for feature in features
                if feature_intersects_emprise(feature, filter_geometry)
            ]
            st.write(f"Photos intersectant l'emprise dessinee : {len(features)}")

        features = filter_features_by_year(features, year_min, year_max)
        st.write(f"Photos dans la plage d'annees : {len(features)}")

        st.session_state["candidate_features"] = features
        st.session_state["candidate_grouped_features"] = group_features_by_dataset(features)
        status.update(label="Filtrage termine", state="complete")

candidate_features = st.session_state.get("candidate_features", [])
candidate_grouped = st.session_state.get("candidate_grouped_features", {})

if not candidate_features:
    st.info("Cadre la carte sur la zone voulue, puis lance le filtrage.")
    st.stop()

mission_rows = build_mission_rows(candidate_grouped)

if not mission_rows:
    st.warning("Aucune mission candidate dans cette vue.")
    st.stop()

st.subheader("Missions candidates")

left_select, right_select = st.columns(2)
if left_select.button("Tout selectionner"):
    for row in mission_rows:
        st.session_state[f"mission_download_{row['dataset_id']}"] = True

if right_select.button("Tout deselectionner"):
    for row in mission_rows:
        st.session_state[f"mission_download_{row['dataset_id']}"] = False

for row in mission_rows:
    key = f"mission_download_{row['dataset_id']}"
    if key not in st.session_state:
        st.session_state[key] = True

mission_editor_rows = []
for row in mission_rows:
    mission_editor_rows.append({
        **row,
        "Telecharger": st.session_state[f"mission_download_{row['dataset_id']}"],
    })

mission_editor_df = pd.DataFrame(mission_editor_rows)

edited_mission_df = st.data_editor(
    mission_editor_df,
    hide_index=True,
    use_container_width=True,
    disabled=["dataset_id", "annee_mission", "nombre_photo"],
    column_config={
        "Telecharger": st.column_config.CheckboxColumn(
            "Telecharger",
            default=True,
        ),
    },
    key="missions_candidates_editor",
)

for row in edited_mission_df.to_dict("records"):
    st.session_state[f"mission_download_{row['dataset_id']}"] = bool(row["Telecharger"])

selected_missions = [
    row["dataset_id"]
    for row in edited_mission_df.to_dict("records")
    if row["Telecharger"]
]

candidate_selected_features = [
    feature
    for mission in selected_missions
    for feature in candidate_grouped.get(mission, [])
]

left, right = st.columns(2)
left.metric("Missions selectionnees", len(selected_missions))
right.metric("Photos candidates selectionnees", len(candidate_selected_features))

simulate_clicked = st.button(
    "Simuler le georeferencement",
    disabled=not candidate_selected_features,
)

if simulate_clicked:
    clear_downstream_state()

    with st.status("Simulation du georeferencement...", expanded=True) as status:
        simulation_rows, georef_features = simulate_features(
            candidate_selected_features,
            max_rms=max_rms,
        )
        mission_summary_rows = build_simulation_summary(
            simulation_rows,
            candidate_selected_features,
        )
        rejected_count = sum(
            1
            for row in simulation_rows
            if not row.get("georeferenceable") and not row.get("error")
        )
        error_count = sum(1 for row in simulation_rows if row.get("error"))

        st.write(f"Photos simulees : {len(simulation_rows)}")
        st.write(f"Photos georeferencables automatiquement : {len(georef_features)}")
        st.write(f"Photos rejetees par simulation : {rejected_count}")
        st.write(f"Erreurs de simulation : {error_count}")

        st.session_state["simulation_rows"] = simulation_rows
        st.session_state["georef_features"] = georef_features
        st.session_state["simulation_summary_rows"] = mission_summary_rows
        st.session_state["simulation_selected_missions"] = selected_missions
        st.session_state["simulation_max_rms"] = max_rms
        status.update(label="Simulation terminee", state="complete")

simulation_rows = st.session_state.get("simulation_rows", [])
georef_features = st.session_state.get("georef_features", [])
simulation_summary_rows = st.session_state.get("simulation_summary_rows", [])
simulation_selected_missions = st.session_state.get("simulation_selected_missions", [])
simulation_max_rms = st.session_state.get("simulation_max_rms", max_rms)

if not simulation_rows:
    st.info("Selectionne les missions candidates, puis lance la simulation.")
    st.stop()

left, middle, right = st.columns(3)
left.metric("Images simulees", len(simulation_rows))
middle.metric("Images telechargeables", len(georef_features))
right.metric(
    "Images rejetees",
    sum(1 for row in simulation_rows if not row.get("georeferenceable")),
)

st.caption(f"Seuil RMQ utilise pour cette simulation : {simulation_max_rms:.2f} m")

if simulation_max_rms != max_rms:
    st.warning(
        "Le seuil RMQ affiche dans le panneau lateral a change depuis cette simulation. "
        "Relance la simulation pour appliquer le nouveau seuil."
    )

if simulation_summary_rows:
    st.subheader("Resume par mission")
    st.dataframe(simulation_summary_rows, use_container_width=True, hide_index=True)

grouped = group_features_by_dataset(georef_features)

if not grouped:
    st.warning("Aucune image georeferencable automatiquement dans les missions selectionnees.")

with st.expander("Details simulation"):
    st.dataframe(simulation_rows, use_container_width=True)
    st.download_button(
        "Telecharger le CSV de simulation",
        data=build_simulation_csv(simulation_rows),
        file_name=f"simulation_georef_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        disabled=not simulation_rows,
    )

simulation_threshold_changed = simulation_max_rms != max_rms

if st.button(
    "Exporter et telecharger",
    disabled=not grouped or simulation_threshold_changed,
):
    downloadable_missions = [
        mission
        for mission in simulation_selected_missions
        if mission in grouped
    ]
    download_summary = export_and_download_selected(grouped, downloadable_missions)
    st.session_state["download_done"] = True
    st.session_state["download_summary"] = download_summary
    st.session_state["download_grouped_features"] = grouped
    st.session_state["download_selected_missions"] = downloadable_missions

if st.session_state.get("download_done"):
    summary = st.session_state.get("download_summary", {})
    st.success(
        "Traitement termine. "
        f"Photos telechargees : {summary.get('downloaded', 0)}. "
        f"Photos deja presentes : {summary.get('skipped', 0)}. "
        f"Erreurs : {len(summary.get('errors', []))}. "
        f"Total : {summary.get('total', 0)}."
    )

    if summary.get("errors"):
        st.error("Certaines images n'ont pas ete telechargees.")
        st.dataframe(summary["errors"], use_container_width=True)

    if st.button(
        "Lancer le georeferencement",
        type="primary",
        disabled=bool(summary.get("errors")),
    ):
        with st.status("Georeferencement en cours...", expanded=True) as status:
            try:
                georef_summaries = run_selected_georef(
                    st.session_state["download_grouped_features"],
                    st.session_state["download_selected_missions"],
                    max_rms=simulation_max_rms,
                )
                for summary in georef_summaries:
                    st.write(
                        f"{summary['dataset_identifier']} : "
                        f"{summary['processed']}/{summary['total']} georeferencees, "
                        f"{summary['rejected']} rejetees, "
                        f"{summary['failed']} erreurs"
                    )
                    st.write(f"Log : {summary['log_path']}")

                    if summary["failed"]:
                        raise RuntimeError(
                            f"{summary['failed']} erreur(s) de georeferencement "
                            f"pour {summary['dataset_identifier']}"
                        )

                status.update(label="Georeferencement termine", state="complete")
                st.success("Georeferencement termine.")
            except Exception as exc:
                status.update(label="Georeferencement echoue", state="error")
                st.error(f"Georeferencement interrompu : {exc}")
