from osgeo import gdal

from config import GEOTIFF_CREATION_OPTIONS


gdal.UseExceptions()


def write_georeferenced_copy(input_tif, output_tif, geotransform, projection):
    src = gdal.Open(str(input_tif), gdal.GA_ReadOnly)
    if src is None:
        raise ValueError(f"TIFF invalide : {input_tif}")

    driver = gdal.GetDriverByName("GTiff")
    dst = driver.CreateCopy(
        str(output_tif),
        src,
        strict=0,
        options=GEOTIFF_CREATION_OPTIONS,
    )

    if dst is None:
        src = None
        raise RuntimeError(f"Creation GeoTIFF echouee : {output_tif}")

    dst.SetGCPs([], "")
    dst.SetGeoTransform(geotransform)
    dst.SetProjection(projection)

    dst.FlushCache()
    dst = None
    src = None
