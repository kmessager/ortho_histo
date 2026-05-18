import csv
from datetime import datetime
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

from config import DATASET_IDENTIFIER, GEOREF_MAX_RMS, GEOREF_METHOD
from georef.gdal_writer import write_georeferenced_copy
from georef.methods import get_method
from georef.tiff_gcps import (
    CONTROL_TARGETS,
    match_gcps_to_targets,
    read_footprint_gcp_candidates,
)
from paths import (
    get_georef_image_path,
    get_georef_log_path,
    get_images_georef_method_dir,
    get_images_raw_dir,
)


CORNER_TARGETS = ("UL", "UR", "DR", "DL")


def get_image_id(path: Path):
    return path.stem


def estimate_labeled_transform(control_gcps, labels, estimate_transform):
    gcps = [control_gcps[label] for label in labels]
    transform = estimate_transform(gcps)
    transform["gcp_count"] = len(labels)
    transform["gcp_labels"] = labels
    return transform


def choose_strict_helmert(gcps, estimate_transform, max_rms=GEOREF_MAX_RMS):
    if len(gcps) < 4:
        raise ValueError("Au moins 4 GCP sont necessaires")

    control_gcps = match_gcps_to_targets(gcps, CONTROL_TARGETS)

    eight_transform = None
    if len(gcps) >= 8:
        eight_transform = estimate_labeled_transform(
            control_gcps,
            CONTROL_TARGETS,
            estimate_transform,
        )

    corner_transform = estimate_labeled_transform(
        control_gcps,
        CORNER_TARGETS,
        estimate_transform,
    )

    if eight_transform is not None and eight_transform["rms"] <= max_rms:
        return eight_transform, eight_transform, corner_transform

    if corner_transform["rms"] <= max_rms:
        return corner_transform, eight_transform, corner_transform

    return None, eight_transform, corner_transform


def choose_best_strict_helmert(candidates, estimate_transform, max_rms=GEOREF_MAX_RMS):
    eight_transforms = []
    corner_transforms = []

    for gcps in candidates:
        control_gcps = match_gcps_to_targets(gcps, CONTROL_TARGETS)

        if len(gcps) >= 8:
            eight_transforms.append(
                estimate_labeled_transform(
                    control_gcps,
                    CONTROL_TARGETS,
                    estimate_transform,
                )
            )

        corner_transforms.append(
            estimate_labeled_transform(
                control_gcps,
                CORNER_TARGETS,
                estimate_transform,
            )
        )

    eight_transform = None
    if eight_transforms:
        eight_transform = min(eight_transforms, key=lambda item: item["rms"])

    corner_transform = min(corner_transforms, key=lambda item: item["rms"])

    if eight_transform is not None and eight_transform["rms"] <= max_rms:
        return eight_transform, eight_transform, corner_transform

    if corner_transform["rms"] <= max_rms:
        return corner_transform, eight_transform, corner_transform

    return None, eight_transform, corner_transform


def empty_log_row(image_id, run_source, run_id):
    return {
        "run_source": run_source,
        "run_id": run_id,
        "image_id": image_id,
        "status": "",
        "orientation_wfs": "",
        "orientation_north_deg": "",
        "gcp_count": "",
        "gcp_labels": "",
        "rms_m": "",
        "max_error_m": "",
        "orientation": "",
        "scale": "",
        "rotation_deg": "",
        "try_8_rms_m": "",
        "try_8_max_error_m": "",
        "try_4_rms_m": "",
        "try_4_max_error_m": "",
        "output_path": "",
        "stale_output_removed": "",
        "error": "",
    }


def format_number(value):
    if value is None:
        return ""

    return f"{value:.6f}"


def fill_transform_fields(row, transform):
    row["gcp_count"] = transform["gcp_count"]
    row["gcp_labels"] = ",".join(transform["gcp_labels"])
    row["rms_m"] = format_number(transform["rms"])
    row["max_error_m"] = format_number(transform["max_error"])
    row["orientation"] = transform.get("orientation", "")
    row["scale"] = format_number(transform.get("scale"))
    row["rotation_deg"] = format_number(transform.get("rotation_deg"))


def fill_orientation_fields(row, gcp_candidates):
    if not gcp_candidates or not gcp_candidates[0]:
        return

    first_gcp = gcp_candidates[0][0]
    row["orientation_wfs"] = format_number(first_gcp.get("orientation_wfs"))
    row["orientation_north_deg"] = format_number(first_gcp.get("orientation_north"))


def fill_attempt_fields(row, prefix, transform):
    if transform is None:
        return

    row[f"{prefix}_rms_m"] = format_number(transform["rms"])
    row[f"{prefix}_max_error_m"] = format_number(transform["max_error"])


def write_georef_log(log_path, rows):
    log_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "run_source",
        "run_id",
        "image_id",
        "status",
        "orientation_wfs",
        "orientation_north_deg",
        "gcp_count",
        "gcp_labels",
        "rms_m",
        "max_error_m",
        "orientation",
        "scale",
        "rotation_deg",
        "try_8_rms_m",
        "try_8_max_error_m",
        "try_4_rms_m",
        "try_4_max_error_m",
        "output_path",
        "stale_output_removed",
        "error",
    ]

    with open(log_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def run_georef_batch(
    debug=False,
    overwrite=True,
    method_name=GEOREF_METHOD,
    dataset_identifier=DATASET_IDENTIFIER,
    image_ids=None,
    run_source="batch",
    run_id=None,
    max_rms=GEOREF_MAX_RMS,
):
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=== GEOREFERENCEMENT ===")
    print(f"Mission : {dataset_identifier}")
    print(f"Run : {run_source}/{run_id}")
    print(f"Methode : {method_name}")
    print(f"Strategie GCP : 8 GCP puis 4 coins")
    print(f"Seuil RMQ : {max_rms:.2f} m")

    input_dir = get_images_raw_dir(dataset_identifier)
    output_dir = get_images_georef_method_dir(method_name, dataset_identifier)
    log_path = get_georef_log_path(
        method_name,
        dataset_identifier,
        run_source,
        run_id,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    tif_paths = sorted(input_dir.glob("*.tif"))
    if image_ids is not None:
        image_ids = set(image_ids)
        tif_paths = [
            tif_path
            for tif_path in tif_paths
            if get_image_id(tif_path) in image_ids
        ]

    print(f"Photos a georeferencer : {len(tif_paths)}")

    if not tif_paths:
        print(f"[WARN] Aucun TIFF trouve dans {input_dir}")
        return {
            "dataset_identifier": dataset_identifier,
            "run_source": run_source,
            "run_id": run_id,
            "processed": 0,
            "skipped": 0,
            "rejected": 0,
            "failed": 0,
            "total": 0,
            "log_path": str(log_path),
            "output_dir": str(output_dir),
        }

    estimate_transform = get_method(method_name)

    processed = 0
    skipped = 0
    failed = 0
    rejected = 0
    rms_values = []
    max_errors = []
    log_rows = []

    for tif_path in tqdm(tif_paths, desc=f"Georeferencement {method_name}", unit="photo"):
        image_id = get_image_id(tif_path)
        output_tif = get_georef_image_path(
            image_id,
            method_name,
            dataset_identifier,
        )
        log_row = empty_log_row(image_id, run_source, run_id)

        if output_tif.exists() and not overwrite:
            log_row["status"] = "skipped"
            log_row["output_path"] = str(output_tif)
            log_rows.append(log_row)
            skipped += 1
            continue

        try:
            gcp_candidates, projection = read_footprint_gcp_candidates(tif_path)
            fill_orientation_fields(log_row, gcp_candidates)
            transform, eight_transform, corner_transform = choose_best_strict_helmert(
                gcp_candidates,
                estimate_transform,
                max_rms=max_rms,
            )
            fill_attempt_fields(log_row, "try_8", eight_transform)
            fill_attempt_fields(log_row, "try_4", corner_transform)

            if transform is None:
                log_row["status"] = "rejected"
                if corner_transform is not None:
                    fill_transform_fields(log_row, corner_transform)
                elif eight_transform is not None:
                    fill_transform_fields(log_row, eight_transform)

                if output_tif.exists() and overwrite:
                    output_tif.unlink()
                    log_row["stale_output_removed"] = "yes"

                rejected += 1
                log_rows.append(log_row)

                if debug:
                    print(
                        f"{image_id} : rejete "
                        f"rms={log_row['rms_m']}m "
                        f"gcp={log_row['gcp_count']}"
                    )

                continue

            if output_tif.exists() and overwrite:
                output_tif.unlink()

            write_georeferenced_copy(
                input_tif=tif_path,
                output_tif=output_tif,
                geotransform=transform["geotransform"],
                projection=projection,
            )

            rms_values.append(transform["rms"])
            max_errors.append(transform["max_error"])
            fill_transform_fields(log_row, transform)
            log_row["status"] = "georeferenced"
            log_row["output_path"] = str(output_tif)
            log_rows.append(log_row)

            if debug:
                print(
                    f"{image_id} : "
                    f"gcp={transform['gcp_count']} "
                    f"rms={transform['rms']:.2f}m "
                    f"max={transform['max_error']:.2f}m "
                    f"orientation={transform['orientation']} "
                    f"rotation={transform['rotation_deg']:.2f}deg "
                    f"scale={transform['scale']:.6f}"
                )

            processed += 1

        except Exception as exc:
            print(f"[ERROR] {image_id} : {exc}")
            log_row["status"] = "error"
            log_row["error"] = str(exc)
            log_rows.append(log_row)
            failed += 1

    write_georef_log(log_path, log_rows)

    if failed == 0 and skipped == 0 and processed == len(tif_paths):
        print(f"Georeferencement : complet ({processed}/{len(tif_paths)})")
    else:
        print(f"Georeferencement : partiel ({processed}/{len(tif_paths)})")
        print(f"Ignorees : {skipped}")
        print(f"Rejetees : {rejected}")
        print(f"Erreurs  : {failed}")

    if rms_values:
        mean_rms = sum(rms_values) / len(rms_values)
        max_error = max(max_errors)
        print(f"Residuals GCP : rms moyen {mean_rms:.2f} m, max {max_error:.2f} m")
        print(f"Sortie : {output_dir}")

    print(f"Log : {log_path}")

    return {
        "dataset_identifier": dataset_identifier,
        "run_source": run_source,
        "run_id": run_id,
        "processed": processed,
        "skipped": skipped,
        "rejected": rejected,
        "failed": failed,
        "total": len(tif_paths),
        "log_path": str(log_path),
        "output_dir": str(output_dir),
    }


if __name__ == "__main__":
    run_georef_batch(debug=True)
