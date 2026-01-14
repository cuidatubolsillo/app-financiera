@echo off
echo ========================================
echo CORRIGIENDO ERROR 500 EN ANALIZAR-PDF
echo ========================================
echo.

cd /d C:\Users\arcad\app_financiera

echo Agregando archivos a git...
git add pdf_analyzer.py
git add app.py
git add CONTEXTO_DESARROLLO_ESTADO_CUENTA.md

echo.
echo Haciendo commit...
git commit -m "fix: Corregir error 500 en analizar-pdf - agregar parametro extraer_movimientos_detallados"

echo.
echo Subiendo a GitHub...
git push origin master

echo.
echo ========================================
echo COMPLETADO!
echo ========================================
pause

