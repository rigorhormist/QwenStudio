#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
app="Qwen Studio.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
MACOSX_DEPLOYMENT_TARGET=14.0 xcrun swiftc native/main.swift -o "$app/Contents/MacOS/QwenStudio" -target arm64-apple-macos14.0 -framework Cocoa -framework WebKit
# Only source assets are bundled. setup.command installs Python into the local data directory.
for component in backend web; do
  mkdir -p "$app/Contents/Resources/$component"
  rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' --exclude '._*' "$component/" "$app/Contents/Resources/$component/"
done
cp setup.command find-python.command requirements.txt "$app/Contents/Resources/"
cp assets/AppIcon.icns "$app/Contents/Resources/AppIcon.icns"
cat > "$app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>QwenStudio</string>
<key>CFBundleIdentifier</key><string>io.github.qwenstudio</string>
<key>CFBundleName</key><string>Qwen Studio</string>
<key>CFBundleDisplayName</key><string>Qwen Studio</string>
<key>CFBundleVersion</key><string>224</string>
<key>CFBundleShortVersionString</key><string>2.2.4</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleIconFile</key><string>AppIcon.icns</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict></plist>
PLIST
codesign --force --sign - "$app"
echo "Built $app. Open the app to check and prepare the environment."
