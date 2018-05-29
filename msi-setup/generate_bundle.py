from xml.etree import ElementTree as ET
import os.path
import semver
from win32api import GetShortPathName

import sys

import re


def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


class WixSetup:
    def __init__(self, path, version):
        self.path = path

        self.component_list = []
        self.current_dir_id = 0
        self.current_file_id = 0

        com_subtree = [
            ET.Element('Class', {
                'Id ': '{C2B9C7C6-A5C1-49FD-9808-F03F2F697F6C}',
                'Context ': 'InprocServer32',
                'Description ': 'CrossCloud.OverlayUnSyncedExt Class',
                'ThreadingModel ': 'apartment'}),
            ET.Element('Class', {
                'Id ': '{FD67F358-021E-49D1-933A-D1D50E59F34A}',
                'Context ': 'InprocServer32',
                'Description ': 'CrossCloud.FileContextMenuExt Class',
                'ThreadingModel ': 'apartment'}),
            ET.Element('Class', {
                'Id ': '{75EC2AF1-C1A5-4CCD-96DC-2BB9FB2FE7F1}',
                'Context ': 'InprocServer32',
                'Description ': 'CrossCloud.OverlaySyncedExt Class',
                'ThreadingModel ': 'apartment'})]

        shelxt_subtree = [
            ET.Element('RegistryValue',
                       {'Root': 'HKCR',
                        'Key': r'*\shellex\ContextMenuHandlers\{'
                               r'FD67F358-021E-49D1-933A-D1D50E59F34A}',
                        'Value': 'CrossCloud.FileContextMenuExt',
                        'Type': 'string', 'Action': 'write'}),
            ET.Element('RegistryValue',
                       {'Root': 'HKCR',
                        'Key': r'Folder\shellex\ContextMenuHandlers\{'
                               r'FD67F358-021E-49D1-933A-D1D50E59F34A}',
                        'Value': 'CrossCloud.FileContextMenuExt',
                        'Type': 'string', 'Action': 'write'}),
            # this needs admin priviledges :(
            # ET.Element('RegistryValue',
            #            {'Root': 'HKLM',
            #             'Key': r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer'
            #                    r'\ShellIconOverlayIdentifiers\   CrossCloudSynced',
            #             'Value': '{75EC2AF1-C1A5-4CCD-96DC-2BB9FB2FE7F1}',
            #             'Type': 'string', 'Action': 'write'}),
            # ET.Element('RegistryValue',
            #            {'Root': 'HKLM',
            #             'Key': r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer'
            #                    r'\ShellIconOverlayIdentifiers\   CrossCloudUnSynced',
            #             'Value': '{C2B9C7C6-A5C1-49FD-9808-F03F2F697F6C}',
            #             'Type': 'string', 'Action': 'write'})
        ]

        shortcuts = [ET.Element('Shortcut',
                                {'Id': 'ExeShortcut', 'Directory': 'ProgramMenuFolder',
                                 'Name': 'CrossCloud',
                                 'Advertise': 'no',
                                 'WorkingDirectory': 'WORKINGDIRECTORY',
                                 'Icon': 'CrossCloudIcon', 'IconIndex': '0'}),
                     ET.Element('Shortcut',
                                {'Id': 'DesktopShortcut', 'Directory': 'DesktopFolder',
                                 'Name': 'CrossCloud',
                                 'WorkingDirectory': 'WORKINGDIRECTORY',
                                 'Advertise': 'no',
                                 'Icon': 'CrossCloudIcon', 'IconIndex': '0'}),
                     ]

        reg_key = ET.Element('RegistryKey',
                             {'Root': "HKCU", 'Key': "Software\CrossCloud\CrossCloud"})
        ET.SubElement(reg_key, 'RegistryValue',
                      {'Name': "Version", 'Value': version, 'Type': "string",
                       'KeyPath': "yes"})

        #
        # Id="DesktopShortcut" Directory="DesktopFolder" Name="CrossCloud" Advertise="no"
        #          Icon="CrossCloudIcon" IconIndex="0"
        # Id="StartupShortcut" Directory="StartupFolder" Name="CrossCloud" Advertise="no"
        #          Icon="CrossCloudIcon" IconIndex="0"


        self.extra_childs = {'CCShellExt_x64.dll': com_subtree,
                             'crosscloud.exe': shortcuts}
        self.extra_siblings = {'CCShellExt_x64.dll': shelxt_subtree,
                               'crosscloud.exe': [reg_key]}
        self.guid = {'crosscloud.exe': 'a6f65f04-e89f-4c70-aedd-6f721eadaf99'}
        self.file_id = {'crosscloud.exe': 'cc_main'}
        self.component_list.append('CrossCloudAutostart')
        self.component_list.append('RemoveExplorerSidebar')
        self.folder_references = ['DesktopFolder', 'ProgramMenuFolder']

    def generate_components_from_path(self, element, path):
        for file_name in os.listdir(path):
            full_path = os.path.join(path, file_name)
            print(full_path)

            if os.path.isdir(full_path):
                dir_elm = ET.SubElement(element, "Directory",
                                        {'Name': file_name,
                                         'Id': 'dirid{}'.format(self.current_dir_id)})
                self.current_dir_id += 1
                self.generate_components_from_path(dir_elm, full_path)
            else:
                comp_id = 'comp{}'.format(len(self.component_list))
                self.component_list.append(comp_id)
                component_elm = ET.SubElement(element, "Component",
                                              {'Id': comp_id, 'Win64': 'yes'})
                file_elm = ET.SubElement(component_elm, "File",
                                         {'Id': 'fileid{}'.format(self.current_file_id),
                                          'Name': file_name,
                                          'Source': GetShortPathName(full_path)[4:],
                                          'DiskId': '1'})
                self.current_file_id += 1
                if file_name in self.guid:
                    component_elm.attrib['Guid'] = self.guid[file_name]
                else:
                    file_elm.attrib['KeyPath'] = 'yes'

                if file_name in self.file_id:
                    file_elm.attrib['Id'] = self.file_id[file_name]

                if file_name.endswith('.dll') or file_name.endswith('.exe'):
                    file_elm.attrib['Checksum'] = 'yes'

                if file_name.endswith('.dll'):
                    file_elm.attrib['ProcessorArchitecture'] = 'x64'

                if file_name in self.extra_childs:
                    file_elm.extend(self.extra_childs[file_name])

                if file_name in self.extra_siblings:
                    component_elm.extend(self.extra_siblings[file_name])

    def generate_bundle(self, path):
        root = ET.Element("Include")

        dir_path = ET.SubElement(root, "Directory",
                                 {'Id': 'TARGETDIR', 'Name': 'SourceDir'})
        dir_path = ET.SubElement(dir_path, "Directory",
                                 {'Id': 'ProgramFiles64Folder', 'Name': 'PFiles'})
        dir_path = ET.SubElement(dir_path, "Directory",
                                 {'Id': 'APPLICATIONFOLDER', 'Name': 'CrossCloud'})

        long_path = "\\\\?\\"  + os.path.abspath(path)
        self.generate_components_from_path(dir_path, long_path)

        for folder in self.folder_references:
            ET.SubElement(dir_path, "Directory", {'Id': folder})

        feature = ET.SubElement(root, 'Feature', {'Id': "DefaultFeature", 'Level': "1"})
        for component in self.component_list:
            ET.SubElement(feature, 'ComponentRef', {'Id': component})

        return root

    def bundle(self):
        element = self.generate_bundle(self.path)
        indent(element)
        f_out = open('bundle.wxi', 'wb')

        ET.ElementTree(element).write(f_out, encoding='utf-8')


def set_version(windows_version, version, wxs='CrossCloud.wxs'):
    et = open(wxs)
    new = re.sub(r'\ Version=".*"', ' Version="{}"'.format(windows_version), et.read())
    new = re.sub(r'\ Comments=".*"', ' Comments="Version: {}"'.format(version), new)
    et.close()
    et = open(wxs, 'w')
    et.write(new)
    et.close()


def build_windows_version(version, build_version):
    """Create a windows MSI compatible version string from the given semver string.
    
    1.0.0-client+commit -> 1.0.0.374837
    
    The 4th part in the windows version number will be ignored. Updates will only be triggered 
    if the first three change (see https://msdn.microsoft.com/en-us/library/windows/desktop/aa370859(v=vs.85).aspx)
    """
    version_info = semver.parse_version_info(version)
    return ".".join(str(x) for x in [version_info.major,
                                     version_info.minor,
                                     version_info.patch,
                                     build_version])


if __name__ == "__main__":
    path = sys.argv[1]
    version = os.environ['VERSION']
    build_version = os.environ.get('CI_PIPELINE_ID', 1337)
    win_version_string = build_windows_version(version, build_version)
    set_version(win_version_string, version)
    setup = WixSetup(path, win_version_string)
    setup.bundle()
