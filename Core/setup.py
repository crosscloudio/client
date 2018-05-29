# pylint: skip-file
import os
import sys
import shutil
import semver
import cx_Freeze
import certifi

from cx_Freeze import setup, Executable, Freezer

BUILD_QT_GUI = False

additional_includes = []
additional_include_files = []

base = None
packages = ['cryptography']
if sys.platform == 'win32':
    base = 'Win32GUI'
    import comtypes.client

    # generate interfaces
    comtypes.client.CreateObject('WScript.Shell')
    packages.append('comtypes.gen')

    additional_includes.extend([  # this is needed so that pywintypes is included and keyring is
        # working. ARRRRRRRRRRRRRRRRR. As soon as keyring can use
                                  # win32ctypes again this might be removed
                                  'win32api',
                                  'win32timezone']
                               )


# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {'includes': [
                                  # Keyring expects all backends to be delivered allways
                                  'keyring.backends.OS_X',
                                  'keyring.backends.Windows',
                                  'keyring.backends.SecretService',
                                  'keyring.backends.kwallet',
                                  'six',
                                  'raven.processors',
                                  'idna.idnadata',
                                  'packaging',
                                  'packaging.version',
                                  'packaging.specifiers',
                                  'packaging.requirements',
                                  'certifi'] + additional_includes,
                     'packages': packages,
                     'excludes': [
                         'tkinter',
                         'sphinx',
                         # win32ctypes as an optional dependency of keyring breaks the binary.
                         # In theory it would work, but pycparser, which is an depedency of cffi
                         # has not included the current version of ply(https://github.com/dabeaz/ply/issues/97)
                         'win32ctypes'
],
    'include_msvcr': True,
    'zip_includes': [],
    # 'optimize': 2,  # removes all docstrings and asserts
    # this breakes keyring and maybe other packages

    'include_files': [certifi.where(),
                      'profile.json',
                      'cc/assets/findersync.zip',
                      'cc/assets/'] + additional_include_files,
    # this makes the CONSTANTS module available in the build with the version constant
    'constants': 'version="development"'
}

if 'CI' in os.environ:
    # this runs in a ci environment, we set the version to the one set in the env
    build_exe_options['constants'] = 'version="{}"'.format(os.environ['VERSION'])

    version_info = semver.parse_version_info(os.environ['VERSION'])
    print(version_info)
    profile_name = version_info.prerelease
    print(profile_name)
    profile = os.path.join('..', 'build-configs', '{}.json'.format(profile_name))
    assert os.path.exists(profile)
    print(profile)
    shutil.copy(profile, os.path.join('.', 'profile.json'))
    assert os.path.exists(os.path.join('.', 'profile.json'))

if __name__ == '__main__':
    import sys

    executables = []

    if BUILD_QT_GUI:
        executables.append(
            Executable('cc/qt_client.py', base=base, targetName='crosscloud.exe',
                       icon='../electron-ui/assets/icon.ico'))
    else:
        targe_name = 'CrossCloudSync'
        if os.name == 'nt':
            targe_name += '.exe'
        executables.append(Executable('cc/client.py'))
        executables.append(Executable('cc/ipc_core.py', targetName=targe_name,
                                      icon='../electron-ui/assets/icon.ico'))

    setup(name='crosscloud-client',
          version='1.0',
          options={'build_exe': build_exe_options
                   },
          executables=executables)
