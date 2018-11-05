* Installation
  * common
    ```bash
    git clone https://github.com/leongenius/papirus-tether-control.git
    
    sudo pip3 install -r requirements.txt --system
    
    cp papirus-tether-control.py /usr/local/bin/papirus-tether-control
    chmod 755 /usr/local/bin/papirus-tether-control
    
    cp papirus-tether-control.service /etc/systemd/system/
    ```

  * Customization - interfaces
    Edit `/etc/systemd/system/papirus-tether-control.service` with a list of desired interface
    names in `ExecStart` line.

  * Special - for Samsung devices
    ```bash
    sudo cp misc/73-samsung-usb-net.rules /etc/udev/rules.d/
    sudo cp misc/samsung-usb-tether.sh /usr/local/bin/
    ```

* Enable and start as a service
```bash
sudo systemctl enable papirus-tether-control
sudo systemctl start papirus-tether-control
```