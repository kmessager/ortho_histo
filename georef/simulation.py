import struct

import requests

from config import DOWNLOAD_TIMEOUT, GEOREF_MAX_RMS
from download.tif_downloader import build_url
from georef.georef_runner import (
    CORNER_TARGETS,
    estimate_labeled_transform,
    match_gcps_to_targets,
)
from georef.methods.helmert import estimate_transform
from georef.tiff_gcps import (
    CONTROL_TARGETS,
    build_image_targets,
    build_oriented_footprint_gcps,
    get_exterior_ring_points,
)


TIFF_HEADER_RANGE_SIZE = 65536


def get_feature_properties(feature):
    return feature.get("properties", {})


def get_feature_image_id(feature):
    return get_feature_properties(feature).get("image_identifier")


def get_feature_dataset_id(feature):
    return get_feature_properties(feature).get("dataset_identifier")


def read_remote_tiff_header(url, timeout=DOWNLOAD_TIMEOUT):
    response = requests.get(
        url,
        headers={"Range": f"bytes=0-{TIFF_HEADER_RANGE_SIZE - 1}"},
        timeout=timeout,
    )
    response.raise_for_status()

    if response.status_code != 206:
        raise ValueError(f"Le serveur n'a pas respecte HTTP Range : {response.status_code}")

    return response.content, response.headers


def parse_classic_tiff_size(header):
    endian_tag = header[:2]
    if endian_tag == b"II":
        endian = "<"
    elif endian_tag == b"MM":
        endian = ">"
    else:
        raise ValueError("Signature TIFF inconnue")

    magic = struct.unpack(endian + "H", header[2:4])[0]
    if magic != 42:
        raise ValueError(f"TIFF non gere pour la simulation : magic={magic}")

    ifd_offset = struct.unpack(endian + "I", header[4:8])[0]
    if ifd_offset + 2 > len(header):
        raise ValueError("IFD TIFF hors de l'en-tete lu")

    entry_count = struct.unpack(endian + "H", header[ifd_offset:ifd_offset + 2])[0]
    pos = ifd_offset + 2
    values = {}

    for _ in range(entry_count):
        if pos + 12 > len(header):
            raise ValueError("Entree IFD TIFF hors de l'en-tete lu")

        tag, field_type, count, value_offset = struct.unpack(
            endian + "HHII",
            header[pos:pos + 12],
        )
        pos += 12

        if tag not in (256, 257):
            continue

        if count != 1:
            raise ValueError(f"Tag TIFF {tag} inattendu : count={count}")

        if field_type == 3:
            if endian == "<":
                values[tag] = value_offset & 0xFFFF
            else:
                values[tag] = value_offset >> 16
        elif field_type == 4:
            values[tag] = value_offset
        else:
            raise ValueError(f"Type TIFF non gere pour tag {tag}: {field_type}")

    if 256 not in values or 257 not in values:
        raise ValueError("Largeur/hauteur TIFF introuvables dans l'en-tete")

    return values[256], values[257]


def read_remote_tiff_size(url, timeout=DOWNLOAD_TIMEOUT):
    header, response_headers = read_remote_tiff_header(url, timeout=timeout)
    width, height = parse_classic_tiff_size(header)
    return width, height, response_headers


def simulate_feature_georef(feature, max_rms=GEOREF_MAX_RMS, timeout=DOWNLOAD_TIMEOUT):
    image_id = get_feature_image_id(feature)
    dataset_id = get_feature_dataset_id(feature)

    if not image_id:
        raise ValueError("image_identifier absent")
    if not dataset_id:
        raise ValueError("dataset_identifier absent")

    url = build_url(image_id, dataset_id)
    width, height, headers = read_remote_tiff_size(url, timeout=timeout)
    ring_points = get_exterior_ring_points(feature)
    image_targets = build_image_targets(width, height)
    gcps = build_oriented_footprint_gcps(feature, ring_points, image_targets)
    control_gcps = match_gcps_to_targets(gcps, CONTROL_TARGETS)

    transform_8 = estimate_labeled_transform(
        control_gcps,
        CONTROL_TARGETS,
        estimate_transform,
    )
    transform_4 = estimate_labeled_transform(
        control_gcps,
        CORNER_TARGETS,
        estimate_transform,
    )

    best_transform = transform_8
    if transform_8["rms"] > max_rms and transform_4["rms"] <= max_rms:
        best_transform = transform_4

    georeferenceable = best_transform["rms"] <= max_rms
    first_gcp = gcps[0]

    return {
        "image_id": image_id,
        "dataset_id": dataset_id,
        "url": url,
        "width": width,
        "height": height,
        "content_range": headers.get("Content-Range", ""),
        "orientation_wfs": first_gcp["orientation_wfs"],
        "orientation_north_deg": first_gcp["orientation_north"],
        "try_8_rms_m": transform_8["rms"],
        "try_8_max_error_m": transform_8["max_error"],
        "try_4_rms_m": transform_4["rms"],
        "try_4_max_error_m": transform_4["max_error"],
        "selected_gcp_count": best_transform["gcp_count"],
        "selected_rms_m": best_transform["rms"],
        "selected_max_error_m": best_transform["max_error"],
        "georeferenceable": georeferenceable,
        "error": "",
    }
