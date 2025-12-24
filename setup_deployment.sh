#!/bin/bash
# Calibre-Web Deployment Setup Script
# Nastaví alias a sudoers pravidlo pro bezheslovný restart služby

set -e

SCRIPT_DIR="/opt/calibre-web"
SERVICE_NAME="calibre-web"
CURRENT_USER=$(whoami)

echo "🔧 Calibre-Web Deployment Setup"
echo "================================"
echo ""
echo "Current user: $CURRENT_USER"
echo "Script directory: $SCRIPT_DIR"
echo ""

# 1. Nastavit alias v .bashrc
echo "📝 Setting up alias 'cwupdate'..."
ALIAS_LINE="alias cwupdate='cd /opt/calibre-web && ./update_from_git.sh'"

if grep -q "alias cwupdate=" ~/.bashrc; then
    echo "   ℹ️  Alias already exists in ~/.bashrc"
else
    echo "" >> ~/.bashrc
    echo "# Calibre-Web update alias" >> ~/.bashrc
    echo "$ALIAS_LINE" >> ~/.bashrc
    echo "   ✅ Alias added to ~/.bashrc"
fi

# 2. Vytvořit sudoers pravidlo pro bezheslovný restart
echo ""
echo "🔐 Setting up passwordless sudo for service restart..."

SUDOERS_FILE="/etc/sudoers.d/calibre-web-restart"
SUDOERS_CONTENT="# Allow $CURRENT_USER to restart calibre-web without password
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart $SERVICE_NAME
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/systemctl status $SERVICE_NAME
$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/systemctl is-active $SERVICE_NAME"

echo "   Creating sudoers rule..."
echo "$SUDOERS_CONTENT" | sudo tee "$SUDOERS_FILE" > /dev/null
sudo chmod 0440 "$SUDOERS_FILE"

# Ověřit syntaxi sudoers
if sudo visudo -c -f "$SUDOERS_FILE" > /dev/null 2>&1; then
    echo "   ✅ Sudoers rule created successfully"
else
    echo "   ❌ Sudoers syntax error! Removing file..."
    sudo rm -f "$SUDOERS_FILE"
    exit 1
fi

# 3. Načíst nový alias
echo ""
echo "🔄 Reloading bash configuration..."
source ~/.bashrc || true

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 What was configured:"
echo "   • Alias 'cwupdate' added to ~/.bashrc"
echo "   • Passwordless sudo for 'systemctl restart $SERVICE_NAME'"
echo "   • Passwordless sudo for 'systemctl status $SERVICE_NAME'"
echo ""
echo "🚀 Usage:"
echo "   Run 'cwupdate' from anywhere to update Calibre-Web"
echo ""
echo "⚠️  Note: You may need to logout and login again, or run:"
echo "   source ~/.bashrc"
echo ""
