# BBBread

BeagleBone Black - Redis Activity Display, a new way to monitor Control System's most important nodes

## BBB

Requirements:

* Redis database running on port 6379
* BBB Python module (comes with bbb-function)

Installation:

After installing [bbb-function](https://github.com/lnls-sirius/bbb-function) clone this repository in the `/root`  directory and use the following command to install:

```bash
make install
```

Or the following to uninstall:
```bash
make uninstall
```

### Manual Installation

* Install [bbb-function](https://github.com/lnls-sirius/bbb-function)
* Clone this repository in BBB's /root directory

```bash
cd /root && git clone https://github.com/lnls-sirius/bbbread
cd bbbread
```

* Install dependencies
```bash
pip3 install -r requirements.txt
```

* Configure and start systemd service
```
cp bbbread.service /etc/systemd/system
systemctl daemon-reload
systemctl start bbbread
systemctl enable bbbread
```

## The files

* BBBread: project's main Python module.
* BBBread_Server: monitors Redis database for disconnected nodes.
* BBBread_Client: runs on BBBs, pings server's Redis database.

For the UI, visit [PyDM-OPI](https://github.com/lnls-sirius/pydm-opi).

For more information, visit the [Sharepoint Document](https://cnpemcamp.sharepoint.com/sites/iot/SitePages/BBBread.aspx) (requires authentication)

## UI

<img src="Screenshots/main.png" width="400"> <img src="Screenshots/logs_tab.png" width="400"> <img src="Screenshots/logs.png" width="400"> <img src="Screenshots/config.png" width="400"> <img src="Screenshots/info.png" width="400">
