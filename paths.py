from pathlib import Path

from config import DATASET_IDENTIFIER, EXPORT_DIR, GEOREF_METHOD, GEOREF_OUTPUT_SUFFIX


# ---------------------------------------------------
# ROOT DATASET
# ---------------------------------------------------

def get_dataset_dir(dataset_identifier=DATASET_IDENTIFIER):
    return EXPORT_DIR / dataset_identifier


# ---------------------------------------------------
# IMAGES
# ---------------------------------------------------

def get_images_raw_dir(dataset_identifier=DATASET_IDENTIFIER):
    return get_dataset_dir(dataset_identifier) / "images" / "raw"


def get_images_georef_dir(dataset_identifier=DATASET_IDENTIFIER):
    return get_dataset_dir(dataset_identifier) / "images" / "georef"


def get_images_georef_method_dir(
    method_name=GEOREF_METHOD,
    dataset_identifier=DATASET_IDENTIFIER,
):
    return get_images_georef_dir(dataset_identifier) / method_name


# ---------------------------------------------------
# GEOJSON
# ---------------------------------------------------

def get_geojson_dir(dataset_identifier=DATASET_IDENTIFIER):
    return get_dataset_dir(dataset_identifier) / "geojson"


def get_footprint_path(dataset_identifier=DATASET_IDENTIFIER):
    """Footprint brut IGN"""
    return get_geojson_dir(dataset_identifier) / f"{dataset_identifier}_footprint.geojson"


def get_georef_image_path(
    image_id,
    method_name=GEOREF_METHOD,
    dataset_identifier=DATASET_IDENTIFIER,
):
    return (
        get_images_georef_method_dir(method_name, dataset_identifier)
        / f"{image_id}{GEOREF_OUTPUT_SUFFIX}.tif"
    )


# ---------------------------------------------------
# LOGS
# ---------------------------------------------------

def get_logs_dir(dataset_identifier=DATASET_IDENTIFIER):
    return get_dataset_dir(dataset_identifier) / "logs"


def get_georef_logs_dir(
    run_source="batch",
    dataset_identifier=DATASET_IDENTIFIER,
):
    return get_logs_dir(dataset_identifier) / run_source


def get_georef_log_path(
    method_name=GEOREF_METHOD,
    dataset_identifier=DATASET_IDENTIFIER,
    run_source="batch",
    run_id=None,
):
    filename = f"{dataset_identifier}_georef_{method_name}_log.csv"
    if run_id:
        filename = f"{run_id}_{filename}"

    return (
        get_georef_logs_dir(run_source, dataset_identifier)
        / filename
    )


# ---------------------------------------------------
# INIT FOLDERS
# ---------------------------------------------------

def ensure_dirs(dataset_identifier=DATASET_IDENTIFIER):
    """
    Cree toute l'arborescence necessaire.
    """
    dirs = [
        get_images_raw_dir(dataset_identifier),
        get_images_georef_dir(dataset_identifier),
        get_images_georef_method_dir(dataset_identifier=dataset_identifier),
        get_geojson_dir(dataset_identifier),
        get_logs_dir(dataset_identifier),
        get_georef_logs_dir("batch", dataset_identifier),
        get_georef_logs_dir("app", dataset_identifier),
    ]

    for directory in dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
