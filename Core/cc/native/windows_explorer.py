"""Module to help creating explorer Quick Access items."""
import sys
import ctypes
import logging
import os.path
import platform
import winreg

import comtypes
import comtypes.client

from cc import config

logger = logging.getLogger(__name__)

if hasattr(sys, 'frozen'):
    ICON = sys.executable
else:
    ICON = ""

CSP_NAME = "CrossCloud"
CSP_ID = '{E7748DA5-81E7-4753-A5BA-C7C42E17A1C7}'

DESKTOP_INI = """
[.ShellClassInfo]
ConfirmFileOp=1
InfoTip=Syncs your Cloud Storages
IconFile={}
IconIndex=0
"""

HKCU = winreg.HKEY_CURRENT_USER
VALUES = \
    [(HKCU, r'Software\Classes\CLSID\{}'.format(CSP_ID), None, winreg.REG_SZ, CSP_NAME),
     (HKCU, r'Software\Classes\CLSID\{}\DefaultIcon'.format(CSP_ID), None,
      winreg.REG_EXPAND_SZ, ICON),
     (HKCU, r'Software\Classes\CLSID\{}'.format(CSP_ID), 'System.IsPinnedToNameSpaceTree',
      winreg.REG_DWORD, 0x1),
     (HKCU, r'Software\Classes\CLSID\{}'.format(CSP_ID), 'SortOrderIndex',
      winreg.REG_DWORD, 0x42),
     (HKCU, r'Software\Classes\CLSID\{}\InProcServer32'.format(CSP_ID), None,
      winreg.REG_EXPAND_SZ, r'%%systemroot%%\system32\shell32.dll'),
     (HKCU, r'Software\Classes\CLSID\{}\Instance'.format(CSP_ID), 'CLSID', winreg.REG_SZ,
      '{0E5AAE11-A475-4c5b-AB00-C66DE400274E}'),
     (HKCU, r'Software\Classes\CLSID\{}\Instance\InitPropertyBag'.format(CSP_ID),
      'Attributes', winreg.REG_DWORD, 0x11),
     (HKCU, r'Software\Classes\CLSID\{}\Instance\InitPropertyBag'.format(CSP_ID),
      'TargetFolderPath', winreg.REG_EXPAND_SZ, config.sync_root),
     (HKCU, r'Software\Classes\CLSID\{}\ShellFolder'.format(CSP_ID), 'FolderValueFlags',
      winreg.REG_DWORD, 0x28),
     (HKCU, r'Software\Classes\CLSID\{}\ShellFolder'.format(CSP_ID), 'Attributes',
      winreg.REG_DWORD, 0xF080004D),
     (HKCU,
      r'Software\Microsoft\Windows\CurrentVersion\Explorer\Desktop\NameSpace\{}'.format(
          CSP_ID), None, winreg.REG_SZ, CSP_NAME),
     (HKCU,
      r'Software\Microsoft\Windows\CurrentVersion\Explorer\HideDesktopIcons'
      r'\NewStartPanel',
      CSP_ID, winreg.REG_DWORD, 0x1)]


def _win10_register():
    """Register a Cloud Storage Provider extension in Explorer.

    More information:
    https://msdn.microsoft.com/en-us/library/windows/desktop/dn889934.aspx?f=255&MSPPError=-2147217396
    """
    for basekey, subkey, name, type_, value in VALUES:
        key = winreg.CreateKeyEx(basekey, subkey, 0,
                                 access=winreg.KEY_WOW64_64KEY | winreg.KEY_WRITE)
        winreg.SetValueEx(key, name, 0, type_, value)


def _win_create_quick_launch():
    """Create a quicklaunch icon for windows, 7,8,8.1."""
    # pylint: disable=no-name-in-module,import-error
    from comtypes.gen.IWshRuntimeLibrary import IWshShortcut
    comtypes.CoInitializeEx()
    shell = comtypes.client.CreateObject('WScript.Shell')
    shortcut = shell.CreateShortCut(os.path.expanduser(r'~\Links\CrossCloud.lnk'))
    shortcut = shortcut.QueryInterface(IWshShortcut)
    shortcut.TargetPath = config.sync_root
    # shortcut.Icon = ICON
    try:
        shortcut.Save()
    except comtypes.COMError:
        logger.exception('Cant create shortcut')


def register_quick_access():
    """Register the quick access icon depending on the windows version."""
    create_desktop_ini()

    win_ver, _, _, _ = platform.win32_ver()
    if win_ver == '10':
        _win10_register()
    else:
        _win_create_quick_launch()


def create_desktop_ini():
    """Create a desktop ini and sets the icon to crosscloud the icon.

    More information:
    https://msdn.microsoft.com/en-us/library/windows/desktop/cc144102(v=vs.85).aspx
    https://hwiegman.home.xs4all.nl/desktopini.html
    """
    ini_path = os.path.join(config.sync_root, 'desktop.ini')
    if os.path.isfile(ini_path):
        # if exists everything is done
        return

    with open(ini_path, 'w') as ini:
        ini.write(DESKTOP_INI.format(ICON))

    # PathMakeSystemFolder
    ctypes.windll.shlwapi.PathMakeSystemFolderW(config.sync_root)


if __name__ == '__main__':
    _win_create_quick_launch()
    register_quick_access()
