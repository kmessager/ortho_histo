# ortho_histo

Pipeline Python pour recuperer, simuler et georeferencer des prises de vues
aeriennes historiques IGN issues du service WFS `pva:image`.

## Objectif

Le projet propose deux points d'entree qui partagent le meme coeur metier :

- un pipeline batch/debug lance depuis VS Code ou un terminal ;
- une application Streamlit dynamique pilotee par la vue cartographique.

Dans les deux cas, la chaine s'appuie sur les footprints WFS IGN, l'orientation
des cliches et une transformation Helmert stricte. Les TIFF bruts ne sont pas
supposes contenir des GCP internes.

## Structure

```text
ortho_histo/
  config.py
  paths.py
  main.py
  main_georef.py
  environment.yml
  install_env.bat
  lancer_application.bat

  core/
    fetch_wfs.py
    build_geojson.py
    filter_emprise.py
    pipeline_download.py

  download/
    tif_downloader.py

  export/
    footprint_geojson.py

  georef/
    simulation.py
    tiff_gcps.py
    gdal_writer.py
    georef_runner.py
    methods/
      helmert.py

  _application/
    app_streamlit.py

  _data/
    {dataset_id}/
      geojson/
      images/
        raw/
        georef/
      logs/
```

## Configuration Batch

`config.py` contient les valeurs par defaut du mode batch/debug :

```python
DATASET_IDENTIFIER = "2219-0441"
DATASET_IDENTIFIERS = [
    DATASET_IDENTIFIER,
]
```

Pour traiter plusieurs missions depuis VS Code, ajouter les identifiants dans
`DATASET_IDENTIFIERS`.

Le filtrage par emprise shapefile reste possible en mode batch :

```python
EMPRISE_SHAPE_PATH = None
```

Si `EMPRISE_SHAPE_PATH` est renseigne, `main.py` interroge le WFS sur la bbox
de l'emprise, filtre exactement les footprints cote Python, puis regroupe les
photos par `dataset_identifier`.

## Pipeline Batch Telechargement

```powershell
python main.py
```

Ce script :

- utilise `DATASET_IDENTIFIERS` si aucune emprise n'est configuree ;
- utilise `EMPRISE_SHAPE_PATH` si une emprise est configuree ;
- exporte les footprints dans `_data/{dataset_id}/geojson/` ;
- telecharge les TIFF dans `_data/{dataset_id}/images/raw/` ;
- ignore les TIFF deja presents.

## Pipeline Batch Georeferencement

```powershell
python main_georef.py
```

Le seuil RMQ peut etre surcharge ponctuellement sans modifier `config.py` :

```powershell
python main_georef.py --max-rms 25
```

Ce script boucle sur `DATASET_IDENTIFIERS` et appelle le runner commun :

```python
run_georef_batch(dataset_identifier=dataset_id, max_rms=max_rms)
```

Le georeferencement :

- reconstruit les GCP depuis le footprint GeoJSON et la taille pixel du TIFF ;
- recalcule l'orientation nord IGN avec `180 - orientation_wfs` ;
- applique la convention IGN : angle positif horaire, angle negatif
  anti-horaire ;
- teste une Helmert avec 8 points ;
- retombe sur les 4 coins si necessaire ;
- rejette l'image si la RMQ reste superieure au seuil.

Les sorties sont ecrites dans :

```text
_data/{dataset_id}/images/georef/{method}/
_data/{dataset_id}/logs/batch/
```

Les GeoTIFF ne sont pas prefixes par le point d'entree. Un GeoTIFF produit par
le batch ou par l'application a le meme chemin si les parametres metier sont
identiques. La distinction app/batch est portee par les logs avec `run_source`
et `run_id`.

## Application Streamlit

L'application est lancee avec :

```powershell
lancer_application.bat
```

ou :

```powershell
streamlit run _application/app_streamlit.py
```

Elle ne modifie pas `config.py`. Elle utilise la selection dynamique de
l'utilisateur :

1. cadrage de la carte ;
2. selection du seuil RMQ dans le panneau lateral ;
3. clic sur `Filtrer l'emprise` ;
4. interrogation WFS sur la vue courante ou l'emprise dessinee ;
5. selection des missions candidates dans un tableau ;
6. simulation du georeferencement via HTTP Range, sans telecharger les TIFF
   complets ;
7. affichage d'un resume par mission ;
8. export optionnel de la selection et du CSV de simulation ;
9. export des footprints et telechargement des images retenues ;
10. georeferencement des images selectionnees uniquement avec le meme seuil RMQ.

Le bouton de georeferencement de l'application appelle :

```python
run_georef_batch(dataset_identifier=dataset_id, image_ids=image_ids, max_rms=max_rms)
```

Donc l'application ne depend pas de `DATASET_IDENTIFIER`.

Les logs de l'application sont ecrits dans :

```text
_data/{dataset_id}/logs/app/
```

## Simulation Avant Telechargement

`georef/simulation.py` lit uniquement l'en-tete TIFF distant avec HTTP Range
pour obtenir `width` et `height`. La simulation utilise ensuite :

- footprint WFS ;
- orientation WFS ;
- taille pixel ;
- Helmert 8 points puis 4 coins.

Si aucune tentative ne passe le seuil RMQ choisi, l'image n'est pas proposee au
telechargement dans l'application. En mode batch, le seuil vient de
`GEOREF_MAX_RMS`, sauf surcharge par `python main_georef.py --max-rms ...`.

## Environnement

Le projet est prevu pour etre deplace sur un autre poste Windows a condition
que Miniconda ou Anaconda soit installe.

Installation de l'environnement :

```powershell
install_env.bat
```

Ce script :

- cherche `conda` dans le PATH et dans les emplacements Miniconda/Anaconda
  courants ;
- cree l'environnement `ortho_histo` depuis `environment.yml` s'il n'existe
  pas ;
- met l'environnement a jour s'il existe deja.

Lancement de l'application :

```powershell
lancer_application.bat
```

Ce script :

- cherche `conda` ;
- active l'environnement `ortho_histo` ;
- lance Streamlit sur `_application/app_streamlit.py`.

Creation manuelle equivalente :

```text
conda env create -f environment.yml
conda activate ortho_histo
```

GDAL vient de conda/miniconda. Ne pas installer GDAL via `pip`.
