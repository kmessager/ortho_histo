# ortho_histo

Pipeline Python permettant de récupérer, simuler et géoréférencer des prises de vues aériennes historiques IGN issues du service WFS `pva:image`.

---

# Fonctionnalités

Le projet propose deux modes d'utilisation partageant le même cœur métier :

- **Mode batch/debug** lancé depuis VS Code ou un terminal ;
- **Application Streamlit interactive** pilotée par une vue cartographique.

Dans les deux cas, la chaîne de traitement s'appuie sur :

- les footprints WFS IGN ;
- l’orientation des clichés ;
- une transformation Helmert stricte ;
- des TIFF bruts ne contenant pas de GCP internes.

---

# Structure du projet

```text
ortho_histo/
│
├── config.py
├── paths.py
├── main.py
├── main_georef.py
├── environment.yml
├── install_env.bat
├── lancer_application.bat
│
├── core/
│   ├── fetch_wfs.py
│   ├── build_geojson.py
│   ├── filter_emprise.py
│   └── pipeline_download.py
│
├── download/
│   └── tif_downloader.py
│
├── export/
│   └── footprint_geojson.py
│
├── georef/
│   ├── simulation.py
│   ├── tiff_gcps.py
│   ├── gdal_writer.py
│   ├── georef_runner.py
│   └── methods/
│       └── helmert.py
│
├── _application/
│   └── app_streamlit.py
│
└── _data/
    └── {dataset_id}/
        ├── geojson/
        ├── images/
        │   ├── raw/
        │   └── georef/
        └── logs/
```

---

# Configuration du mode batch

Le fichier `config.py` contient les valeurs par défaut du mode batch/debug :

```python
DATASET_IDENTIFIER = "2219-0441"

DATASET_IDENTIFIERS = [
    DATASET_IDENTIFIER,
]
```

Pour traiter plusieurs missions depuis VS Code :

```python
DATASET_IDENTIFIERS = [
    "2219-0441",
    "XXXX-XXXX",
]
```

Le filtrage par emprise shapefile reste possible :

```python
EMPRISE_SHAPE_PATH = None
```

Si `EMPRISE_SHAPE_PATH` est renseigné :

- `main.py` interroge le WFS sur la bbox de l’emprise ;
- les footprints sont filtrés côté Python ;
- les photos sont regroupées par `dataset_identifier`.

---

# Pipeline batch — téléchargement

## Lancement

```powershell
python main.py
```

## Fonctionnement

Le script :

- utilise `DATASET_IDENTIFIERS` si aucune emprise n’est configurée ;
- utilise `EMPRISE_SHAPE_PATH` si une emprise est définie ;
- exporte les footprints dans :

```text
_data/{dataset_id}/geojson/
```

- télécharge les TIFF dans :

```text
_data/{dataset_id}/images/raw/
```

- ignore automatiquement les TIFF déjà présents.

---

# Pipeline batch — géoréférencement

## Lancement

```powershell
python main_georef.py
```

## Surcharge ponctuelle du seuil RMS

```powershell
python main_georef.py --max-rms 25
```

## Fonctionnement

Le script boucle sur `DATASET_IDENTIFIERS` et appelle :

```python
run_georef_batch(
    dataset_identifier=dataset_id,
    max_rms=max_rms
)
```

Le géoréférencement :

- reconstruit les GCP depuis le footprint GeoJSON ;
- utilise la taille pixel du TIFF ;
- recalcule l’orientation nord IGN avec :

```python
180 - orientation_wfs
```

- applique la convention IGN :
  - angle positif = horaire ;
  - angle négatif = anti-horaire ;
- teste une Helmert avec 8 points ;
- retombe sur les 4 coins si nécessaire ;
- rejette l’image si la RMS reste supérieure au seuil.

## Sorties

```text
_data/{dataset_id}/images/georef/{method}/
_data/{dataset_id}/logs/batch/
```

Les GeoTIFF ne sont pas préfixés selon le point d’entrée.

Ainsi :

- un GeoTIFF produit par le batch ;
- ou un GeoTIFF produit par l’application

auront exactement le même chemin si les paramètres métier sont identiques.

La distinction batch/app est portée uniquement par les logs via :

- `run_source`
- `run_id`

---

# Application Streamlit

## Lancement

### Via le script batch

```powershell
lancer_application.bat
```

### Ou directement

```powershell
streamlit run _application/app_streamlit.py
```

---

# Workflow de l’application

L’application ne modifie pas `config.py`.

Elle repose entièrement sur la sélection dynamique de l’utilisateur :

1. cadrage de la carte ;
2. sélection du seuil RMS ;
3. clic sur **Filtrer l’emprise** ;
4. interrogation WFS sur :
   - la vue courante ;
   - ou l’emprise dessinée ;
5. sélection des missions candidates ;
6. simulation du géoréférencement via HTTP Range ;
7. affichage d’un résumé par mission ;
8. export optionnel :
   - de la sélection ;
   - du CSV de simulation ;
9. export des footprints ;
10. téléchargement des images retenues ;
11. géoréférencement des images sélectionnées uniquement.

Le bouton de géoréférencement appelle :

```python
run_georef_batch(
    dataset_identifier=dataset_id,
    image_ids=image_ids,
    max_rms=max_rms
)
```

L’application ne dépend donc pas de `DATASET_IDENTIFIER`.

## Logs application

```text
_data/{dataset_id}/logs/app/
```

---

# Simulation avant téléchargement

Le module :

```text
georef/simulation.py
```

lit uniquement l’en-tête TIFF distant via HTTP Range afin de récupérer :

- `width`
- `height`

La simulation utilise ensuite :

- le footprint WFS ;
- l’orientation WFS ;
- la taille pixel ;
- Helmert 8 points puis 4 coins.

Si aucune tentative ne respecte le seuil RMS choisi :

- l’image n’est pas proposée au téléchargement dans l’application.

En mode batch :

- le seuil vient de `GEOREF_MAX_RMS` ;
- sauf surcharge via :

```powershell
python main_georef.py --max-rms ...
```

---

# Installation de l’environnement

Le projet est prévu pour être déplacé sur un autre poste Windows disposant de :

- Miniconda ;
- ou Anaconda.

## Installation automatique

```powershell
install_env.bat
```

Ce script :

- cherche `conda` dans le PATH ;
- détecte automatiquement Miniconda/Anaconda ;
- crée l’environnement `ortho_histo` si nécessaire ;
- met à jour l’environnement s’il existe déjà.

---

# Lancement de l’application

```powershell
lancer_application.bat
```

Ce script :

- détecte `conda` ;
- active l’environnement `ortho_histo` ;
- lance Streamlit.

---

# Installation manuelle équivalente

```powershell
conda env create -f environment.yml

conda activate ortho_histo
```

---

# Notes importantes

- GDAL provient de Conda/Miniconda ;
- ne pas installer GDAL via `pip`.
