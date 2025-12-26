@echo off
title Nastaveni Knihovny - CTENAR
echo ======================================================
echo   INSTALACNI BALICEK PRO CTENARE (Jen pro cteni)
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
net use Y: /delete /y >nul 2>&1

echo 3. Pripojovani sitoveho disku (Knihovna_Public)...
net use Y: \\100.124.78.21\Knihovna_Public /persistent:yes

if errorlevel 1 (
    echo [CHYBA] Nepodarilo se pripojit disk.
    pause
    exit /b
)

echo.
echo ======================================================
echo   HOTOVO! Disk Y: byl uspesne pripojen.
echo   Muzete prohlizet knihy v Calibre Desktop na disku Y:\
echo ======================================================
echo.
pause
