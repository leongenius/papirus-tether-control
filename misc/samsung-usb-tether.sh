#!/usr/bin/env bash
## Installation target: /usr/local/bin/samsung-usb-tether.sh
INTERFACE=${1}
/sbin/ifconfig ${INTERFACE} down
/usr/bin/macchanger -a ${INTERFACE}
/bin/sleep 2
exec /bin/systemctl --no-block start $(systemd-escape --template ifup@.service ${INTERFACE})
