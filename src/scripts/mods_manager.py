from dataclasses import dataclass
import requests
import os
import shutil
from hashlib import sha256
from zipfile import ZipFile, BadZipfile
from heroes_v_file_seeker import filehash


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
                         download_folder="./",
                         installation_folder="./"):
                if download_url is None:
                    raise ModManager.ManagementError("Donwload URL missed") from ValueError
                self.name = version_name
                self.download_url = download_url
                self.temporary_storage = download_folder
                self.destination = installation_folder
                self.manifest = manifest
                self.package_path = ''
                self.package_namelist = []
                self.__downloaded = False
                self.__installed = False
                self.__enabled = False

            def isDownloaded(self):
                return self.__enabled

            def isInstalled(self):
                return self.__installed

            def isEnabled(self):
                return self.__enabled

            def consistency(self):
                if len(self.manifest.keys()) == 0:
                    return 0
                checked_dir = self.temporary_storage if self.__installed and not self.__enabled else self.destination
                matches = 0
                entries = len(self.manifest)
                for rel_path, standard_hash in self.manifest.items():
                    abs_path = os.path.join(checked_dir, rel_path)
                    if os.path.exists(abs_path):
                        # Only files are counted
                        if filehash(abs_path) == standard_hash:
                            matches += 1
                if entries == 0:
                    return 0
                return matches / entries

            def updateInstalled(self):
                consistency = self.consistency()
                if consistency == 1:
                    self.__downloaded = True
                    self.__enabled = True if not self.__installed else self.__enabled
                    self.__installed = True
                # todo: add 'installed but modified' state of mod version
                # elif consistency >= 0.95:
                #     pass
                else:
                    self.__installed = False
                    self.__enabled = False

            def download(self):
                if not self.__downloaded:
                    response = requests.get(self.download_url, timeout=10, stream=True)
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
                        raise ConnectionError("Failed to download mod version : " + self.download_url)

            def install(self):
                # If no package downloaded, download it
                if not self.__downloaded:
                    for progress in self.download():
                        yield progress
                # If already installed, nothing to do
                if not self.__installed:
                    file_size = int(os.path.getsize(self.package_path))
                    # Unpack (install) downloaded package
                    yield Progress(0, file_size)
                    try:
                        with ZipFile(self.package_path, 'r') as installed_package:
                            self.package_namelist = installed_package.namelist()
                            installed_package.extractall(self.destination)
                        yield Progress(file_size, file_size)
                        self.__installed = True
                        self.__enabled = True
                    except BadZipfile as er:
                        raise ModManager.ManagementError("Invalid package provided : " + self.package_path) from er
                elif not self.__enabled:
                    self.enable()

            def _movePackages(self, src, dst):
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
                if not self.__enabled:
                    self.__enabled = True
                    for _ in self._movePackages(self.temporary_storage, self.destination):
                        yield _

            def uninstall(self):
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

    def __init__(self):
        self.update_url = "https://localhost/Gems.xml"
        self.version = "v0.0.0"


def wait(gen):
    return list(gen)


if __name__ == "__main__":
    test = ModManager.SupportedMod.ModVersion(
        "v1.0.0",
        manifest={
            'MapFilters.xml':
                '8b848aecc68c001e236120912a76ecb4',
            'Roofs.pak':
                '27fa69a92b8726b062468a612d0512ed',
            'Icons/Generated/MapObjects/_(AdvMapObjectLink)/ENOD/Roof1.(AdvMapObjectLink)-icon.tga':
                '8f4c265f7800b7ed58f211dce2317a4a',
            'Icons/Generated/MapObjects/_(AdvMapObjectLink)/ENOD/Roof2-icon.tga':
                'a4d58b12993b9148822bf708c1ab30a2',
            'Icons/Generated/MapObjects/_(AdvMapObjectLink)/ENOD/Roof3.(AdvMapObjectLink)-icon.tga':
                '4e6819f3dac114ac52ac35d1745ee079',
            'Icons/Generated/MapObjects/_(AdvMapObjectLink)/ENOD/Roof4-icon.tga':
                'b9ca91a8dcf9f3e912e327a6f2b2673e',
            'Icons/Generated/MapObjects/_(AdvMapObjectLink)/ENOD/Roof5.(AdvMapObjectLink)-icon.tga':
                'c378fc0d2c66921dfb26ce9d62bf3301',
        },
        download_url="https://forum.heroesworld.ru/attachment.php?attachmentid=64176&d=1612189147",
        installation_folder="D:\\My Programmes\\TestServer\\Mods",
        download_folder="D:\\My Programmes\\TestServer\\Temporary"
    )
    print(test.isInstalled())
    test.updateInstalled()
    print(test.isInstalled())
    for _ in test.install():
        print(f"{_.desc} in progress: {int(_.percent())} %...")
    input(f"{'--' * 15}")
