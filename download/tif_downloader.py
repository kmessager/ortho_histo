from time import sleep

import requests

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

from config import DOWNLOAD_BASE_URL, DOWNLOAD_CHUNK_SIZE, DOWNLOAD_MAX_RETRIES
from config import DOWNLOAD_RETRY_SLEEP, DOWNLOAD_TIMEOUT
from paths import get_images_raw_dir


def build_url(image_id, dataset_id):
    return f"{DOWNLOAD_BASE_URL}/{dataset_id}/{image_id}.tif"


def get_feature_properties(feature):
    return feature.get("properties", {})


def get_feature_image_id(feature):
    return get_feature_properties(feature).get("image_identifier")


def get_feature_dataset_id(feature):
    return get_feature_properties(feature).get("dataset_identifier")


def download_image(
    feature,
    dataset_identifier=None,
    max_retries=DOWNLOAD_MAX_RETRIES,
    timeout=DOWNLOAD_TIMEOUT,
):
    image_id = get_feature_image_id(feature)
    feature_dataset_id = get_feature_dataset_id(feature)

    if not image_id:
        raise ValueError("image_identifier absent")
    if not feature_dataset_id:
        raise ValueError("dataset_identifier absent")

    output_dataset_id = dataset_identifier or feature_dataset_id
    image_dir = get_images_raw_dir(output_dataset_id)
    image_dir.mkdir(parents=True, exist_ok=True)

    output_path = image_dir / f"{image_id}.tif"
    if output_path.exists():
        return output_path, "skipped"

    url = build_url(image_id, feature_dataset_id)
    attempt = 0

    while attempt < max_retries:
        try:
            with requests.get(url, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                with open(output_path, "wb") as output:
                    for chunk in response.iter_content(DOWNLOAD_CHUNK_SIZE):
                        if chunk:
                            output.write(chunk)

            return output_path, "downloaded"

        except (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as exc:
            attempt += 1
            if attempt >= max_retries:
                raise
            print(f"[WARN] {image_id} : erreur {exc}, retry {attempt}/{max_retries}")
            sleep(DOWNLOAD_RETRY_SLEEP)

    raise RuntimeError(f"{image_id} : echec apres {max_retries} tentatives")


def download_images(
    features,
    dataset_identifier=None,
    max_retries=DOWNLOAD_MAX_RETRIES,
    timeout=DOWNLOAD_TIMEOUT,
):
    image_features = [
        feature for feature in features
        if get_feature_image_id(feature) and get_feature_dataset_id(feature)
    ]

    summary = {"downloaded": 0, "skipped": 0, "error": 0}

    for feature in tqdm(image_features, desc="Telechargement", unit="photo"):
        try:
            _, status = download_image(
                feature,
                dataset_identifier=dataset_identifier,
                max_retries=max_retries,
                timeout=timeout,
            )
            summary[status] += 1
        except Exception as exc:
            summary["error"] += 1
            print(f"[ERROR] {get_feature_image_id(feature)} : {exc}")

    return summary
