#!/bin/bash
# Augur 首次打开 —— 解除 macOS 对未签名 app 的下载隔离（只需运行这一次）。
# 双击本文件即可；之后正常双击 Augur 打开。

set -e
echo "──────────────────────────────────────────"
echo "  Augur · 首次打开助手"
echo "──────────────────────────────────────────"
echo ""

# 优先找「应用程序」里的 Augur；否则找与本脚本同目录的 Augur.app
APP="/Applications/Augur.app"
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ ! -d "$APP" ] && [ -d "$HERE/Augur.app" ]; then
  APP="$HERE/Augur.app"
fi

if [ ! -d "$APP" ]; then
  echo "✗ 没找到 Augur.app。"
  echo "  请先把 Augur.app 拖进「应用程序」文件夹，或把它和本脚本放进同一个文件夹，再运行本脚本。"
  echo ""
  read -r -p "按回车键关闭。" _
  exit 1
fi

echo "找到：$APP"
echo "正在解除下载隔离…"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
echo ""
echo "✓ 完成！现在可以正常双击「Augur」打开了。"
echo "  （以后无需再运行本脚本。首次启动需等几秒准备数据，出现 🌱 即正常。）"
echo ""
read -r -p "按回车键关闭。" _
