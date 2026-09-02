@echo off
title Loop PDF Replace All - Build EXE
echo.
echo ==================================================
echo       LOOP STRUCTURAL AUTOMATION
echo       PDF REPLACE ALL - EXE BUILDER
echo ==================================================
echo.
echo Checking installed packages...
echo.

py -c "import fitz; print('PyMuPDF:', fitz.__doc__.split()[1] if fitz.__doc__ else 'installed')" || goto :missing
py -c "import PyInstaller; print('PyInstaller:', PyInstaller.__version__)" || goto :missing

echo.
echo Building branded application...
echo.

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Loop_PDF_Replace_All.spec del /q Loop_PDF_Replace_All.spec

py -m PyInstaller --onefile --windowed --name "Loop_PDF_Replace_All" --add-data "loop_logo.png;." loop_pdf_replace_all.py

if errorlevel 1 goto :error

echo.
echo ==================================================
echo SUCCESS!
echo.
echo Your application is:
echo.
echo   dist\Loop_PDF_Replace_All.exe
echo.
echo You can copy this EXE to your Desktop and run it
echo without Python on the target computer.
echo ==================================================
echo.
pause
exit /b 0

:missing
echo.
echo ERROR: PyMuPDF or PyInstaller is not installed.
echo.
echo Try:
echo   py -m pip install PyMuPDF pyinstaller
echo.
pause
exit /b 1

:error
echo.
echo BUILD FAILED. Please send the error shown above.
echo.
pause
exit /b 1
