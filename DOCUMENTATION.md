# Dokumentace projektu CalibreWEB Advanced

Tento dokument obsahuje kompletní technický popis, návod k instalaci a údržbě přizpůsobeného systému Calibre-Web pro portál ebookforum.sk.

## 1. Přehled projektu
Projekt rozšiřuje standardní Calibre-Web o tyto klíčové funkce:
- **Sdílené přihlašování s phpBB**: Uživatelé fóra se mohou přihlásit stejnými údaji.
- **Granulární role (RBAC)**: Nová role "Omezený administrátor".
- **Schvalovací proces**: Noví uživatelé jsou po prvním přihlášení zařazeni na čekací listinu.
- **Library Auditor**: Automatická kontrola zdraví databáze, metadat a integrity souborů v reálném čase.
- **Pokročilé Dashboardy**: Specializované pohledy pro sledování Sérií (Series Tracker) a Autorů.
- **Prémiové téma**: Vlastní CSS motiv "CA Black" inspirovaný vzhledem fóra.

---

## 2. Architektura a integrace

### phpBB Auth Bridge (`cps/phpbb_auth.py`)
Modul zajišťující propojení s databází fóra.
- Používá `bcrypt` pro ověřování hesel phpBB.
- Při prvním úspěšném přihlášení automaticky vytvoří účet v Calibre-Web se statusem "Pending" (Role 0).

### Systém rolí (`cps/roles.py` & `cps/constants.py`)
Standardní bitmasky Calibre-Web byly rozšířeny o:
- **ROLE_LIMITED_ADMIN (1024)**: Umožňuje správu uživatelů, ale skrývá citlivé nastavení systému (Email, Konfigurace DB, Restart atd.).
- **Role 0 (Pending)**: Uživatel má přístup pouze na stránku "Waiting List" (Čekací listina).

### Čekací listina (`cps/approval.py`)
Nový Flask Blueprint, který:
- Zachytává požadavky uživatelů s rolí 0.
- Přesměrovává je na lokalizovanou českou stránku s informací o čekání na schválení.

---

## 3. Instalace na Debian (Produkce)

### Prerekvizity
```bash
sudo apt update && sudo apt install -y python3 python3-venv git cifs-utils python3-mysql.connector python3-bcrypt
```

### Nasazení aplikace
1. Klonování soukromého repozitáře:
   ```bash
   cd /opt
   sudo git clone https://[TOKEN]@github.com/ariael/calibreWEB-Advanced.git calibre-web
   ```
2. Nastavení venv a závislostí:
   ```bash
   cd calibre-web
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install flask-login
   ```

### Síťový disk (Synology)
V souboru `/etc/fstab` musí být tento řádek pro správná práva zápisu:
`//192.168.0.160/knihy_calibre /mnt/calibre_books cifs username=webcalibre,password=[HESLO],uid=1000,gid=1000,file_mode=0664,dir_mode=0775,iocharset=utf8 0 0`

---

## 4. Konfigurace a správa

### Důležité soubory
- `app.db`: Hlavní databáze uživatelů a nastavení (verzováno v gitu).
- `phpbb_config.php`: Konfigurace připojení k MySQL databázi phpBB fóra.
- `cps/static/css/theme.css`: Hlavní soubor pro úpravu barev a vzhledu.

### Správa služby (systemd)
- **Start:** `sudo systemctl start calibre-web`
- **Restart:** `sudo systemctl restart calibre-web`
- **Stav:** `sudo systemctl status calibre-web`
- **Logy:** `sudo journalctl -u calibre-web -f`
- **Cesta (Public):** `\\100.124.78.21\Knihovna_Public`
- **Práva:** Read-Only (jen pro čtení)
- **Poznámka:** Přístup je nastaven jako "Guest", nevyžaduje heslo Samby.

### Automatická instalace (One-click)
Pro maximální zjednodušení jsou v kořenu repozitáře připraveny tyto skripty:
- 🚀 **`setup_knihovna_admin.bat`**: Jedním kliknutím připojí disk **Z:** s právy pro zápis (vhodné pro adminy).
- 🚀 **`setup_knihovna_ctenar.bat`**: Jedním kliknutím připojí disk **Y:** pouze pro čtení (vhodné pro čtenáře).

### Podrobné návody (Balíčky)
Pro jednotlivé role jsem připravil samostatné návody:
- 👑 **[Balíček pro Administrátora (RW)](admin_full_access_guide.md)** - pro hromadné operace.
- 📖 **[Balíček pro Čtenáře (RO)](secondary_user_guide.md)** - pro bezpečné prohlížení.
- 🔐 **[Průvodce Registrací](user_registration_guide.md)** - pro nové uživatele.
- 🚧 **[Plánovaný Vývoj (Roadmap)](ROADMAP.md)** - funkce, na kterých pracujeme.

### Sdílení Tailscale s ostatními uživateli
Aby se druhý uživatel k disku dostal:
1. Majitel Tailscale účtu musí v konzoli u zařízení `debian` kliknout na **Share...**.
2. Vygeneruje odkaz a pošle ho sekundárnímu uživateli.
3. Sekundární uživatel odkaz přijme ve svém Tailscale účtu.

## 5. Bezpečnost a údržba
- **Soukromý repozitář**: Projekt musí zůstat jako "Private" na GitHubu, protože obsahuje citlivá data (`app.db`, `phpbb_config.php`).
- **Aktualizace**:
  1. Proveďte změny na lokálním PC a `git push`.
  2. Na serveru v `/opt/calibre-web` spusťte `git pull`.
  3. Restartujte službu: `sudo systemctl restart calibre-web`.

> [!CAUTION]
> **Nepoužívejte standardní Docker image** (např. od LinuxServer), pokud chcete zachovat tyto úpravy. Standardní image by přepsaly náš upravený kód (`web.py`, `admin.py`, atd.) svou vlastní verzí a znefunkčnily by propojení s phpBB a systém rolí.

---
*Vytvořeno automaticky asistentem Antigravity, prosinec 2025.*
