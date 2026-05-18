from config import DATASET_IDENTIFIERS, EMPRISE_SHAPE_PATH
from core.pipeline_download import (
    fetch_features_for_dataset,
    fetch_features_for_emprise,
    group_features_by_dataset,
    process_dataset,
)


def run_emprise_pipeline(shape_path):
    print(f"Filtre WFS : emprise {shape_path}")
    features = fetch_features_for_emprise(shape_path)
    print(f"Photos dans l'emprise : {len(features)}")

    datasets = group_features_by_dataset(features)
    print(f"Missions a traiter : {len(datasets)}")

    for dataset_id, dataset_features in datasets.items():
        process_dataset(dataset_id, dataset_features)


def run_dataset_pipeline(dataset_identifiers):
    print(f"Filtre WFS : missions {', '.join(dataset_identifiers)}")

    for dataset_id in dataset_identifiers:
        features = fetch_features_for_dataset(dataset_id)
        print(f"Photos WFS trouvees pour {dataset_id} : {len(features)}")
        process_dataset(dataset_id, features)


def main():
    print("=== PIPELINE IGN PVA ===")

    if EMPRISE_SHAPE_PATH:
        run_emprise_pipeline(EMPRISE_SHAPE_PATH)
    else:
        run_dataset_pipeline(DATASET_IDENTIFIERS)


if __name__ == "__main__":
    main()
