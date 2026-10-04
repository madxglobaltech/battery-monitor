#!/bin/bash
set -e

SOURCE="/home/fatboy/battery-monitor/battery-monitor.service"
TARGET="/etc/systemd/system/battery-monitor.service"

echo "Creating systemd symlink..."

sudo ln -sf "$SOURCE" "$TARGET"

echo "Reloading systemd..."
sudo systemctl daemon-reload

echo "Enabling service..."
sudo systemctl enable battery-monitor.service

echo "Starting service..."
sudo systemctl restart battery-monitor.service

echo
echo "Service status:"
sudo systemctl status battery-monitor.service --no-pager
