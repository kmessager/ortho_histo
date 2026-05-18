import json

from config import DATASET_IDENTIFIER
from paths import get_footprint_path, get_geojson_dir


def export_geojson(geojson, filename=None, dataset_identifier=DATASET_IDENTIFIER):
    dataset_dir = get_geojson_dir(dataset_identifier)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        path = get_footprint_path(dataset_identifier)
    else:
        path = dataset_dir / filename

    with open(path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)
