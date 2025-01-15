#!/bin/bash

# Helper function to check and append a line to a file without Python
function append_if_missing() {
  FILE="$1"
  LINE="$2"

  if [ -f "$FILE" ]; then
    grep -qxF "$LINE" "$FILE" || echo "$LINE" >> "$FILE"
  fi
}

# Function to switch to AP mode
function switch_to_ap() {
  echo "Switching to AP mode..."
  local update_needed=0

  # 检查 hostapd 是否已安装
  if ! dpkg -l | grep -qw hostapd; then
    update_needed=1
  fi

  # 检查 dnsmasq 是否已安装
  if ! dpkg -l | grep -qw dnsmasq; then
    update_needed=1
  fi

  # 检查 isc-dhcp-client 是否已安装
  if ! dpkg -l | grep -qw isc-dhcp-client; then
    update_needed=1
  fi

  # 如果有任何包未安装，则先更新 apt
  if [ "$update_needed" -eq 1 ]; then
    echo "Updating package lists..."
    sudo apt update
  fi

  # 根据需要安装各个包
  if ! dpkg -l | grep -qw hostapd; then
    echo "Installing hostapd..."
    sudo apt install -y hostapd
  fi
  if ! dpkg -l | grep -qw dnsmasq; then
    echo "Installing dnsmasq..."
    sudo apt install -y dnsmasq
  fi
  if ! dpkg -l | grep -qw isc-dhcp-client; then
    echo "Installing isc-dhcp-client..."
    sudo apt install -y isc-dhcp-client
  fi


  # Configure hostapd
  cat <<EOL | sudo tee /etc/hostapd/hostapd.conf
interface=wlan0
driver=nl80211
ssid=Zero3AP
hw_mode=g
channel=6
wpa=2
wpa_passphrase=123456789
EOL

  # Update /etc/default/hostapd
  append_if_missing "/etc/default/hostapd" 'DAEMON_CONF="/etc/hostapd/hostapd.conf"'

  sudo systemctl unmask hostapd

  # Configure dnsmasq
  append_if_missing "/etc/dnsmasq.conf" "interface=wlan0"
  append_if_missing "/etc/dnsmasq.conf" "dhcp-range=192.168.111.50,192.168.111.150,24h"

  # Stop and disable systemd-resolved if running
  sudo systemctl stop systemd-resolved
  sudo systemctl disable systemd-resolved

  # Update /etc/resolv.conf
  sudo rm -f /etc/resolv.conf
  echo -e "nameserver 223.5.5.5\nnameserver 119.29.29.29\nnameserver 8.8.8.8" | sudo tee /etc/resolv.conf

  # Restart dnsmasq
  sudo systemctl restart dnsmasq

  # Configure network
  if ! ip addr show wlan0 | grep -q "192.168.111.1/24"; then
    # If not, add the IP address
    sudo ip addr add 192.168.111.1/24 dev wlan0
  fi
  sudo ip link set dev wlan0 up

  # Start hostapd and dnsmasq
  sudo systemctl restart hostapd
  sudo systemctl start dnsmasq

  echo "Switched to AP mode."
}

# Function to switch to STA mode
function switch_to_sta() {
#  echo "Switching to STA mode..."
  if iw dev wlan0 info | grep -q 'type managed'; then
    return
  fi

  sudo systemctl stop hostapd
  sudo iw wlan0 set type station

  # Change wlan0 to station mode
  if ! iw dev wlan0 info | grep -q 'type managed'; then
    sudo ip link set wlan0 down
    sudo ip link set wlan0 up
    sudo iw wlan0 set type station
  fi

  if ! iw dev wlan0 info | grep -q 'type managed'; then
    echo "STA ERROR"
  fi

  # Start wpa_supplicant and acquire IP
#  sudo wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
#  sudo dhclient wlan0

  echo "Switched to STA mode."
}

# Main script
if [[ "$1" == "ap" ]]; then
  switch_to_ap
elif [[ "$1" == "sta" ]]; then
  switch_to_sta
else
  echo "Usage: $0 [ap|sta]"
  exit 1
fi
