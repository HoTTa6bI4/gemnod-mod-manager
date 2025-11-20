from dataclasses import dataclass
import requests
import os
import shutil
from zipfile import ZipFile, BadZipfile


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


class ModManager:
    class ManagementError(Exception):
        pass

    class SupportedMod:

        class ModVersion:

            def __init__(self, version_name: str, download_url: str,
                         download_folder="./",
                         installation_folder="./"):
                if download_url is None:
                    raise ValueError("Donwload URL missed")
                self.name = version_name
                self.download_url = download_url
                self.temporary_storage = download_folder
                self.destination = installation_folder
                self.package_path = None
                self.package_list = None
                self.__downloaded = False
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
                            self.package_list = installed_package.namelist()
                            installed_package.extractall(self.destination)
                        yield Progress(file_size, file_size)
                        self.__installed = True
                        self.__enabled = True
                    except BadZipfile as er:
                        raise ModManager.ManagementError("Invalid package provided : " + self.package_path) from er

            def _movePackages(self, src, dst):
                objects_total = len(self.package_list)
                objects_moved = 0
                dirs_total = 0
                dirs_removed = 0
                moved_packages = []

                for rel_path in self.package_list:
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
                        except (OSError, PermissionError) as exc:
                            # Rollback all moved files
                            for old, new in moved_packages:
                                os.replace(new, old)
                            raise ModManager.ManagementError(f"An error occurred while trying "
                                                             f"to operate with '{old_path}'."
                                                             f"Close all applications that might "
                                                             f"use this file") from exc

                    yield Progress(objects_moved, objects_total, 'Disabling')

                for rel_path in reversed(self.package_list):
                    old_path = os.path.join(src, rel_path)
                    if os.path.isdir(old_path) and len(os.listdir(old_path)) == 0:
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
                    objects_total = len(self.package_list) + 1
                    objects_removed = 0
                    cleaned_dir = self.temporary_storage if not self.__enabled else self.destination
                    for rel_path in reversed(self.package_list):
                        abs_path = os.path.join(cleaned_dir, rel_path)
                        objects_removed += 1
                        yield Progress(objects_removed, objects_total, 'Uninstalling')
                        # If any file deleted someway, it no matters for uninstallation
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
        download_url="https://forum.heroesworld.ru/attachment.php?attachmentid=64176&d=1612189147",
        installation_folder="D:\\My Programmes\\TestServer\\Mods",
        download_folder="D:\\My Programmes\\TestServer\\Temporary"
    )
    for _ in test.install():
        print(f"{_.desc} in progress: {int(_.percent())} %...")
    input(f"{'--' * 15}")
    for _ in test.uninstall():
        print(f"{_.desc} in progress: {int(_.percent())} %...")
