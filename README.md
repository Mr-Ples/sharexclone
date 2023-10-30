# sharexclone
## setup
- `cd /path/to/repo`
- `pip install -r requirements.txt`
- `python sharexyz.py`
- for manjaro env var might be needed `export PYSTRAY_BACKEND=gtk`
- AWS credential env vars needed (poke cedric for sharex bucket access) e.g.
```
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export REGION_NAME=eu-central-1
```
- if monitors with different sizes some manual config might be required, ossi is pro with that
## run
- configure your name in the config file `path/to/repo/data/config/sysconfig.json`
- right click the tray icon to see some config options
- initial binds:
  - `WindowsButton + X`: take screenshot
    - Draw the area of where to take screenshot
      - if draw is enabled it will allow you to draw after choosing the area
      - tap `<Right Mouse>` to save the image
      - `<Escape>` to cancel videos and screenshots
      - hold `<Shift>` to draw rectangles
  - `Alt + Z`: take video
    - Draw the area of where to take video
- drag and drop any file onto the local or online history prompt to upload the file instantly
