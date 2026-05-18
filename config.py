from pathlib import Path


# ---------------------------------------------------
# IGN PVA
# ---------------------------------------------------

DATASET_IDENTIFIER = "2219-0441"
DATASET_IDENTIFIERS = [
    DATASET_IDENTIFIER,
]

WFS_URL = (
    "https://data.geopf.fr/wfs"
    "?service=WFS"
    "&version=2.0.0"
    "&typeName=pva:image"
    "&request=GetFeature"
    "&outputFormat=application/json"
)

DOWNLOAD_BASE_URL = "https://data.geopf.fr/chunk/telechargement/download/pva"


# ---------------------------------------------------
# COORDINATES
# ---------------------------------------------------

CRS = "EPSG:3857"
EPSG_CODE = 3857


# ---------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------

EMPRISE_SHAPE_PATH = None

DOWNLOAD_MAX_RETRIES = 3
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_RETRY_SLEEP = 5


# ---------------------------------------------------
# GEOREFERENCING
# ---------------------------------------------------

GEOREF_DEBUG = False
GEOREF_OVERWRITE = True
GEOREF_METHOD = "helmert"
GEOREF_OUTPUT_SUFFIX = "_helmert"
GEOREF_MAX_RMS = 20

GEOTIFF_CREATION_OPTIONS = [
    "TILED=YES",
    "COMPRESS=LZW",
    "BIGTIFF=IF_SAFER",
]


# ---------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "_data"
