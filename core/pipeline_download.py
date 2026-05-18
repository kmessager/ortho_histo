from config import EMPRISE_SHAPE_PATH
from core.build_geojson import build_geojson
from core.fetch_wfs import fetch_features
from core.filter_emprise import (
    filter_features_by_emprise,
    get_emprise_bbox,
    read_emprise_geometry,
)
from download.tif_downloader import download_images
from export.footprint_geojson import export_geojson
from paths import ensure_dirs, get_footprint_path, get_images_raw_dir


def get_feature_properties(feature):
    return feature.get("properties", {})


def get_feature_dataset_id(feature):
    return get_feature_properties(feature).get("dataset_identifier")


def get_feature_image_id(feature):
    return get_feature_properties(feature).get("image_identifier")


def group_features_by_dataset(features):
    datasets = {}

    for feature in features:
        dataset_id = get_feature_dataset_id(feature)
        if not dataset_id:
            continue

        datasets.setdefault(dataset_id, []).append(feature)

    return dict(sorted(datasets.items()))


def fetch_features_for_dataset(dataset_identifier):
    return fetch_features(dataset_identifier=dataset_identifier)


def fetch_features_for_emprise(shape_path=EMPRISE_SHAPE_PATH):
    emprise_geometry = read_emprise_geometry(shape_path)
    bbox = get_emprise_bbox(emprise_geometry)
    features = fetch_features(bbox=bbox)
    return filter_features_by_emprise(
        features,
        emprise_geometry=emprise_geometry,
    )


def export_dataset_footprints(dataset_identifier, features):
    ensure_dirs(dataset_identifier)
    export_geojson(
        build_geojson(features),
        dataset_identifier=dataset_identifier,
    )
    return get_footprint_path(dataset_identifier)


def process_dataset(dataset_identifier, features):
    image_ids = [
        get_feature_image_id(feature)
        for feature in features
        if get_feature_image_id(feature)
    ]

    print(f"\nMission : {dataset_identifier}")
    print(f"Photos trouvees : {len(image_ids)}")

    footprint_path = export_dataset_footprints(dataset_identifier, features)
    print("GeoJSON exportes :")
    print(f"- Footprints : {footprint_path}")

    summary = download_images(features, dataset_identifier=dataset_identifier)

    raw_dir = get_images_raw_dir(dataset_identifier)
    present = sum((raw_dir / f"{image_id}.tif").exists() for image_id in image_ids)

    if present == len(image_ids) and summary["error"] == 0:
        print(f"Telechargement : complet ({present}/{len(image_ids)})")
    else:
        print(f"Telechargement : incomplet ({present}/{len(image_ids)})")

    if summary["error"] > 0:
        raise RuntimeError(
            f"{summary['error']} erreur(s) de telechargement pour {dataset_identifier}"
        )

    return summary
