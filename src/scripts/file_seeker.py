import os
import zipfile
from datetime import datetime
import time
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, ID
from whoosh.qparser import QueryParser


class SimpleSeeker:

    def __init__(self, root):
        if os.path.isdir(root):
            self.root = root
        else:
            raise FileNotFoundError(808, "Invalid root directory: " + root)

    def getmtime(self, relative_path):
        pass

    def getfile(self, relative_path):
        pass


class FolderSeeker(SimpleSeeker):

    def getmtime(self, relative_path):
        # print(f"> Searching for last version of '{relative_path}' in folder '{self.root}'")
        abs_path = os.path.join(self.root, relative_path)
        if os.path.isfile(abs_path):
            return os.path.getmtime(abs_path)
            # print(f"> Found file in folder '{abs_path}' ({datetime.fromtimestamp(self.lastModificationTime)})")
        return 0.0

    def getfile(self, relative_path):
        # print(f"> Searching for last version of '{relative_path}' in folder '{self.root}'")
        abs_path = os.path.join(self.root, relative_path)
        contents = None
        if os.path.isfile(abs_path):
            lastSeekedFile = open(abs_path, 'r', encoding='utf-8')
            contents = lastSeekedFile.readlines()
            lastSeekedFile.close()
            # print(f"> Found file in folder '{abs_path}' ({datetime.fromtimestamp(self.lastModificationTime)})")
        if contents is None:
            raise FileNotFoundError(f"No file '{relative_path}' found in '{self.root}'")
        return contents


class ArchivesSeeker(SimpleSeeker):

    def __init__(self, root, archive):
        super().__init__(root)
        self.archive_path = os.path.join(root, archive)

    def getmtime(self, relative_path):
        # Reduce relative path to the form ZipFile.namelist() provides:
        # No start slash, all slashes straight '/'
        #
        if relative_path.startswith("/"):
            relative_path = relative_path.replace("/", '', 1)
        relative_path = relative_path.replace("\\", "/")

        with zipfile.ZipFile(self.archive_path, 'r') as archive:
            for archived_file in archive.namelist():
                if archived_file == relative_path:
                    modificationTime = datetime(*archive.getinfo(archived_file).date_time).timestamp()
                    return modificationTime
                    # print(f"> Found file in archive '{item}' "
                    #       f"({relative_path} | {datetime.fromtimestamp(self.lastModificationTime)})")

        return 0.0

    def getfile(self, relative_path):
        # Reduce relative path to the form ZipFile.namelist() provides:
        # No start slash, all slashes straight '/'
        #
        if relative_path.startswith("/"):
            relative_path = relative_path.replace("/", '', 1)
        relative_path = relative_path.replace("\\", "/")

        contents = None

        with zipfile.ZipFile(self.archive_path, 'r') as archive:
            for archived_file in archive.namelist():
                if archived_file == relative_path:
                    lastSeekedFile = archive.open(relative_path, 'r')
                    contents = lastSeekedFile.readlines()
                    # list(map( lambda bstr: bstr.decode("utf-8", errors='ignore').replace('\r\n', '\n'),
                    # lastSeekedFile.readlines()) )
                    lastSeekedFile.close()
                    # print(f"> Found file in archive '{item}' "
                    #       f"({relative_path} | {datetime.fromtimestamp(self.lastModificationTime)})")
                    break

        if contents is None:
            raise FileNotFoundError(f"No file '{relative_path}' found in archive '{self.archive_path}'")
        return contents


class IndexedArchiveSeeker(SimpleSeeker):

    def __init__(self, root, archive, index):
        super().__init__(root)

        self.archive_path = os.path.join(root, archive)

        if not os.path.exists(index):
            raise FileNotFoundError(f"{index} is not an index")

        self.ix = open_dir(index)
        self.schema = self.ix.schema

    def getmtime(self, relative_path):
        lastmtime = 0.0
        with self.ix.searcher() as searcher:
            query = QueryParser('filepath', self.schema).parse(relative_path)
            results = searcher.search(query)
            for result in results:
                mtime = float(result['mtime'])
                if mtime > lastmtime:
                    lastmtime = mtime

        return lastmtime

    def getfile(self, relative_path):
        contents = None
        with self.ix.searcher() as searcher:
            query = QueryParser('filepath', self.schema).parse(relative_path)
            results = searcher.search(query)
            for result in results:
                file_path = result['filepath']
                with zipfile.ZipFile(self.archive_path, 'r') as archive:
                    with archive.open(file_path) as file:
                        try:
                            contents = file.readlines()
                            # list(map(lambda bstr: bstr.decode("utf-8", errors='ignore').replace('\r\n', '\n'),
                            #     file.readlines()))
                        except Exception as error:
                            print(file_path)

        if contents is None:
            raise FileNotFoundError(f"Index search result not found in {self.archive_path}")
        return contents


if __name__ == "__main__":
    try:

        game_folder = "S:/Games/Nival Interactive/Heroes V Clear Version/data/"
        searched_file = "GameMechanics/RPGStats/DefaultStats.xdb"

        # seeker = FolderSeeker(game_folder)
        seeker = ArchivesSeeker(game_folder, "data.pak")
        # seeker = IndexedArchiveSeeker(game_folder, './../indexdir', Schema(filepath=ID(stored=True),
        #                                                                            zipfile_name=ID(stored=True)))

        summ = 0
        repeats = 10

        for i in range(repeats):
            start = time.time()
            mtime = seeker.getmtime(searched_file)
            # file = seeker.getfile(searched_file)
            print(f"Modifiaction time {datetime.fromtimestamp(mtime)}")
            end = time.time()
            summ += end - start

        print(f"Average working time: {summ / repeats}")

    except FileNotFoundError as error:
        print(error)

