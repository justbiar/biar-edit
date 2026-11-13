#!/bin/bash
# Builds biar-edit.app (default: on the Desktop). The app starts the server from this project folder.
set -e
cd "$(dirname "$0")/.."
APP="${1:-$HOME/Desktop/biar-edit.app}"
ROOT="$(pwd)"
rm -rf "$APP"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -o "$APP/Contents/MacOS/biar-edit" mac/main.swift -framework Cocoa -framework WebKit
cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>biar-edit</string>
<key>CFBundleIdentifier</key><string>dev.biar.edit</string>
<key>CFBundleExecutable</key><string>biar-edit</string>
<key>CFBundleIconFile</key><string>biar-edit</string>
<key>BiarRoot</key><string>$ROOT</string>
<key>CFBundleURLTypes</key><array><dict><key>CFBundleURLName</key><string>dev.biar.edit</string><key>CFBundleURLSchemes</key><array><string>biaredit</string></array></dict></array>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>LSMinimumSystemVersion</key><string>13.0</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict></plist>
PL
cp mac/biar-edit.icns "$APP/Contents/Resources/biar-edit.icns"
codesign --force --sign - "$APP" >/dev/null 2>&1 || true
echo "built $APP"
