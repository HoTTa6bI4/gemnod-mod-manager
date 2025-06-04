import os
import shutil
from file_seeker import *
from hashlib import md5
from xml.etree import ElementTree as ET

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
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(HeroesVFileInspector, cls).__new__(cls)
        return cls._instance

    def instance(self=None):
        return HeroesVFileInspector._instance

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

    tables = {
        "artifacts": {'ids': {}, 'server_ptr': '7b059128'},
        "creatures": {'ids': {}, 'server_ptr': 'dd04dd1e'},
        "spells": {'ids': {}, 'server_ptr': '8d02a80a'},
        "skills": {'ids': {}, 'server_ptr': '8c029e0a'},
        "players_filter": {'ids': {}, 'server_ptr': '10000001'},
        "talkbox_close_modes": {'ids': {}, 'server_ptr': '10000006'},
    }

    def __init__(self, game_root, indexed_places_file=default_indexed_places):
        self.game_root = game_root
        if not self.__isHeroesV():
            raise NotADirectoryError("Current directory is not a Heroes V game folder!")
        self.unindexed_places = []
        self.indexes_dictionary = {}
        self.indexed_places_file = indexed_places_file
        self.__readIndexes()
        # Find not indexed (but possible to) places
        for folder, extension in self.inspected_archives:
            inspected_folder = os.path.join(self.game_root, folder)
            if os.path.exists(inspected_folder):
                for any_file in os.listdir(inspected_folder):
                    file_abs_path = os.path.join(inspected_folder, any_file)
                    if any_file.endswith(extension):
                        file_hash = filehash(file_abs_path)
                        index = self.__getIndex(file_hash)
                        if index is None:
                            print(f"> Not indexed place: {any_file} | {file_hash}")
                            self.unindexed_places.append(file_abs_path)

    def __getIndex(self, hashsum):
        if hashsum in self.indexes_dictionary.keys():
            return self.indexes_dictionary[hashsum]
        else:
            return None

    def __readIndexes(self):
        # Read existing indexes dictionary from file
        if os.path.exists(self.indexed_places_file):
            with open(self.indexed_places_file) as ind:
                try:
                    for line in ind:
                        hashsum, index = line.replace('\r', '').replace('\n', '').split(' ')
                        self.indexes_dictionary[hashsum] = index
                except Exception as error:
                    print("<ERROR> Unknown error while parsing indexes database")
                    print("<ERROR", error, ">")
        else:
            # Create empty one for write
            dirs, filename = os.path.split(self.indexed_places_file)
            os.makedirs(dirs, exist_ok=True)
            with open(self.indexed_places_file, 'w'):
                pass

    def __indexNewPlaces(self):
        print(f"> Indexing: {self.unindexed_places}")
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

        self.__writeIndexes()

    def __writeIndexes(self):
        with open(self.indexed_places_file, 'w') as indexes_file:
            for key, value in self.indexes_dictionary.items():
                string = str(key) + ' ' + str(value) + '\r'
                indexes_file.write(string)
        # print(self.indexes_dictionary)

    def __flush(self):
        # Find unknown indexes
        # Remove unknown indexes
        for dir in os.listdir(self.indexes_dir):
            to_del = True
            for index_dir in self.indexes_dictionary.values():
                if dir in index_dir:
                    to_del = False
            if to_del:
                print(f"> Flushing unused index place: {dir}...")
                shutil.rmtree(os.path.join(self.indexes_dir, dir))

    # Simple check whether chosen folder is Heroes V game folder
    #
    def __isHeroesV(self):
        if os.path.exists(os.path.join(self.game_root, 'bin/')):
            if os.path.exists(os.path.join(self.game_root, 'data/')):
                return True
        return False

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

        for folder in self.inspected_folders:
            inspected_fodler = os.path.join(self.game_root, folder)
            if os.path.exists(inspected_fodler):
                seeker = FolderSeeker(inspected_fodler)
                time = seeker.getmtime(rel_path)
                if time > last_modification_time:
                    final_seeker = seeker
                    last_modification_time = time

        for folder, extension in self.inspected_archives:
            inspected_folder = os.path.join(self.game_root, folder)
            if os.path.exists(inspected_folder):
                for any_file in os.listdir(inspected_folder):
                    file_abs_path = os.path.join(inspected_folder, any_file)
                    if any_file.endswith(extension):
                        file_hash = filehash(file_abs_path)
                        index = self.__getIndex(file_hash)
                        # If no index for this archive, use default seeker
                        if index is None:
                            # print(f"> Unindexed place: {any_file} | {file_hash}")
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

    def getNumericID(self, table, string_id):
        if table not in self.tables.keys():
            raise AttributeError(1, f"Invalid table name {table}")
        if string_id not in self.tables[table]['ids'].keys():
            raise AttributeError(1, f"Invalid ID [{string_id}] for table [{table}]")
        numeric_id = self.tables[table]['ids'][string_id]
        return numeric_id

    def updateTypes(self):

        contents = self.get("types.xml")
        document_root = ET.fromstringlist(contents)

        for item in document_root.findall("SharedClasses/Item"):
            server_ptr = item.find("__ServerPtr").text

            for table_name, table_props in self.tables.items():
                if server_ptr == table_props['server_ptr']:
                    for entry in item.findall("Entries/Item"):
                        STRING_ID = entry.find("Name").text
                        numeric_id = entry.find("Value").text
                        self.tables[table_name]['ids'][STRING_ID] = numeric_id

    def updateIndexes(self):
        self.__readIndexes()
        self.__indexNewPlaces()
        self.__writeIndexes()
        self.__flush()


if __name__ == "__main__":
    my_inspc = HeroesVFileInspector("S:\\Games\\Nival Interactive\\Heroes of Might and Magic V - Tribes of the East\\")

    my_inspc.updateIndexes()
    # my_inspc.updateTypes()

    now = time.time()
    repeats = 10
    file = []
    for i in range(repeats):
        file = my_inspc.get("types.xml")
    print(f"{repeats} searches time: {time.time() - now} with {(time.time() - now)/repeats} average search time")
