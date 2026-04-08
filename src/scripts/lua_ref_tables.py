from __future__ import annotations

import time
import xml.etree.ElementTree
from xml.etree import ElementTree as ET
from heroes_v_file_seeker import *
from parse_error import ParseError
from typing import Callable


def isSimilarToID(value: str):
    return value == value.upper()


# Lua compatible XML-element, inherits xml.etree.Element
class LuaCompatibleElement(ET.Element):

    def makeelement(self, tag, attrib):
        return self.__class__(tag, attrib)

    def toLuaVariable(self, variable_name=None, tab='', max_tag_len=0, number=1):

        # Max tag len of all children is used for pretty lua formatting
        # 'Item' tag is treated like a numeric sequence id - SPECIFIC FOR HEROES V
        # todo: make numeric table keys not specifically 'Item's

        if variable_name is None:
            var_name = self.tag if self.tag != 'Item' else f'[{number}]'
        else:
            var_name = variable_name

        strings = [tab + f'{var_name: <{max_tag_len}} = ']

        if len(self) == 0:
            value = None
            if self.text is None or self.text == '':
                if len(self.keys()) == 0:  # empty element with tag refers to nilled variable
                    value = 'nil'
                elif len(self.keys()) == 1:
                    value = f'"{self.get(self.keys()[0])}"'
                # element with attributes and attributes only treated like a table
                else:
                    value = f'{{'
                    j = 1
                    last = len(self.items())
                    for attribute, val in self.items():
                        if j == last:
                            value += f'{attribute} = "{value}", '
                        else:
                            value += f'{attribute} = "{value}"}}'
                        j += 1
            else:
                value = self.text
                try:
                    value = str(float(self.text))
                except ValueError:  # if that was string, then...
                    if value.lower() == 'false':
                        value = 'nil'
                    elif value.lower() == 'true':
                        value = 'not nil'
                    elif not isSimilarToID(value):
                        value = '\"' + self.text + '\"'

            strings[0] += value  # + ','

        # If element has children, it's treated like a table of its children. Attributes and text are ignored
        else:
            strings[0] += f'{{'
            max_tag_len = 0
            for child in self:
                child_tag_len = len(child.tag)
                if child_tag_len > max_tag_len:
                    max_tag_len = child_tag_len
            j = 1
            last = len(self)
            for child in self:
                child_strings = child.toLuaVariable(None, tab + '\t', max_tag_len, j)
                if j < last:
                    child_strings[-1] += ','
                strings.extend(child_strings)
                j += 1
            strings.append(tab + f'}}')

        return strings


# Heroes V types.xml parser that converts all reference tables to Lua meta-tables
class TypesRefTablesParser:
    # Tables that references UID list with db file
    class ReferenceTable:

        def __init__(self, inspector: HeroesVFileInspector, path: str, unique_ids: set):
            self.inspector = inspector
            self.db_path = path
            if unique_ids is None:
                self.UIDs = set()
            else:
                self.UIDs = unique_ids

        def getItems(self) -> set[TypesRefTablesParser.ReferencedObject]:
            pass

    class XdbReferenceTable(ReferenceTable):

        def getItems(self) -> set[TypesRefTablesParser.ReferencedObject]:

            xdb_table = ET.fromstringlist(self.inspector.get(self.db_path))
            items = set()

            for item in xdb_table.findall('objects/Item'):

                if item.find('ID') is None and item.find('obj') is None and item.find(Obj) is None:
                    raise ParseError(f"Invalid object in table '{self.db_path}'")

                id = item.find('ID').text
                obj = item.find('obj') if item.find('obj') is not None else item.find('Obj')

                if id not in self.UIDs:
                    raise ParseError(f"Unknown object ID: '{id}' for table '{self.db_path}'", id, self.db_path)

                items.add(TypesRefTablesParser.ReferencedObject(self.inspector, id, obj))

            if len(items) != len(self.UIDs):
                raise ParseError(f"Several object ID were missed for table '{self.db_path}'", self.db_path)
            return items

    # A simple instance which describes unique object correlated with UID in reference table
    class ReferencedObject:

        def __init__(self, inspector: HeroesVFileInspector, id: str, objectInfo: xml.etree.ElementTree.Element):
            self.inspector = inspector
            self.id = id
            self.object = objectInfo

        def getContents(self):
            if 'href' in self.object.keys():
                href = self.object.get('href')
                file_ref = fileReferenceByXpointerType('/', href)
                return self.inspector.get(file_ref)
            else:
                return ET.tostringlist(self.object)

    def __init__(self, inspector: HeroesVFileInspector):
        # Parsing types.xml
        self.inspector = inspector

    def getInspector(self):
        return self.inspector

    def setInspector(self, inspector: HeroesVFileInspector):
        if inspector is None:
            raise ParseError("Heroes V File Inspector not provided!")
        self.inspector = inspector

    def iterparse(self,
                  #  id_handler: Callable[[str, int], str],  # enum id additional processing
                  script_handler: Callable[[list[str]], list[str]],  # generated script after-processing
                  table_names_filter: Optional[function] = None):

        if table_names_filter is None:
            def table_names_filter(s):
                return s

        if self.getInspector() is None:
            raise ParseError("Heroes V File Inspector not provided! Use .setInspector")
        TypesXMLContents = self.inspector.get('types.xml')
        TypesXML = ET.fromstringlist(TypesXMLContents)

        for table_item in TypesXML.findall("Tables/Item"):

            ReferenceTable = None
            LuaRefTableContents = None

            XPointer = table_item.find("dbid/XPointer")
            enum_entries = table_item.findall('EnumEntries/Item')
            if XPointer is None:
                raise ParseError(f'Entries database reference is missed!')
            if len(enum_entries) == 0:
                # raise ParseError(f'Empty database!')
                pass

            table_path = fileReferenceByXpointerType('', XPointer.text)
            table_name = os.path.basename(table_path)
            if not table_names_filter(table_name):
                continue
            uids = set()

            print(f"> Processing {table_name}...")
            start_time = time.time()

            # Creating .lua unique IDs enumeration
            LuaIDsTableContents = []
            max_id_len = 0

            for enum_entry in enum_entries:
                id = enum_entry.text
                if id is None or id == '':
                    pass
                else:
                    if len(id) > max_id_len:
                        max_id_len = len(id)

            i = 0
            for enum_entry in enum_entries:
                id = enum_entry.text
                if id is None or id == '':
                    raise ParseError(f'Enumeration entry missed for {table_path}', table_path)
                string_id = '\"' + id + '\"'
                LuaIDsTableContents.append(f'{id: <{max_id_len}} = {{num = {i: <3}, str = {string_id: <{max_id_len+2}}}}')
                i += 1
                uids.add(id)

            LuaIDsTableContents = script_handler(LuaIDsTableContents)

            end_time = time.time()
            print(f"> Completed {table_name.replace('.xdb', '.id.lua')} in {end_time - start_time}")
            start_time = time.time()

            # Creating .lua reference table
            ReferenceTable = TypesRefTablesParser.XdbReferenceTable(self.inspector, table_path, uids)
            LuaRefTableContents = [f'{os.path.splitext(table_name)[0]} = {{']

            for object_item in ReferenceTable.getItems():
                id = object_item.id
                fields = ET.fromstringlist(
                    object_item.getContents(),
                    parser=ET.XMLParser(target=ET.TreeBuilder(element_factory=LuaCompatibleElement)))
                lua_fields = fields.toLuaVariable(tab='\t', variable_name=f'[{id}]')
                lua_fields[-1] += ','
                LuaRefTableContents.extend(lua_fields)

            LuaRefTableContents.append(f'}}')

            LuaRefTableContents = script_handler(LuaRefTableContents)

            end_time = time.time()
            print(f"> Completed {table_name.replace('.xdb', '.lua')} in {end_time - start_time}")

            yield table_name, LuaRefTableContents, LuaIDsTableContents


if __name__ == "__main__":

    try:
        my_inspc = HeroesVFileInspector("D:\\Nival Interactive\\Heroes of Might and Magic V - Tribes of the East\\",
                                        hold_mode=True)
        my_inspc.updateIndexes()

        my_lua_tables_creator = TypesRefTablesParser(my_inspc)

        def addImportInfo(required_imports):
            return lambda script: required_imports + [
                '--',
                '-- auto-generated, do not modify',
                '--'
            ] + script + ['\n', '__end_import()']

        for table_name, lua_contents, ids_contents in \
                my_lua_tables_creator.iterparse(
                    script_handler=addImportInfo([]),
                    table_names_filter=lambda s: True if ('Creatures' in s) else False
                ):
            ids_filename = table_name.replace('.xdb', '.ids.lua').lower()
            ref_table_filename = table_name.replace('.xdb', '.lua').lower()
            with open(os.path.join('../generated/lua-libs/', ref_table_filename), 'w+') as lua_lib, \
                    open(os.path.join('../generated/lua-libs/', ids_filename),
                         'w+') as ids_lib:
                lua_lib.write('\n'.join(lua_contents))
                ids_lib.write('\n'.join(ids_contents))
            # input()

        # my_lua_elem = ET.fromstringlist([
        #        '<Texts>',
        #        '<Item href = "/Text/CombatLog/BonusElementalDamage.txt"/>',
        #        '<Item href = "/Text/CombatLog/BonusElementalSpellDamage.txt"/>',
        #        '<Item href = "/Text/CombatLog/BonusFireDamage.txt"/>',
        #        '<Item href = "/Text/CombatLog/BonusColdDamage.txt"/>',
        #        '</Texts>',
        # ], parser=ET.XMLParser(target=ET.TreeBuilder(element_factory=LuaCompatibleElement)))
        #
        # print(my_lua_elem.toLuaVariable(None))

    except KeyboardInterrupt:
        print("\n> Quited.")
