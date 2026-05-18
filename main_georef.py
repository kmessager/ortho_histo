import argparse

from config import DATASET_IDENTIFIERS, GEOREF_DEBUG, GEOREF_MAX_RMS, GEOREF_OVERWRITE
from georef.georef_runner import run_georef_batch


def parse_args():
    parser = argparse.ArgumentParser(
        description="Georeference les missions IGN PVA configurees.",
    )
    parser.add_argument(
        "--max-rms",
        type=float,
        default=GEOREF_MAX_RMS,
        help=f"Seuil RMQ maximum en metres (defaut config.py: {GEOREF_MAX_RMS}).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    for dataset_id in DATASET_IDENTIFIERS:
        run_georef_batch(
            debug=GEOREF_DEBUG,
            overwrite=GEOREF_OVERWRITE,
            dataset_identifier=dataset_id,
            max_rms=args.max_rms,
        )


if __name__ == "__main__":
    main()
