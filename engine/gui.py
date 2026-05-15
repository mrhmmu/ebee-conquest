import pygame
import os
import pygame_gui
import math

troopbadgevisiblezoommultiplier = 2.5
countrylabelvisiblezoommultiplier = 6
troopbadgeoverlapmergethreshold = 0.5
FLAG_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "flags"))
troopbadgelayoutcache = {}
troopbadgeassetcache = {}
hoverlabelcache = {}

#FOR ANY GUI PLEASE PUT IT IN HERE
# THIS SHOULD BE THE ONLY FILE WITH GUI CODE IN IT
# TO USE, CALL THE SYNC FUNCTION
# SYNC FUNCTION ARGUMENTS:
# gamephase: "choosecountry" or "play"
# pendingcountry: the country currently selected in the choosecountry phase, or None if no selection
# playercountry: the country currently controlled by the player, or None if not yet chosen
# currentturnnumber: the current turn number, starting at 1
# playergold: the current gold amount of the player
# playerpopulation: the current population amount of the player
# selectedprovinceid: the id of the currently selected province, or None if no selection
# provincemap: a dict mapping province ids to province data dicts
# recruitamount: the current recruit amount based on economy config and owned province count
# recruitenabled: whether the recruit button should be enabled based on player resources
# developmentmode: whether the game is in development mode (ignores recruit costs)
# recruitgoldcost: the current gold cost to recruit based on recruit amount and economy config
# recruitpopulationcost: the current population cost to recruit based on recruit amount and economy config
# countrymenutarget: the country currently targeted by the country interaction menu, or None if no menu
# countriesatwarset: a set of country names that the player country is currently at war with
# selectedtroopentries: list of selected troop rows, each row includes provinceid and troops
# frontlineplacementmode: whether frontline border placement mode is currently active
# hovertext: the current hover text to display based on hovered province, or None if no hover
# mouseposition: the current mouse position in screen coordinates, used for hover text positioning
# troopbadgelist: a list of (centerposition, troopcount) tuples for rendering troop count badges on provinces


def load_flags():
    flags = {}



    # step 1: check if the flags folder exists
    if not os.path.isdir(FLAG_PATH):
        return flags


    for filename in os.listdir(FLAG_PATH):
        # step 2: only read png files
        if not filename.lower().endswith(".png"):
            continue


        filepath = os.path.join(FLAG_PATH, filename)
        if not os.path.isfile(filepath):
            continue

        # step 3: turn the filename into a country key
        country_key = os.path.splitext(filename)[0].strip().lower().replace(" ", "_").replace("-", "_")
        if not country_key:
            continue

        try:
            img = pygame.image.load(filepath).convert_alpha()
        except pygame.error:
            continue

        # step 4: resize to mini flag size
        img = pygame.transform.scale(img, (20, 14))
        flags[country_key] = img

    # step 5: give back all loaded flags
    return flags

def get_text_color(bg):
    r, g, b = bg
    brightness = (r*0.299 + g*0.587 + b*0.114)
    return (0,0,0) if brightness > 186 else (255,255,255)


def gui_gettroopbadgerect(centerposition, troopcount, fontobject):
    layoutkey = (id(fontobject), str(troopcount))
    cachedsize = troopbadgelayoutcache.get(layoutkey)
    if cachedsize is None:
        labelsurface = fontobject.render(str(troopcount), True, (255, 255, 255))
        labelrectangle = labelsurface.get_rect()
        labelrectangle.inflate_ip(10, 6)
        cachedsize = labelrectangle.size
        troopbadgelayoutcache[layoutkey] = cachedsize
    labelrectangle = pygame.Rect(0, 0, cachedsize[0], cachedsize[1])
    labelrectangle.center = (int(centerposition[0]), int(centerposition[1]))
    
    return labelrectangle


def gui_getcountryflagkey(country_name):
    return str(country_name or "").strip().lower().replace(" ", "_").replace("-", "_")


def gui_gettroopbadgevisualrect(centerposition, troopcount, fontobject, flags=None, country_name=None):
    if not centerposition:
        return pygame.Rect(0, 0, 0, 0)

    labelsurface = fontobject.render(str(troopcount), True, (255, 255, 255))
    flagkey = gui_getcountryflagkey(country_name)
    flagimage = flags.get(flagkey) if flags and flagkey else None
    padding = 6
    spacing = 4
    width = labelsurface.get_width() + padding * 2
    if flagimage:
        width += flagimage.get_width() + spacing
    height = max(labelsurface.get_height(), flagimage.get_height() if flagimage else 0) + padding * 2
    labelrectangle = pygame.Rect(0, 0, width, height)
    labelrectangle.center = (int(centerposition[0]), int(centerposition[1]))
    return labelrectangle


def gui_gettroopbadgerowvisuals(fontobject, flags, country_name, troopcount, text_color):
    flagkey = gui_getcountryflagkey(country_name)
    flagimage = flags.get(flagkey) if flags and flagkey else None
    textsurface = fontobject.render(str(troopcount), True, text_color)
    return flagimage, textsurface


def gui_getoverlapratio(firstrect, secondrect):
    intersection = firstrect.clip(secondrect)
    if intersection.width <= 0 or intersection.height <= 0:
        return 0.0

    firstarea = max(1, firstrect.width * firstrect.height)
    secondarea = max(1, secondrect.width * secondrect.height)
    intersectionarea = intersection.width * intersection.height
    return intersectionarea / float(min(firstarea, secondarea))


def gui_shouldmergetroopbadgerects(firstrect, secondrect):
    intersection = firstrect.clip(secondrect)
    if intersection.width <= 0 or intersection.height <= 0:
        return False

    widthratio = intersection.width / float(max(1, min(firstrect.width, secondrect.width)))
    heightratio = intersection.height / float(max(1, min(firstrect.height, secondrect.height)))
    arearatio = gui_getoverlapratio(firstrect, secondrect)
    return (
        arearatio >= troopbadgeoverlapmergethreshold
        or (
            widthratio >= troopbadgeoverlapmergethreshold
            and heightratio >= troopbadgeoverlapmergethreshold
        )
    )


def gui_findtroopbadgeparent(parentlist, index):
    while parentlist[index] != index:
        parentlist[index] = parentlist[parentlist[index]]
        index = parentlist[index]
    return index


def gui_mergetroopbadgeentries(troopbadgelist, fontobject, flags=None):
    entries = []
    for badgeentry in troopbadgelist:
        if isinstance(badgeentry, dict):
            center = badgeentry.get("center")
            troops = max(0, int(badgeentry.get("troops", 0)))
            country = badgeentry.get("country")
            backgroundcolor = badgeentry.get("backgroundcolor", (0, 0, 0))
            bordercolor = badgeentry.get("bordercolor", (165, 165, 165))
            sourceentry = dict(badgeentry)
        else:
            center, troops = badgeentry
            troops = max(0, int(troops))
            country = None
            backgroundcolor = (0, 0, 0)
            bordercolor = (165, 165, 165)
            sourceentry = {
                "center": center,
                "troops": troops,
                "country": country,
                "backgroundcolor": backgroundcolor,
                "bordercolor": bordercolor,
            }

        if not center or troops <= 0:
            continue

        sourceentry["center"] = center
        sourceentry["troops"] = troops
        sourceentry["country"] = country
        sourceentry["backgroundcolor"] = backgroundcolor
        sourceentry["bordercolor"] = bordercolor
        sourceentry["_visualrect"] = gui_gettroopbadgevisualrect(center, troops, fontobject, flags, country)
        entries.append(sourceentry)

    if len(entries) <= 1:
        return entries

    parentlist = list(range(len(entries)))

    def union(firstindex, secondindex):
        firstroot = gui_findtroopbadgeparent(parentlist, firstindex)
        secondroot = gui_findtroopbadgeparent(parentlist, secondindex)
        if firstroot != secondroot:
            parentlist[secondroot] = firstroot

    for firstindex in range(len(entries)):
        firstrect = entries[firstindex]["_visualrect"]
        for secondindex in range(firstindex + 1, len(entries)):
            secondrect = entries[secondindex]["_visualrect"]
            if not firstrect.colliderect(secondrect):
                continue
            if gui_shouldmergetroopbadgerects(firstrect, secondrect):
                union(firstindex, secondindex)

    clusterlookup = {}
    for index, entry in enumerate(entries):
        root = gui_findtroopbadgeparent(parentlist, index)
        clusterlookup.setdefault(root, []).append(entry)

    mergedentries = []
    for cluster in clusterlookup.values():
        if len(cluster) == 1:
            entry = dict(cluster[0])
            entry.pop("_visualrect", None)
            mergedentries.append(entry)
            continue

        centerx = sum(float(entry["center"][0]) for entry in cluster) / len(cluster)
        centery = sum(float(entry["center"][1]) for entry in cluster) / len(cluster)
        rowsbycountry = {}
        firstbackground = cluster[0].get("backgroundcolor", (0, 0, 0))
        firstborder = cluster[0].get("bordercolor", (165, 165, 165))
        mixedstyle = False

        for entry in cluster:
            country = entry.get("country")
            countrykey = gui_getcountryflagkey(country)
            rowkey = countrykey if countrykey else f"entry-{id(entry)}"
            row = rowsbycountry.get(rowkey)
            if row is None:
                rowsbycountry[rowkey] = {
                    "country": country,
                    "countrykey": countrykey,
                    "troops": 0,
                }
                row = rowsbycountry[rowkey]
            row["troops"] += max(0, int(entry.get("troops", 0)))
            if entry.get("backgroundcolor", (0, 0, 0)) != firstbackground or entry.get("bordercolor", (165, 165, 165)) != firstborder:
                mixedstyle = True

        rowlist = sorted(
            rowsbycountry.values(),
            key=lambda row: (str(row.get("country") or "").lower(), -int(row.get("troops", 0))),
        )
        backgroundcolor = (0, 0, 0) if mixedstyle else firstbackground
        bordercolor = (165, 165, 165) if mixedstyle else firstborder
        mergedentry = {
            "center": (centerx, centery),
            "troops": sum(int(row.get("troops", 0)) for row in rowlist),
            "backgroundcolor": backgroundcolor,
            "bordercolor": bordercolor,
        }

        if len(rowlist) == 1:
            mergedentry["country"] = rowlist[0].get("country")
        else:
            mergedentry["rows"] = rowlist

        mergedentries.append(mergedentry)

    return mergedentries


#def DEBUG():
#    pass


def gui_gettroopbadgeasset(fontobject, troopcount, backgroundcolor, bordercolor):
    cachekey = (
        id(fontobject),
        str(troopcount),
        tuple(backgroundcolor),
        tuple(bordercolor),
    )
    cachedsurface = troopbadgeassetcache.get(cachekey)
    if cachedsurface is not None:
        return cachedsurface

    labelsurface = fontobject.render(str(troopcount), True, (255, 255, 255))
    labelrectangle = gui_gettroopbadgerect((0, 0), troopcount, fontobject)
    renderedsurface = pygame.Surface(labelrectangle.size, pygame.SRCALPHA)
    pygame.draw.rect(renderedsurface, backgroundcolor, renderedsurface.get_rect(), border_radius=1)
    pygame.draw.rect(renderedsurface, bordercolor, renderedsurface.get_rect(), width=1, border_radius=1)
    renderedsurface.blit(labelsurface, labelsurface.get_rect(center=renderedsurface.get_rect().center))
    troopbadgeassetcache[cachekey] = renderedsurface
    return renderedsurface


def gui_gethoverlabelsurface(fontobject, state):
    if not state:
        return None

    name = state.get("name", "unknown")
    provinceid = state.get("provinceid", "unknown")
    population = state.get("population", "unknown")
    country = state.get("country", "unknown")
    terrain = state.get("terrain", "unknown")
    province_count = state.get("province_count", "unknown")
    vp = state.get("victory_points", 0)

    lines = [
        f"State: {name}",
        f"Province: {provinceid}",
        f"Population: {population}",
        f"Country: {country}",
        f"Terrain Type: {terrain}",
        f"Number of states: {province_count}",
    ]

    if vp > 0:
        lines.append(f"Victory Points: {vp}")

    cachekey = (id(fontobject), tuple(lines))
    cachedsurface = hoverlabelcache.get(cachekey)
    if cachedsurface is not None:
        return cachedsurface

    padding = 8
    textsurfaces = [fontobject.render(line, True, (255, 255, 255)) for line in lines]
    width = max(text.get_width() for text in textsurfaces) + padding * 2
    height = sum(text.get_height() for text in textsurfaces) + padding * 2

    renderedsurface = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(renderedsurface, (20, 20, 20), renderedsurface.get_rect())
    pygame.draw.rect(renderedsurface, (255, 200, 0), renderedsurface.get_rect(), 2)

    offsety = padding
    for textsurface in textsurfaces:
        renderedsurface.blit(textsurface, (padding, offsety))
        offsety += textsurface.get_height()

    hoverlabelcache[cachekey] = renderedsurface
    return renderedsurface

def gui_buildcountrylabelanchors(stateshapelist, gamephase):
    countryanchorlookup = {}
    for stateshape in stateshapelist:
        staterect = stateshape["rectangle"]

        countryname = stateshape.get("controllercountry", stateshape.get("country"))
        if gamephase == "choosecountry":
            countryname = stateshape.get("country", countryname)
        if not countryname:
            continue

        statewidth = max(1.0, float(staterect.width))
        stateheight = max(1.0, float(staterect.height))
        statearea = statewidth * stateheight
        centerx = float(staterect.centerx)
        centery = float(staterect.centery)
        stateleft = float(staterect.x)
        statetop = float(staterect.y)
        stateright = stateleft + statewidth
        statebottom = statetop + stateheight

        fixedentry = countryanchorlookup.get(countryname)
        if fixedentry is None:
            countryanchorlookup[countryname] = {
                "weightedx": centerx * statearea,
                "weightedy": centery * statearea,
                "weight": statearea,
                "minx": stateleft,
                "miny": statetop,
                "maxx": stateright,
                "maxy": statebottom,
            }
            continue

        fixedentry["weightedx"] += centerx * statearea
        fixedentry["weightedy"] += centery * statearea
        fixedentry["weight"] += statearea
        fixedentry["minx"] = min(fixedentry["minx"], stateleft)
        fixedentry["miny"] = min(fixedentry["miny"], statetop)
        fixedentry["maxx"] = max(fixedentry["maxx"], stateright)
        fixedentry["maxy"] = max(fixedentry["maxy"], statebottom)

    return countryanchorlookup




def gui_lightencolor(colorvalue, amount):


    #print("gui_lightencolor called", colorvalue, amount)


    amount = max(0.0, min(1.0, amount))
    red, green, blue = colorvalue
    return (
        int(red + (255 - red) * amount),
        int(green + (255 - green) * amount),
        int(blue + (255 - blue) * amount),
    )




class EngineUI:
    actionchoosecountry = "choosecountry"
    actionrecruit = "recruit"
    actionendturn = "endturn"
    actiondeclarewar = "declarewar"
    actionsplit = "split"
    actionmerge = "merge"
    actionfrontline = "frontline"


    def __init__(self, window_size):
        #print("EngineUI init start", window_size)
        self.window_size = window_size
        self.manager = pygame_gui.UIManager(window_size)
        self.troopbadgelist = []
        self.troopbadgefont = pygame.font.SysFont("Arial", 16)
        self.hudfont = pygame.font.SysFont("Arial", 18)
        self.hudsmallfont = pygame.font.SysFont("Arial", 16)
        self.hoverfont = pygame.font.SysFont("Arial", 13)
        self.countrylabelfont = pygame.font.SysFont("Arial", 18, bold=True)
        self.countrylabelcache = {}
        self.choosetitlefont = pygame.font.SysFont("Arial", 32, bold=True)
        self.choosetextfont = pygame.font.SysFont("Arial", 16)
        self.choosebuttonrect = pygame.Rect(0, 0, 190, 38)
        self.gamephase = "choosecountry"
        self.pendingcountry = None
        self.choosebuttonenabled = False
        self.hovertextcurrent = None
        self.hovermousepos = (0, 0)
        self.hudheadertext = ""
        self.huddetailtext = ""
        self.hudcontrolstext = ""
        self.selectionpanelwidth = 356 
        self.selectionpanelheight = 308
        self.selectionrowlabels = []
        self.flags = load_flags()

        #print("build elementstest")
        self.buildelements()
        #print("layout")
        self.applylayout()








    def buildelements(self):
        #print("function element")
        self.choose_title = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(0, 0, 420, 28),
            text="Choose your country",
            manager=self.manager,
        )


        self.choose_help = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(0, 0, 620, 24),
            text="click on any province to select the country",
            manager=self.manager,
        )

        self.choose_selected = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(0, 0, 520, 24),
            text="SELECTED: none",
            manager=self.manager,
        )
        self.choose_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(0, 0, 190, 38),
            text="Choose country",
            manager=self.manager,
        )



        self.hud_panel = pygame_gui.elements.UIPanel(
            relative_rect=pygame.Rect(0, 0, 100, 74),
            manager=self.manager,
        )
        self.hud_header = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(10, 8, 1100, 20),
            text="",
            manager=self.manager,
            container=self.hud_panel,
            object_id="#hudheader",
        )
        self.hud_detail = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(10, 30, 1100, 20),
            text="",
            manager=self.manager,
            container=self.hud_panel,
            object_id="#huddetail",
        )
        self.hud_controls = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(10, 52, 1100, 20),
            text="",
            manager=self.manager,
            container=self.hud_panel,
            object_id="#hudcontrols",
        )
        self.hud_header.hide()
        self.hud_detail.hide()
        self.hud_controls.hide()





        self.recruit_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(0, 0, 170, 38),
            text="recruit",
            manager=self.manager,
        )
        self.end_turn_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(0, 0, 190, 38),
            text="end turn",
            manager=self.manager,
        )
        self.recruit_cost_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(0, 0, 330, 20),
            text="",
            manager=self.manager,
            object_id="#recruitcost",
        )


        self.country_panel = pygame_gui.elements.UIPanel(
            relative_rect=pygame.Rect(0, 0, 280, 154),
            manager=self.manager,
        )
        self.country_title = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(12, 10, 240, 22),
            text="Country actions",
            manager=self.manager,
            container=self.country_panel,
        )
        self.country_name = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(12, 34, 240, 22),
            text="",
            manager=self.manager,
            container=self.country_panel,
        )
        self.country_status = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(12, 58, 240, 22),
            text="",
            manager=self.manager,
            container=self.country_panel,
        )




        self.declare_war_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(12, 82, 256, 38),
            text="declare war",
            manager=self.manager,
            container=self.country_panel,
        )
        self.country_hint = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(12, 126, 240, 20),
            text="left click to confirm action",
            manager=self.manager,
            container=self.country_panel,
        )

        self.selection_panel = pygame_gui.elements.UIPanel(
            relative_rect=pygame.Rect(0, 0, self.selectionpanelwidth, self.selectionpanelheight),
            manager=self.manager,
        )
        self.selection_title = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(10, 8, self.selectionpanelwidth - 20, 22),
            text="Troop Information",
            manager=self.manager,
            container=self.selection_panel,
        )
        self.selection_summary = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(10, 30, self.selectionpanelwidth - 20, 22),
            text="",
            manager=self.manager,
            container=self.selection_panel,
        )
        self.selection_status = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(10, 214, self.selectionpanelwidth - 20, 22),
            text="",
            manager=self.manager,
            container=self.selection_panel,
        )
        rowwidth = self.selectionpanelwidth - 20
        for rowindex in range(7):
            rowlabel = pygame_gui.elements.UILabel(
                relative_rect=pygame.Rect(10, 58 + rowindex * 22, rowwidth, 20),
                text="",
                manager=self.manager,
                container=self.selection_panel,
            )
            self.selectionrowlabels.append(rowlabel)

        buttonwidth = 106
        self.split_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(10, 254, buttonwidth, 40),
            text="split",
            manager=self.manager,
            container=self.selection_panel,
        )
        self.merge_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(124, 254, buttonwidth, 40),
            text="merge",
            manager=self.manager,
            container=self.selection_panel,
        )
        self.frontline_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(238, 254, buttonwidth, 40),
            text="frontline",
            manager=self.manager,
            container=self.selection_panel,
        )



        self.hideplayelements()
        self.hidechooseelements()
        self.country_panel.hide()
        self.selection_panel.hide()


    #def applylayout(self):
        #print("applylayout running")
        #window_width, window_height = self.window_size
        #self.choose_title.set_relative_position((window_width // 2 - 210, 14))
        #self.choose_help.set_relative_position((window_width // 2 - 310, 46))
        #self.choose_selected.set_relative_position((20, window_height - 48))
        #self.choose_button.set_relative_position((window_width - 210, window_height - 56))
        #self.choosebuttonrect = pygame.Rect(window_width - 210, window_height - 56, 190, 38)
        #self.hud_panel.set_dimensions((window_width, 74))

    def applylayout(self):


        #print("applylayout running")
        window_width, window_height = self.window_size

        self.choose_title.set_relative_position((window_width // 2 - 210, 14))
        self.choose_help.set_relative_position((window_width // 2 - 310, 46))
        self.choose_selected.set_relative_position((20, window_height - 48))
        self.choose_button.set_relative_position((window_width - 210, window_height - 56))
        self.choosebuttonrect = pygame.Rect(window_width - 210, window_height - 56, 190, 38)


        self.hud_panel.set_dimensions((window_width, 74))
        self.hud_panel.set_relative_position((0, 0))


        self.recruit_button.set_relative_position((window_width - 390, window_height - 56))
        self.end_turn_button.set_relative_position((window_width - 210, window_height - 56))
        self.recruit_cost_label.set_relative_position((window_width - 390, window_height - 72))


        self.country_panel.set_relative_position((0, (window_height - 154) // 2))
        self.selection_panel.set_relative_position(
            (window_width - self.selectionpanelwidth - 16, max(90, (window_height - self.selectionpanelheight) // 2))
        )



    def showchooseelements(self):


        #print("showchooseelements")

        self.choose_title.show()
        self.choose_help.show()
        self.choose_selected.show()
        self.choose_button.show()

    def hidechooseelements(self):


        #print("hidechooseelements")

        self.choose_title.hide()
        self.choose_help.hide()
        self.choose_selected.hide()
        self.choose_button.hide()

    def showplayelements(self):
        #print("showplayelements")


        self.hud_panel.show()
        self.recruit_button.show()
        self.end_turn_button.show()

    def hideplayelements(self):

        #print("hideplayelements")


        self.hud_panel.hide()
        self.hud_header.hide()
        self.hud_detail.hide()
        self.hud_controls.hide()
        self.recruit_button.hide()
        self.end_turn_button.hide()
        self.recruit_cost_label.hide()
        self.selection_panel.hide()

    def setwindowsize(self, window_size):

        #print("setwindowsize", window_size)
        self.window_size = window_size
        self.manager.set_window_resolution(window_size)
        self.applylayout()







    # FUNCITON TO UPDATE EVERY TIME SYNC IS CALLED, UPDATE UI WITH NEW DATA
    def sync(
        self,
        gamephase,
        pendingcountry,
        playercountry,
        currentturnnumber,
        playergold,
        playerpopulation,
        selectedprovinceid,
        provincemap,
        recruitamount,
        recruitenabled,
        developmentmode,
        recruitgoldcost,
        recruitpopulationcost,
        countrymenutarget,
        countriesatwarset,
        selectedtroopentries,
        frontlineplacementmode,
        hovertext,
        mouseposition,
        troopbadgelist,
    ):
        
        #print("sync", gamephase, pendingcountry)
        self.applylayout()
        self.gamephase = gamephase
        self.pendingcountry = pendingcountry
        self.choosebuttonenabled = pendingcountry is not None

        if gamephase == "choosecountry":
            #print("sync choosecountry phase")
            self.hideplayelements()
            self.country_panel.hide()
            self.selection_panel.hide()
            self.hidechooseelements()
            


        else:
            #print("sync play phase")

            self.hidechooseelements()
            self.showplayelements()


            headertext = (
                f"{playercountry} | turn {currentturnnumber} | gold {playergold} | population {playerpopulation}"
            )
            self.hudheadertext = headertext



            if selectedprovinceid:
                #print("selected province", selectedprovinceid)
                selectedprovince = provincemap[selectedprovinceid]
                detailtext = (
                    f"province: {selectedprovinceid} | troops: {selectedprovince['troops']} | "
                    f"terrain: {selectedprovince['terrain']}"
                )



            else:
                #print("no selected province")
                detailtext = "select a province in your country"
            self.huddetailtext = detailtext



            if frontlineplacementmode:
                self.hudcontrolstext = (
                    "frontline mode: hover highlighted border and left click to place line"
                )
            else:
                self.hudcontrolstext = (
                    "left click troop badge: select | drag: multi-select troops | right click: move/order country actions"
                )



            self.recruit_button.set_text(f"recruit +{recruitamount}")


            if recruitenabled:

                #print("recruit enabled")
                self.recruit_button.enable()
            else:
                #print("recruit disabled")
                self.recruit_button.disable()



            if developmentmode:
                #print("dev mode on")
                self.recruit_cost_label.hide()

            else:
                #print("dev mode off show cost")
                self.recruit_cost_label.set_text(
                    f"Cost: {recruitgoldcost}g, {recruitpopulationcost} pop"
                )
                self.recruit_cost_label.show()




            if countrymenutarget:

                #print("country menu target", countrymenutarget)
                self.country_panel.show()
                self.country_name.set_text(countrymenutarget)
                alreadyatwar = countrymenutarget in countriesatwarset
                self.country_status.set_text("Status: at war" if alreadyatwar else "Status: peace")
                self.declare_war_button.set_text("Already at war!" if alreadyatwar else "Declare War")


                if alreadyatwar:
                    self.declare_war_button.disable()
                else:
                    self.declare_war_button.enable()
            else:
                #print("hide country menu")
                self.country_panel.hide()

            selectedentries = list(selectedtroopentries or [])
            totaltroops = sum(max(0, int(entry.get("troops", 0))) for entry in selectedentries)
            if selectedentries:
                self.selection_panel.show()
                self.selection_summary.set_text(
                    f"{len(selectedentries)} selected (Total troops: {totaltroops})"
                )

                maxrows = len(self.selectionrowlabels)
                for rowindex, rowlabel in enumerate(self.selectionrowlabels):
                    if rowindex < maxrows and rowindex < len(selectedentries):
                        rowentry = selectedentries[rowindex]
                        provinceid = rowentry.get("provinceid", "unknown")
                        troopcount = int(rowentry.get("troops", 0))
                        rowlabel.set_text(f"{provinceid}: {troopcount} troops")
                        rowlabel.show()
                    else:
                        rowlabel.set_text("")
                        rowlabel.hide()

                if len(selectedentries) > maxrows:
                    overflowcount = len(selectedentries) - maxrows
                    self.selectionrowlabels[-1].set_text(f" ----> AND {overflowcount} more provinces")
                    self.selectionrowlabels[-1].show()

                if frontlineplacementmode:
                    self.selection_status.set_text("frontline: click highlighted border")
                    self.frontline_button.set_text("CANCEL!!")
                else:
                    self.selection_status.set_text("")
                    self.frontline_button.set_text("Set Frontline")

                if totaltroops > 1:
                    self.split_button.enable()
                else:
                    self.split_button.disable()

                if len(selectedentries) > 1:
                    self.merge_button.enable()
                else:
                    self.merge_button.disable()

                if totaltroops > 0:
                    self.frontline_button.enable()
                else:
                    self.frontline_button.disable()
            else:
                self.selection_panel.hide()



        self.hovertextcurrent = hovertext
        self.hovermousepos = mouseposition

        self.troopbadgelist = list(troopbadgelist)  


    def process_event(self, event):

        #print("process_event", event)
        self.manager.process_events(event)



        if event.type == pygame.USEREVENT and event.user_type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.recruit_button:
                return self.actionrecruit
            if event.ui_element == self.end_turn_button:
                return self.actionendturn
            if event.ui_element == self.declare_war_button:
                return self.actiondeclarewar
            if event.ui_element == self.split_button:
                return self.actionsplit
            if event.ui_element == self.merge_button:
                return self.actionmerge
            if event.ui_element == self.frontline_button:
                return self.actionfrontline


        return None


    def update(self, elapsedseconds):

        #print("update", elapsedseconds)
        self.manager.update(elapsedseconds)



    # RENDER FUNCTION
    def draw(self, screen):
        #print("draw")


        # this is for choose country overlay
        if self.gamephase == "choosecountry":
            self.drawchooseoverlay(screen)


        # this is for main gameplay 
        self.manager.draw_ui(screen)
        if self.gamephase != "choosecountry":
            screen.blit(self.hudfont.render(self.hudheadertext, True, (242, 242, 242)), (10, 8))
            screen.blit(self.hudfont.render(self.huddetailtext, True, (236, 236, 236)), (10, 30))
            screen.blit(self.hudsmallfont.render(self.hudcontrolstext, True, (215, 215, 215)), (10, 52))
        visiblebadgelist = gui_mergetroopbadgeentries(self.troopbadgelist, self.troopbadgefont, self.flags)
        for badgeentry in visiblebadgelist:
            if isinstance(badgeentry, dict):
                gui_drawtroopcountbadge(
                    screen,
                    badgeentry.get("center"),
                    badgeentry.get("troops", 0),
                    self.troopbadgefont,
                    self.flags,
                    badgeentry.get("country"),
                    backgroundcolor=badgeentry.get("backgroundcolor", (0, 0, 0)),
                    bordercolor=badgeentry.get("bordercolor", (165, 165, 165)),
                    rows=badgeentry.get("rows"),
                )
                continue

            badgecenter, badgetroops = badgeentry
            gui_drawtroopcountbadge(screen, badgecenter, badgetroops, self.troopbadgefont, self.flags, None)
        if self.hovertextcurrent:
            mousex, mousey = self.hovermousepos
            gui_drawhoverlabel(screen, self.hoverfont, self.hovertextcurrent, (mousex, mousey))





    def drawchooseoverlay(self, screen):

        #print("drawchooseoverlay")
        window_width, window_height = self.window_size

        darksurface = pygame.Surface((window_width, window_height), pygame.SRCALPHA)
        darksurface.fill((0, 0, 0, 95))
        screen.blit(darksurface, (0, 0))

        titletext = self.choosetitlefont.render("choose your country", True, (250, 250, 250))
        screen.blit(titletext, titletext.get_rect(midtop=(window_width // 2, 16)))

        helptext = self.choosetextfont.render("click on any province to select the country", True, (225, 225, 225))
        screen.blit(helptext, helptext.get_rect(midtop=(window_width // 2, 60)))

        selectedtext = f"selected: {self.pendingcountry}" if self.pendingcountry else "selected: none"

        selectedlabel = self.choosetextfont.render(selectedtext, True, (240, 240, 240))

        screen.blit(selectedlabel, (20, window_height - 48))

        buttoncolor = (56, 116, 198) if self.choosebuttonenabled else (70, 70, 70)
        pygame.draw.rect(screen, buttoncolor, self.choosebuttonrect, border_radius=1)
        pygame.draw.rect(screen, (35, 35, 35), self.choosebuttonrect, width=1, border_radius=1)
        buttontext = self.choosetextfont.render("choose country", True, (240, 240, 240))
        screen.blit(buttontext, buttontext.get_rect(center=self.choosebuttonrect.center))





    def clickchoosebutton(self, mouseposition):
        #print("clickchoosebutton", mouseposition)
        if self.gamephase != "choosecountry":
            return False
        if not self.choosebuttonenabled:
            return False
        return self.choosebuttonrect.collidepoint(mouseposition)






    def ispointeroverui(self, mouseposition):
        #print("ispointeroverui", mouseposition)

        # choosecountry button is drawn manually, so check its rect directly
        if self.gamephase == "choosecountry":
            if self.choosebuttonrect.collidepoint(mouseposition):
                return True
            return False

        # in play phase, only block map clicks for actual clickable UI controls
        hittestelements = [
            self.recruit_button,
            self.end_turn_button,
            self.declare_war_button,
            self.split_button,
            self.merge_button,
            self.frontline_button,
        ]

        for element in hittestelements:
            if not getattr(element, "visible", True):
                continue
            if element.get_abs_rect().collidepoint(mouseposition):
                return True

        # country menu panel should block map clicks while visible
        if getattr(self.country_panel, "visible", True) and self.country_panel.get_abs_rect().collidepoint(mouseposition):
            return True
        if getattr(self.selection_panel, "visible", True) and self.selection_panel.get_abs_rect().collidepoint(mouseposition):
            return True

        return False


#def helperAaa():
#    pass






















def gui_drawtroopcountbadge(
    screen,
    centerposition,
    troopcount,
    fontobject,
    flags=None,
    country_name=None,
    backgroundcolor=(0, 0, 0),
    bordercolor=(165, 165, 165),
    rows=None,
):
    # step 1: stop if center position is missing
    if not centerposition:
        return

    x, y = centerposition

    # step 2: render readable text color against the badge background
    if backgroundcolor in [(214, 194, 64), (214, 122, 36)]:
        text_color = (0, 0, 0)
    else:
        r, g, b = backgroundcolor
        brightness = (r * 0.299 + g * 0.587 + b * 0.114)
        text_color = (0, 0, 0) if brightness > 186 else (255, 255, 255)

    padding = 6
    spacing = 4
    rowspacing = 2

    if rows:
        rowvisuals = []
        contentwidth = 0
        rowheights = []
        for row in rows:
            flag_img, text_surf = gui_gettroopbadgerowvisuals(
                fontobject,
                flags or {},
                row.get("country"),
                row.get("troops", 0),
                text_color,
            )
            rowwidth = text_surf.get_width()
            if flag_img:
                rowwidth += flag_img.get_width() + spacing
            rowheight = max(text_surf.get_height(), flag_img.get_height() if flag_img else 0)
            rowvisuals.append((flag_img, text_surf, rowwidth, rowheight))
            contentwidth = max(contentwidth, rowwidth)
            rowheights.append(rowheight)

        width = contentwidth + padding * 2
        height = sum(rowheights) + rowspacing * max(0, len(rowheights) - 1) + padding * 2
        rect = pygame.Rect(x - width // 2, y - height // 2, width, height)
        pygame.draw.rect(screen, backgroundcolor, rect, border_radius=4)
        pygame.draw.rect(screen, bordercolor, rect, 1, border_radius=4)

        draw_y = rect.y + padding
        for flag_img, text_surf, rowwidth, rowheight in rowvisuals:
            draw_x = rect.x + padding
            center_y = draw_y + rowheight // 2
            if flag_img:
                screen.blit(flag_img, (draw_x, center_y - flag_img.get_height() // 2))
                draw_x += flag_img.get_width() + spacing
            screen.blit(text_surf, (draw_x, center_y - text_surf.get_height() // 2))
            draw_y += rowheight + rowspacing
        return

    country_key = gui_getcountryflagkey(country_name)
    text_surf = fontobject.render(str(troopcount), True, text_color)
    
    # step 3: get matching mini flag if it exists
    flag_img = flags.get(country_key) if flags and country_key else None

    # step 4: compute badge size from text and optional flag
    content_width = text_surf.get_width()

    if flag_img:
        content_width += flag_img.get_width() + spacing

    width = content_width + padding * 2
    height = max(
        text_surf.get_height(),
        flag_img.get_height() if flag_img else 0
    ) + padding * 2

    rect = pygame.Rect(
        x - width // 2,
        y - height // 2,
        width,
        height
    )

    # step 5: draw the badge box
    pygame.draw.rect(screen, backgroundcolor, rect, border_radius=4)
    pygame.draw.rect(screen, bordercolor, rect, 1, border_radius=4)

    draw_x = rect.x + padding

    # step 6: find vertical center for alignment
    center_y = rect.y + rect.height // 2

    # step 7: draw flag on the left
    if flag_img:
        flag_y = center_y - flag_img.get_height() // 2
        screen.blit(flag_img, (draw_x, flag_y))
        draw_x += flag_img.get_width() + spacing

    # step 8: draw troop number on the right
    text_y = center_y - text_surf.get_height() // 2
    screen.blit(text_surf, (draw_x, text_y))

def gui_drawhoverlabel(screen, fontobject, state, mouseposition):
    if not state:
        return

    x = mouseposition[0] + 16
    y = mouseposition[1] + 16
    hoverlabelsurface = gui_gethoverlabelsurface(fontobject, state)
    if hoverlabelsurface is None:
        return
    screen.blit(hoverlabelsurface, (x, y))


def gui_shouldshowtroopbadges(zoomvalue, minimumzoom):
    # made badge visiblity relative to zoom instead of fixed
    basezoomthreshold = minimumzoom * troopbadgevisiblezoommultiplier
    cappedzoomthreshold = minimumzoom + 0.9
    return zoomvalue >= min(basezoomthreshold, cappedzoomthreshold)


def gui_shouldshowcountrylabels(zoomvalue, minimumzoom):
    return zoomvalue <= minimumzoom * countrylabelvisiblezoommultiplier

def gui_buildoutlinedtext(
    fontobject,
    textvalue,
    textcolor=(235, 235, 235),
    outlinecolor=(26, 26, 26),
    outlinewidth=2,
):
    labelsurface = fontobject.render(textvalue, True, textcolor)
    width = labelsurface.get_width() + outlinewidth * 2
    height = labelsurface.get_height() + outlinewidth * 2
    renderedsurface = pygame.Surface((width, height), pygame.SRCALPHA)

    outlinesurface = fontobject.render(textvalue, True, outlinecolor)
    for offsetx in range(-outlinewidth, outlinewidth + 1):
        for offsety in range(-outlinewidth, outlinewidth + 1):
            if offsetx == 0 and offsety == 0:
                continue
            renderedsurface.blit(outlinesurface, (offsetx + outlinewidth, offsety + outlinewidth))

    renderedsurface.blit(labelsurface, (outlinewidth, outlinewidth))
    return renderedsurface


def gui_getcountrylabelsurface(labelcache, fontobject, textvalue, fontsize):
    fontcache = labelcache.setdefault("_fontcache", {})
    baselabelcache = labelcache.setdefault("_baselabels", {})

    fontsize = int(max(11, min(58, fontsize)))

    fontentry = fontcache.get(fontsize)
    if fontentry is None:
        fontname = pygame.font.get_default_font()
        try:
            fontname = fontobject.get_name()
        except AttributeError:
            pass
        fontentry = pygame.font.SysFont(fontname, fontsize, bold=True)
        fontcache[fontsize] = fontentry

    basekey = (textvalue, fontsize)
    baselabelsurface = baselabelcache.get(basekey)
    if baselabelsurface is None:
        outlinewidth = max(2, min(4, int(fontsize * 0.08)))
        baselabelsurface = gui_buildoutlinedtext(
            fontentry,
            textvalue,
            outlinewidth=outlinewidth,
        )
        baselabelcache[basekey] = baselabelsurface

    baselabelsurface.set_alpha(128)
    return baselabelsurface


def gui_drawcountrylabels(
    screen,
    stateshapelist,
    zoomvalue,
    camerax,
    cameray,
    copyshiftlist,
    screenrectangle,
    fontobject,
    labelcache,
    gamephase,
):
    # Ebee Super Optimization (ESO) 27/4
    # O(k*s) -> O(s + k*c)
    # build country anchors once per frame and reuse across wrapped copies
    countryanchorlookup = gui_buildcountrylabelanchors(stateshapelist, gamephase)

    for copyshift in copyshiftlist:
        drawcamerax = camerax + copyshift

        for countryname, fixedentry in countryanchorlookup.items():
            labeltext = str(countryname).replace("_", " ")

            weight = max(1.0, fixedentry["weight"])
            centerx = (fixedentry["weightedx"] / weight) * zoomvalue + drawcamerax
            centery = (fixedentry["weightedy"] / weight) * zoomvalue + cameray
            boxwidth = max(1.0, (fixedentry["maxx"] - fixedentry["minx"]) * zoomvalue)
            boxheight = max(1.0, (fixedentry["maxy"] - fixedentry["miny"]) * zoomvalue)

            if boxwidth < 50 or boxheight < 20:
                continue

            labelscale = math.sqrt((boxwidth * boxheight) / 12000.0)
            fontsize = int(12 + labelscale * 13)

            labelsurface = gui_getcountrylabelsurface(
                labelcache,
                fontobject,
                labeltext,
                fontsize,
            )

            labelrectangle = labelsurface.get_rect(center=(int(centerx), int(centery)))
            if not labelrectangle.colliderect(screenrectangle):
                continue

            countrybox = pygame.Rect(
                int(fixedentry["minx"] * zoomvalue + drawcamerax),
                int(fixedentry["miny"] * zoomvalue + cameray),
                max(1, int(boxwidth)),
                max(1, int(boxheight)),
            )
            if labelrectangle.width > countrybox.width * 1.55 or labelrectangle.height > countrybox.height * 1.25:
                continue
            screen.blit(labelsurface, labelrectangle)


def gui_arrowhead(screen, endpoint, directionvector, colorvalue, arrowsize, linewidth):
    vectorlength = math.hypot(directionvector[0], directionvector[1])
    if vectorlength <= 1e-9: # divide by zero error
        return


    #skip drawing arrowhead
    normalizedx = directionvector[0] / vectorlength
    normalizedy = directionvector[1] / vectorlength
    sideangle = math.radians(24)
    cosinevalue = math.cos(sideangle)
    sinevalue = math.sin(sideangle)

    leftx = normalizedx * cosinevalue - normalizedy * sinevalue # this is the left side of the arrowhead
    lefty = normalizedx * sinevalue + normalizedy * cosinevalue 
    rightx = normalizedx * cosinevalue + normalizedy * sinevalue # right
    righty = -normalizedx * sinevalue + normalizedy * cosinevalue

    leftpoint = (endpoint[0] - leftx * arrowsize, endpoint[1] - lefty * arrowsize)
    rightpoint = (endpoint[0] - rightx * arrowsize, endpoint[1] - righty * arrowsize)

    pygame.draw.polygon(screen, colorvalue, [endpoint, leftpoint, rightpoint])
    pygame.draw.polygon(screen, (30, 30, 30), [endpoint, leftpoint, rightpoint], max(1, linewidth // 2))


def gui_getmovementpathworldpoints(movementorder, provincemap, startindex):
    pathlist = movementorder.get("path", [])
    cacheentry = movementorder.get("_pathworldpointcache")
    if (
        cacheentry is not None
        and cacheentry.get("path") is pathlist
        and cacheentry.get("startindex") == startindex
    ):
        return cacheentry.get("points", [])

    pathpointsworld = []
    for provinceid in pathlist[startindex:]:
        province = provincemap.get(provinceid)
        if not province:
            pathpointsworld = []
            break
        pathpointsworld.append(province.get("center", (province["rectangle"].centerx, province["rectangle"].centery)))

    movementorder["_pathworldpointcache"] = {
        "path": pathlist,
        "startindex": startindex,
        "points": pathpointsworld,
    }
    return pathpointsworld




def gui_drawmovementorderpaths(
    screen,
    movementorderlist,
    provincemap,
    zoomvalue,
    camerax,
    cameray,
    copyshiftlist,
    screenrectangle,
):
    linewidth = max(2, min(6, int(zoomvalue * 3.0)))
    arrowsize = max(7, min(16, int(zoomvalue * 10.0)))



    for movementorder in movementorderlist:
        pathlist = movementorder.get("path", [])
        if len(pathlist) < 2:
            continue

        startindex = int(movementorder.get("index", 0))
        if startindex < 0:
            startindex = 0
        if startindex >= len(pathlist) - 1:
            continue

        # Ebee Super Optimization (ESO) 27/4
        # O(m*p) -> O(m)
        # cache world-space path points until the order advances
        pathpointsworld = gui_getmovementpathworldpoints(movementorder, provincemap, startindex)
        if len(pathpointsworld) < 2:
            continue



        basecolor = movementorder.get("countrycolor") or (124, 196, 255)
        linecolor = gui_lightencolor(basecolor, 0.2)

        for copyshift in copyshiftlist:
            drawcamerax = camerax + copyshift
            pathpointsscreen = [
                (worldpoint[0] * zoomvalue + drawcamerax, worldpoint[1] * zoomvalue + cameray)
                for worldpoint in pathpointsworld
            ]



            hasscreensegment = False
            for segmentindex in range(len(pathpointsscreen) - 1):
                segmentstart = pathpointsscreen[segmentindex]
                segmentend = pathpointsscreen[segmentindex + 1]
                segmentleft = int(min(segmentstart[0], segmentend[0])) - arrowsize
                segmenttop = int(min(segmentstart[1], segmentend[1])) - arrowsize
                segmentwidth = int(abs(segmentend[0] - segmentstart[0])) + arrowsize * 2
                segmentheight = int(abs(segmentend[1] - segmentstart[1])) + arrowsize * 2
                segmentrectangle = pygame.Rect(segmentleft, segmenttop, max(1, segmentwidth), max(1, segmentheight))
                if segmentrectangle.colliderect(screenrectangle):
                    hasscreensegment = True
                    break



            if not hasscreensegment:
                continue



            pygame.draw.lines(screen, linecolor, False, pathpointsscreen, linewidth)
            for segmentindex in range(len(pathpointsscreen) - 1):
                segmentstart = pathpointsscreen[segmentindex]
                segmentend = pathpointsscreen[segmentindex + 1]
                directionvector = (segmentend[0] - segmentstart[0], segmentend[1] - segmentstart[1])
                if abs(directionvector[0]) <= 1e-9 and abs(directionvector[1]) <= 1e-9:
                    continue
                gui_arrowhead(screen, segmentend, directionvector, linecolor, arrowsize, linewidth)



def drawdevfpsgraph(screen, fontobject, fpshistory):
    if len(fpshistory) < 2:
        return

    graphwidth = 220
    graphheight = 96
    marginleft = 10
    marginbottom = 10
    graphx = marginleft
    graphy = screen.get_height() - graphheight - marginbottom
    graphrect = pygame.Rect(graphx, graphy, graphwidth, graphheight)

    graphsurface = pygame.Surface((graphwidth, graphheight), pygame.SRCALPHA)
    graphsurface.fill((8, 12, 16, 120))
    pygame.draw.rect(graphsurface, (170, 200, 240, 92), graphsurface.get_rect(), width=1)

    innerleft = 8
    innertop = 8
    innerright = graphwidth - 8
    innerbottom = graphheight - 20
    innerwidth = max(1, innerright - innerleft)
    innerheight = max(1, innerbottom - innertop)

    maxfps = max(10.0, max(fpshistory))
    maxfps = maxfps * 1.10
    minfps = 0.0

    gridlinecolor = (130, 165, 195, 48)
    for ratio in (0.25, 0.5, 0.75):
        gridy = int(innerbottom - innerheight * ratio)
        pygame.draw.line(graphsurface, gridlinecolor, (innerleft, gridy), (innerright, gridy), 1)

    pointcount = len(fpshistory)
    stepx = innerwidth / max(1, pointcount - 1)
    graphpoints = []
    for index, samplefps in enumerate(fpshistory):
        normalized = (samplefps - minfps) / max(1e-6, (maxfps - minfps))
        normalized = max(0.0, min(1.0, normalized))
        pointx = innerleft + int(index * stepx)
        pointy = innerbottom - int(normalized * innerheight)
        graphpoints.append((pointx, pointy))

    pygame.draw.lines(graphsurface, (95, 210, 145, 220), False, graphpoints, 2)

    currentfps = fpshistory[-1]
    minrecentfps = min(fpshistory)
    summarylabel = fontobject.render(
        f"FPS {currentfps:4.1f} | low {minrecentfps:4.1f}",
        True,
        (228, 236, 248),
    )
    graphsurface.blit(summarylabel, (innerleft, graphheight - 16))

    screen.blit(graphsurface, graphrect.topleft)


def gui_drawcountryborders(
    screen,
    bordersegmentlist,
    zoomvalue,
    camerax,
    cameray,
    copyshiftlist,
    screenrectangle,
):
    if not bordersegmentlist or zoomvalue <= 0:
        return

    borderwidth = max(1, min(4, int(zoomvalue * 1.2)))
    bordercolor = (0, 0, 0)
    minlengthsquared = 1.2 * 1.2



    for copyshift in copyshiftlist:
        drawcamerax = camerax + copyshift
        visibleworldleft = (screenrectangle.left - drawcamerax) / zoomvalue
        visibleworldright = (screenrectangle.right - drawcamerax) / zoomvalue
        visibleworldtop = (screenrectangle.top - cameray) / zoomvalue
        visibleworldbottom = (screenrectangle.bottom - cameray) / zoomvalue



        for bordersegmententry in bordersegmentlist:
            if isinstance(bordersegmententry, dict):
                if (
                    bordersegmententry["maxx"] < visibleworldleft
                    or bordersegmententry["minx"] > visibleworldright
                    or bordersegmententry["maxy"] < visibleworldtop
                    or bordersegmententry["miny"] > visibleworldbottom
                ):
                    continue
                worldsegmentstart = bordersegmententry["start"]
                worldsegmentend = bordersegmententry["end"]
            else:
                worldsegmentstart, worldsegmentend = bordersegmententry

            segmentstart = (
                worldsegmentstart[0] * zoomvalue + drawcamerax,
                worldsegmentstart[1] * zoomvalue + cameray,
            )
            segmentend = (
                worldsegmentend[0] * zoomvalue + drawcamerax,
                worldsegmentend[1] * zoomvalue + cameray,
            )



            segmentleft = int(min(segmentstart[0], segmentend[0])) - borderwidth
            segmenttop = int(min(segmentstart[1], segmentend[1])) - borderwidth
            segmentwidth = int(abs(segmentend[0] - segmentstart[0])) + borderwidth * 2
            segmentheight = int(abs(segmentend[1] - segmentstart[1])) + borderwidth * 2
            segmentrectangle = pygame.Rect(segmentleft, segmenttop, max(1, segmentwidth), max(1, segmentheight))
            if not segmentrectangle.colliderect(screenrectangle):
                continue

            dx = segmentend[0] - segmentstart[0] # avoid short segment
            dy = segmentend[1] - segmentstart[1]
            if dx * dx + dy * dy < minlengthsquared:
                continue

            pygame.draw.line(screen, bordercolor, segmentstart, segmentend, borderwidth)




def gui_drawchoosecountryoverlay(screen, titlefontobject, fontobject, selectedcountry):
    windowwidth, windowheight = screen.get_size()
    darksurface = pygame.Surface((windowwidth, windowheight), pygame.SRCALPHA)
    darksurface.fill((0, 0, 0, 95))
    screen.blit(darksurface, (0, 0))

    titletext = titlefontobject.render("choose your country", True, (250, 250, 250))
    screen.blit(titletext, titletext.get_rect(midtop=(windowwidth // 2, 16)))

    helptext = fontobject.render("click on any provinces to select the country", True, (225, 225, 225))
    screen.blit(helptext, helptext.get_rect(midtop=(windowwidth // 2, 58)))

    choosebuttonrectangle = pygame.Rect(windowwidth - 210, windowheight - 56, 190, 38)

    pygame.draw.rect(screen, (56, 116, 198), choosebuttonrectangle, border_radius=1)
    pygame.draw.rect(screen, (35, 35, 35), choosebuttonrectangle, width=1, border_radius=1)

    labelsurface = fontobject.render("choose country", True, (240, 240, 240))
    screen.blit(labelsurface, labelsurface.get_rect(center=choosebuttonrectangle.center))

    if selectedcountry:
        selectedlabel = fontobject.render(f"selected: {selectedcountry}", True, (240, 240, 240))
        screen.blit(selectedlabel, (20, windowheight - 48))

    return choosebuttonrectangle, selectedcountry is not None


def gui_countryactionmenu(screen, fontobject, smallfontobject, targetcountry, alreadyatwar):
    placehldr, windowheight = screen.get_size()
    menuwidth = 280
    menuheight = 154
    menux = 0
    menuy = (windowheight - menuheight) // 2
    menurectangle = pygame.Rect(menux, menuy, menuwidth, menuheight)

    pygame.draw.rect(screen, (26, 26, 35), menurectangle, border_radius=1)
    pygame.draw.rect(screen, (92, 92, 116), menurectangle, width=2, border_radius=1)

    titlelabel = fontobject.render("Country actions", True, (240, 240, 240))
    screen.blit(titlelabel, (menurectangle.x + 12, menurectangle.y + 10))

    countrylabel = fontobject.render(targetcountry, True, (220, 220, 220))
    screen.blit(countrylabel, (menurectangle.x + 12, menurectangle.y + 34))

    statustext = "status: at war" if alreadyatwar else "status: peace"
    statuslabel = smallfontobject.render(statustext, True, (205, 205, 215))
    screen.blit(statuslabel, (menurectangle.x + 12, menurectangle.y + 58))

    declarebuttonrectangle = pygame.Rect(menurectangle.x + 12, menurectangle.y + 82, menurectangle.width - 24, 38)
    pygame.draw.rect(screen, (56, 116, 198), declarebuttonrectangle, border_radius=1)
    pygame.draw.rect(screen, (35, 35, 35), declarebuttonrectangle, width=1, border_radius=1)
    buttontext = "already at war" if alreadyatwar else "declare war"
    buttonlabel = fontobject.render(buttontext, True, (240, 240, 240))
    screen.blit(buttonlabel, buttonlabel.get_rect(center=declarebuttonrectangle.center))

    hintlabel = smallfontobject.render("left click to confirm action", True, (178, 178, 188))
    screen.blit(hintlabel, (menurectangle.x + 12, menurectangle.y + 126))

    return menurectangle, declarebuttonrectangle


def gui_drawgameplayhud(
    screen,
    fontobject,
    smallfontobject,
    playercountry,
    currentturnnumber,
    currentgold,
    currentpopulation,
    selectedprovinceid,
    provincemap,
    recruitamount,
    recruitenabled,
    developmentmode,
    recruitgoldcost,
    recruitpopulationcost,
):
    windowwidth, windowheight = screen.get_size()
    topsurface = pygame.Surface((windowwidth, 74), pygame.SRCALPHA)
    topsurface.fill((0, 0, 0, 120))
    screen.blit(topsurface, (0, 0))

    headertext = f"{playercountry} | turn {currentturnnumber} | gold {currentgold} | population {currentpopulation}"
    screen.blit(fontobject.render(headertext, True, (242, 242, 242)), (10, 8))

    if selectedprovinceid:
        selectedprovince = provincemap[selectedprovinceid]
        detailtext = (
            f"province: {selectedprovinceid} | troops: {selectedprovince['troops']} | "
            f"terrain: {selectedprovince['terrain']}"
        )
        screen.blit(fontobject.render(detailtext, True, (236, 236, 236)), (10, 30))
    else:
        screen.blit(fontobject.render("select a province in your country", True, (205, 205, 205)), (10, 30))

    controltext = "left click: open state/select province | right click foreign province: country actions"
    screen.blit(smallfontobject.render(controltext, True, (215, 215, 215)), (10, 52))

    recruitbuttonrectangle = pygame.Rect(windowwidth - 390, windowheight - 56, 170, 38)
    endturnbuttonrectangle = pygame.Rect(windowwidth - 210, windowheight - 56, 190, 38)
    pygame.draw.rect(screen, (56, 116, 198), recruitbuttonrectangle, border_radius=1)
    pygame.draw.rect(screen, (35, 35, 35), recruitbuttonrectangle, width=1, border_radius=1)
    pygame.draw.rect(screen, (56, 116, 198), endturnbuttonrectangle, border_radius=1)
    pygame.draw.rect(screen, (35, 35, 35), endturnbuttonrectangle, width=1, border_radius=1)

    recruitlabel = fontobject.render(f"recruit +{recruitamount}", True, (240, 240, 240))
    endturnlabel = fontobject.render("end turn", True, (240, 240, 240))
    screen.blit(recruitlabel, recruitlabel.get_rect(center=recruitbuttonrectangle.center))
    screen.blit(endturnlabel, endturnlabel.get_rect(center=endturnbuttonrectangle.center))

    if not developmentmode:
        costtext = smallfontobject.render(
            f"cost: {recruitgoldcost}g, {recruitpopulationcost} pop",
            True,
            (210, 210, 210),
        )
        screen.blit(costtext, (windowwidth - 390, windowheight - 72))

    return recruitbuttonrectangle, endturnbuttonrectangle
