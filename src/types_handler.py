import os.path
from parse_error import ParseError
from heroes_v_file_seeker import *
from xml.etree import ElementTree as ET


class TypesXmlHandler:

    tables = {
        "artifacts": {'ids': {}, 'server_ptr': '7b059128'},
        "creatures": {'ids': {}, 'server_ptr': 'dd04dd1e'},
        "spells": {'ids': {}, 'server_ptr': '8d02a80a'},
        "skills": {'ids': {}, 'server_ptr': '8c029e0a'},
        "players_filter": {'ids': {}, 'server_ptr': '10000001'},
        "talkbox_close_modes": {'ids': {}, 'server_ptr': '10000006'},
    }

    def updateTypes(self):

        contents = self.file_inspector.get("types.xml")
        document_root = ET.fromstringlist(contents)

        for item in document_root.findall("SharedClasses/Item"):
            server_ptr = item.find("__ServerPtr").text

            for table_name, table_props in self.tables.items():
                if server_ptr == table_props['server_ptr']:
                    for entry in item.findall("Entries/Item"):
                        STRING_ID = entry.find("Name").text
                        numeric_id = entry.find("Value").text
                        self.tables[table_name]['ids'][STRING_ID] = numeric_id

    def __init__(self, file_inspector):
        self.file_inspector = file_inspector
        self.updateTypes()

    def getNumericID(self, table, string_id):
        if table not in self.tables.keys():
            raise ParseError(1, f"Invalid table name {table}")
        if string_id not in self.tables[table]['ids'].keys():
            raise ParseError(1, f"Invalid ID [{string_id}] for table [{table}]")
        numeric_id = self.tables[table]['ids'][string_id]
        return numeric_id


if __name__ == "__main__":
    inspector = HeroesVFileInspector("S:\\Games\\Nival Interactive\\Heroes V Clear Version\\")
    myTypes = TypesXmlHandler(inspector)
    id = ''
    table = ''
    while id is not None:
        print("Enter table name:")
        table = input()
        print("Enter id:")
        id = input()
        print(myTypes.getNumericID(table, id))
