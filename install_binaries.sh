#!/bin/bash
# Calibre & Kepubify Installation Script
# Installs necessary binaries for "Embed Metadata" and "Convert to Kepub" features
# Target OS: Debian

set -e

KEPUBIFY_URL="https://github.com/pgaskin/kepubify/releases/latest/download/kepubify-linux-64bit"
CALIBRE_INSTALLER_URL="https://download.calibre-ebook.com/linux-installer.sh"
INSTALL_DIR_CALIBRE="/opt/calibre"
INSTALL_DIR_KEPUBIFY="/opt/kepubify"

# Check for root/sudo
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root or with sudo"
    exit 1
fi

echo "🔧 Installing dependencies..."
apt-get update
# Calibre dependencies (glibc, xdg, etc.) usually handled by installer, but some system libs might be needed
# libgl1 is often needed for Qt plugins in Calibre
# libxcb-cursor0 is explicitly required by recent qt versions in Calibre
apt-get install -y wget python3 xz-utils libgl1 libnss3 libegl1 libopengl0 libxcb-cursor0

echo ""
echo "📚 Installing Calibre..."
# Create directory if it doesn't exist
mkdir -p "$INSTALL_DIR_CALIBRE"

# Run official installer, directing it to isolate the installation to /opt/calibre
# Note: The installer usage for isolated install:
# sudo -v && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sudo sh /dev/stdin install_dir=/opt/calibre isolated=y
wget -nv -O- "$CALIBRE_INSTALLER_URL" | sh /dev/stdin install_dir="$INSTALL_DIR_CALIBRE" isolated=y

echo "   ✅ Calibre installed to $INSTALL_DIR_CALIBRE"

echo ""
echo "📘 Installing Kepubify..."
mkdir -p "$INSTALL_DIR_KEPUBIFY"
cd "$INSTALL_DIR_KEPUBIFY"

echo "   Downloading executable..."
wget -nv -O kepubify-linux-64bit "$KEPUBIFY_URL"

echo "   Setting permissions..."
chmod +x kepubify-linux-64bit

echo "   ✅ Kepubify installed to $INSTALL_DIR_KEPUBIFY/kepubify-linux-64bit"

echo ""
echo "🎉 Installation complete!"
echo "   Calibre path:  $INSTALL_DIR_CALIBRE"
echo "   Kepubify path: $INSTALL_DIR_KEPUBIFY/kepubify-linux-64bit"
echo ""
echo "⚠️  Restart Calibre-Web to detect new binaries!"
