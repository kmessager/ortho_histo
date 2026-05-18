@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "ENV_NAME=ortho_histo"

call :find_conda
if errorlevel 1 (
    echo Conda introuvable.
    echo.
    echo Lance d'abord install_env.bat apres avoir installe Miniconda.
    echo https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

pushd "%PROJECT_DIR%"

call "%CONDA_BAT%" activate "%ENV_NAME%"
if errorlevel 1 (
    echo Impossible d'activer l'environnement %ENV_NAME%.
    echo Lance install_env.bat pour le creer ou le mettre a jour.
    popd
    pause
    exit /b 1
)

python -m streamlit run "_application\app_streamlit.py" --server.headless false

if errorlevel 1 (
    echo.
    echo L'application s'est arretee avec une erreur.
    popd
    pause
    exit /b 1
)

popd
endlocal
exit /b 0

:find_conda
set "CONDA_BAT="

where conda >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('where conda 2^>nul') do (
        set "CONDA_EXE=%%I"
        goto :found_conda_exe
    )
)

if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" (
    set "CONDA_BAT=%USERPROFILE%\miniconda3\condabin\conda.bat"
    exit /b 0
)

if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" (
    set "CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat"
    exit /b 0
)

if exist "%ProgramData%\miniconda3\condabin\conda.bat" (
    set "CONDA_BAT=%ProgramData%\miniconda3\condabin\conda.bat"
    exit /b 0
)

if exist "%ProgramData%\anaconda3\condabin\conda.bat" (
    set "CONDA_BAT=%ProgramData%\anaconda3\condabin\conda.bat"
    exit /b 0
)

exit /b 1

:found_conda_exe
for %%I in ("%CONDA_EXE%") do set "CONDA_DIR=%%~dpI"
if exist "%CONDA_DIR%conda.bat" (
    set "CONDA_BAT=%CONDA_DIR%conda.bat"
    exit /b 0
)

for %%I in ("%CONDA_DIR%..") do set "CONDA_ROOT=%%~fI"
if exist "%CONDA_ROOT%\condabin\conda.bat" (
    set "CONDA_BAT=%CONDA_ROOT%\condabin\conda.bat"
    exit /b 0
)

exit /b 1
