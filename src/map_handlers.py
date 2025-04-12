import shutil
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import os
from re import match
from file_seeker import ArchivesSeeker

# from file_seeker import *
import file_seeker


def extractMapRoot(map_file_path):
    # Extract root AdvMapDesc file from *.h5m file (map.xdb usually)
    #
    if os.path.isfile(map_file_path):
        with ZipFile(map_file_path, "r") as MapArchive:
            map_file_filelist = MapArchive.namelist()
            # Search for map.xdb in map archive
            for filename in map_file_filelist:
                # Copy to working directory if found
                # something that suits
                #   Maps/SingleMissions/.../map.xdb
                # or
                #   Maps/Multiplayer/.../map.xdb
                #
                if match(r"^Maps/(SingleMissions|Multiplayer)/[a-zA-Z0-9_~.]+/map\.xdb$", filename):
                    map_xdb = MapArchive.open(filename, "r")
                    contents = list(map(lambda bstr: bstr.decode("UTF-8").replace('\r\n', '\n'), map_xdb.readlines()))
                    map_xdb.close()
                    return filename, contents

            # Raise exception else
            raise FileNotFoundError(810, "No map root 'map.xdb' found. If root AdvMapDesc file name is"
                                         "different from 'map.xdb', try renaming it.")

    else:
        raise FileNotFoundError(809, "Map file is not a valid file")


def createEffectFromMapObjects(map_path):
    pass


def addMapScript(map_file_path, script_template=""):
    print(f"> Adding MapScript for map {map_file_path}.")
    print(f"> Searching for existing valid script.")

    # Get map root bytes and convert them to
    # string list
    #
    map_xdb_path, map_xdb_contents = extractMapRoot(map_file_path)
    map_file_dir, map_file_name = os.path.split(map_file_path)
    map_xdb_rel_dir, map_xdb_name = os.path.split(map_xdb_path)

    # Get info about MapScript from map.xdb
    #
    MapXDB = ET.ElementTree(ET.fromstringlist(map_xdb_contents))
    MapXDBroot = MapXDB.getroot()
    MapScript = MapXDBroot.find("MapScript")
    is_valid_script = True

    # Check whether referenced script is valid
    #
    if 'href' not in MapScript.attrib.keys():
        is_valid_script = False
    else:

        MapScriptRef = MapScript.attrib['href'].split("#")[0]
        if not MapScriptRef.startswith("/"):
            MapScriptRef = os.path.join(map_xdb_rel_dir, MapScriptRef)

        lines, time = ArchivesSeeker(map_file_dir, ".h5m").getLastVersionOf(MapScriptRef)

        if lines is None:
            is_valid_script = False

    if not is_valid_script:

        print(f"> No valid script set for current map")

        # Update map.xdb
        #
        new_script_filename = "../../_ENOD Patcher/MapScript.(Script).xdb"
        new_map_filename = "../../_ENOD Patcher/map.xdb"
        MapScript.set("href", new_script_filename + "#xpointer(/Script)")
        MapXDB.write(new_map_filename)

        # Create map script file according to passed template
        #
        MapScriptXDBroot = ET.fromstringlist(script_template)
        MapScriptXDB = ET.ElementTree(MapScriptXDBroot)
        MapScriptXDB.write(new_script_filename)

        print(f"> Created new {new_script_filename}")

        with ZipFile(map_file_path, "a") as MapArchive:
            MapArchive.write(new_map_filename, arcname=map_xdb_path)
            MapArchive.write(new_script_filename, arcname=os.path.join(map_xdb_rel_dir, new_script_filename))


    else:
        print(f"> Valid map script is already set for this map. Continue...")


if __name__ == '__main__':
    addMapScript(
        "S:\\Games\\Nival Interactive\\Heroes of Might and Magic V - Tribes of the East\\Maps\\temp\\Map.h5m",
        script_template=[
            '<?xml version="1.0" encoding="UTF-8"?>\n',
            '<Script>\n',
            '\t<FileName/>\n',
            '\t<ScriptText/>\n',
            '</Script>\n',
        ])
