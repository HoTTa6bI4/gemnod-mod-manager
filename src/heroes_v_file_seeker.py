import os
import shutil
from file_seeker import *
from hashlib import md5


# Default storage of indexed files
# todo: make it users environment variable
#
default_indexed_places = "../index/index.db"


def filehash(file_path):
    if os.path.isfile(file_path):
        file_info = os.stat(file_path)
        size = file_info.st_size
        name = os.path.basename(file_path)
        date = file_info.st_ctime
        mdate = file_info.st_mtime
        string = str(size) + str(mdate) + str(name) + str(date)
        return md5(string.encode('utf-8')).hexdigest()
    else:
        raise FileNotFoundError(f"{file_path} is not a file")


class HeroesVFileInspector:

    inspected_folders = [
        "data"
    ]

    inspected_archives = [
        ("data", ".pak"),
        ("UserMODs", ".h5u"),
        # ("Maps", ".h5m"),
        # ("UserCampaigns", ".h5c"),
    ]

    indexes_dir = '../index/indexes/'

    # Simple check whether chosen folder is Heroes V game folder
    #
    def __isheroesv(self):
        if os.path.exists(os.path.join(self.game_root, 'bin/')):
            if os.path.exists(os.path.join(self.game_root, 'data/')):
                return True
        return False

    def __init__(self, game_root, indexed_places_file=default_indexed_places):
        self.game_root = game_root
        if not self.__isheroesv():
            raise NotADirectoryError("Current directory is not a Heroes V game folder!")
        self.unindexed_places = []
        self.indexes_dictionary = {}
        self.indexed_places_file = indexed_places_file
        # Read existing indexes dictionary from file
        if os.path.exists(indexed_places_file):
            with open(indexed_places_file) as ind:
                try:
                    for line in ind:
                        hashsum, index = line.replace('\r', '').replace('\n', '').split(' ')
                        self.indexes_dictionary[hashsum] = index
                except Exception as error:
                    print("<ERROR> Uknown error while parsing indexes database")
                    print("<ERROR", error, ">")

    def __getindex(self, hashsum):
        if hashsum in self.indexes_dictionary.keys():
            return self.indexes_dictionary[hashsum]
        else:
            return None

    def get(self, rel_path):

        # print(f"Searching for {rel_path} in {self.game_root}")
        rel_path = rel_path.replace('\\', '/')
        if rel_path.startswith('/'):
            rel_path = rel_path.replace('/', '', 1)

        # Get last version of 'rel_path' for installed game
        #
        seeker = None
        final_seeker = None
        contents = []
        last_modification_time = 0.0

        for inspected_folder in self.inspected_folders:
            seeker = FolderSeeker(os.path.join(self.game_root, inspected_folder))
            time = seeker.getmtime(rel_path)
            if time > last_modification_time:
                final_seeker = seeker
                last_modification_time = time

        for folder, extension in self.inspected_archives:
            inspected_folder = os.path.join(self.game_root, folder)
            for any_file in os.listdir(inspected_folder):
                file_abs_path = os.path.join(inspected_folder, any_file)
                if any_file.endswith(extension):
                    file_hash = filehash(file_abs_path)
                    index = self.__getindex(file_hash)
                    # If no index for this archive, use default seeker
                    if index is None:
                        print(f"> Unindexed place: {any_file} | {file_hash}")
                        seeker = ArchivesSeeker(inspected_folder, any_file)
                        self.unindexed_places.append(file_abs_path)
                    else:
                        # print(f"> Indexed place: {any_file} | {file_hash}")
                        seeker = IndexedArchiveSeeker(inspected_folder, any_file, index)
                        pass
                    mtime = seeker.getmtime(rel_path)
                    if mtime > last_modification_time:
                        final_seeker = seeker

        if final_seeker is not None:
            contents = final_seeker.getfile(rel_path)
        else:
            raise FileNotFoundError(f"Inspector didn't find any file '{rel_path}'")

        return contents

    def indexnewplaces(self):
        # print(f"> Indexing: {self.unindexed_places}")
        for place in self.unindexed_places:
            # Index dir name is idexed file hash
            hashsum = filehash(place)
            print(f"> Hash: {hashsum}")
            index_dir = self.indexes_dir + str(hashsum)
            # Flushing possibly existing indexes
            if os.path.exists(index_dir):
                shutil.rmtree(index_dir)
            os.makedirs(index_dir, exist_ok=True)
            # Create index object in created dir
            ix = create_in(index_dir, schema=Schema(filepath=ID(stored=True), mtime=ID(stored=True)))
            self.indexes_dictionary[hashsum] = index_dir
            writer = ix.writer()
            with zipfile.ZipFile(place, 'r') as archive:
                for fileinfo in archive.infolist():
                    fn = fileinfo.filename
                    try:
                        mtime = datetime(*fileinfo.date_time).timestamp()
                        writer.add_document(filepath=fn, mtime=str(mtime))
                    except Exception as error:
                        print(f"<ERROR> Uknown error while processing '{fn}'!")
                        print("<ERROR:", error, ">")

            print(f"> Created index for {place}...")
            writer.commit()

        self.writeindexes()

    def writeindexes(self):
        with open(self.indexed_places_file, 'w') as indexes_file:
            for key, value in self.indexes_dictionary.items():
                string = str(key) + ' ' + str(value) + '\r'
                indexes_file.write(string)
        # print(self.indexes_dictionary)

    def flush(self):
        # Find unknown indexes
        # Remove unknkown indexes
        for dir in os.listdir(self.indexes_dir):
            to_del = True
            for index_dir in self.indexes_dictionary.values():
                if dir in index_dir:
                    to_del = False
            if to_del:
                print(f"> Flushing unused index place: {dir}...")
                shutil.rmtree(os.path.join(self.indexes_dir, dir))


if __name__ == "__main__":
    my_inspc = HeroesVFileInspector("S:\\Games\\Nival Interactive\\Heroes V Clear Version\\")
    now = time.time()
    repeats = 100
    file, mtime = [], 0.0
    for i in range(repeats):
        file, mtime = my_inspc.get("Folder/Text.txt")
    print(f"{repeats} searches time: {time.time() - now} with {(time.time() - now)/repeats} average search time")
    my_inspc.indexnewplaces()
    my_inspc.writeindexes()
    my_inspc.flush()
