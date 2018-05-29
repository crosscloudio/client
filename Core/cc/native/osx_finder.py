"""
Module to help handling FinderSync extension.
"""
import plistlib
import shutil
import zipfile
from contextlib import suppress

import os
import logging
import subprocess
from threading import Thread

import time
from pkg_resources import resource_filename


from cc import config

logger = logging.getLogger(__name__)


def init_findersync():
    """ registers finder sync extension """
    init_thread = Thread(target=_init_internal)
    init_thread.start()


# noinspection PyBroadException
# pylint: disable=broad-except
def _init_internal():
    """ """
    try:
        # unzip file
        zipped_file = resource_filename('cc.resources', 'findersync.zip')
        ext_dir = os.path.join(config.config_dir, 'findersync')
        ext_app = os.path.join(ext_dir, 'CrossCloud.app')

        need_to_install = False
        if not os.path.exists(ext_app):
            need_to_install = True
        else:
            # reading currently installed version
            ext_app_plist = os.path.join(ext_app, 'Contents', 'Info.plist')

            # opening currently installed plist file
            with open(ext_app_plist, 'rb') as installed_plist:
                plist_dict = plistlib.load(installed_plist)
                installed_version = plist_dict.get('CFBundleShortVersionString', None)
                logger.debug('installed version %s', installed_version)

            # opening plist of zipped extension
            with zipfile.ZipFile(zipped_file, 'r') as my_extension_zip:
                # opening file in zip
                plist_file = my_extension_zip.open(os.path.join(
                    'CrossCloud.app', 'Contents', 'Info.plist'))

                # reading content of file (seek no supported by zipfile)
                plist_data = plist_file.read()

                # parsing plist file
                plist_dict = plistlib.loads(plist_data)
                my_version = plist_dict.get('CFBundleShortVersionString', None)
                logger.debug('new version: %s', my_version)

            # checking if versions match
            if my_version is None or installed_version is None:
                need_to_install = False
            elif my_version != installed_version:
                need_to_install = True

        # if we need to install -> do it
        if need_to_install:
            logger.debug('need to install new extension')
            # removing old
            with suppress(OSError):
                shutil.rmtree(ext_app)

            # extracting new
            subprocess.call(['unzip', zipped_file, '-d', ext_dir],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # execute app
        subprocess.Popen(['open', '-a', ext_app])

        # wait for app to start
        time.sleep(5)

        # enable plugin (first char is a '+' if enabled)
        output = u'-'
        num_trials = 0
        while not output.startswith('+') and num_trials < 60:
            os.system('pluginkit -e use -i crosscloud.ui.FinderSync')
            status_cmd = "pluginkit -m -ADv -i crosscloud.ui.FinderSync"
            output = subprocess.check_output(status_cmd, shell=True)
            output = output.decode(('utf-8'))

            num_trials += 1
            time.sleep(1)

    except Exception:
        logger.exception('error while initializing finder sync extension')
