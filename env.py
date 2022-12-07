# -*- coding: utf-8 -*-
import base64
import datetime
import enum
import json
import os
import subprocess
import traceback

import binaries

try:
    import tkinter as tk
except:
    raise Exception("Please install Tkinter with command: sudo apt-get install python3-tk")

HOME = os.path.abspath(".")
print(HOME)
if not os.path.isdir(HOME):
    os.mkdir(HOME)

DATA_PATH = os.path.join(HOME, 'data')
if not os.path.isdir(DATA_PATH):
    os.mkdir(DATA_PATH)

UPLOADS_DIR = os.path.join(DATA_PATH, 'uploads')
if not os.path.isdir(UPLOADS_DIR):
    os.mkdir(UPLOADS_DIR)

CONFIG_PATH = os.path.join(DATA_PATH, 'config')
if not os.path.isdir(CONFIG_PATH):
    os.mkdir(CONFIG_PATH)

LOGS_SESSION = datetime.datetime.now().replace(microsecond=0)
LOGS_PATH = os.path.join(HOME, 'logs')
if not os.path.isdir(LOGS_PATH):
    os.mkdir(LOGS_PATH)

SOUNDS_DIR = os.path.join(DATA_PATH, 'sounds')
if not os.path.isdir(SOUNDS_DIR):
    os.mkdir(SOUNDS_DIR)

CONFIG_TEMPLATE = {
    "global":  {
        "nvidia_disable_flipping": "ask"
    },
    "input":   {
        "audio_alsa_source":                  "default",
        "audio_backend":                      "pulseaudio",
        "audio_enabled":                      "false",
        "audio_jack_connect_system_capture":  "true",
        "audio_jack_connect_system_playback": "false",
        "audio_pulseaudio_source":            "alsa_output.pci-0000_26_00.1.hdmi-stereo-extra3.monitor",
        "glinject_auto_launch":               "false",
        "glinject_channel":                   "",
        "glinject_command":                   "",
        "glinject_limit_fps":                 "false",
        "glinject_relax_permissions":         "false",
        "glinject_working_directory":         "",
        "video_area":                         "cursor",
        "video_area_follow_fullscreen":       "false",
        "video_area_screen":                  "0",
        "video_frame_rate":                   "24",
        "video_h":                            "726",
        "video_record_cursor":                "true",
        "video_scale":                        "false",
        "video_scaled_h":                     "480",
        "video_scaled_w":                     "854",
        "video_v4l2_device":                  "/dev/video0",
        "video_w":                            "1148",
        "video_x":                            "0",
        "video_y":                            "0"
    },
    "output":  {
        "add_timestamp":              "false",
        "audio_codec":                "vorbis",
        "audio_codec_av":             "aac",
        "audio_kbit_rate":            "128",
        "audio_options":              "",
        "container":                  "mp4",
        "container_av":               "3g2",
        "file":                       "/home/simonl/sharez/videos/video.mp4",
        "profile":                    "",
        "separate_files":             "false",
        "video_allow_frame_skipping": "true",
        "video_codec":                "h264",
        "video_codec_av":             "alias_pix",
        "video_h264_crf":             "35",
        "video_h264_preset":          "1",
        "video_kbit_rate":            "5000",
        "video_options":              "",
        "video_vp8_cpu_used":         "5"
    },
    "record":  {
        "hotkey_alt":                 "false",
        "hotkey_ctrl":                "false",
        "hotkey_enable":              "false",
        "hotkey_key":                 "25",
        "hotkey_shift":               "false",
        "hotkey_super":               "false",
        "preview_frame_rate":         "10",
        "schedule_num_entries":       "0",
        "schedule_time_zone":         "local",
        "show_recording_area":        "false",
        "sound_notifications_enable": "false"
    },
    "welcome": {
        "skip_page": "true"
    }
}


class RecordingMode(enum.Enum):
    Area = 0
    FollowCursor = 1
    Screen1 = 2
    Screen2 = 3
    All = 4


class HistoryDays(enum.Enum):
    Days7 = 0
    Days28 = 1
    Days56 = 2
    Days84 = 3
    All = 4


if not os.path.isfile(os.path.join(CONFIG_PATH, f'{RecordingMode.Area.name}.json')):
    CONFIG_TEMPLATE['input']["video_area"] = "fixed"

    open(os.path.join(CONFIG_PATH, f'{RecordingMode.Area.name}.json'), 'w+').write(
        json.dumps(CONFIG_TEMPLATE, indent=2)
    )

if not os.path.isfile(os.path.join(CONFIG_PATH, f'{RecordingMode.FollowCursor.name}.json')):
    open(os.path.join(CONFIG_PATH, f'{RecordingMode.FollowCursor.name}.json'), 'w+').write(
        json.dumps(CONFIG_TEMPLATE, indent=2)
    )

SETTINGS_TEMPLTE = {
    "upload":                        True,
    "draw":                          False,
    "user":                          "yournamehere",
    "mode":                          0,
    "pystray_backend":               None,  # https://pystray.readthedocs.io/en/latest/usage.html
    "instant_start":                 True,
    "history_days":                  0,
    "sub_folder":                    True,
    "open_after_offline_screenshot": False,
    "binds":                         {
        "screenshot":    "<Super>X",
        "waiter":        "<Super>W",
        "history":       "<Super>H",
        "destroy":       "<Escape>",
        "upload_latest": "<Super>U",
        "video":         "<Alt>Z"
    },
    "monitors":                      {
        "monitor1": {
            "y_offset": 0,
            "x_offset": 0
        },
        "monitor2": {
            "y_offset": 0,
            "x_offset": 0
        }
    }
}

if not os.path.isfile(os.path.join(CONFIG_PATH, 'sysconfig.json')):
    open(os.path.join(CONFIG_PATH, 'sysconfig.json'), 'w+').write(
        json.dumps(SETTINGS_TEMPLTE, indent=2)
    )

SYSTEM_CONFIG = json.load(open(os.path.join(CONFIG_PATH, 'sysconfig.json')))
updated_dict = {}
for entry, value in SYSTEM_CONFIG.items():
    updated_dict.update({entry: value})
for entry, value in SETTINGS_TEMPLTE.items():
    if entry in updated_dict.keys():
        continue
    updated_dict.update({entry: value})
open(os.path.join(CONFIG_PATH, 'sysconfig.json'), 'w+').write(
    json.dumps(updated_dict, indent=2)
)
print('Done writing settings:\n', json.dumps(updated_dict, indent=2))

HISTORY_DAYS = SYSTEM_CONFIG['history_days']
USER = SYSTEM_CONFIG['user']
INSTANT_START = SYSTEM_CONFIG['instant_start']
SUB_FOLDER = SYSTEM_CONFIG['sub_folder']
BINDS = SYSTEM_CONFIG['binds']
OPEN_AFTER_SS = SYSTEM_CONFIG['open_after_offline_screenshot']
MONITORS_OFFSET = SYSTEM_CONFIG['monitors']
if SYSTEM_CONFIG['pystray_backend'] is not None:
    os.environ['PYSTRAY_BACKEND'] = SYSTEM_CONFIG['pystray_backend']

try:
    import gi
except:
    requirements = [
        'pycairo',
        'PyGObject'
    ]

    for requirement in requirements:
        try:
            subprocess.Popen(f'pip install --upgrade --force-reinstall {requirement}', shell=True).wait()
        except:
            traceback.print_exc()

    raise Exception("\nPlease install PyGObject dependencies manually: https://pygobject.readthedocs.io/en/latest/devguide/dev_environ.html?highlight=install#install-dependencies")

try:
    import psutil
    import requests
    import pytz
    import mss
    import mss.tools
    import gi
    import boto3
    import pyperclip
    import pystray
    from PIL import (
        ImageGrab,
        ImageTk,
        Image,
        ImageDraw,
    )
    from botocore.exceptions import ClientError
    from mss import ScreenShotError
    from pynput import keyboard
    from playsound import playsound
    from screeninfo import get_monitors
except:
    requirements = [
        'boto3==1.21.39',
        'pyperclip==1.8.2',
        "pystray==0.19.3",
        'Pillow==9.1.0',
        'screeninfo==0.8',
        'playsound==1.3.0',
        'pgi',
        'mss==6.1.0',
        'pytz',
        'requests',
        'psutil',
        'botocore',
        'pycairo',
        'PyGObject',
        'pynput'
    ]

    for requirement in requirements:
        try:
            subprocess.Popen(f'pip install --upgrade --force-reinstall {requirement}', shell=True).wait()
        except:
            traceback.print_exc()

if len([True for p in psutil.process_iter() if 'sharexyz' in p.name()]) > 1:
    print("Sharexyz already running. Exiting.")
    exit()

SCT = None

if not os.path.isfile(os.path.join(SOUNDS_DIR, 'upload_success.wav')):
    with open(os.path.join(SOUNDS_DIR, 'upload_success.wav'), "wb") as fh:
        fh.write(base64.decodebytes(binaries.upload_success))

if not os.path.isfile(os.path.join(SOUNDS_DIR, 'upload_failed.wav')):
    with open(os.path.join(SOUNDS_DIR, 'upload_failed.wav'), "wb") as fh:
        fh.write(base64.decodebytes(binaries.upload_failed))

# s3
BUCKET_NAME = 'cos-dev-attachments'


def get_bucket_folder():
    if SUB_FOLDER:
        MONTH_SUB_FOLDER_NAME = str(datetime.datetime.now().date().strftime("%m%y"))
        BUCKET_FOLDER = f'ShareX/{USER}/{MONTH_SUB_FOLDER_NAME}/'
    else:
        BUCKET_FOLDER = f'ShareX/{USER}/'
    return BUCKET_FOLDER


URL = f'https://s3.{os.getenv("REGION_NAME")}.amazonaws.com/{BUCKET_NAME}/{get_bucket_folder()}'
print(URL)
# local dirs
VIDEOS_DIR = os.path.join(HOME, 'videos')
if not os.path.isdir(VIDEOS_DIR):
    os.mkdir(VIDEOS_DIR)

SCREENSHOTS_DIR = os.path.join(HOME, 'screenshots')
if not os.path.isdir(SCREENSHOTS_DIR):
    os.mkdir(SCREENSHOTS_DIR)

ICONS_DIR = os.path.join(DATA_PATH, 'icons')
if not os.path.isdir(ICONS_DIR):
    os.mkdir(ICONS_DIR)

HISTORY_DIR = os.path.join(DATA_PATH, 'history.json')
if not os.path.isfile(HISTORY_DIR):
    open(HISTORY_DIR, 'w+').write('{}')

ONLINE_HISTORY_DIR = os.path.join(DATA_PATH, 'online_history.json')
if not os.path.isfile(ONLINE_HISTORY_DIR):
    open(ONLINE_HISTORY_DIR, 'w+').write('{}')

TEMP_PATH = os.path.join(DATA_PATH, 'temp')
if not os.path.isdir(TEMP_PATH):
    os.mkdir(TEMP_PATH)

# history window cache
HISTORY = json.load(open(HISTORY_DIR))
ONLINE_HISTORY = json.load(open(ONLINE_HISTORY_DIR))

WAITER = {
    'active': False
}

# tray icon
ICON_PATH = os.path.join(ICONS_DIR, "ShareX.png")
if not os.path.isfile(ICON_PATH):
    icons = [
        ('online_video.png', binaries.online_video_icon),
        ('online_image.png', binaries.online_image_icon),
        ('offline_video.png', binaries.offline_video_icon),
        ('offline_image.png', binaries.offline_image_icon),
        ('ShareX.png', binaries.share_x_icon),
        ('doc.png', binaries.unknown_file),
    ]
    for icon_name, icon in icons:
        with open(os.path.join(ICONS_DIR, icon_name), "wb") as fh:
            fh.write(base64.decodebytes(icon))

DESKTOP_FILE_PATH = os.path.join(HOME, 'sharex.desktop')
DESKTOP_ENTRY = [
    '#!/usr/bin/env xdg-open\n',
    '[Desktop Entry]\n',
    f'Exec=cd {HOME}; python {os.path.join(HOME, "sharexyz.py")}\n',
    f"Icon={ICON_PATH}\n",
    'Name=ShareX\n',
    'Terminal=true\n',
    'Type=Application\n'
]

if not os.path.isfile(DESKTOP_FILE_PATH):
    with open(DESKTOP_FILE_PATH, "w+") as de:
        for entry in DESKTOP_ENTRY:
            de.write(entry)

UPLOAD_AFTER_TASK = SYSTEM_CONFIG['upload'] == True
DRAW_AFTER_TASK = SYSTEM_CONFIG['draw'] == True
LATEST_KEY = None
KEY_HISTORY = []
KEY_PRESSED = None
FIRST_HISTORY_OPEN = True
VIDEO_RECORDER = None
RECORDING_PROC = None

print(SYSTEM_CONFIG)
