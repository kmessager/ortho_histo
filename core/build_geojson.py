from config import CRS


def build_geojson(features):
    """
    Construit un GeoJSON standard a partir des features WFS.
    """

    return {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {
                "name": CRS,
            },
        },
        "features": features,
    }
