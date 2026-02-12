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
    if os.path.exists(file_path) and os.path.isfile(file_path):
        file_info = os.stat(file_path)
        size = file_info.st_size
        name = os.path.basename(file_path)
        date = file_info.st_ctime
        mdate = file_info.st_mtime
        string = str(size) + str(mdate) + str(name) + str(date)
        return md5(string.encode('utf-8')).hexdigest()
    else:
        raise FileNotFoundError(f"{file_path} is not a file")


# Creating action instance according to its reference File.xdb#xpointer(/Type)
def classInstanceByXpointerType(xpointer):
    if "#n:inline" in xpointer:
        base = xpointer.split("#n:inline")[1]
    elif "#xpointer" in xpointer:
        base = xpointer.split("#xpointer")[1]
    else:
        raise AttributeError("Invalid xpointer! (" + xpointer + ")")
    class_name = base.replace('(/', '').replace('(', '').replace(')', '')
    cls = global_types.get(class_name)
    if cls is not None:
        return cls
    else:
        raise AttributeError("Invalid xpointer class! (" + class_name + ")")


def fileReferenceByXpointerType(context, xpointer):
    def makeAbsolute(context, ref):
        ref = ref.replace('\\', '/')
        if not ref.startswith('/'):
            if not self.context.startswith('/'):
                ref = '/' + os.path.join(self.context, ref)
            else:
                ref = os.path.join(self.context, ref)
        return ref.replace('\\', '/')

    file_ref = xpointer.split("#xpointer")[0].replace("\\", "/")
    file_ref = makeAbsolute(context, file_ref)

    return file_ref


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

    indexes_dir = '../../index/indexes/'

    tables = {
        "artifacts": {'ids': {}, 'server_ptr': '7b059128'},
        "creatures": {'ids': {}, 'server_ptr': 'dd04dd1e'},
        "spells": {'ids': {}, 'server_ptr': '8d02a80a'},
        "skills": {'ids': {}, 'server_ptr': '8c029e0a'},
        "players_filter": {'ids': {}, 'server_ptr': '10000001'},
        "talkbox_close_modes": {'ids': {}, 'server_ptr': '10000006'},
    }

    def __init__(self, game_root, indexed_places_file=default_indexed_places, hold_mode=False):
        self.game_root = game_root
        if not self.__isHeroesV():
            raise NotADirectoryError("Current directory is not a Heroes V game folder!")
        self.__hold_mode = hold_mode
        self.__used_seekers = {}
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
        for used_seeker in self.__used_seekers.values():
            used_seeker.free()

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
                        seeker = None

                        # In hold mode, archive seekers are saved into inspector memory
                        if self.__hold_mode:
                            if file_abs_path in self.__used_seekers.keys():
                                seeker = self.__used_seekers.get(file_abs_path)

                        # If no seeker was pre-found (not hold mode or first usage either)
                        if seeker is None:
                            # If no index for this archive, use default seeker
                            if index is None:
                                # print(f"> Unindexed place: {any_file} | {file_hash}")
                                seeker = ArchivesSeeker(inspected_folder, any_file)
                                self.unindexed_places.append(file_abs_path)
                            else:
                                # print(f"> Indexed place: {any_file} | {file_hash}")
                                seeker = IndexedArchiveSeeker(inspected_folder, any_file, index)
                                pass
                            if self.__hold_mode:
                                seeker.hold()
                                self.__used_seekers[file_abs_path] = seeker

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
    my_inspc = HeroesVFileInspector("D:\\Nival Interactive\\Heroes of Might and Magic V - Tribes of the East\\",
                                    hold_mode=True)

    my_inspc.updateIndexes()
    # my_inspc.updateTypes()

    now = time.time()
    repeats = 100
    file = []
    for i in range(repeats):
        file = my_inspc.get("GameMechanics/RPGStats/DefaultStats.xdb")
    end = time.time()
    print(f"{repeats} searches time: {end - now} with {(end - now)/repeats} average search time")
