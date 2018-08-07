* Installation
```bash
git clone https://github.com/leongenius/papirus-tether-control.git

sudo pip3 install -r requirements.txt --system

cp papirus-tether-control.py /usr/local/bin/papirus-tether-control
chmod 755 /usr/local/bin/papirus-tether-control

cp papirus-tether-control.service /etc/systemd/system/

sudo systemctl enable papirus-tether-control
sudo systemctl start papirus-tether-control
```