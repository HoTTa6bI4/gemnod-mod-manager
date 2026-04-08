import xml.etree.ElementTree
from dataclasses import dataclass
import queue
import requests
import os
import shutil
from hashlib import sha256
from zipfile import ZipFile, BadZipfile
from src.scripts.heroes_v_file_seeker import filehash
from xml.etree import ElementTree as ET
from typing import Optional


# As will be used below, a return value that is indicating artificial internal
# progress of any task
@dataclass
class Progress:
    passed: int
    total: int
    desc: str = 'Work'

    def percent(self):
        if self.total == 0:
            return 100.0
        return round(self.passed / self.total * 100, 2)


# def fileContentHash(abs_path):
#     if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
#         raise FileNotFoundError(f"File '{abs_path}' not found!")
#     with open(abs_path, 'rb') as file:
#         return sha256(file.read()).hexdigest()


class ModManager:
    class ManagementError(Exception):
        pass

    class SupportedMod:

        class ModVersion:

            def __init__(self, version_name: str, download_url: str,
                         manifest: dict[str, str],
                         temporary_storage="./",
                         installation_folder="./"):
                if download_url is None:
                    raise ModManager.ManagementError("Donwload URL missed") from ValueError
                self.name = version_name
                self.download_url = download_url
                self.temporary_storage = temporary_storage
                self.destination = installation_folder
                self.manifest = manifest
                self.package_path = ''
                self.package_namelist = []
                self.__downloaded = False
                self.__installed = False
                self.__enabled = False

            def __eq__(self, other):
                if not isinstance(other, ModManager.SupportedMod.ModVersion):
                    return NotImplemented
                if self.name != other.name:
                    return False
                if self.download_url != other.download_url:
                    return False
                for file, hash in self.manifest.keys():
                    if other.manifest.get(file) != hash:
                        return False
                return True

            def __ne__(self, other):
                return not self.__eq__(other)

            def isDownloaded(self):
                return self.__enabled

            def isInstalled(self):
                return self.__installed

            def isEnabled(self):
                return self.__enabled

            def isDisabled(self):
                return not self.__enabled and self.__installed

            def consistencyInFolder(self, folder):
                if len(self.manifest.keys()) == 0:
                    return 0
                matches = 0
                entries = len(self.manifest)
                for rel_path, standard_hash in self.manifest.items():
                    abs_path = os.path.join(folder, rel_path)
                    if os.path.exists(abs_path):
                        # Only files are counted
                        if filehash(abs_path) == standard_hash:
                            matches += 1
                if entries == 0:
                    return 0
                return matches / entries

            def updateState(self):
                # Check installation folder

                if self.consistencyInFolder(self.destination) == 1:
                    self.__downloaded = True
                    self.__enabled = True
                    self.__installed = True
                # todo: add 'installed but modified' state of mod version
                # elif consistency >= 0.95:
                #     pass
                else:
                    if self.consistencyInFolder(self.temporary_storage):
                        self.__downloaded = True
                        self.__installed = False
                        self.__enabled = False
                return self.__installed, self.__downloaded, self.__enabled
 
            def download(self):
                self.updateState()
                if not self.__downloaded:
                    try:
                        response = requests.get(self.download_url, timeout=10, stream=True)
                    except requests.RequestException:
                        raise
                    else:
                        if response.status_code == 200:
                            temporary_file_name = self.name + '.bin'

                            # Get file name from response metadata (HTTP headers)
                            if 'content-disposition' in response.headers.keys():
                                content_disposition = response.headers.get('content-disposition')
                                if 'attachment' in content_disposition or 'inline' in content_disposition:
                                    if 'filename=' in content_disposition:
                                        temporary_file_name = content_disposition.split('filename=')[1].strip('\'\"')
                            elif 'application/' in response.headers.get('content-type'):
                                temporary_file_name = self.download_url.split('/')[-1]

                            # Save downloaded file to local
                            file_size = int(response.headers.get('content-length'))
                            written = 0
                            yield Progress(written, file_size, 'Downloading')

                            self.package_path = os.path.join(self.temporary_storage, temporary_file_name)
                            with open(self.package_path, 'wb') as temporary_file:
                                for chunk in response.iter_content(chunk_size=262144):  # iter by 256 kb
                                    written += len(chunk)
                                    temporary_file.write(chunk)
                                    yield Progress(written, file_size, 'Downloading')
                                self.__downloaded = True
                        else:
                            raise ConnectionError(f"Failed to download mod version: {self.download_url}"
                                                  f"(ERROR: {response.status_code})")

            def install(self):
                self.updateState()
                # If no package downloaded, download it
                if not self.__downloaded:
                    for progress in self.download():
                        yield progress
                # If already installed, nothing to do
                if not self.__installed:
                    file_size = int(os.path.getsize(self.package_path))
                    # Unpack (install) downloaded package
                    yield Progress(0, file_size, 'Unpacking')
                    try:
                        with ZipFile(self.package_path, 'r') as installed_package:
                            self.package_namelist = installed_package.namelist()
                            installed_package.extractall(self.destination)
                        yield Progress(file_size, file_size, 'Unpacked')
                        self.__installed = True
                        self.__enabled = True
                    except BadZipfile as er:
                        raise ModManager.ManagementError("Invalid package provided : " + self.package_path) from er
                elif not self.__enabled:
                    for _ in self.enable():
                        yield _

            def _movePackages(self, src, dst):
                self.updateState()

                objects_total = len(self.package_namelist)
                objects_moved = 0
                dirs_total = 0
                dirs_removed = 0
                moved_packages = []

                for rel_path in self.package_namelist:
                    old_path = os.path.join(src, rel_path)
                    new_path = os.path.join(dst, rel_path)
                    objects_moved += 1
                    if os.path.isdir(old_path):
                        dirs_total += 1
                        os.makedirs(new_path, exist_ok=True)
                    elif os.path.isfile(old_path):
                        try:
                            os.replace(old_path, new_path)
                            moved_packages.append((old_path, new_path))
                        # If any errors,
                        # Rollback all moved files
                        except (OSError, PermissionError) as exc:
                            for old, new in moved_packages:
                                os.replace(new, old)
                            raise ModManager.ManagementError(f"An error occurred while trying "
                                                             f"to operate with '{old_path}'."
                                                             f"Close all applications that might "
                                                             f"use this file") from exc

                    yield Progress(objects_moved, objects_total, 'Disabling')

                for rel_path in reversed(self.package_namelist):
                    old_path = os.path.join(src, rel_path)
                    if os.path.isdir(old_path):
                        if len(os.listdir(old_path)) == 0:
                            os.rmdir(old_path)
                        dirs_removed += 1
                        yield Progress(dirs_removed, dirs_total, 'Cleaning up')

            def disable(self):
                if self.__enabled:
                    self.__enabled = False
                    for _ in self._movePackages(self.destination, self.temporary_storage):
                        yield _

            def enable(self):
                if self.__disabled:
                    self.__enabled = True
                    for _ in self._movePackages(self.temporary_storage, self.destination):
                        yield _

            def uninstall(self):
                self.updateState()
                if self.__installed:
                    self.__installed = False
                    objects_total = len(self.package_namelist) + 1
                    objects_removed = 0
                    cleaned_dir = self.temporary_storage if not self.__enabled else self.destination
                    for rel_path in reversed(self.package_namelist):
                        abs_path = os.path.join(cleaned_dir, rel_path)
                        objects_removed += 1
                        yield Progress(objects_removed, objects_total, 'Uninstalling')
                        # If any file deleted someway, it doesn't matter for uninstallation
                        if not os.path.exists(abs_path):
                            continue
                        if os.path.isfile(abs_path):
                            os.remove(abs_path)
                        else:
                            shutil.rmtree(abs_path, ignore_errors=True)
                    if os.path.exists(self.package_path):
                        os.remove(self.package_path)
                    self.__downloaded = False
                    yield Progress(objects_total, objects_total, 'Uninstalling')

        def __init__(self, versions: list[ModVersion],
                     name: str = '', description: str = '', homepage: str = ''):
            self.versions = versions
            self.name = name
            self.desc = description
            self.home_page = homepage

        def getAllVersions(self):
            return self.versions

        def getVersion(self, version: str | int):
            index = None
            if type(version) is int:
                index = version
            elif type(version) is str:
                for i, elem in enum(self.versions):
                    if elem.name == version:
                        index = i
                        break
            else:
                raise TypeError(f"Invalid object type '{type(version)}."
                                f" 'int' index, or 'str' object name, or 'ModManager.SupportedMod.ModVersion' instance"
                                f" expected")
            return self.versions[index]

        def addVersion(self, version: ModVersion):
            self.versions.append(version)

        def removeVersion(self, version: ModVersion | str | int):
            if type(version) is ModManager.SupportedMod.ModVersion:
                version = version.name
            self.versions.remove(self.getVersion(version))

        def getInstalledVersion(self):
            for version in self.versions:
                version.updateInstalled()
                if version.isInstalled():
                    return version
            return None

        def getLatestVersion(self):
            return self.versions[0]

        def install(self, version: Optional[ModVersion] = None):
            if version is None:
                version = self.getLatestVersion()
            current = self.getInstalledVersion()
            if current == version:
                yield Progress(0, 0, 'Installed already')
            else:
                for progress in current.disable():
                    yield progress

            for progress in version.install():
                yield progress

        def uninstall(self):
            installed = self.getInstalledVersion()
            if installed is None:
                raise ModManager.ManagementError('Uninstallation impossible: mod is not installed')

        def enable(self):
            installed = self.getInstalledVersion()
            if installed is None:
                raise ModManager.ManagementError('Enabling is impossible: mod is not installed')
            elif installed is not None:
                for progress in installed.enable():
                    yield progress

        def disable(self):
            installed = self.getInstalledVersion()
            if installed is None:
                raise ModManager.ManagementError('Disabling is impossible: mod is not installed')
            elif installed is not None:
                for progress in installed.disable():
                    yield progress

        def update(self):
            latest = self.getLatestVersion()
            current = self.getInstalledVersion()
            if current is None:
                for progress in latest.install():
                    yield progress
            elif latest != current:
                for progress in current.uninstall():
                    yield progress
                for progress in latest.install():
                    yield progress

        def updateTo(self, version: ModVersion | str | int):
            if type(version) is ModManager.SupportedMod.ModVersion:
                target = version
            else:
                target = self.getVersion(version)
            current = self.getInstalledVersion()
            if current is not None:
                for progress in current.uninstall():
                    yield progress
            for progress in target.install():
                yield progress

    def __init__(self, mod_db_url):
        self.url = mod_db_url
        self.mods = {}

    def getAllMods(self):
        return self.mods

    def getMod(self, mod_name: str):
        return self.mods.get(mod_name)

    def addMod(self, mod: SupportedMod):
        if mod.name in self.mods.keys():
            raise ModManager.ManagementError(f"Mod '{mod.name}' already exists!")
        self.mods[mod.name] = mod

    def removeMod(self, mod: SupportedMod | str):
        if type(mod) is str:
            name = mod
        elif type(mod) is ModManager.SupportedMod:
            name = mod.name
        else:
            raise TypeError(f"Invalid object type '{type(mod)}."
                            f" 'str' object name or 'ModManager.SupportedMod' instance"
                            f" expected")
        return self.mods.pop(name)

    # I suppose different possible ways to store mods DB.
    # Currently, XML is enough
    def parseModDB(self):
        try:
            response = requests.get(self.url, timeout=10, allow_redirects=False)
        except requests.RequestException:
            raise
        else:
            if response.status_code == 200:
                try:
                    db_root = ET.fromstring(response.content)
                except xml.etree.ElementTree.ParseError:
                    raise
                else:
                    for mod_info in db_root.findall("ModInfo"):
                        name = mod_info.attrib.get('name')
                        desc = mod_info.find('DetailedDesc').text
                        home_page = mod_info.find('HomePage').attrib.get('url')
                        mod = ModManager.SupportedMod([], name, desc, home_page)
                        for version in mod_info.findall("Versions/Version"):
                            vname = version.attrib.get("v")
                            download_url = version.find("Download").attrib.get("url")
                            manifest = {}
                            for item in version.findall("Manifest/Item"):
                                file_rel_path = item.attrib.get('ref')
                                file_hash = item.attrib.get('hash')
                                manifest[file_rel_path] = file_hash
                            mod.addVersion(ModManager.SupportedMod.ModVersion(vname, download_url, manifest))
                        self.addMod(mod)

            else:
                raise ModManager.ManagementError(f"Failed to get Mods DB from remote server "
                                                 f"(ERROR: {response.status_code})")
        return self


if __name__ == "__main__":
    manager = ModManager("http://localhost:8080/Gems.xml")
    manager.parseModDB()
    print(f"Removed {manager.removeMod('Gemnod').name}")
