# must be at the top
import env

import base64
import datetime
import glob
import io
import json
import mimetypes
import os
import secrets
import shutil
import string
import subprocess
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from itertools import islice
from operator import getitem

import boto3
import gi
import keyboard
import mss
import mss.tools
import pystray
import requests
from PIL import (
    ImageGrab,
    ImageTk,
    Image,
)

gi.require_version("Gtk", "3.0")
gi.require_version("Keybinder", "3.0")
gi.require_version('Notify', '0.7')
from gi.repository import (
    Gtk,
    Keybinder,
    GdkPixbuf,
    Gdk,
    Notify,
    GObject,
    GLib,
)
from mss import ScreenShotError
from playsound import playsound
from pynput import keyboard
from screeninfo import get_monitors


class File:
    VIDEO = ('.m1v', '.mpeg', '.mov', '.qt', '.mpa', '.mpg', '.mpe', '.avi', '.movie', '.mp4', '.mkv')
    AUDIO = ('.ra', '.aif', '.aiff', '.aifc', '.wav', '.au', '.snd', '.mp3', '.mp2')
    IMAGE = ('.ras', '.xwd', '.bmp', '.jpe', '.jpg', '.jpeg', '.xpm', '.ief', '.pbm', '.tif', '.gif', '.ppm', '.xbm',
             '.tiff', '.rgb', '.pgm', '.png', '.pnm')

    def __init__(self, file_name: str = '', extension: str = '', path: str = ''):
        self._date = ''
        self._file_name = file_name
        self._path = path

        if not file_name:
            self._date = datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).astimezone(tz=datetime.timezone.utc)
            self._file_name = str(self._date).split('+')[0] + extension

        if self._path:
            self._file_name = self._path.split('/')[-1]

        if not self._date:
            if ":" in self._file_name and not self._path:
                self._date = datetime.datetime.strptime(self.clean_name, "%Y-%m-%d %H:%M:%S").replace(microsecond=0, tzinfo=datetime.timezone.utc).astimezone(tz=datetime.timezone.utc)
            else:
                self._date = datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).astimezone(tz=datetime.timezone.utc)

        self._extension = '.' + self._file_name.split('.')[-1] if '.' in self._file_name else ''
        self._type = 'unknown'
        if any(video_type in self._extension for video_type in self.VIDEO):
            self._type = 'video'
        if any(image_type in self._extension for image_type in self.IMAGE):
            self._type = 'screenshot'

        directory = env.SCREENSHOTS_DIR if self._extension == '.png' else env.VIDEOS_DIR
        if not self._path:
            self._path = os.path.join(directory, self.file_name)
        print(self)

    def __str__(self):
        return f"file_name={self.file_name}\n"\
               f"type={self.type}\n"\
               f"extension={self.extension}\n"\
               f"file_path={self.file_path}\n"\
               f"clean_name={self.clean_name}\n"\
               f"date={self.date}\n"

    @property
    def file_name(self):
        return self._file_name

    @property
    def type(self):
        return self._type

    @property
    def extension(self):
        return self._extension

    @property
    def file_path(self):
        return self._path

    @property
    def clean_name(self):
        return self._file_name[:-4].split('+')[0]

    @property
    def date(self):
        return self._date


def update_history_file(file: File):
    env.HISTORY[file.file_name] = {}
    env.HISTORY[file.file_name]['type'] = file.type
    env.HISTORY[file.file_name]['date'] = file.date
    env.HISTORY[file.file_name]['place'] = 'online'
    if not env.UPLOAD_AFTER_TASK:
        env.HISTORY[file.file_name]['place'] = 'local'
        _generate_cache()
    else:
        env.ONLINE_HISTORY[file.file_name] = {}
        env.ONLINE_HISTORY[file.file_name]['type'] = file.type
        env.ONLINE_HISTORY[file.file_name]['date'] = file.date
        env.ONLINE_HISTORY[file.file_name]['place'] = 'online'

    _order_history()


def get_default_icon_path(dict_data):
    if dict_data['type'] == 'unknown':
        return os.path.join(env.ICONS_DIR, 'doc.png')
    if dict_data['type'] == 'video':
        if dict_data['place'] == 'local':
            return os.path.join(env.ICONS_DIR, 'offline_video.png')
        return os.path.join(env.ICONS_DIR, 'online_video.png')
    if dict_data['place'] == 'online':
        return os.path.join(env.ICONS_DIR, 'online_image.png')
    return os.path.join(env.ICONS_DIR, 'offline_image.png')


def _clear_local_files_not_in_history():
    print("Clearing old files")
    for dir in [env.SCREENSHOTS_DIR, env.TEMP_PATH, env.VIDEOS_DIR]:
        for file in os.listdir(dir):
            if file not in env.HISTORY.keys():
                os.remove(os.path.join(dir, file))
    print("Cleared old files")


def _generate_cache():
    print('generate cache')
    start = time.time()
    _order_history()
    for file_name, data in env.ONLINE_HISTORY.items():
        # add url entry if there is none
        if data['place'] == 'online' and not data.get('url'):
            print(f'file={file_name}, Adding url')
            data['url'] = env.URL + file_name

        # if history entry has a path and the path exists return
        if env.ONLINE_HISTORY[file_name].get('icon_path') and os.path.isfile(env.ONLINE_HISTORY[file_name].get('icon_path')):
            print(f'file={file_name}, Icon path already exists: ', env.ONLINE_HISTORY[file_name].get('icon_path'))
            continue

        # create path, should be png always
        temp_file = os.path.join(env.TEMP_PATH, file_name[:-4] + '.png')

        # if the new path already exists update the history file and return
        if os.path.isfile(temp_file):
            env.ONLINE_HISTORY[file_name]['icon_path'] = temp_file
            print(f'file={file_name}, Temp Icon path already exists: ', temp_file)
            continue

        if data['type'] == 'unknown':
            print(f'file={file_name}, Data type unknown, getting icon path')
            env.ONLINE_HISTORY[file_name]['icon_path'] = get_default_icon_path(env.ONLINE_HISTORY[file_name])
            continue

        if data['type'] == 'video':
            print(f'file={file_name}, Data type video, getting icon path')
            if data['place'] == 'local':
                print(f'file={file_name}, local video')
                subprocess.Popen(
                    ["ffmpeg",
                     "-i",
                     f"{os.path.join(env.VIDEOS_DIR, file_name)}",
                     "-ss",
                     "00:00:1",
                     "-vframes",
                     "1",
                     '-f',
                     'image2',
                     f"{temp_file}"]
                ).wait(10)
                if os.path.isfile(temp_file):
                    env.ONLINE_HISTORY[file_name]['icon_path'] = temp_file
                    print('thumbnail from local video SUCCESS', env.ONLINE_HISTORY[file_name])
                else:
                    env.ONLINE_HISTORY[file_name]['icon_path'] = get_default_icon_path(env.ONLINE_HISTORY[file_name])
                    print('thumbnail from local video FAILED', env.ONLINE_HISTORY[file_name])
                continue
            print(f'file={file_name}, online video')
            subprocess.Popen(
                ["ffmpeg",
                 "-i",
                 f"{data['url']}",
                 "-ss",
                 "00:00:1",
                 "-vframes",
                 "1",
                 "-f",
                 "image2",
                 temp_file]
            ).wait(10)
            if os.path.isfile(temp_file):
                env.ONLINE_HISTORY[file_name]['icon_path'] = temp_file
                print('thumbnail from online video  SUCCESS', env.ONLINE_HISTORY[file_name])
            else:
                env.ONLINE_HISTORY[file_name]['icon_path'] = get_default_icon_path(env.ONLINE_HISTORY[file_name])
                print('thumbnail from online video FAILED', env.ONLINE_HISTORY[file_name])
            continue
        if data['place'] == 'online':
            print(f'file={file_name}, online screenshot')
            try:
                img = Image.open(requests.get(data['url'], stream=True).raw)
                img.save(temp_file)
                print(f'file={file_name}, online screenshot gotten')
            except:
                traceback.print_exc()
            if os.path.isfile(temp_file):
                env.ONLINE_HISTORY[file_name]['icon_path'] = temp_file
                print('thumbnail from online picture SUCCESS', env.ONLINE_HISTORY[file_name])
            else:
                env.ONLINE_HISTORY[file_name]['icon_path'] = get_default_icon_path(env.ONLINE_HISTORY[file_name])
                print('thumbnail from online picture FAILED', env.ONLINE_HISTORY[file_name])
            continue
        print(f'file={file_name}, local screenshot gotten')
        shutil.copy2(os.path.join(env.SCREENSHOTS_DIR, file_name), temp_file)
        env.ONLINE_HISTORY[file_name]['icon_path'] = temp_file
        if os.path.isfile(temp_file):
            env.ONLINE_HISTORY[file_name]['icon_path'] = temp_file
            print('thumbnail from offline picture SUCCESS', env.ONLINE_HISTORY[file_name])
        else:
            env.ONLINE_HISTORY[file_name]['icon_path'] = get_default_icon_path(env.ONLINE_HISTORY[file_name])
            print('thumbnail from offline picture FAILED', env.ONLINE_HISTORY[file_name])

        if not os.path.isfile(env.ONLINE_HISTORY[file_name]['icon_path']):
            env.ONLINE_HISTORY[file_name]['icon_path'] = get_default_icon_path(data)
            raise Exception("Icon path doesn't exist even though we think it does" + env.ONLINE_HISTORY[file_name])

    for file_name, data in env.HISTORY.items():

        # add url entry if there is none
        if data['place'] == 'online' and not data.get('url'):
            print(f'file={file_name}, Adding url')
            data['url'] = env.URL + file_name

        # if history entry has a path and the path exists return
        if env.HISTORY[file_name].get('icon_path') and os.path.isfile(env.HISTORY[file_name].get('icon_path')):
            print(f'file={file_name}, Icon path already exists: ', env.HISTORY[file_name].get('icon_path'))
            continue

        # create path, should be png always
        temp_file = os.path.join(env.TEMP_PATH, file_name[:-4] + '.png')

        # if the new path already exists update the history file and return
        if os.path.isfile(temp_file):
            env.HISTORY[file_name]['icon_path'] = temp_file
            print(f'file={file_name}, Temp Icon path already exists: ', temp_file)
            continue

        if data['type'] == 'unknown':
            print(f'file={file_name}, Data type unknown, getting icon path')
            env.HISTORY[file_name]['icon_path'] = get_default_icon_path(env.HISTORY[file_name])

            continue

        if data['type'] == 'video':
            print(f'file={file_name}, Data type video, getting icon path')
            if data['place'] == 'local':
                print(f'file={file_name}, local video')
                subprocess.Popen(
                    ["ffmpeg",
                     "-i",
                     f"{os.path.join(env.VIDEOS_DIR, file_name)}",
                     "-ss",
                     "00:00:1",
                     "-vframes",
                     "1",
                     '-f',
                     'image2',
                     f"{temp_file}"]
                ).wait(10)
                if os.path.isfile(temp_file):
                    env.HISTORY[file_name]['icon_path'] = temp_file
                    print('thumbnail from local video SUCCESS', env.HISTORY[file_name])
                else:
                    env.HISTORY[file_name]['icon_path'] = get_default_icon_path(env.HISTORY[file_name])
                    print('thumbnail from local video FAILED', env.HISTORY[file_name])
                continue
            print(f'file={file_name}, online video')
            subprocess.Popen(
                ["ffmpeg",
                 "-i",
                 f"{data['url']}",
                 "-ss",
                 "00:00:1",
                 "-vframes",
                 "1",
                 "-f",
                 "image2",
                 temp_file]
            ).wait(10)
            if os.path.isfile(temp_file):
                env.HISTORY[file_name]['icon_path'] = temp_file
                print('thumbnail from online video  SUCCESS', env.HISTORY[file_name])
            else:
                env.HISTORY[file_name]['icon_path'] = get_default_icon_path(env.HISTORY[file_name])
                print('thumbnail from online video FAILED', env.HISTORY[file_name])
            continue
        if data['place'] == 'online':
            print(f'file={file_name}, online screenshot')
            try:
                img = Image.open(requests.get(data['url'], stream=True).raw)
                img.save(temp_file)
                print(f'file={file_name}, online screenshot gotten')
            except:
                traceback.print_exc()
            if os.path.isfile(temp_file):
                env.HISTORY[file_name]['icon_path'] = temp_file
                print('thumbnail from online picture SUCCESS', env.HISTORY[file_name])
            else:
                env.HISTORY[file_name]['icon_path'] = get_default_icon_path(env.HISTORY[file_name])
                print('thumbnail from online picture FAILED', env.HISTORY[file_name])
            continue
        print(f'file={file_name}, local screenshot gotten')
        shutil.copy2(os.path.join(env.SCREENSHOTS_DIR, file_name), temp_file)
        env.HISTORY[file_name]['icon_path'] = temp_file
        if os.path.isfile(temp_file):
            env.HISTORY[file_name]['icon_path'] = temp_file
            print('thumbnail from offline picture SUCCESS', env.HISTORY[file_name])
        else:
            env.HISTORY[file_name]['icon_path'] = get_default_icon_path(env.HISTORY[file_name])
            print('thumbnail from offline picture FAILED', env.HISTORY[file_name])

        if not os.path.isfile(env.HISTORY[file_name]['icon_path']):
            env.HISTORY[file_name]['icon_path'] = get_default_icon_path(data)
            raise Exception("Icon path doesn't exist even though we think it does" + env.HISTORY[file_name])

    _order_history()
    open(env.HISTORY_DIR, 'w+').write(json.dumps(env.HISTORY, indent=2, default=str))
    open(env.ONLINE_HISTORY_DIR, 'w+').write(json.dumps(env.ONLINE_HISTORY, indent=2, default=str))
    print(f'Cache generated, duration={time.time() - start}')


def _order_history():
    sorted_dict = OrderedDict(
        sorted(
            env.HISTORY.items(),
            key=lambda x: datetime.datetime.strptime(str(getitem(x[1], 'date')).split('+')[0], "%Y-%m-%d %H:%M:%S").replace(microsecond=0, tzinfo=datetime.timezone.utc).astimezone(tz=datetime.timezone.utc),
            reverse=True
        )
    )
    sliced = islice(sorted_dict.items(), 50)
    sliced_dict = OrderedDict(sliced)
    env.HISTORY = sliced_dict

    sorted_dict = OrderedDict(
        sorted(
            env.ONLINE_HISTORY.items(),
            key=lambda x: datetime.datetime.strptime(str(getitem(x[1], 'date')).split('+')[0], "%Y-%m-%d %H:%M:%S").replace(microsecond=0, tzinfo=datetime.timezone.utc).astimezone(tz=datetime.timezone.utc),
            reverse=True
        )
    )
    sliced = islice(sorted_dict.items(), 500)
    sliced_dict = OrderedDict(sliced)
    env.ONLINE_HISTORY = sliced_dict


def validate_date_age(date: datetime.datetime):
    time_between_insertion = datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).astimezone(tz=datetime.timezone.utc) - date.replace(microsecond=0, tzinfo=datetime.timezone.utc).astimezone(tz=datetime.timezone.utc)
    return time_between_insertion.days < 30


def get_bucket_history(limit: int = 100):
    def _get_type(fiel_name: str):
        return 'video' if 'mp4' in fiel_name else 'screenshot'

    def obj_last_modified(myobj):
        return myobj.last_modified

    session = boto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    # Then use the session to get the resource
    s3 = session.resource('s3')

    my_bucket = s3.Bucket(env.BUCKET_NAME)

    sorted_objects = sorted(
        my_bucket.objects.filter(
            Prefix=env.BUCKET_FOLDER
        ),
        key=obj_last_modified,
        reverse=True
    )[:limit]

    for my_bucket_object in sorted_objects:
        if not validate_date_age(my_bucket_object.last_modified):
            break
        if not ('.mp4' in my_bucket_object.key or '.png' in my_bucket_object.key):
            continue
        name = my_bucket_object.key.split('/')[-1]
        if limit > 100:
            env.ONLINE_HISTORY[name] = {
                "date":  my_bucket_object.last_modified.replace(microsecond=0, tzinfo=datetime.timezone.utc).astimezone(tz=datetime.timezone.utc),
                "type":  _get_type(my_bucket_object.key),
                "place": "online",
                "url":   env.URL + name
            }
        else:
            env.HISTORY[name] = {
                "date":  my_bucket_object.last_modified.replace(microsecond=0, tzinfo=datetime.timezone.utc).astimezone(tz=datetime.timezone.utc),
                "type":  _get_type(my_bucket_object.key),
                "place": "online",
                "url":   env.URL + name
            }


def _get_history():
    def _get_local_history():
        for directory in [env.SCREENSHOTS_DIR, env.VIDEOS_DIR]:
            for file_name in os.listdir(directory)[:100]:
                if env.HISTORY.get(file_name):
                    continue
                if '-' not in file_name:
                    continue
                file = File(file_name=file_name)
                if not validate_date_age(file.date):
                    break
                env.HISTORY[file.file_name] = {
                    "date":  file.date,
                    "type":  file.type,
                    "place": "local"
                }

    setup_notify = NotificationBubble()
    setup_notify.send_notification(
        "Setting up...", "This may take a few minutes."
    )
    start = time.time()

    thread_pool = ThreadPoolExecutor()

    future = thread_pool.submit(get_bucket_history)
    try:
        future.result(15)
    except:
        traceback.print_exc()

    future = thread_pool.submit(get_bucket_history, 500)
    try:
        future.result(15)
    except:
        traceback.print_exc()

    _get_local_history()

    _generate_cache()

    print(json.dumps(env.HISTORY, indent=2, default=str))

    # for file in os.listdir(os.path.join(env.DATA_PATH, 'temp')):
    # 	if file not in sliced_doct.keys():
    # 		os.remove(os.path.join(env.DATA_PATH, 'temp', file))

    # except:
    # 	traceback.print_exc()
    # finally:
    # 	env.REFRESH_PROC = None

    print(f'History downloaded, duration={time.time() - start}')
    setup_notify.close()


def init_xclip_clipboard():
    DEFAULT_SELECTION = 'c'
    PRIMARY_SELECTION = 'p'
    ENCODING = 'utf-8'

    def copy_xclip(text, primary=False):
        text = str(text)  # Converts non-str values to str.
        selection = DEFAULT_SELECTION
        if primary:
            selection = PRIMARY_SELECTION
        p = subprocess.Popen(
            ['xclip', '-selection', selection],
            stdin=subprocess.PIPE, close_fds=True
        )
        p.communicate(input=text.encode('utf-8'))

    def paste_xclip(primary=False):
        selection = DEFAULT_SELECTION
        if primary:
            selection = PRIMARY_SELECTION
        p = subprocess.Popen(
            ['xclip', '-selection', selection, '-o'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True
        )
        stdout, stderr = p.communicate()
        # Intentionally ignore extraneous output on stderr when clipboard is empty
        return stdout.decode(ENCODING)

    return copy_xclip, paste_xclip


copy, paste = init_xclip_clipboard()


def upload_file(file: File, keep=False):
    def _upload_file(s3_client, file_name, path):
        object_name = os.path.join(env.BUCKET_FOLDER, file_name)
        print(
            f'path={path}\n'
            f'file_name={file_name}\n'
            f'object_name={object_name}'
        )
        # mimetypes.add_type('video/mp4', '.mp4')
        file_mime_type, _ = mimetypes.guess_type(file_name)
        print(file_mime_type)
        # print(file_mime_type)
        extra_args = {
            'ACL': 'public-read'
        }
        # if 'video/mp4' not in file_mime_type:
        # 	print('not')
        extra_args['ContentType'] = file_mime_type

        try:
            response = s3_client.upload_file(
                path, env.BUCKET_NAME, object_name, ExtraArgs=extra_args
            )
        except:
            traceback.print_exc()
            return False
        return True

    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("REGION_NAME")
    )

    file_name_new = ''.join(
        secrets.choice(string.ascii_uppercase + string.ascii_lowercase) for _ in range(16)
    ) + file.extension

    if keep:
        shutil.copy2(file.file_path, os.path.join(env.UPLOADS_DIR, file_name_new))
        file_new = File(path=os.path.join(env.UPLOADS_DIR, file_name_new))
    else:
        file_new = File(file_name_new)
        os.rename(file.file_path, file_new.file_path)

    if env.HISTORY.get(file.file_name):
        del env.HISTORY[file.file_name]

    env.HISTORY[file_name_new] = {}
    env.HISTORY[file_name_new]['type'] = file_new.type
    env.HISTORY[file_name_new]['date'] = file_new.date

    if _upload_file(s3_client, file_new.file_name, file_new.file_path):
        print('debug 2')
        if not keep:
            os.remove(file_new.file_path)

        clipboard = env.URL + file_name_new
        copy(clipboard)
        print(f'Url={clipboard}')
        env.HISTORY[file_name_new]['place'] = 'online'
        env.HISTORY[file_name_new]['url'] = clipboard

        env.ONLINE_HISTORY[file_name_new] = {}
        env.ONLINE_HISTORY[file_name_new]['type'] = file_new.type
        env.ONLINE_HISTORY[file_name_new]['date'] = file_new.date
        env.ONLINE_HISTORY[file_name_new]['place'] = 'online'
        env.ONLINE_HISTORY[file_name_new]['url'] = clipboard

        notify.send_notification("Copied to clipboard", clipboard, clickable=True)
        playsound(os.path.join(env.SOUNDS_DIR, 'upload_success.wav'))
        print('debug x')
    else:
        print('debug 7')
        os.system('xdg-open "%s"' % env.VIDEOS_DIR)
        env.HISTORY[file_name_new]['place'] = 'local'
        notify.send_notification(
            "Failure!", "Upload failed. Check internet connection or poke simon if the issue persists."
        )
        playsound(os.path.join(env.SOUNDS_DIR, 'upload_failed.wav'))

    _generate_cache()

    env.WAITER['active'] = False
    return file_name_new


def _kill_process(process_name: str):
    # proc = subprocess.Popen([f'pidof {process_name}'], stdout=subprocess.PIPE, shell=True)
    # stdout, _ = proc.communicate()
    # decoded = stdout.decode('utf-8')
    # print(decoded)
    subprocess.Popen([f'pkill -f {process_name}'], stdout=subprocess.PIPE, shell=True)


class VideoRecorder:
    def __init__(self):
        self.file = File(extension='.mp4')
        self.setting = env.RecordingMode(env.SYSTEM_CONFIG['mode'])
        self.recording = False
        self.proc = None

        Keybinder.bind("<Alt>Z", self.take_video)

    def take_video(self, keystring):
        print('take video in')

        if self.recording and self.proc:
            # _end_recording()
            def _save_recording():
                try:
                    _, _ = self.proc.communicate(input=b"record-save\n")
                except OSError:
                    pass

            self.recording = False
            save_notify = NotificationBubble()
            save_notify.send_notification("Saving...", "")

            threading.Thread(
                target=_save_recording
            ).start()

            for line in io.TextIOWrapper(self.proc.stderr, encoding="utf-8"):
                print(line)
                if 'kb/s' in line or 'Stopped page' in line or 'Standard input closed' in line:
                    break

            self.proc = None

            try:
                _kill_process('simplescreenrecorder')
            except:
                pass

            try:
                if not env.UPLOAD_AFTER_TASK:
                    os.system('xdg-open "%s"' % env.VIDEOS_DIR)
                    update_history_file(self.file)

                    save_notify.close()
                    env.WAITER['active'] = False
                else:
                    upload_file(self.file)
                    # GLib.idle_add(lambda: upload_file(self.file))
            except:
                traceback.print_exc()
        else:
            if env.WAITER['active']:
                video_waiter_notify = NotificationBubble()
                video_waiter_notify.send_notification(
                    "Please wait...", "Recording or uploading video."
                )
                print('Waiter active video')
                return

            env.WAITER['active'] = True

            self.update_config()
            self.start_recording()
        print('take video out')

    def update_config(self):
        def _generate_config():
            with open(os.path.join(env.CONFIG_PATH, f'{self.setting.name}.conf'), 'w+') as conf_file:
                for header, settings in config.items():
                    print(header, settings)
                    conf_file.write(f'[{header}]\n')
                    for setting, value in settings.items():
                        conf_file.write(f'{setting}={value}\n')
                    conf_file.write('\n')

        self.file = File(extension='.mp4')
        self.setting = env.RecordingMode(env.SYSTEM_CONFIG['mode'])
        config = json.load(open(os.path.join(env.CONFIG_PATH, f'{self.setting.name}.json')))
        print(self.setting)
        if self.setting.value == env.RecordingMode.Area.value:
            canvas = ScreenshotCanvas(take_screenshot=False)
            canvas.mainloop()

            x, y, w, h = canvas.coordinates
            config['input']['video_x'] = x
            config['input']['video_y'] = y
            config['input']['video_w'] = w - x
            config['input']['video_h'] = h - y

        config['output']['file'] = self.file.file_path
        _generate_config()
        print(config)

    def start_recording(self):
        try:
            self.kill_recorder()
        except:
            pass
        self.recording = True
        self.proc = subprocess.Popen(
            ["simplescreenrecorder",
             "--start-hidden",
             "--start-recording",
             f"--settingsfile={os.path.join(env.CONFIG_PATH, f'{self.setting.name}.conf')}"],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # bufsize=0
        )


class ShareXYZTool(Gtk.Window):
    def __init__(self):
        super().__init__()

        env.SCT = mss.mss()

        VideoRecorder()
        Keybinder.init()
        Keybinder.bind("<Super>X", self.take_screenshot)
        Keybinder.bind("<Super>W", self.disable_waiter)
        Keybinder.bind("<Super>H", HistoryWindow.reopen_history_window)

    def take_screenshot(self, keystring):
        print('take screenshot in')
        if env.WAITER['active']:
            screenshot_waiter_notify = NotificationBubble()
            screenshot_waiter_notify.send_notification(
                "Please wait...", "Taking or uploading screenshot"
            )
            print("waiter active screenshot")
            return

        env.WAITER['active'] = True

        canvas = ScreenshotCanvas()
        canvas.mainloop()

        env.WAITER['active'] = False
        print('take screenshot out')

    def disable_waiter(self, keystring):
        env.WAITER['active'] = False


class ScreenshotCanvas(tk.Tk):
    def __init__(self, take_screenshot: bool = True):
        super().__init__()
        self.withdraw()

        self._take_screenshot = take_screenshot
        self._bbox = None

        abs_coord_x = self.winfo_pointerx() - self.winfo_vrootx()

        monitor1 = get_monitors()[0]
        monitor2 = get_monitors()[1]

        bbox_monitor1 = (monitor1.x, monitor1.y, monitor1.width, monitor1.height)
        bbox_monitor2 = (monitor2.x, monitor2.y, monitor1.width + monitor2.width, monitor2.height)

        self.monitor = monitor1
        if abs_coord_x > monitor1.width:
            self.monitor = monitor2

        bbox = bbox_monitor1

        self.geometry(f"+{self.monitor.x}+0")
        if self.monitor.x > 0:
            bbox = bbox_monitor2

        self.attributes('-fullscreen', True)

        self.first_tap = True
        self.canvas = tk.Canvas(self)
        self.canvas.pack(fill="both", expand=True)
        image = ImageGrab.grab(bbox=bbox, include_layered_windows=False, all_screens=True)

        self.image = ImageTk.PhotoImage(image)
        self.photo = self.canvas.create_image(0, 0, image=self.image, anchor="nw")

        self.lasx, self.lasy = 0, 0
        self.x, self.y = 0, 0
        self.rect, self.start_x, self.start_y = None, None, None
        self.deiconify()

        self.canvas.tag_bind(self.photo, "<ButtonPress-1>", self.on_button_press)
        self.canvas.tag_bind(self.photo, "<B1-Motion>", self.on_move_press)
        self.canvas.tag_bind(self.photo, "<ButtonRelease-1>", self.on_button_release)
        self.canvas.tag_bind(self.photo, '<ButtonPress-3>', self.close_me)
        self.canvas.bind_all('<Escape>', self.destroy_me)

    def destroy_me(self, event):
        print('destroy_me')
        self.withdraw()

        self.destroy()

    def close_me(self, event):
        print('close_me')
        self.withdraw()

        if self._take_screenshot:
            try:
                self.take_screenshot()
            except:
                traceback.print_exc()

        self.destroy()

    def on_button_press(self, event):
        if self.first_tap:
            self.start_x = event.x
            self.start_y = event.y
            self.rect = self.canvas.create_rectangle(self.x, self.y, 1, 1, outline='red')
        elif env.KEY_PRESSED == keyboard.Key.shift:
            self.start_x = event.x
            self.start_y = event.y
            self.draw_rect = self.canvas.create_rectangle(self.x, self.y, 1, 1, outline='red', width=8)
        else:
            self.lasx, self.lasy = event.x, event.y
            self.canvas.create_line(
                (self.lasx, self.lasy, event.x, event.y),
                fill='red',
                width=8
            )
            self.lasx, self.lasy = event.x, event.y

    def on_move_press(self, event):
        if self.first_tap:
            curX, curY = (event.x, event.y)
            self.canvas.coords(self.rect, self.start_x, self.start_y, curX, curY)
        elif env.KEY_PRESSED == keyboard.Key.shift:
            curX, curY = (event.x, event.y)
            self.canvas.coords(self.draw_rect, self.start_x, self.start_y, curX, curY)
        else:
            self.canvas.create_line(
                (self.lasx, self.lasy, event.x, event.y),
                fill='red',
                width=8
            )
            self.lasx, self.lasy = event.x, event.y

    def on_button_release(self, event):
        if self.first_tap:
            self._bbox = self.canvas.bbox(self.rect)
            x, y, w, h = self._bbox

            # make all values positive
            if self.monitor.x == 0:
                x = max(x, 0)
            y = max(y, 0)

            self._bbox = (x, y, w, h)

            if self.monitor.x > 0:
                self._bbox = (x + self.monitor.x, y, w + self.monitor.width, h)
            self.first_tap = False

            if not self._take_screenshot:
                self.withdraw()
                self.destroy()

    def take_screenshot(self):
        try:
            sct_img = env.SCT.grab(self._bbox)
            file = File(extension='.png')
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            aspect_ratio = img.size[1] / img.size[0]

            print("Size before resize: ", img.size, "\n aspect ratio: ", aspect_ratio)

            if int(aspect_ratio * self.monitor.width) > self.monitor.height:
                size = (int(self.monitor.height / aspect_ratio), self.monitor.height)
            else:
                size = (self.monitor.width, int(aspect_ratio * self.monitor.width))

            img_resized = img.resize(size)
            print("Size after resize: ", img_resized.size)

            img_resized.save(file.file_path)
            img_resized.save(os.path.join(env.DATA_PATH, 'temp', file.file_name))

            update_history_file(file)

            if not env.UPLOAD_AFTER_TASK:
                notify_me = NotificationBubble()
                notify_me.send_notification("Screenshot captured", "Screenshot captured", clickable=True, action_callable=lambda *args: img_resized.show())
            else:
                upload_file(file)
                # GLib.idle_add(lambda: upload_file(file))

        except ScreenShotError:
            traceback.print_exc()
            print(env.SCT.get_error_details())
        except:
            traceback.print_exc()

    @property
    def coordinates(self):
        return self._bbox


class TrayIcon:
    def __init__(self):
        self.tray_icon = pystray.Icon(
            name='ShareXYZ',
            icon=Image.open(env.ICON_PATH),
            title='ShareXYZ',
            menu=self._build_menus()
        )
        Keybinder.bind("<Super>U", self.__upload_latest)

    def _build_menus(self):
        online_history = pystray.MenuItem(
            'Online History',
            self.show_online_history
        )
        history = pystray.MenuItem(
            'History',
            self.show_history
        )
        radio_menu = pystray.Menu(
            pystray.MenuItem(
                'Select Region',
                self._set_state(0),
                checked=self._get_state(0),
                radio=True
            ),
            pystray.MenuItem(
                'Follow Cursor',
                self._set_state(1),
                checked=self._get_state(1),
                radio=True
            )
        )

        recording_mode = pystray.MenuItem(
            'Recording Mode',
            radio_menu
        )

        upload_after_capture = pystray.MenuItem(
            'Upload after capture',
            self._on_upload_after_task,
            checked=lambda item: env.UPLOAD_AFTER_TASK
        )

        draw_after_capture = pystray.MenuItem(
            'Draw after capture',
            self._on_draw_after_task,
            checked=lambda item: env.DRAW_AFTER_TASK
        )

        upload_latest = pystray.MenuItem(
            'Upload latest',
            self._upload_latest,
        )

        clear_cache = pystray.MenuItem(
            'Clear Cache',
            self._clear_cache,
        )

        exit_menu = pystray.MenuItem('Quit', self.exit_everything)
        return pystray.Menu(
            online_history,
            history,
            recording_mode,
            upload_after_capture,
            draw_after_capture,
            upload_latest,
            clear_cache,
            exit_menu
        )

    def _clear_cache(self):
        if env.WAITER['active']:
            cache_waiter_notify = NotificationBubble()
            cache_waiter_notify.send_notification(
                "Clearing Cache...", "Please wait for cache to generate."
            )
            return

        env.WAITER['active'] = True
        print('Clearing cache..')
        cache_notify = NotificationBubble()
        cache_notify.send_notification(
            "Clearing Cache...", "This may take a few minutes."
        )
        env.HISTORY = {}

        open(env.HISTORY_DIR, 'w+').write('{}')
        for dir in [env.SCREENSHOTS_DIR, env.VIDEOS_DIR, env.TEMP_PATH]:
            for file in os.listdir(dir):
                os.remove(os.path.join(dir, file))

        for history in [env.HISTORY_DIR, env.ONLINE_HISTORY_DIR]:
            open(history, 'w+').write('{}')

        print('Cache cleared..')
        _get_history()
        cache_notify.close()
        cleared_notify = NotificationBubble()
        cleared_notify.send_notification(
            "Cache cleared!", ""
        )
        env.WAITER['active'] = False

    def _on_upload_after_task(self, icon, item):
        env.UPLOAD_AFTER_TASK = not item.checked
        env.SYSTEM_CONFIG['upload'] = env.UPLOAD_AFTER_TASK
        open(os.path.join(env.CONFIG_PATH, 'sysconfig.json'), 'w+').write(json.dumps(env.SYSTEM_CONFIG, indent=2))

    def __upload_latest(self, *args):
        list_of_files = glob.glob(f'{env.SCREENSHOTS_DIR}/*') + glob.glob(f'{env.VIDEOS_DIR}/*')
        latest_file = max(list_of_files, key=os.path.getctime)
        print(latest_file)
        upload_file(File(path=latest_file), keep=True)

    def _upload_latest(self, icon, item):
        self.__upload_latest()

    def _on_draw_after_task(self, icon, item):
        env.DRAW_AFTER_TASK = not item.checked
        env.SYSTEM_CONFIG['draw'] = env.DRAW_AFTER_TASK
        open(os.path.join(env.CONFIG_PATH, 'sysconfig.json'), 'w+').write(json.dumps(env.SYSTEM_CONFIG, indent=2))

    def _set_state(self, v):
        def inner(icon, item):
            env.SYSTEM_CONFIG['mode'] = v

            open(os.path.join(env.CONFIG_PATH, 'sysconfig.json'), 'w+').write(json.dumps(env.SYSTEM_CONFIG, indent=2))

        return inner

    def _get_state(self, v):
        def inner(item):
            return env.SYSTEM_CONFIG['mode'] == v

        return inner

    def exit_everything(self):
        _generate_cache()
        exit()

    def show_online_history(self):
        OnlineHistoryWindow.reopen_history_window()

    def show_history(self):
        HistoryWindow.reopen_history_window()

    def run(self):
        self.tray_icon.run_detached()


class OnlineHistoryWindow(Gtk.Window):
    ONLINE_HISTORY_WINDOW = None

    def __init__(self):
        super().__init__()
        grid = Gtk.Grid()

        self.set_icon_from_file(env.ICON_PATH)
        self.modify_bg(Gtk.StateType.NORMAL, Gdk.Color(65535, 65535, 65535))
        self.set_title("Online History")
        self.set_size_request(700, 800)

        sw = Gtk.ScrolledWindow()
        problem_files = []
        print(env.ONLINE_HISTORY.items())
        for index, item in enumerate(env.ONLINE_HISTORY.items()):
            file_name, data = item
            try:
                thumbnail = Gtk.Image.new_from_pixbuf(
                    GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        filename=data['icon_path'],
                        width=500,
                        height=300,
                        preserve_aspect_ratio=False
                    )
                )

                icon = Gtk.Image.new_from_pixbuf(
                    GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        filename=get_default_icon_path(data),
                        width=50,
                        height=50,
                        preserve_aspect_ratio=True
                    )
                )
            except:
                problem_files.append(file_name)
                traceback.print_exc()
                continue

            date = Gtk.Label(label=f"{data['place']} {data['type']}\n{data['date']}\n{file_name}")

            upload = Gtk.Button(label="Upload")
            if data['place'] == 'online':
                upload.set_sensitive(False)

            copy_url = Gtk.Button(label="Copy Url")

            upload.connect("clicked", self.on_upload, file_name, data, date, copy_url, icon)
            copy_url.connect("clicked", self.on_copy_url, file_name, data, date, upload)

            if data['place'] == 'local':
                copy_url.set_sensitive(False)

            thumbnail.set_size_request(500, 300)
            icon.set_size_request(50, 50)
            upload.set_size_request(70, 150)
            copy_url.set_size_request(70, 150)
            date.set_size_request(180, 150)
            grid.attach(thumbnail, 0, index * 2, 1, 2)
            grid.attach(icon, 1, index * 2, 1, 1)
            grid.attach(upload, 2, index * 2, 1, 1)
            grid.attach(copy_url, 3, index * 2, 1, 1)
            grid.attach(date, 1, index * 2 + 1, 3, 1)

        for problem_file in problem_files:
            del env.ONLINE_HISTORY[problem_file]

        self.connect("delete-event", self.on_rekt)
        self.connect("destroy", self.on_rekt)
        self.connect("drag-data-received", self.on_drag_and_drop)

        self.drag_dest_set_target_list(None)
        self.drag_dest_add_text_targets()

        sw.add(grid)
        self.add(sw)

        self.show_all()
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW = self

        # _clear_local_files_not_in_history()

    def on_drag_and_drop(self, wid, context, x, y, data, info, time):
        notify.send_notification("Uploading files...", '')
        file_paths = data.get_data().decode('utf-8').replace('file:///', '').split('\n')

        for file_path in file_paths:
            upload_file(File(path=f'/{file_path}'), keep=True)
        print(file_paths)

    def on_rekt(self, *kestring):
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW = None
        self.destroy()

    def on_upload(self, button, *data):
        notify_upload = NotificationBubble()
        notify_upload.send_notification('Uploading...', '')
        file_name, _, date, copy_button, icon = data
        new_name = upload_file(File(file_name))
        new_data = env.ONLINE_HISTORY[new_name]
        copy_button.set_sensitive(True)
        button.set_sensitive(False)
        icon.set_from_file(get_default_icon_path(new_data))
        date.set_label(f"{new_data['place']} {new_data['type']}\n{new_data['date']}\n{new_name}")

    def on_copy_url(self, button, *data):
        notify_copy = NotificationBubble()
        _, _, date, _ = data
        label = date.get_label()
        url = env.ONLINE_HISTORY[label.split('\n')[-1]]['url']
        copy(url)
        notify_copy.send_notification('Copied to clipboard', url, clickable=True)

    @staticmethod
    def destroy_window():
        print('destoy window')
        if OnlineHistoryWindow.ONLINE_HISTORY_WINDOW:
            print('destoying window')
            OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.destroy()
            OnlineHistoryWindow.ONLINE_HISTORY_WINDOW = None

    @staticmethod
    def initialize():
        print('initialize')
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW = OnlineHistoryWindow()
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.set_keep_above(True)
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.show()
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.hide()
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.show()
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.set_keep_above(True)
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.present()
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.set_keep_above(True)
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.set_keep_above(False)

    @staticmethod
    def refresh_window():
        print('refresh')
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW = OnlineHistoryWindow()
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.hide()
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.show()
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.set_keep_above(True)
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.present()
        OnlineHistoryWindow.ONLINE_HISTORY_WINDOW.set_keep_above(False)

    @staticmethod
    def reopen_history_window(*args):
        print('reopen_history_window')
        if env.FIRST_HISTORY_OPEN:
            _get_history()
            env.FIRST_HISTORY_OPEN = False
        OnlineHistoryWindow.destroy_window()
        OnlineHistoryWindow.initialize()


class HistoryWindow(Gtk.Window):
    HISTORY_WINDOW = None

    def __init__(self):
        super().__init__()
        grid = Gtk.Grid()

        self.set_icon_from_file(env.ICON_PATH)
        self.modify_bg(Gtk.StateType.NORMAL, Gdk.Color(65535, 65535, 65535))
        self.set_title("History")
        self.set_size_request(700, 800)

        sw = Gtk.ScrolledWindow()
        problem_files = []
        for index, item in enumerate(env.HISTORY.items()):
            file_name, data = item
            try:
                thumbnail = Gtk.Image.new_from_pixbuf(
                    GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        filename=data['icon_path'],
                        width=500,
                        height=300,
                        preserve_aspect_ratio=False
                    )
                )

                icon = Gtk.Image.new_from_pixbuf(
                    GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        filename=get_default_icon_path(data),
                        width=50,
                        height=50,
                        preserve_aspect_ratio=True
                    )
                )
            except:
                problem_files.append(file_name)
                traceback.print_exc()
                continue

            date = Gtk.Label(label=f"{data['place']} {data['type']}\n{data['date']}\n{file_name}")

            upload = Gtk.Button(label="Upload")
            if data['place'] == 'online':
                upload.set_sensitive(False)

            copy_url = Gtk.Button(label="Copy Url")

            upload.connect("clicked", self.on_upload, file_name, data, date, copy_url, icon)
            copy_url.connect("clicked", self.on_copy_url, file_name, data, date, upload)

            if data['place'] == 'local':
                copy_url.set_sensitive(False)

            thumbnail.set_size_request(500, 300)
            icon.set_size_request(50, 50)
            upload.set_size_request(70, 150)
            copy_url.set_size_request(70, 150)
            date.set_size_request(180, 150)
            grid.attach(thumbnail, 0, index * 2, 1, 2)
            grid.attach(icon, 1, index * 2, 1, 1)
            grid.attach(upload, 2, index * 2, 1, 1)
            grid.attach(copy_url, 3, index * 2, 1, 1)
            grid.attach(date, 1, index * 2 + 1, 3, 1)

        for problem_file in problem_files:
            del env.HISTORY[problem_file]

        self.connect("delete-event", self.on_rekt)
        self.connect("destroy", self.on_rekt)
        self.connect("drag-data-received", self.on_drag_and_drop)

        self.drag_dest_set_target_list(None)
        self.drag_dest_add_text_targets()

        sw.add(grid)
        self.add(sw)

        self.show_all()
        HistoryWindow.HISTORY_WINDOW = self

        # _clear_local_files_not_in_history()

    def on_drag_and_drop(self, wid, context, x, y, data, info, time):
        notify.send_notification("Uploading files...", '')
        file_paths = data.get_data().decode('utf-8').replace('file:///', '').split('\n')

        for file_path in file_paths:
            upload_file(File(path=f'/{file_path}'), keep=True)
        print(file_paths)

    def on_rekt(self, *kestring):
        HistoryWindow.HISTORY_WINDOW = None
        self.destroy()

    def on_upload(self, button, *data):
        notify_upload = NotificationBubble()
        notify_upload.send_notification('Uploading...', '')
        file_name, _, date, copy_button, icon = data
        new_name = upload_file(File(file_name))
        new_data = env.HISTORY[new_name]
        copy_button.set_sensitive(True)
        button.set_sensitive(False)
        icon.set_from_file(get_default_icon_path(new_data))
        date.set_label(f"{new_data['place']} {new_data['type']}\n{new_data['date']}\n{new_name}")

    def on_copy_url(self, button, *data):
        notify_copy = NotificationBubble()
        _, _, date, _ = data
        label = date.get_label()
        url = env.HISTORY[label.split('\n')[-1]]['url']
        copy(url)
        notify_copy.send_notification('Copied to clipboard', url, clickable=True)

    @staticmethod
    def destroy_window():
        print('destoy window')
        if HistoryWindow.HISTORY_WINDOW:
            print('destoying window')
            HistoryWindow.HISTORY_WINDOW.destroy()
            HistoryWindow.HISTORY_WINDOW = None

    @staticmethod
    def initialize():
        print('initialize')
        HistoryWindow.HISTORY_WINDOW = HistoryWindow()
        HistoryWindow.HISTORY_WINDOW.set_keep_above(True)
        HistoryWindow.HISTORY_WINDOW.show()
        HistoryWindow.HISTORY_WINDOW.hide()
        HistoryWindow.HISTORY_WINDOW.show()
        HistoryWindow.HISTORY_WINDOW.set_keep_above(True)
        HistoryWindow.HISTORY_WINDOW.present()
        HistoryWindow.HISTORY_WINDOW.set_keep_above(True)
        HistoryWindow.HISTORY_WINDOW.set_keep_above(False)

    @staticmethod
    def refresh_window():
        print('refresh')
        HistoryWindow.HISTORY_WINDOW = HistoryWindow()
        HistoryWindow.HISTORY_WINDOW.hide()
        HistoryWindow.HISTORY_WINDOW.show()
        HistoryWindow.HISTORY_WINDOW.set_keep_above(True)
        HistoryWindow.HISTORY_WINDOW.present()
        HistoryWindow.HISTORY_WINDOW.set_keep_above(False)

    @staticmethod
    def reopen_history_window(*args):
        print('reopen_history_window')
        if env.FIRST_HISTORY_OPEN:
            _get_history()
            env.FIRST_HISTORY_OPEN = False
        HistoryWindow.destroy_window()
        HistoryWindow.initialize()


class NotificationBubble(GObject.Object):
    def __init__(self):
        super().__init__()
        Notify.init("ShareX_yz")
        self.notification = None
        self.text = ''

    def send_notification(self, title, text, file_path_to_icon=env.ICON_PATH, clickable=False, action_callable=None):
        self.text = text
        self.notification = Notify.Notification.new(title, text, file_path_to_icon)
        if clickable:
            if action_callable:
                self.notification.add_action('clicked', 'Open', action_callable)
            else:
                self.notification.add_action('clicked', 'Open', self.go_to_link)
        self.notification.show()

    def go_to_link(self, *args):
        webbrowser.open(self.text)

    def close(self):
        self.notification.close()


notify = NotificationBubble()

tray_icon = TrayIcon()
tray_icon.run()

background = ShareXYZTool()


def on_press(key):
    try:
        env.KEY_PRESSED = key.char
        # print('Alphanumeric key pressed: {0} '.format(key.char))
    except AttributeError:
        env.KEY_PRESSED = key
        # print('special key pressed: {0}'.format(key))
    env.LATEST_KEY = env.KEY_PRESSED


def on_release(key):
    env.KEY_PRESSED = None
    if key == keyboard.Key.esc:
        print('ESC!')
    # print('Key released: {0}'.format(key))


with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    Gtk.main()


def encode_file_to_b64_string(file_path: str = "doc.png"):
    """
    Takes any file and encodes it into base64 string
    """
    with open(os.path.join(env.ICONS_DIR, file_path), "rb") as img_file:
        b64_string = base64.b64encode(img_file.read())
    print(b64_string)
