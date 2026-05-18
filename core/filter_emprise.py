import json
from pathlib import Path

from config import EPSG_CODE


def _get_target_srs():
    from osgeo import osr

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(EPSG_CODE)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def _normalize_srs(srs):
    from osgeo import osr

    if srs is None:
        return None

    srs = srs.Clone()
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def _union_layer_geometries(layer, target_srs):
    from osgeo import osr

    layer_srs = _normalize_srs(layer.GetSpatialRef())
    if layer_srs is None:
        layer_name = layer.GetName()
        raise ValueError(
            f"Projection introuvable pour la couche d'emprise : {layer_name}. "
            "Le shapefile doit fournir un fichier .prj lisible."
        )

    transform = None

    if not layer_srs.IsSame(target_srs):
        transform = osr.CoordinateTransformation(layer_srs, target_srs)

    geometries = []

    for feature in layer:
        geometry = feature.GetGeometryRef()
        if geometry is None or geometry.IsEmpty():
            continue

        geometry = geometry.Clone()
        if transform is not None:
            geometry.Transform(transform)

        geometries.append(geometry)

    if not geometries:
        return None

    union = geometries[0]
    for geometry in geometries[1:]:
        union = union.Union(geometry)

    return union


def read_emprise_geometry(shape_path):
    from osgeo import ogr

    ogr.UseExceptions()

    path = Path(shape_path)
    if not path.exists():
        raise FileNotFoundError(f"Emprise introuvable : {path}")

    datasource = ogr.Open(str(path))
    if datasource is None:
        raise ValueError(f"Emprise illisible : {path}")

    target_srs = _get_target_srs()
    union = None

    for layer_index in range(datasource.GetLayerCount()):
        layer = datasource.GetLayerByIndex(layer_index)
        layer_union = _union_layer_geometries(layer, target_srs)
        if layer_union is None:
            continue

        if union is None:
            union = layer_union
        else:
            union = union.Union(layer_union)

    datasource = None

    if union is None or union.IsEmpty():
        raise ValueError(f"Emprise sans geometrie exploitable : {path}")

    return union


def get_emprise_bbox(emprise_geometry):
    min_x, max_x, min_y, max_y = emprise_geometry.GetEnvelope()
    return min_x, min_y, max_x, max_y


def feature_intersects_emprise(feature, emprise_geometry):
    from osgeo import ogr

    geometry_json = feature.get("geometry")
    if not geometry_json:
        return False

    geometry = ogr.CreateGeometryFromJson(json.dumps(geometry_json))
    if geometry is None or geometry.IsEmpty():
        return False

    return geometry.Intersects(emprise_geometry)


def filter_features_by_emprise(features, shape_path=None, emprise_geometry=None):
    if emprise_geometry is None and not shape_path:
        return features

    if emprise_geometry is None:
        emprise_geometry = read_emprise_geometry(shape_path)

    return [
        feature
        for feature in features
        if feature_intersects_emprise(feature, emprise_geometry)
    ]
