@echo off
echo ================================================
echo Abriendo puerto 5000 en el Firewall de Windows
echo ================================================
echo.
echo IMPORTANTE: Este script debe ejecutarse como Administrador
echo.
pause

netsh advfirewall firewall add rule name="Flask App Puerto 5000" dir=in action=allow protocol=TCP localport=5000

if %errorlevel% == 0 (
    echo.
    echo ================================================
    echo PUERTO 5000 ABIERTO EXITOSAMENTE
    echo ================================================
    echo.
    echo Ya puedes acceder a la aplicacion desde tu celular
    echo usando la IP local de tu computadora.
    echo.
) else (
    echo.
    echo ================================================
    echo ERROR: No se pudo abrir el puerto
    echo ================================================
    echo.
    echo Posibles causas:
    echo - El script no se ejecuto como Administrador
    echo - El puerto ya esta abierto
    echo.
)

pause

