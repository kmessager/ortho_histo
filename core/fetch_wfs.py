import requests

from config import CRS, WFS_URL


def format_bbox_filter(bbox):
    min_x, min_y, max_x, max_y = bbox
    return f"{min_x},{min_y},{max_x},{max_y},{CRS}"


def fetch_features(bbox=None, dataset_identifier=None):
    """
    Recupere les features WFS pva:image avec filtrage serveur.
    """

    url = WFS_URL

    if bbox is not None:
        url += f"&bbox={format_bbox_filter(bbox)}"
    elif dataset_identifier:
        url += f"&CQL_FILTER=dataset_identifier='{dataset_identifier}'"

    response = requests.get(url)
    response.raise_for_status()

    data = response.json()

    return data.get("features", [])
