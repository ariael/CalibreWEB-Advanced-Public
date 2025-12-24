#!/bin/bash
# Calibre-Web Git Update Script
# Automaticky stáhne nejnovější změny z GitHubu a restartuje službu

set -e  # Ukončit při chybě

SCRIPT_DIR="/opt/calibre-web"
BRANCH="main"
SERVICE_NAME="calibre-web"

echo "🚀 Calibre-Web Update Script"
echo "=============================="
echo ""

# Přejít do adresáře
cd "$SCRIPT_DIR" || exit 1
echo "📁 Working directory: $(pwd)"
echo ""

# Zkontrolovat aktuální stav
echo "📊 Current status:"
git status --short
echo ""

# Stáhnout změny z GitHubu
echo "📥 Fetching updates from GitHub..."
git fetch origin "$BRANCH"
echo ""

# Zobrazit, co se bude měnit
CHANGES=$(git log HEAD..origin/$BRANCH --oneline)
if [ -z "$CHANGES" ]; then
    echo "✅ Already up to date! No changes to pull."
    echo ""
    read -p "Restart service anyway? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "ℹ️  No action taken."
        exit 0
    fi
else
    echo "📝 Changes to be applied:"
    echo "$CHANGES"
    echo ""
    
    # Pull změn
    echo "⬇️  Pulling changes..."
    git pull origin "$BRANCH"
    echo ""
fi

# Restart služby
echo "🔄 Restarting $SERVICE_NAME service..."
sudo systemctl restart "$SERVICE_NAME"

# Zkontrolovat status
sleep 2
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Service restarted successfully!"
    echo ""
    echo "📊 Service status:"
    sudo systemctl status "$SERVICE_NAME" --no-pager -l | head -n 10
else
    echo "❌ Service failed to start!"
    echo ""
    echo "📊 Service status:"
    sudo systemctl status "$SERVICE_NAME" --no-pager -l
    exit 1
fi

echo ""
echo "🎉 Update complete!"
