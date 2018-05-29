
import gitlab
import semver
import io
import zipfile
import posixpath
import os


from fabric.api import *
from fabric.operations import put, reboot
from fabric.contrib import files


GITLAB_PROJECT_ID = 35
UPDATE_SERVER = 'update-2.crosscloud.me'
UPDATE_SERVER_PATH = '/srv/updates/update-server/channels/'

gl = gitlab.Gitlab('https://gitlab.crosscloud.me/', 'hfxTfV8xFjT3Sz8HUBcc')

env.hosts = [UPDATE_SERVER]

def mac_filenames(version):
    return ['electron-ui/build/dist/crosscloud-{}.dmg'.format(version),
        'electron-ui/build/dist/crosscloud-{}-mac.zip'.format(version)]

def win_filenames(version):
    return ['msi-setup/crosscloud-x64-{}.msi'.format(version)]

def  download_from_gitlab(build_id):
    """ downloads a release from gitlab """
    build = gl.project_builds.get(build_id, project_id=GITLAB_PROJECT_ID)
    print('downloading install files from gitlab')
    f_out = io.BytesIO()
    build.artifacts(streamed=True, action=f_out.write)
    f_out.seek(0)
    artifact = zipfile.ZipFile(f_out)

    # check if it is a windows or a mac build
    if 'msi-setup/.versioninfo' in artifact.namelist():
        # the msi build directory exists only for windows builds
        versionfilename = 'msi-setup/.versioninfo'
        platform = 'win32_x64'
        version = io.TextIOWrapper(artifact.open(versionfilename)).read().strip()
        filenames = win_filenames(version)
    elif 'electron-ui/build/dist/.versioninfo' in artifact.namelist():
        # this is a mac build
        versionfilename = 'electron-ui/build/dist/.versioninfo'
        platform = 'darwin_x64'
        version = io.TextIOWrapper(artifact.open(versionfilename)).read().strip()
        filenames = mac_filenames(version)
    else:
        raise ValueError('No version info found')

    versionfile = io.StringIO(version)
    versionfile.filename = '.versioninfo'

    files = []
    for filename in filenames:
        file_obj = io.BytesIO(artifact.open(filename).read())
        file_obj.filename = posixpath.basename(filename)
        files.append(file_obj)
    
    files.append(version_file)

    print('version {} for platform {}'.format(version, platform))
    return version, platform, files

def upload_files(path, files):
    run('mkdir -p {}'.format(path))
    for file_obj in files:
        put(file_obj, remote_path=posixpath.join(path, file_obj.filename))

def link_release(update_path, filename, version):
    link = filename.replace(version, 'latest')
    run('rm -f {}'.format(posixpath.join(update_path, link)))
    run('ln -s {} {}'.format(posixpath.join(update_path, filename), posixpath.join(update_path, link)))


def release_it(version, platform, files):
    print('uploading {} for {}'.format(version, platform))
    channel = semver.parse(version)['prerelease']
    update_path = posixpath.join(UPDATE_SERVER_PATH, channel, platform)

    upload_files(update_path, files)
    link_release(update_path, posixpath.basename(files[0].filename), version)

def upload_release(build_number):
    print("Preparing upload of the release with the build number {}".format(build_number))
    version, platform, files = download_from_gitlab(build_number)
    release_it(version, platform, files)

def upload_release_ci():
    env.key = os.environ['SSH_KEY']
    env.user = 'master-builds'
    version, platform, files = use_ci_files('win32_x64')
    release_it(version, platform, files)
    version, platform, files = use_ci_files('darwin_x64')
    release_it(version, platform, files)


def use_ci_files(platform):
    version = os.environ['CI_COMMIT_REF_NAME']
    assert version[0] == 'v'
    version = version[1:]

    version_file = io.StringIO(version)
    version_file.filename = '.versioninfo'
    files = []
    
    if platform == 'win32_x64':
        filenames = win_filenames(version)
    elif platform == 'darwin_x64':
        filenames = mac_filenames(version)

    for filename in filenames:
        f_in=open(os.path.join(os.environ['CI_PROJECT_DIR'], filename), 'rb')
        f_in.filename = posixpath.basename(filename)
        files.append(f_in)

    files.append(version_file)

    return version, platform, files

        

    
    


