@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "ENV_NAME=ortho_histo"
set "ENV_FILE=%PROJECT_DIR%environment.yml"

call :find_conda
if errorlevel 1 (
    echo Conda introuvable.
    echo.
    echo Installe Miniconda, puis relance ce script depuis un terminal Windows.
    echo https://docs.conda.io/en/latest/miniconda.html
    echo.
    echo Si Miniconda est deja installe, ouvre "Anaconda Prompt" ou ajoute conda au PATH.
    pause
    exit /b 1
)

if not exist "%ENV_FILE%" (
    echo Fichier environment.yml introuvable :
    echo %ENV_FILE%
    pause
    exit /b 1
)

pushd "%PROJECT_DIR%"

call "%CONDA_BAT%" env list | findstr /R /C:"^%ENV_NAME% " >nul
if errorlevel 1 (
    echo Creation de l'environnement conda %ENV_NAME%...
    call "%CONDA_BAT%" env create -f "%ENV_FILE%"
) else (
    echo Mise a jour de l'environnement conda %ENV_NAME%...
    call "%CONDA_BAT%" env update -n "%ENV_NAME%" -f "%ENV_FILE%" --prune
)

if errorlevel 1 (
    echo.
    echo Installation ou mise a jour de l'environnement echouee.
    popd
    pause
    exit /b 1
)

echo.
echo Environnement pret : %ENV_NAME%
echo Tu peux lancer l'application avec lancer_application.bat

popd
pause
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
