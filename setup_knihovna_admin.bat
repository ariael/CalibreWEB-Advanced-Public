@echo off
title Nastaveni Knihovny - ADMINISTRATOR
echo ======================================================
echo   INSTALACNI BALICEK PRO SPRAVCE KNIHOVNY
echo ======================================================
echo.
echo 1. Kontrola pripojeni k Tailscale...
ping -n 1 100.124.78.21 >nul
if errorlevel 1 (
    echo [CHYBA] Server debian neni v siti Tailscale videt.
    echo Ujistete se, ze mate zapnuty Tailscale a prijate sdileni od majitele.
    pause
    exit /b
)

echo 2. Odpojovani starych jednotek (pokud existuji)...
net use Z: /delete /y >nul 2>&1

echo 3. Pripojovani sitoveho disku (Knihovna_Admin)...
net use Z: \\100.124.78.21\Knihovna_Admin Amigo159- /user:ari /persistent:yes

if errorlevel 1 (
    echo [CHYBA] Nepodarilo se pripojit disk. Zkontrolujte Tailscale.
    pause
    exit /b
)

echo.
echo ======================================================
echo   HOTOVO! Disk Z: byl uspesne pripojen.
echo   Nyni v Calibre Desktop zvolte "Prepnout knihovnu"
echo   a vyberte disk Z:\
echo ======================================================
echo.
pause
