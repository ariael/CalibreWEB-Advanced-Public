# Calibre-Web Deployment Guide

## 🚀 Jednorázová instalace na Debian serveru

### 1. Opravit Git oprávnění
```bash
sudo chown -R ari:ari /opt/calibre-web/.git
```

### 2. Stáhnout nejnovější změny
```bash
cd /opt/calibre-web
git pull origin main
```

### 3. Spustit setup skript
```bash
cd /opt/calibre-web
chmod +x setup_deployment.sh update_from_git.sh
./setup_deployment.sh
```

### 4. Instalace binárek (Calibre + Kepubify)
Potřebné pro konverzi a embed metadat:
```bash
sudo chmod +x install_binaries.sh
sudo ./install_binaries.sh
```

### 5. Načíst novou konfiguraci
```bash
source ~/.bashrc
```

## ✨ Použití

Po instalaci stačí spustit odkudkoliv:

```bash
cwupdate
```

**Skript automaticky:**
- ✅ Stáhne změny z GitHubu
- ✅ Zobrazí, co se změnilo
- ✅ Restartuje službu **BEZ zadávání hesla**
- ✅ Ověří, že služba běží

## 📝 Workflow pro vývoj

### Na Windows (lokální změny):
```powershell
cd C:\GitHub\CalibreWEB\repo
# Upravte soubory...
git add .
git commit -m "Popis změn"
git push origin main
```

### Na Debian serveru (deployment):
```bash
cwupdate
```

Hotovo! 🎉

## 🔧 Co bylo nakonfigurováno

### Bash alias
V `~/.bashrc` byl přidán:
```bash
alias cwupdate='cd /opt/calibre-web && ./update_from_git.sh'
```

### Sudoers pravidlo
V `/etc/sudoers.d/calibre-web-restart`:
```
ari ALL=(ALL) NOPASSWD: /bin/systemctl restart calibre-web
ari ALL=(ALL) NOPASSWD: /bin/systemctl status calibre-web
ari ALL=(ALL) NOPASSWD: /bin/systemctl is-active calibre-web
```

Toto umožňuje restartovat službu bez zadávání hesla.

## 🐛 Řešení problémů

### Alias nefunguje
```bash
source ~/.bashrc
```

### Git pull selhává kvůli oprávněním
```bash
sudo chown -R ari:ari /opt/calibre-web/.git
```

### Služba se nerestartuje
```bash
sudo systemctl status calibre-web
journalctl -u calibre-web -n 50
```
