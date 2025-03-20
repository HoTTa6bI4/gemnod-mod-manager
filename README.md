# Heroes V: map editor 'Scratch' addon
## Brief project info
This project is developed specifically for Heroes of Might and Magic V: Tribes of the East, 3.1 version. It aims to simplify writing lua-scripts, which are a core of flexible gameplay design for custom maps, for beginners.
All script bricks must be included in map file (*.h5m), and map file should be patched then for all script bricks to be transformed to corresponding lua-code.

Map patcher is provided with [GEMNOD modification](https://forum.heroesworld.ru/showthread.php?t=15368) and would be updated separately. Patcher mirror on [Google Disk](https://drive.google.com/file/d/1e5UhONxTfvon1zMGHCODa0fRZZZhyBQl/view).  

## Usage
Put 'types.xml' file into your ../GameFolder/data/. Run editor and enjoy!

## Current milestones
Therefore currently we consider to add:
  - Multipage TalkBoxForPlayers wrap
  - Wrap for chain dialogs based on TalkBoxForPlayers without answers choice
  - Wraps for simple actions:
    1. Map quests updating
    2. Heroes equipment and army updating
    3. Players' resources updating
    4. If-else conditions
    5. Showing mentioned wraps
    6. Updating map objects info and their placement
   
