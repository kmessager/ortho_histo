import json
import math

from osgeo import gdal

from config import CRS
from paths import get_footprint_path


gdal.UseExceptions()


CONTROL_TARGETS = (
    "UL",
    "UM",
    "UR",
    "RM",
    "DR",
    "BM",
    "DL",
    "LM",
)


def distance_sq(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def get_dataset_identifier_from_tif_path(tif_path):
    parts = list(tif_path.parts)
    try:
        images_index = parts.index("images")
    except ValueError as exc:
        raise ValueError(f"Chemin TIFF inattendu : {tif_path}") from exc

    if images_index < 1:
        raise ValueError(f"Dataset introuvable dans le chemin : {tif_path}")

    return parts[images_index - 1]


def read_image_size(tif_path):
    ds = gdal.Open(str(tif_path), gdal.GA_ReadOnly)
    if ds is None:
        raise ValueError(f"TIFF invalide : {tif_path}")

    width = ds.RasterXSize
    height = ds.RasterYSize
    ds = None

    return width, height


def get_image_id(tif_path):
    return tif_path.stem


def load_footprint_feature(tif_path):
    dataset_identifier = get_dataset_identifier_from_tif_path(tif_path)
    footprint_path = get_footprint_path(dataset_identifier)

    if not footprint_path.exists():
        raise FileNotFoundError(f"Footprint GeoJSON introuvable : {footprint_path}")

    with open(footprint_path, "r", encoding="utf-8") as geojson_file:
        geojson = json.load(geojson_file)

    image_id = get_image_id(tif_path)

    for feature in geojson.get("features", []):
        properties = feature.get("properties", {})
        if properties.get("image_identifier") == image_id:
            return feature

    raise ValueError(f"Footprint introuvable pour l'image : {image_id}")


def get_exterior_ring_points(feature):
    geometry = feature.get("geometry") or {}
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geometry_type == "Polygon":
        ring = coordinates[0]
    elif geometry_type == "MultiPolygon":
        ring = coordinates[0][0]
    else:
        raise ValueError(f"Geometrie footprint non supportee : {geometry_type}")

    if len(ring) >= 2 and ring[0] == ring[-1]:
        ring = ring[:-1]

    if len(ring) != len(CONTROL_TARGETS):
        raise ValueError(
            f"Footprint attendu avec 8 sommets, recu {len(ring)} sommets"
        )

    return [(float(point[0]), float(point[1])) for point in ring]


def angle_north_clockwise(a, b):
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    angle = math.degrees(math.atan2(dx, dy))
    if angle < 0:
        angle += 360
    return angle


def angular_delta(a, b):
    return abs((a - b + 180) % 360 - 180)


def build_image_targets(width, height):
    max_pixel = float(width - 1)
    max_line = float(height - 1)
    mid_pixel = max_pixel / 2
    mid_line = max_line / 2

    return {
        "UL": (0.0, 0.0),
        "UM": (mid_pixel, 0.0),
        "UR": (max_pixel, 0.0),
        "RM": (max_pixel, mid_line),
        "DR": (max_pixel, max_line),
        "BM": (mid_pixel, max_line),
        "DL": (0.0, max_line),
        "LM": (0.0, mid_line),
    }


def rotate_image_point_by_ign_angle(point, center, angle_deg):
    """Rotate an image point using the IGN north-orientation convention.

    In image coordinates, pixel X goes right and line Y goes down.
    A positive IGN angle is clockwise; a negative angle is counter-clockwise.
    """
    angle = math.radians(angle_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    x = point[0] - center[0]
    y = point[1] - center[1]

    return (
        center[0] + x * cos_a - y * sin_a,
        center[1] + x * sin_a + y * cos_a,
    )


def normalize_signed_angle(angle):
    angle = float(angle)
    while angle > 180.0:
        angle -= 360.0
    while angle <= -180.0:
        angle += 360.0
    return angle


def get_feature_wfs_orientation(feature):
    orientation = feature.get("properties", {}).get("orientation")
    if orientation is None:
        raise ValueError("Orientation absente du footprint")

    return float(orientation) % 360


def recalculate_north_orientation(wfs_orientation):
    return normalize_signed_angle(180.0 - float(wfs_orientation))


def get_feature_north_orientation(feature):
    return recalculate_north_orientation(get_feature_wfs_orientation(feature))


def label_rotated_image_points(image_targets, orientation_north):
    center = image_targets["BM"][0], image_targets["RM"][1]
    rotated = {
        label: rotate_image_point_by_ign_angle(pixel, center, orientation_north)
        for label, pixel in image_targets.items()
    }

    sorted_by_y = sorted(rotated, key=lambda label: rotated[label][1])
    top = sorted(sorted_by_y[:3], key=lambda label: rotated[label][0])
    middle = sorted(sorted_by_y[3:5], key=lambda label: rotated[label][0])
    bottom = sorted(sorted_by_y[5:], key=lambda label: rotated[label][0])

    return {
        "UL": top[0],
        "UM": top[1],
        "UR": top[2],
        "LM": middle[0],
        "RM": middle[1],
        "DL": bottom[0],
        "BM": bottom[1],
        "DR": bottom[2],
    }


def build_oriented_footprint_gcps(feature, ring_points, image_targets):
    wfs_orientation = get_feature_wfs_orientation(feature)
    north_orientation = recalculate_north_orientation(wfs_orientation)
    source_label_by_oriented_label = label_rotated_image_points(
        image_targets,
        north_orientation,
    )

    return [
        {
            "label": oriented_label,
            "source_label": source_label_by_oriented_label[oriented_label],
            "pixel": image_targets[source_label_by_oriented_label[oriented_label]],
            "geo": ring_points[index],
            "orientation_wfs": wfs_orientation,
            "orientation_north": north_orientation,
        }
        for index, oriented_label in enumerate(CONTROL_TARGETS)
    ]


def read_footprint_gcp_candidates(tif_path):
    feature = load_footprint_feature(tif_path)
    ring_points = get_exterior_ring_points(feature)
    width, height = read_image_size(tif_path)
    image_targets = build_image_targets(width, height)
    gcps = build_oriented_footprint_gcps(feature, ring_points, image_targets)

    return [gcps], CRS


def build_control_targets(gcps):
    pixels = [gcp["pixel"] for gcp in gcps]
    min_pixel = min(pixel[0] for pixel in pixels)
    max_pixel = max(pixel[0] for pixel in pixels)
    min_line = min(pixel[1] for pixel in pixels)
    max_line = max(pixel[1] for pixel in pixels)
    mid_pixel = (min_pixel + max_pixel) / 2
    mid_line = (min_line + max_line) / 2

    return {
        "UL": (min_pixel, min_line),
        "UM": (mid_pixel, min_line),
        "UR": (max_pixel, min_line),
        "RM": (max_pixel, mid_line),
        "DR": (max_pixel, max_line),
        "BM": (mid_pixel, max_line),
        "DL": (min_pixel, max_line),
        "LM": (min_pixel, mid_line),
    }


def match_gcps_to_targets(gcps, labels):
    targets = build_control_targets(gcps)
    selected = {}
    remaining = list(gcps)

    for label in labels:
        target = targets[label]
        gcp = min(remaining, key=lambda item: distance_sq(item["pixel"], target))
        selected[label] = gcp
        remaining.remove(gcp)

    return selected
