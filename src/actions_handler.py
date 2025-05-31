import os.path
from xml.etree import ElementTree as ET
from types_handler import TypesXmlHandler
# from hashlib import md5
from heroes_v_file_seeker import *
from parse_error import ParseError

global_types = globals()


def stringArrayHash(lines):
    return md5(''.join(lines).encode('UTF-8', errors='ignore')).hexdigest()


# Creating action instance according to its reference File.xdb#xpointer(/Action)
def classInstanceByXpointerType(xpointer=str()):
    base = xpointer.split("#xpointer")[1]
    class_name = base.replace('(/', '').replace(')', '')
    cls = global_types.get(class_name)
    if cls is not None:
        return cls
    else:
        raise TypeError(813, "Invalid class xpointer! (" + class_name + ")")


""" Classes related to XDB-bricks for Heroes V lua scripts """


class XmlScriptBrick:

    def __init__(self, ref, inspector, script_types_ids, usecases_table=None, hero_variable_name='hero'):
        if usecases_table is None:
            self.usecases_table = set()
        else:
            self.usecases_table = usecases_table.copy()
        contents = inspector.get(ref)
        self.root = ET.fromstringlist(contents)
        self.document = ET.ElementTree(self.root)
        self.hero = hero_variable_name
        self.types = script_types_ids
        self.inspector = inspector
        self.name = None
        self.context = None

        filepath, filename = os.path.split(ref)
        self.name = filename
        if filepath.startswith('/'):
            self.context = filepath.replace('/', '', 1)
        elif not filepath.endswith('/'):
            self.context = filepath + '/'
        else:
            self.context = filepath

        # Recursive actions defend:
        #
        hash = stringArrayHash(contents)

        if hash in self.usecases_table:
            raise RecursionError(812, f"Recursive .(Action) objects referring. Check links logic. Failed in: '{ref}'")
        else:
            self.usecases_table.add(hash)

    def makeAbsolute(self, ref):
        ref = ref.replace('\\', '/')
        if not ref.startswith('/'):
            ref = '/' + os.path.join(self.context, ref)
        return ref.replace('\\', '/')

    def getChildBrick(self, child_brick):
        if child_brick is not None:
            if 'href' in child_brick.attrib:
                xpointer = child_brick.attrib['href']
                file_ref = xpointer.split("#xpointer")[0].replace("\\", "/")
                file_ref = self.makeAbsolute(file_ref)

                new_context = os.path.split(file_ref)[0]

                following_brick_class = classInstanceByXpointerType(xpointer)

                return following_brick_class(file_ref, self.inspector, self.types, self.usecases_table, self.hero)
            else:
                return None
        else:
            raise AttributeError("Invalid tag for child xpointer!")

    def toScript(self, indentation_level=1, brackets_level=0):
        pass


class Condition(XmlScriptBrick):

    def toScript(self, indentation_level=1, brackets_level=0):

        tab = '\t' * indentation_level

        script_contents = [
            tab + 'local hero = ' + self.hero + ';',
            tab + 'local player = GetObjectOwner(hero);'
        ]

        # Create conditional expression
        #
        and_expr = ' and '
        or_expr = ' or '

        clauses = {
            and_expr: [],  # Dict key is the divider between array elements ( smth1 and smth2 and ... )
            or_expr: [],  # ( smth1 or smth2 or ... )
        }

        HasHero = self.root.find("HasHero")

        for pair in (("AllOf", and_expr), ("AnyOf", or_expr)):
            block_name = pair[0]
            divider = pair[1]
            Block = HasHero.find(block_name)

            # Adding creatures info
            for creature_item in Block.find("ArmyCreatures"):
                string_id = creature_item.find("Creature").text
                id = self.types.getNumericID('creatures', string_id)
                count = creature_item.find("Count").text
                if int(count) > 0:
                    clauses[divider].append(f'(GetHeroCreatures(hero, {id}) >= {count})')

            # Adding artifacts info
            for artifact_item in Block.find("Artifacts"):
                string_id = artifact_item.text
                id = self.types.getNumericID('artifacts', string_id)
                clauses[divider].append(f'HasArtefact(hero, {id})')

            # Adding resources info
            Resources = Block.find("Resources")
            resources = {
                'WOOD': Resources.find("Wood").text,
                'ORE': Resources.find("Ore").text,
                'MERCURY': Resources.find("Mercury").text,
                'CRYSTAL': Resources.find("Crystal").text,
                'SULFUR': Resources.find("Sulfur").text,
                'GEM': Resources.find("Gem").text,
                'GOLD': Resources.find("Gold").text
            }
            for id, count in resources.items():
                if int(count) > 0:
                    clauses[divider].append(f"(GetPlayerResource(player, {id}) >= {count})")

            # Adding skills info
            for skill_item in Block.find("PerksAndSkills"):
                string_id = skill_item.text
                id = self.types.getNumericID('skills', string_id)
                clauses[divider].append(f'HasHeroSkill(hero, {id})')

            # Adding spells info
            for spell_item in Block.find("Spells"):
                string_id = spell_item.text
                id = self.types.getNumericID('spells', string_id)
                clauses[divider].append(f'KnowHeroSpell(hero, {id})')

            # Adding war machines info
            war_machines = {  # could be replaced with simple class
                "Ballista": 'WAR_MACHINE_BALLISTA',
                "FirstAidTent": 'WAR_MACHINE_FIRST_AID_TENT',
                "AmmoCart": 'WAR_MACHINE_AMMO_CART',
            }
            for war_machine_tag, war_machine_string_id in war_machines.items():
                WarMachine = Block.find('WarMachines/' + war_machine_tag)
                if WarMachine.text == 'true':
                    clauses[divider].append(f'HasHeroWarMachine(hero, {war_machine_string_id})')

        condition = tab

        if len(clauses[or_expr]) > 0 and len(clauses[and_expr]) > 0:
            condition += f'if ({and_expr.join(clauses[and_expr])}) ' \
                         f'and ({or_expr.join(clauses[or_expr])}) then\n'
        elif len(clauses[or_expr]) == 0:
            condition += f'if {and_expr.join(clauses[and_expr])} then'
        elif len(clauses[and_expr]) == 0:
            condition += f'if {or_expr.join(clauses[or_expr])} then'
        else:
            raise ParseError(1, f"Empty condition expression! Failed in: '{self.name}'")

        script_contents.append(condition)

        # Create callback on statement is truth
        #
        script_contents_on_true = self.getChildBrick(self.root.find("OnTrue"))
        if script_contents_on_true is not None:
            script_contents += script_contents_on_true.toscript(indentation_level + 1)

        # Create callback on statement is lie
        #
        script_contents_on_false = self.getChildBrick(self.root.find("OnFalse"))
        if script_contents_on_false is not None:
            script_contents.append(tab + 'else')
            script_contents += script_contents_on_false.toscript(indentation_level + 1)

        # Close if-clause with 'end'
        #
        script_contents.append(tab + 'end\n')

        return script_contents


class Action(XmlScriptBrick):

    def onEnd(self):
        # Get OnEnd action reference
        #
        return self.getChildBrick(self.root.find("OnEnd"))


class ActionShow(Action):

    def __init__(self, ref, inspector, script_types_ids, usecases_table=None, hero_variable_name='hero'):
        super().__init__(ref, inspector, script_types_ids, usecases_table, hero_variable_name)
        self.players_filter = self.types.getNumericID('players_filter', self.root.find("PlayersFilter").text)
        self.modal = None
        BeModal = self.root.find("BeModal")
        if BeModal is not None:
            self.modal = BeModal.text
        # else: raise ParseError(1, "Invalid modality set!")


class ActionShowMessage(ActionShow):

    def toScript(self, indentation_level=1, brackets_level=0):
        tab = '\t' * indentation_level
        open_bracket = '[' + brackets_level * '=' + '['
        close_bracket = ']' + brackets_level * '=' + ']'

        Text = self.root.find("Text")
        if 'href' not in Text.attrib:
            raise ParseError(1, f"ActionShowMessage has no reference to text file! Failed in: '{self.name}'")
        txt_reference = Text.attrib['href']
        txt_reference = self.makeAbsolute(txt_reference)

        script_contents = []

        following = self.onEnd()
        if following is not None:
            if self.modal == 'true':
                following_script = following.toscript(indentation_level, brackets_level+1)
                script_contents.append(tab + f'MessageBoxForPlayers({self.players_filter},'
                                             f' "{txt_reference}" {open_bracket}')
                script_contents += list(map(lambda s: '\t' + s, following_script))
                script_contents.append(tab + f'return parse(\"\") {close_bracket}) '
                                             f'-- MessageBox callback waits for function() call')
                pass
            elif self.modal == 'false':
                following_script = following.toscript(indentation_level, brackets_level)
                script_contents.append(tab + f'MessageBoxForPlayers({self.players_filter},'
                                             f' "{txt_reference}")')
                script_contents += following_script
                pass
            else:
                raise ParseError(1, f"Unknown error in {self.name}")

        return script_contents


class ActionShowFlyingSign(ActionShow):

    def toScript(self, indentation_level=1, brackets_level=0):

        tab = '\t' * indentation_level
        script_contents = []

        # Sign text
        Text = self.root.find("Text")
        if 'href' not in Text.attrib:
            raise ParseError(1, f"ActionShowFlyingSign has no reference to text file! Failed in: '{self.name}'")
        txt_reference = Text.attrib['href']
        txt_reference = self.makeAbsolute(txt_reference)

        Duration = self.root.find("Duration").text
        if Duration is None:
            Duration = '3'  # Default flying sign duration

        Target = self.root.find("Target").text
        if Target is None:
            Target = self.hero
        else:
            Target = "\'" + Target + "\'"

        script_contents.append(tab + f'ShowFlyingSign("{txt_reference}", {Target}, player, {Duration})')

        following = self.onEnd()
        if following is not None:
            script_contents += following.toscript(indentation_level + 1, brackets_level)

        return script_contents


class ActionShowBranchedDialog(ActionShow):

    # Converts \Some/Path to/Dir/Root.(TalkboxSheet).txt
    # to list as following: ['Some', 'Pathto', 'Dir', 'Root']
    #
    def __splitpath(self, path):
        dirs, name = os.path.split(path)
        keys = list(dirs.replace("\\", "/").strip('/').split('/'))
        keys.append(name.split('.')[0])
        return keys

    def parseSheet(self, talkboxsheet, indentation_level=1, brackets_level=0):
        pass
        tab = '\t' * indentation_level
        tab_plus = '\t' + tab
        open_bracket = '[' + brackets_level * '=' + '['
        close_bracket = ']' + brackets_level * '=' + ']'
        script_contents = []
        tables = []

        talkboxsheet_contents = self.inspector.get(talkboxsheet)
        TalkboxSheet = ET.fromstringlist(talkboxsheet_contents)

        keys = self.__splitpath(talkboxsheet)
        script_table_field = 'BranchedDialog.Dialogs.' + '.'.join(keys)
        keys = "{'" + "', '".join(keys) + "'}"

        script_contents.append(tab + f'createNestedTable(BranchedDialog.Dialogs, {keys})')
        script_contents.append(tab + script_table_field + ' = {')

        # Get talkbox sheet params
        #
        # Talkbox icon (can be empty)
        Icon = TalkboxSheet.find("Icon")
        if 'href' in Icon.attrib:
            icon_path = Icon.attrib['href']
            script_contents.append(tab + '\t' + 'icon = "' + self.makeAbsolute(icon_path) + '",')

        # Talkbox title (mustn't be empty)
        Title = TalkboxSheet.find("Title")
        text_path = Title.attrib['href']
        if text_path != "":
            script_contents.append(tab + '\t' + 'title = "' + self.makeAbsolute(text_path) + '",')
        else:
            raise ParseError(1, f"TalkboxSheet no title set! Failed in: {self.name}")

        # Talkbox text (mustn't be empty)
        Text = TalkboxSheet.find("Text")
        text_path = Text.attrib['href']
        if text_path != "":
            script_contents.append(tab + '\t' + 'text = "' + self.makeAbsolute(text_path) + '",')
        else:
            raise ParseError(1, f"TalkboxSheet no main text set! Failed in: {self.name}")

        # Talkbox close mode
        CloseMode = TalkboxSheet.find("CloseMode")
        mode = self.types.getNumericID("talkbox_close_modes", CloseMode.text)
        script_contents.append(tab + '\t' + 'mode = ' + mode + ',')

        # Talkbox icon tooltip text (could be empty)
        IconTooltip = TalkboxSheet.find("IconTooltip")
        text_path = IconTooltip.attrib['href']
        if text_path != "":
            script_contents.append(tab + '\t' + 'iconTooltip = "' + self.makeAbsolute(text_path) + '",')

        # Talkbox selection text (could be empty)
        SelectionText = TalkboxSheet.find("SelectionText")
        text_path = SelectionText.attrib['href']
        if text_path != "":
            script_contents.append(tab + '\t' + 'selectionText = "' + self.makeAbsolute(text_path) + '",')

        # Talkbox additional text (could be empty)
        AdditionalText = TalkboxSheet.find("AdditionalText")
        text_path = AdditionalText.attrib['href']
        if text_path != "":
            script_contents.append(tab + '\t' + 'additionalText = "' + self.makeAbsolute(text_path) + '",')

        script_contents.append(tab + '\t' + 'options = {')
        # Add options info
        OptionsList = TalkboxSheet.find("OptionsList")
        if len(OptionsList) == 0:
            raise ParseError(1, f"Talkbox sheet has zero answers! Failed in: {self.name}")
        n = 1
        for item in OptionsList:
            BriefDesc = item.find("BriefDesc")
            comment_text = BriefDesc.text
            if comment_text != "":
                script_contents.append(tab + 2*'\t' + "-- " + comment_text)
            script_contents.append(tab + 2*'\t' + "[" + str(n) + "] = {")

            AnswerText = item.find("AnswerText")
            text_path = AnswerText.attrib['href']
            if text_path == "":
                raise ParseError(1, f"Empty option text! Failed in: {self.name}")
            text_path = self.makeAbsolute(text_path)
            script_contents.append(tab + 3*'\t' + "optionText = \"" + text_path + '\",')

            action = self.getChildBrick(item.find("OnChoose"))
            if action is not None:
                script_contents.append(tab + 3*'\t' + "action = function()")
                script_contents += action.toscript(indentation_level+4, brackets_level)
                script_contents.append(tab + 3*'\t' + "end,")

            FollowingSheet = item.find("FollowingSheet")
            if 'href' in FollowingSheet.attrib:
                xpointer = FollowingSheet.attrib['href']
                file_ref = xpointer.split("#xpointer")[0].replace("\\", "/")
                file_ref = self.makeAbsolute(file_ref)
                following_sheet_table_field, following_script_contents = self.parseSheet(file_ref,
                                                                                         indentation_level,
                                                                                         brackets_level)
                script_contents.append(tab + 3*'\t' + "following = '" + following_sheet_table_field + "',")
                tables.append(following_script_contents)

            script_contents.append(tab + 2*'\t' + "},")

            n += 1

        script_contents.append(tab + '\t' + '}')

        script_contents.append(tab + '}')

        for table in tables:
            script_contents += table

        return script_table_field, script_contents

    def toScript(self, indentation_level=1, brackets_level=0):

        tab = '\t' * indentation_level
        script_contents = []

        # Final callback on whole branched dialog ends
        #
        following = self.onEnd()
        if following is not None:
            script_contents.append(tab + '-- Functions to be called after whole BranchDialog ends')
            script_contents.append(tab + 'local callback = function()')
            script_contents += following.toscript(indentation_level + 1)
            script_contents.append(tab + 'end')

        FollowingSheet = self.root.find("StartSheet")
        if 'href' in FollowingSheet.attrib:
            sheet_ref = FollowingSheet.attrib['href'].split("#xpointer")[0]
            sheet_ref = self.makeAbsolute(sheet_ref)
            script_table_field, script_sheet_contents = self.parseSheet(sheet_ref, indentation_level, brackets_level)
        else:
            raise ParseError(1, f"Branched dialog has no start sheet! Failed in: {self.name}")

        script_contents.append(tab + '-- Branched dialog separate pages are created in BranchedDialog.Dialogs')
        script_contents.append(tab + '-- and accessed by string path then')
        script_contents.append(tab + '--')
        script_contents += script_sheet_contents
        script_contents.append(tab + '-- Finally, call dialog creator to run.')
        script_contents.append(tab + '--')

        if self.modal == 'true':
            if following is not None:
                script_contents.append(tab + 'BranchedDialog.new(' + script_table_field + ', callback)')
            else:
                script_contents.append(tab + 'BranchedDialog.new(' + script_table_field + ')')
        elif self.modal == 'false':
            script_contents.append(tab + 'BranchedDialog.new(' + script_table_field + ')')
            if following is not None:
                script_contents.append(tab + "callback()")

        return script_contents


class ActionShowLinearDialog(ActionShow):

    def toScript(self, indentation_level=1, brackets_level=0):
        tab = '\t' * indentation_level
        script_contents = []

        following = self.onEnd()
        if following is not None:
            script_contents.append(tab + '-- Functions to be called after whole LinearDialog ends')
            script_contents.append(tab + 'local callback = function()')
            script_contents += following.toscript(indentation_level + 1)
            script_contents.append(tab + 'end')

        script_contents.append(tab + 'local sentences = {')

        i = 1
        for sentence in self.root.findall("Sentences/Item"):
            Icon = sentence.find("Icon")
            Text = sentence.find("Text")
            Title = sentence.find("Title")
            if 'href' in Icon.attrib.keys() and 'href' in Text.attrib.keys() and 'href' in Title.attrib.keys():
                icon = self.makeAbsolute(Icon.attrib['href'])
                text = self.makeAbsolute(Text.attrib['href'])
                title = self.makeAbsolute(Title.attrib['href'])
                script_contents.append(tab + '\t' + f'[{i:2}]' + " = {icon  = \'" + icon + "\', ")
                script_contents.append(tab + '\t' + 8*' ' + "title = \'" + title + "\', ")
                script_contents.append(tab + '\t' + 8*' ' + "text  = \'" + text + "\'},")
            else:
                raise ParseError(1, f"Invalid sentence in ActionShowLinearDialog (no icon or text set)! "
                                    f"Failed in: {self.name}")
            i += 1

        script_contents.append(tab + '}')

        if self.modal == 'true':
            if following is not None:
                script_contents.append(tab + 'Dialog.new(sentences, callback)')
            else:
                script_contents.append(tab + 'Dialog.new(sentences)')
        elif self.modal == 'false':
            script_contents.append(tab + 'Dialog.new(sentences)')
            if following is not None:
                script_contents.append(tab + "callback()")

        return script_contents


class AdvMapObjectBase(XmlScriptBrick):

    def getPos(self):
        Position = self.root.find("Pos")
        X, Y, Z = Position.find("x"), Position.find("y"), Position.find("z")
        x, y, z = float(X.text), float(Y.text), float(Z.text)
        Floor = self.root.find("Floor")
        f = int(Floor.text)
        return x, y, z, f

    def getScriptName(self):
        ScriptName = self.root.find("Name")
        object_script_name = ""
        if ScriptName.text is None:
            raise ParseError(f"Object has no custom script name! Failed in {self.name}")
            # x, y, z, fl = self.getPos()
            # object_script_name = type(self).__name__ + "_" + str(int(x)) + "_" + str(int(y)) + "_" + str(int(z))
            # if fl == 0:
            #     object_script_name += "_ground"
            # elif fl == 1:
            #     object_script_name += "_underground"
            # else:
            #     raise ParseError(f"Invalid object floor type! Failed in: {self.name}")
        else:
            object_script_name = ScriptName.text

        return object_script_name

    def __getValidScriptName(self):
        from re import match, sub
        valid_string = sub(r"[^A-Za-z0-9_]", '', self.getScriptName())
        if match(r"^[0-9]", valid_string):
            valid_string = valid_string[1:]
        if valid_string == "":
            raise ValueError(f"No valid script name could be constructed! Failed in {self.name}")
        return valid_string


class AdvMapInteractiveBase(AdvMapObjectBase):

    def onTouch(self):
        return self.getChildBrick(self.root.find("Behaviour/OnTouch"))

    def onRemove(self):
        return self.getChildBrick(self.root.find("Behaviour/OnRemove"))

    def toScript(self, indentation_level=1, brackets_level=0):

        tab = '\t' * indentation_level
        script_contents = []

        variable_name = self.__getValidScriptName()
        object_script_name = self.getScriptName()

        action_on_touch = self.onTouch()

        if action_on_touch is not None:
            script_contents += map(lambda s: tab + s, [
                "-- Touch handler",
                f"function {variable_name}_onTouch(hero, object)",
                *action_on_touch.toScript(indentation_level + 1, brackets_level),
                "end",
                "",
                f"AddEventHandler(EVENT_OBJECT_TOUCHED, '{object_script_name}', \"{variable_name}_onTouch\")",
                "--"
            ])

        action_on_remove = self.onRemove()
        if action_on_remove is not None:
            script_contents += map(lambda s: tab + s, [
                "-- Touch handler",
                f"function {variable_name}_onRemove(hero, object)",
                *action_on_touch.toScript(indentation_level + 1, brackets_level),
                "end",
                "",
                f"AddEventHandler(EVENT_OBJECT_REMOVED, '{object_script_name}', {variable_name}_onRemove)",
                "--"
            ])

        return script_contents


class AdvMapInteractiveAndOwnedBase(AdvMapInteractiveBase):

    def onCapture(self):
        return self.getChildBrick(self.root.find("Behaviour/OnCapture"))

    def toScript(self, indentation_level=1, brackets_level=0):
        script_contents_old = super().toScript(indentation_level, brackets_level)

        tab = '\t' * indentation_level
        script_contents = []

        variable_name = self.__getValidScriptName()
        object_script_name = self.getScriptName()

        action_on_capture = self.onCapture()
        if action_on_capture is not None:
            script_contents += map(lambda s: tab + s, [
                "-- Touch handler",
                f"function {variable_name}_onCapture(hero, object, old_owner, new_owner)",
                *action_on_capture.toScript(indentation_level + 1, brackets_level),
                "end",
                "",
                f"AddEventHandler(EVENT_OBJECT_CAPTURED, '{object_script_name}', {variable_name}_onCapture)",
                "--"
            ])

        script_contents += script_contents_old

        return script_contents


if __name__ == '__main__':

    game_folder = "S:/Games/Nival Interactive/Heroes V Clear Version/"

    heroesVinspector = HeroesVFileInspector(game_folder)
    types = TypesXmlHandler(heroesVinspector)

    # cond = Condition('/Scripts/Conditions/Demo/TestConditon.(Condition).xdb', heroesVinspector, types)

    # sheet = ActionShowBranchedDialog('/TalkboxSheets/Demo/StartSmth.(ActionShowBranchedDialog).xdb',
    #                                  heroesVinspector, types)

    # for line in cond.toScript():
    #     print(line)

    # for line in sheet.toscript(1):
    #     print(line)
