import os
import json
import math
import time
import platform
import pygame
import xml.etree.ElementTree as elementtree
from svgelements import Path
import ctypes
ctypes.windll.user32.SetProcessDPIAware()

#TODO - OPTIMIZATION: consider using numpy for heavy geometry calculations and data handling, especially for large maps with many provinces and complex shapes. This could significantly improve performance for operations like point-in-polygon tests, polygon transformations, and adjacency graph construction.
#Local module
from game.ingame_ui import InGameUI
from game.focuseffects import FocusEffectContext
from game.focusloader import loadfocustreeforcountry
from engine.console import developmentconsole, loaddevmodeflag 
from engine.gui import (
    gui_lightencolor,
    gui_gettroopbadgerect,
    gui_shouldshowtroopbadges,
    gui_shouldshowcountrylabels,
    gui_drawmovementorderpaths,
    gui_drawcountrylabels,
    gui_drawcountryborders,
    drawdevfpsgraph,
)
from engine.diagnostics import logstartupdiagnostics, createloadingprogresscallback, logslowpath
from . import core as coremodule
from . import movement as movementmodule
from . import economy as economymodule
from . import api as apimodule
from . import camera as cameramodule
from . import eso as esomodule
from . import npc as npcmodule
from .events import EventBus, EngineEventType


from .apicalltest.newsbannereventtest import NewsSystem, NewsPopup # TEST API CALL


# THIS FILE IS A MESS!!!!
# Write everything twice or something i forgot

print("CURRENT VERSION - APRIL 29 2024")
# MAIN GAME LOOP FILE


# configuration

#filepath = "map.csv"
statefilepath = "map/states.svg"
provincefilepath = "map/provinces.svg"
countrydatafilepath = "map/countries.json"
defaultwindowwidth = 1280
defaultwindowheight = 720
backgroundcolor = (30, 30, 30)
defaultshapecolor = (200, 200, 200)
hovercolor = (255, 100, 100)
minimumzoomvalue = cameramodule.minimumzoomvalue
maximumzoomvalue = cameramodule.maximumzoomvalue
zoomstepvalue = cameramodule.zoomstepvalue
edgepanmargin = cameramodule.defaultpanconfig.margin
edgepanspeed = cameramodule.defaultpanconfig.speed
curvesamplestep = 1.5
maxsegmentsteps = 48


# GAME LOGIC AND RENDERING STARTS




def getsegmentsamplecount(segment):
    segmenttypename = type(segment).__name__
    if segmenttypename == "Move":
        return 1 #no need to sample this

    if hasattr(segment, "start") and hasattr(segment, "end"):
        dx = segment.end.x - segment.start.x 
        dy = segment.end.y - segment.start.y
        approximatelength = math.hypot(dx, dy)
    else:
        approximatelength = 0.0

    samplecount = max(1, min(maxsegmentsteps, int(approximatelength / curvesamplestep)))
    if segmenttypename in {"Arc", "CubicBezier", "QuadraticBezier"}:
        samplecount = min(maxsegmentsteps, max(2, samplecount * 2))
    return samplecount


#TODO: OPTIMIZATION for curve sampling



def convertpathtopolygons(svgpath):

    polygonlist = []

    for subpath in svgpath.as_subpaths():
        sampledpoints = []
        for segment in subpath:
            segmenttypename = type(segment).__name__
            if segmenttypename == "Move":
                sampledpoints.append((segment.end.x, segment.end.y))
                continue
            #print(segment)
            if not sampledpoints and hasattr(segment, "start"):
                sampledpoints.append((segment.start.x, segment.start.y))

            samplecount = getsegmentsamplecount(segment)


            for sampleindex in range(1, samplecount + 1):
                positionratio = sampleindex / samplecount
                point = segment.point(positionratio)
                sampledpoints.append((point.x, point.y))

        cleanedpoints = []


        for pointx, pointy in sampledpoints:
            if not cleanedpoints or abs(pointx - cleanedpoints[-1][0]) or abs(pointy - cleanedpoints[-1][1]) > 1e-6: #1e-6 is a threshold to consider points different
                cleanedpoints.append((pointx, pointy))
                #print(cleanedpoints[-1])

        #OLD CODE THIS ONE IS TOO SLOW
        #if not pointx, pointy in cleanedpoints:
        #   cleanedpoints.append((pointx, pointy))


        if len(cleanedpoints) >= 3:
            polygonxvalues = [point[0] for point in cleanedpoints]
            polygonyvalues = [point[1] for point in cleanedpoints]
            polygonlist.append(
                {
                    "points": cleanedpoints,
                    "rectangle": pygame.Rect(
                        min(polygonxvalues),
                        min(polygonyvalues),
                        max(polygonxvalues) - min(polygonxvalues),
                        max(polygonyvalues) - min(polygonyvalues),
                    ),
                }
            )

    return polygonlist




def ispointinsidepolygon(point, polygon):
    mousex, mousey = point
    inside = False
    previousindex = len(polygon) - 1

    for currentindex in range(len(polygon)):
        currentx, currenty = polygon[currentindex]
        previousx, previousy = polygon[previousindex]
        crossed = ((currenty > mousey) != (previousy > mousey)) and (
            mousex < (previousx - currentx) * (mousey - currenty) / ((previousy - currenty) or 1e-9) + currentx
        )
        if crossed:
            inside = not inside
        previousindex = currentindex

    return inside




def getparentstateidfromprovinceid(provinceid):
    if "_" not in provinceid:
        return provinceid
    parentname = provinceid.rsplit("_", 1)[0]
    namemismatchlookup = {"Trung_Bo": "Trong_Bo"}
    return namemismatchlookup.get(parentname, parentname)




def parsecolorvalue(rawcolorvalue):


    if isinstance(rawcolorvalue, str):
        colorstring = rawcolorvalue.strip()
        if colorstring.startswith("#"):
            colorstring = colorstring[1:]
        if len(colorstring) == 6:
            try:
                return (
                    int(colorstring[0:2], 16), # red
                    int(colorstring[2:4], 16), # green
                    int(colorstring[4:6], 16), # blue
                )
            except ValueError:
                return None



    if isinstance(rawcolorvalue, (list, tuple)) and len(rawcolorvalue) == 3:
        try:
            redvalue = int(rawcolorvalue[0])
            greenvalue = int(rawcolorvalue[1])
            bluevalue = int(rawcolorvalue[2])
            return (
                max(0, min(255, redvalue)),
                max(0, min(255, greenvalue)),
                max(0, min(255, bluevalue)),
            )
        
        except (TypeError, ValueError):
            return None

    return None


def blackworld(nonplayablestateshapelist, mapbox):
    if not nonplayablestateshapelist:
        return None

    surfacewidth = max(1, int(math.ceil(mapbox["width"])) + 2)
    surfaceheight = max(1, int(math.ceil(mapbox["height"])) + 2)
    worldsurface = pygame.Surface((surfacewidth, surfaceheight), pygame.SRCALPHA)

    offsetx = -mapbox["minimumx"]
    offsety = -mapbox["minimumy"]

    for stateshape in nonplayablestateshapelist:
        for polygon in stateshape.get("polygons", ()): 
            worldpoints = polygon.get("points", ())
            if len(worldpoints) < 3:
                continue
            shiftedpoints = [
                (int(pointx + offsetx), int(pointy + offsety))
                for pointx, pointy in worldpoints
            ]
            if len(shiftedpoints) >= 3:
                pygame.draw.polygon(worldsurface, (0, 0, 0, 255), shiftedpoints)

    return worldsurface


def blitblackworldslice(screen, worldsurface, mapbox, zoomvalue, drawcamerax, cameray):
    screenwidth, screenheight = screen.get_size()

    minimumworldx = (0.0 - drawcamerax) / zoomvalue
    maximumworldx = (screenwidth - drawcamerax) / zoomvalue
    minimumworldy = (0.0 - cameray) / zoomvalue
    maximumworldy = (screenheight - cameray) / zoomvalue

    sourceleft = int(math.floor(minimumworldx - mapbox["minimumx"]))
    sourceright = int(math.ceil(maximumworldx - mapbox["minimumx"]))
    sourcetop = int(math.floor(minimumworldy - mapbox["minimumy"]))
    sourcebottom = int(math.ceil(maximumworldy - mapbox["minimumy"]))

    sourceleft = max(0, min(worldsurface.get_width(), sourceleft))
    sourceright = max(0, min(worldsurface.get_width(), sourceright))
    sourcetop = max(0, min(worldsurface.get_height(), sourcetop))
    sourcebottom = max(0, min(worldsurface.get_height(), sourcebottom))

    sourcewidth = sourceright - sourceleft
    sourceheight = sourcebottom - sourcetop
    if sourcewidth <= 0 or sourceheight <= 0:
        return

    sourcesurface = worldsurface.subsurface(pygame.Rect(sourceleft, sourcetop, sourcewidth, sourceheight))
    targetwidth = max(1, int(sourcewidth * zoomvalue))
    targetheight = max(1, int(sourceheight * zoomvalue))
    scaledslice = pygame.transform.scale(sourcesurface, (targetwidth, targetheight))

    sourceworldx = mapbox["minimumx"] + sourceleft
    sourceworldy = mapbox["minimumy"] + sourcetop
    blitx = int(sourceworldx * zoomvalue + drawcamerax)
    blity = int(sourceworldy * zoomvalue + cameray)
    screen.blit(scaledslice, (blitx, blity))



# TROOP BADGE MULTISELECT

def makerectfrompoints(startposition, endposition):
    startx, starty = startposition
    endx, endy = endposition
    left = min(startx, endx)
    top = min(starty, endy)
    width = abs(endx - startx)
    height = abs(endy - starty)
    return pygame.Rect(left, top, width, height)


def getbadgehitprovinceid(mouseposition, badgehitlist):
    for badgeentry in reversed(badgehitlist):
        if badgeentry["rect"].collidepoint(mouseposition):
            return badgeentry["provinceid"]
    return None




    # for countryindex, countryentry in enumerate(rawdata):
    #         if not isinstance(countryentry, dict):
    #             continue
    #
    #         countryname = str(countryentry.get("Country", "")).strip()
    #         if not countryname:
    #             continue
    #
    #         # No color in new format, assign default (CHATGPT)
    #         parsedcolor = autocountrycolors[countryindex % len(autocountrycolors)]
    #         countrytocolorlookup[countryname] = parsedcolor
    #
    #         statesdict = countryentry.get("States", {})
    #         if not isinstance(statesdict, dict):
    #             continue
    #
    #         for statename in statesdict.keys():
    #             if isinstance(statename, str) and statename.strip():
    #                 statetocountrylookup[statename.strip()] = countryname
    #
    #     return statetocountrylookup, countrytocolorlookup
def getdragselectedprovinceids(selectionrect, badgehitlist, provincemap, playercountry):
    selectedids = []
    for badgeentry in badgehitlist:
        provinceid = badgeentry["provinceid"]
        province = provincemap.get(provinceid)
        if not province:
            continue
        if getprovincecontroller(province) != playercountry:
            continue
        if badgeentry["rect"].colliderect(selectionrect):
            selectedids.append(provinceid)
    return selectedids


def getprovinceundercursorinstate(mouseposition, stateid, stateshapelist, zoomvalue, camerax, cameray, copyshiftlist):
    # Ebee Super Optimization (ESO) 27/4
    # O(s) -> O(1)
    # fetch hovered states from a direct id lookup
    stateobject = stateshapelist.get(stateid)
    if not stateobject:
        return None

    subdivisions = stateobject.get("subdivisions", [])
    if not subdivisions:
        return None

    for copyshift in copyshiftlist:
        drawcamerax = camerax + copyshift
        for province in subdivisions:
            for polygon in province.get("polygons", []):
                polygonrectanglescreen = getscreenrectangle(polygon["rectangle"], zoomvalue, drawcamerax, cameray)
                if not polygonrectanglescreen.collidepoint(mouseposition):
                    continue

                polygonpointsscreen = getscreenpoints(polygon["points"], zoomvalue, drawcamerax, cameray)
                if ispointinsidepolygon(mouseposition, polygonpointsscreen):
                    return province

    return None


def buildstaterenderlookup(playablestateshapelist, expandedstateid, gamephase, defaultshapecolor):
    staterenderlookup = {}
    sentinel = object()

    # Ebee Super Optimization (ESO) 27/4
    # O(k*s*p) -> O(s*p + k*s)
    # precompute state control and subdivision draw choices once per frame
    for stateshape in playablestateshapelist:
        drawitemlist = (stateshape,)
        uniformsubdivisioncolor = None

        if gamephase != "choosecountry":
            subdivisions = stateshape.get("subdivisions", ())
            hasmixedcontrol = False
            if subdivisions:
                firstcontroller = sentinel
                firstnonnullcontroller = None
                multiplecontrollers = False
                multiplenonnullcontrollers = False
                firstcolor = sentinel
                multiplecolors = False

                for province in subdivisions:
                    controllercountry = getprovincecontroller(province)
                    if firstcontroller is sentinel:
                        firstcontroller = controllercountry
                    elif controllercountry != firstcontroller:
                        multiplecontrollers = True

                    if controllercountry is not None:
                        if firstnonnullcontroller is None:
                            firstnonnullcontroller = controllercountry
                        elif controllercountry != firstnonnullcontroller:
                            multiplenonnullcontrollers = True

                    countrycolor = province.get("countrycolor")
                    if countrycolor is not None:
                        if firstcolor is sentinel:
                            firstcolor = countrycolor
                        elif countrycolor != firstcolor:
                            multiplecolors = True

                hasmixedcontrol = multiplecontrollers
                if firstnonnullcontroller is not None and not multiplenonnullcontrollers:
                    stateshape["controllercountry"] = firstnonnullcontroller
                    stateshape["country"] = firstnonnullcontroller
                    stateshape["countrycolor"] = subdivisions[0].get(
                        "countrycolor",
                        stateshape.get("countrycolor", defaultshapecolor),
                    )
                else:
                    stateshape["controllercountry"] = None
                    stateshape["country"] = None

                if firstcolor is not sentinel and not multiplecolors:
                    uniformsubdivisioncolor = firstcolor

                if expandedstateid == stateshape["id"] or hasmixedcontrol:
                    drawitemlist = tuple(subdivisions)

        staterenderlookup[stateshape["id"]] = {
            "drawitems": drawitemlist,
            "uniformsubdivisioncolor": uniformsubdivisioncolor,
        }

    return staterenderlookup


def getselectedtroopentries(selectedprovinceidset, selectedprovinceid, provincemap, playercountry):
    selectedids = []
    if selectedprovinceidset:
        selectedids.extend(sorted(selectedprovinceidset))
    elif selectedprovinceid:
        selectedids.append(selectedprovinceid)

    entries = []
    for provinceid in selectedids:
        province = provincemap.get(provinceid)
        if not province:
            continue
        if playercountry and getprovincecontroller(province) != playercountry:
            continue
        entries.append(
            {
                "provinceid": provinceid,
                "troops": int(province.get("troops", 0)),
                "stateid": province.get("parentid"),
            }
        )

    entries.sort(key=lambda entry: (entry["provinceid"]))
    return entries


def getkruskalbridges(segmentlist, maxgapdistance=16.0):

    if not segmentlist:
        return []



    maxgapsquared = maxgapdistance * maxgapdistance
    endpointpositionlist = []
    endpointsegmentindexlist = []


    for segmentindex, segment in enumerate(segmentlist):
        
        segmentstart, segmentend = segment
        endpointpositionlist.append(segmentstart)
        endpointsegmentindexlist.append(segmentindex)
        endpointpositionlist.append(segmentend)
        endpointsegmentindexlist.append(segmentindex)

    endpointcount = len(endpointpositionlist)


    if endpointcount < 2:
        return []

    # First pass: collect all viable endpoint pairs within the gap threshold.
    # This forms local "gap clusters" we can stitch using a minimum spanning bridge set.
    candidateedgelist = []



    for endpointindex in range(endpointcount):
        endpointx, endpointy = endpointpositionlist[endpointindex]
        endpointsegmentindex = endpointsegmentindexlist[endpointindex]
        for candidateindex in range(endpointindex + 1, endpointcount):
            if endpointsegmentindexlist[candidateindex] == endpointsegmentindex:
                continue



            candidatex, candidatey = endpointpositionlist[candidateindex]
            offsetx = candidatex - endpointx
            offsety = candidatey - endpointy
            distancesquared = offsetx * offsetx + offsety * offsety


            if distancesquared <= 1e-6 or distancesquared > maxgapsquared:
                continue
            candidateedgelist.append((distancesquared, endpointindex, candidateindex))


    if not candidateedgelist:
        return []

    # KRUSKAL ALGORITHM
    bridgeparent = list(range(endpointcount))
    bridgerank = [0] * endpointcount




    def findbridgeparent(index):
        while bridgeparent[index] != index:
            bridgeparent[index] = bridgeparent[bridgeparent[index]]
            index = bridgeparent[index]
        return index




    def combinebridgegroup(firstindex, secondindex):
        firstroot = findbridgeparent(firstindex)
        secondroot = findbridgeparent(secondindex)
        if firstroot == secondroot:
            return False
        if bridgerank[firstroot] < bridgerank[secondroot]:
            bridgeparent[firstroot] = secondroot
        elif bridgerank[firstroot] > bridgerank[secondroot]:
            bridgeparent[secondroot] = firstroot
        else:
            bridgeparent[secondroot] = firstroot
            bridgerank[firstroot] += 1
        return True

    bridgelines = []
    bridgepairset = set()
    candidateedgelist.sort(key=lambda edge: edge[0])



    for distancesquared, endpointindex, candidateindex in candidateedgelist:
        if not combinebridgegroup(endpointindex, candidateindex):
            continue

        pairkey = (endpointindex, candidateindex)
        bridgepairset.add(pairkey)
        bridgelines.append(
            (
                endpointpositionlist[endpointindex],
                endpointpositionlist[candidateindex],
            )
        )

    return bridgelines












#  from https://stackoverflow.com/a/29643643  




def loadcountrydata(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as fileobject:
            rawdata = json.load(fileobject)
    except (OSError, json.JSONDecodeError):
        return {}, {}

    if not isinstance(rawdata, list):
        return {}, {}

    statetocountrylookup = {}


    for countryindex, countryentry in enumerate(rawdata):
        if not isinstance(countryentry, dict):
            continue

        countryname = str(countryentry.get("Country", "")).strip()
        if not countryname:
            continue


        statesdict = countryentry.get("States", {})
        if not isinstance(statesdict, dict):
            continue

        for statename in statesdict.keys():
            if isinstance(statename, str) and statename.strip():
                statetocountrylookup[statename.strip()] = countryname

    return statetocountrylookup

# group subdivision to their parent state for rendering 


def groupsubdivisionsbystate(provincelist, statelist):

    stateidset = {stateid["id"] for stateid in statelist}
    groupedlookup = {stateid: [] for stateid in stateidset}


    for province in provincelist:
        parentstateid = getparentstateidfromprovinceid(province["id"])
        if parentstateid not in stateidset:
            continue
        province["parentid"] = parentstateid
        province["victory_points"] = stateidset.get("victory_points", 0)
        groupedlookup[parentstateid].append(province)
        #print(province["id"], "parent", parentstateid)
    #print(groupedlookup)

    return groupedlookup # stateid to list of provinces for example ("Malaya" -> [province1, province2])













# check if rect are close to be considered adjacent to build provinece graph for path finding


def rectanglesclose(firstrectangle, secondrectangle, padding=1):
    return not (
        firstrectangle.right + padding < secondrectangle.left
        or secondrectangle.right + padding < firstrectangle.left
        or firstrectangle.bottom + padding < secondrectangle.top
        or secondrectangle.bottom + padding < firstrectangle.top
    )



def getshapecenter(shape):
    return (shape["rectangle"].centerx, shape["rectangle"].centery)

# GAME LOGIC AND RENDERING ENDSS


# get the current province at mouse position
def getprovinceatmouse(mouseposition, provincelist, zoomvalue, camerax, cameray, screenrectangle=None):
    # Delegate to API module to keep runtime thin.
    return apimodule.getprovinceatmouse(mouseposition, provincelist, zoomvalue, camerax, cameray, screenrectangle)

# Loading screen and main loop starts 
# start after main()




def drawloadingscreen(
    screen,
    largefont,
    smallfont,
    completedcount,
    totalcount,
    stage="Loading map data",
    statusline="",
    loglines=None,
):
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False


    progressvalue = 0.0 if totalcount <= 0 else completedcount / totalcount


    progressvalue = max(0.0, min(1.0, progressvalue))

    screen.fill((18, 18, 22))
    windowwidth, windowheight = screen.get_size()

    titletextabovebar = largefont.render(f"Engine: {stage}", True, (240, 240, 240))
    screen.blit(titletextabovebar, titletextabovebar.get_rect(center=(windowwidth // 2, windowheight // 2 - 40)))

    barwidth = min(760, windowwidth - 120)
    barheight = 22
    barx = (windowwidth - barwidth) // 2
    bary = windowheight // 2 - 8

    pygame.draw.rect(screen, (60, 60, 70), (barx, bary, barwidth, barheight), border_radius=2)
    pygame.draw.rect(screen, (120, 190, 255), (barx, bary, int(barwidth * progressvalue), barheight), border_radius=2)
    pygame.draw.rect(screen, (120, 120, 130), (barx, bary, barwidth, barheight), 1, border_radius=2)

    overlaytext = statusline if statusline else f"{completedcount}/{totalcount}"
    maxoverlaywidth = max(20, barwidth - 12)
    while overlaytext and smallfont.size(overlaytext)[0] > maxoverlaywidth:
        overlaytext = overlaytext[:-1]
    if overlaytext != statusline and overlaytext:
        overlaytext = overlaytext[:-3] + "..." if len(overlaytext) > 3 else overlaytext

    overlaytextshadow = smallfont.render(overlaytext, True, (20, 20, 24))
    overlaytextsurface = smallfont.render(overlaytext, True, (245, 245, 245))
    overlayrect = overlaytextsurface.get_rect(center=(windowwidth // 2, bary + 11))
    shadowrect = overlayrect.move(1, 1)
    screen.blit(overlaytextshadow, shadowrect)
    screen.blit(overlaytextsurface, overlayrect)

    paneltop = bary + 40
    panelheight = min(180, max(100, windowheight - paneltop - 40))
    panelrect = pygame.Rect(barx, paneltop, barwidth, panelheight)

    pygame.draw.rect(screen, (23, 26, 31), panelrect, border_radius=3)
    pygame.draw.rect(screen, (60, 70, 85), panelrect, 1, border_radius=3)

    visibleloglines = list(loglines or ())
    maxvisiblelines = max(1, (panelrect.height - 16) // 18)
    visibleloglines = visibleloglines[-maxvisiblelines:]
    texty = panelrect.y + 8
    for logline in visibleloglines:
        loglinesurface = smallfont.render(logline, True, (190, 210, 230))
        screen.blit(loglinesurface, (panelrect.x + 10, texty))
        texty += 18

    pygame.display.flip()
    return True





def main(eventbus=None, is_fullscreen=False):
    if eventbus is None:
        eventbus = EventBus()
    startupbegintimestamp = time.perf_counter()
    pygame.init()
    logstartupdiagnostics(startupbegintimestamp, "pygame init", f"python={platform.python_version()} pygame={pygame.version.ver}")

    # Set display mode once based on is_fullscreen
    if is_fullscreen:
        display_flags = pygame.FULLSCREEN
        screen = pygame.display.set_mode((0, 0), display_flags)
    else:
        display_flags = pygame.RESIZABLE  
        screen = pygame.display.set_mode((defaultwindowwidth, defaultwindowheight), display_flags)

    logstartupdiagnostics(
        startupbegintimestamp,
        "window created",
        f"size={screen.get_width()}x{screen.get_height()} driver={pygame.display.get_driver()} fullscreen={is_fullscreen}",
    )
        
    if os.path.exists("dev.txt"):
        pygame.display.set_caption("EbeeEngine Dev Build - APRIL 19 2024")
    else:
        pygame.display.set_caption("EbeeEngine - APRIL 19 2024")



    normalfont = pygame.font.SysFont("Arial", 14)
    smallfont = pygame.font.SysFont("Arial", 12)
    titlefont = pygame.font.SysFont("Arial", 32, bold=True)
    loadingtitlefont = pygame.font.SysFont("Arial", 36, bold=True)
    loadingtextfont = pygame.font.SysFont("Arial", 18)
    developmentmode = loaddevmodeflag("dev.txt")

    loadingloglines = []

    def appendloadinglog(logline):
        loadingloglines.append(f"local@EbeeEngine:~$  {logline}")
        if len(loadingloglines) > 200:
            del loadingloglines[:-200]




    logstartupdiagnostics(startupbegintimestamp, "fonts done", f"development_mode={developmentmode}")
    if not drawloadingscreen(
        screen,
        loadingtitlefont,
        loadingtextfont,
        0,
        1,
        stage="Initializing",
        statusline="Starting engine...",
        loglines=loadingloglines,
    ):
        pygame.quit()
        return

    #TODO: make loading screen better, preferably show which file is loading,
    # current state, it just says provinces and never update


    stateprogresscallback = createloadingprogresscallback(
        lambda completed, total, stage, statusline: drawloadingscreen(
            screen,
            loadingtitlefont,
            loadingtextfont,
            completed,
            total,
            stage=stage,
            statusline=statusline,
            loglines=loadingloglines,
        ),
        startupbegintimestamp,
        "Precompiling states geometry...",
        onlog=appendloadinglog,
    )


    stateshapelist = loadsvgshapes(
        statefilepath,
        onprogress=stateprogresscallback,
    )
    if not stateshapelist:
        pygame.quit()
        return
    

    logstartupdiagnostics(startupbegintimestamp, "states loaded", f"count={len(stateshapelist)}")

    
    statetocountrylookup, countrytocolorlookup = loadcountrydata(countrydatafilepath)

    with open(countrydatafilepath, "r", encoding="utf-8") as f:
        countries_raw = json.load(f)

    def parse_population(text):
        text = str(text).strip().lower().replace(" ", "").replace(",", "")
        if "million" in text:
            return int(float(text.replace("million", "")) * 1_000_000)
        if "billion" in text:
            return int(float(text.replace("billion", "")) * 1_000_000_000)
        try:
            return int(float(text))
        except ValueError:
            return 0

    country_stats_lookup = {}
    for entry in countries_raw:
        name = str(entry.get("Country", "")).strip()
        if not name:
            continue
        country_stats_lookup[name] = {
            "population": parse_population(entry.get("population", 0)),
            "manpower": parse_population(entry.get("manpower", 0)),
            "stability": float(str(entry.get("stability", 0)).strip() or 0),
            "leader": str(entry.get("Leader", "Unknown")).strip(),
            "leading_party": str(entry.get("LeadingParty", "")).strip(),
            "parties": entry.get("MajorPoliticalParties", []),
        }
       
    
    statetocountrylookup, countrytocolorlookup = loadcountrydata(countrydatafilepath)
    allowedstateidset = set(statetocountrylookup.keys())
    state_data_lookup = esomodule.buildstatedatalookup(stateshapelist)
    logstartupdiagnostics(
        startupbegintimestamp,
        "countries loaded",
        f"state_links={len(statetocountrylookup)} country_colors={len(countrytocolorlookup)} visible_states={len(allowedstateidset)} total_states={len(stateshapelist)}",
    )
    for stateshape in stateshapelist: # to prepare to load province data and assign countries to state 
        statecountry = statetocountrylookup.get(stateshape["id"])
        stateshape["ownercountry"] = statecountry
        stateshape["controllercountry"] = statecountry
        stateshape["country"] = statecountry
        stateshape["countrycolor"] = countrytocolorlookup.get(statecountry, (85, 85, 85)) 




    provinceprogresscallback = createloadingprogresscallback(
        lambda completed, total, stage, statusline: drawloadingscreen(
            screen,
            loadingtitlefont,
            loadingtextfont,
            completed,
            total,
            stage=stage,
            statusline=statusline,
            loglines=loadingloglines,
        ),
        startupbegintimestamp,
        "Precompiling provinces geometry...",
        onlog=appendloadinglog,
    )



    provinceshapelist = loadsvgshapes(
        provincefilepath if False else provincefilepath,
        onprogress=provinceprogresscallback,
    )



    # fix accidental typo safely
    if not provinceshapelist:
        provinceprogresscallback = createloadingprogresscallback(
            lambda completed, total, stage, statusline: drawloadingscreen(
                screen,
                loadingtitlefont,
                loadingtextfont,
                completed,
                total,
                stage=stage,
                statusline=statusline,
                loglines=loadingloglines,
            ),
            startupbegintimestamp,
            "Precompiling provinces geometry... (ERROR! retrying..)",
            onlog=appendloadinglog,
        )
        provinceshapelist = loadsvgshapes(
            provincefilepath if False else provincefilepath,
            onprogress=provinceprogresscallback,
        )
    if not provinceshapelist:
        pygame.quit()
        return
    


    logstartupdiagnostics(startupbegintimestamp, "provinces loaded", f"count={len(provinceshapelist)}")
    provinceenrichedlist = prepareprovincemetadata(provinceshapelist)
    logstartupdiagnostics(startupbegintimestamp, "province metadata done", f"count={len(provinceenrichedlist)}")



    for province in provinceenrichedlist:
        provincecountry = statetocountrylookup.get(province["parentstateid"])
        province["ownercountry"] = provincecountry
        province["controllercountry"] = provincecountry
        province["country"] = provincecountry
        province["countrycolor"] = countrytocolorlookup.get(provincecountry, (85, 85, 85))

    provincemap = {province["id"]: province for province in provinceenrichedlist} 



    graphprogresscallback = createloadingprogresscallback(
        lambda completed, total, stage, statusline: drawloadingscreen(
            screen,
            loadingtitlefont,
            loadingtextfont,
            completed,
            total,
            stage=stage,
            statusline=statusline,
            loglines=loadingloglines,
        ),
        startupbegintimestamp,
        "Compiling province graph..",
        onlog=appendloadinglog,
    )
    graphcacheloadstart = time.perf_counter()
    graphcachevalidationstatus = "miss"
    provincegraph = esomodule.loadprovincegraphcache(provincefilepath, allowedstateidset)
    if provincegraph is not None:
        cachedprovinceidset = set(provincegraph.keys())
        expectedprovinceidset = set(provincemap.keys())
        if cachedprovinceidset != expectedprovinceidset:
            graphcachevalidationstatus = "messedUPNODE"
            provincegraph = None
        else:
            for provinceid, neighborids in provincegraph.items():
                if not neighborids.issubset(expectedprovinceidset):
                    graphcachevalidationstatus = "NOTneighborref"
                    provincegraph = None
                    break
            if provincegraph is not None:
                graphcachevalidationstatus = "hit"
    graphcacheloadelapsed = time.perf_counter() - graphcacheloadstart
    logstartupdiagnostics(
        startupbegintimestamp,
        "province graph cache check",
        f"status={graphcachevalidationstatus} elapsed={graphcacheloadelapsed:.3f}s nodes={(0 if provincegraph is None else len(provincegraph))}",
    )

    if provincegraph is not None:
        appendloadinglog(f"ESO cache hit for province graph with {len(provincegraph)} nodes!")
        if graphprogresscallback and not graphprogresscallback(0, 1):
            pygame.quit()
            return
        if graphprogresscallback and not graphprogresscallback(1, 1):
            pygame.quit()
            return
    else:
        graphbuildstart = time.perf_counter()
        provincegraph = buildprovinceadjacencygraph(
            provincemap,
            onprogress=graphprogresscallback,
        )
        graphbuildelapsed = time.perf_counter() - graphbuildstart
        logstartupdiagnostics(
            startupbegintimestamp,
            "province graph build",
            f"elapsed={graphbuildelapsed:.3f}s nodes={(0 if provincegraph is None else len(provincegraph))}",
        )
        if provincegraph is not None:
            graphcachestorestart = time.perf_counter()
            esomodule.storeprovincegraphcache(provincefilepath, provincegraph, allowedstateidset)
            graphcachestoreelapsed = time.perf_counter() - graphcachestorestart
            logstartupdiagnostics(
                startupbegintimestamp,
                "province graph cache store",
                f"elapsed={graphcachestoreelapsed:.3f}s nodes={len(provincegraph)}",
            )



    #CRASH if no provincegraph, this is for Benedict's AMD issue
    if provincegraph is None:
        pygame.quit()
        return
    playableprovinceidset = {
        provinceid
        for provinceid, province in provincemap.items()
        if province.get("parentstateid") in allowedstateidset
    }


    # ESO optimization 22/04
    # O(cp) --> O(p)
    # iterate only playable provinces instead of all provinces


    playableprovincemap = {provinceid: provincemap[provinceid] for provinceid in playableprovinceidset}
    playableprovincegraph = {
        provinceid: {
            neighborid
            for neighborid in provincegraph.get(provinceid, set())
            if neighborid in playableprovinceidset
        }
        for provinceid in playableprovinceidset
    }

    provinceedgepairlist = []
    for firstprovinceid, neighboridset in playableprovincegraph.items():
        for secondprovinceid in neighboridset:
            if firstprovinceid < secondprovinceid:
                provinceedgepairlist.append((firstprovinceid, secondprovinceid))

    totaledges = sum(len(neighborset) for neighborset in provincegraph.values()) // 2
    logstartupdiagnostics(
        startupbegintimestamp,
        "province graph done",
        f"nodes={len(provincegraph)} edges={totaledges}",
    )



    subdivisiongroupstart = time.perf_counter()
    groupedsubdivisionlookup = groupsubdivisionsbystate(provinceenrichedlist, stateshapelist)
    subdivisiongroupelapsed = time.perf_counter() - subdivisiongroupstart

    playablestateshapelist = [stateshape for stateshape in stateshapelist if stateshape["id"] in allowedstateidset]
    nonplayablestateshapelist = [stateshape for stateshape in stateshapelist if stateshape["id"] not in allowedstateidset]
    logstartupdiagnostics(
        startupbegintimestamp,
        "world partitioned",
        f"playable_states={len(playablestateshapelist)} non_playable_states={len(nonplayablestateshapelist)} grouping_elapsed={subdivisiongroupelapsed:.3f}s",
    )

    for stateshape in stateshapelist:

        subdivisionsforstate = groupedsubdivisionlookup.get(stateshape["id"], [])
        
        for province in subdivisionsforstate:
            ownercountry = stateshape.get("ownercountry", stateshape.get("country"))
            controllercountry = stateshape.get("controllercountry", stateshape.get("country"))
            province["ownercountry"] = ownercountry
            setprovincecontroller(province, controllercountry, stateshape.get("countrycolor", (85, 85, 85)))
        stateshape["subdivisions"] = subdivisionsforstate

    stateobjectlookup = {stateshape["id"]: stateshape for stateshape in stateshapelist}



    mapbox = getmapbox(stateshapelist)
    blackedbuildstart = time.perf_counter()
    blackedoutworldsurface = blackworld(nonplayablestateshapelist, mapbox)
    blackedbuildelapsed = time.perf_counter() - blackedbuildstart
    blackedpolygoncount = sum(len(stateshape.get("polygons", ())) for stateshape in nonplayablestateshapelist)
    blackedsurfacesize = "none"
    if blackedoutworldsurface is not None:
        blackedsurfacesize = f"{blackedoutworldsurface.get_width()}x{blackedoutworldsurface.get_height()}"
    logstartupdiagnostics(
        startupbegintimestamp,
        "blacked world prepared",
        f"states={len(nonplayablestateshapelist)} polygons={blackedpolygoncount} surface={blackedsurfacesize} elapsed={blackedbuildelapsed:.3f}s",
    )
    blackedoutscaledsurface = None
    blackedoutscaledzoombucket = None
    logstartupdiagnostics(
        startupbegintimestamp,
        "blacked render config",
        "bucket_step=0.03 close_zoom_threshold=1.45",
    )
    logstartupdiagnostics(
        startupbegintimestamp,
        "startup complete",
        f"map_size={mapbox['width']:.1f}x{mapbox['height']:.1f}",
    )
    eventbus.emit(
        EngineEventType.WORLDLOADED,
        {
            "stateCount": len(stateshapelist),
            "provinceCount": len(provincemap),
            "edgeCount": totaledges,
        },
    )


    
    windowwidth, windowheight = screen.get_size()
    runtimeui = InGameUI((windowwidth, windowheight))
    maprect = runtimeui.map_rect
    camerastate = cameramodule.createcamerastate(maprect.width, maprect.height, mapbox)









    clock = pygame.time.Clock()
    fpshistory = []
    fpshistorymaxsamples = 180
    expandedstateid = None
    selectedprovinceid = None
    selectedprovinceidset = set()

    gamephase = "choosecountry"
    pendingcountry = None
    playercountry = None

    # Economy defaults come from economy module
    currentturnnumber = 1
    economyconfig = getdefaulteconomyconfig()
    (
        playergold,
        playerpopulation,
        recruitamount,
        recruitgoldcostperunit,
        recruitpopulationcostperunit,
    ) = initializeplayereconomy(economyconfig)
    focustree = loadfocustreeforcountry(None)


    # THIS is the NPC instance
    # controls non player country
    # access to runtime data but not rendering or input
    # provincemap and provincegraph for decision making, 
    # can emit orders through eventbus, economyconfig for economic decisions, countrytocolorlookup for any color needs
    npcdirector = npcmodule.NpcDirector(
        provincemap,
        provincegraph,
        countrytocolorlookup=countrytocolorlookup,
        emit=eventbus.emit,
        economyconfig=economyconfig,
    )


    movementorderlist = []
    routepreviewset = set()
    frontlineplacementmode = False
    activefrontlineedgekeyset = set()
    frontlineassignmentlist = []
    frontlineassignmentcounter = 0
    frontlinebordersegmentcache = {}
    countrybordersegmentcache = {}
    countryborderentrylist = []
    countrybordersdirty = True
    countriesatwarset = set() # track countries at war
    warpairset = set()
    warrecordlookup = {}
    countrymenutarget = None

    def normalizewarpair(firstcountry, secondcountry):
        if not firstcountry or not secondcountry:
            return None
        first = str(firstcountry).strip()
        second = str(secondcountry).strip()
        if not first or not second or first == second:
            return None
        if first <= second:
            return (first, second)
        return (second, first)

    def canonicalizecountry(rawcountry):
        if rawcountry is None:
            return None

        countrytext = str(rawcountry).strip()
        if not countrytext:
            return None

        aliaslookup = {}
        for province in provincemap.values():
            for key in ("ownercountry", "controllercountry", "country"):
                knowncountry = province.get(key)
                if not knowncountry:
                    continue
                knowntext = str(knowncountry).strip()
                if not knowntext:
                    continue
                lowerknown = knowntext.lower()
                if lowerknown not in aliaslookup:
                    aliaslookup[lowerknown] = knowntext

        return aliaslookup.get(countrytext.lower(), countrytext)

    def safeint(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def getstatevictorypoints(stateid):
        statedata = state_data_lookup.get(str(stateid or "").lower())
        if not isinstance(statedata, dict):
            return 0.0
        return float(max(0, safeint(statedata.get("victory_points", 0), 0)))

    def ensurewarrecord(firstcountry, secondcountry, aggressor=None, defender=None, turn=None):
        normalizedpair = normalizewarpair(firstcountry, secondcountry)
        if normalizedpair is None:
            return None

        # keep declaration metadata keyed by the normalized war pair.
        record = warrecordlookup.get(normalizedpair)
        if record is None:
            record = {
                "pair": normalizedpair,
                "aggressor": aggressor or normalizedpair[0],
                "defender": defender or normalizedpair[1],
                "startturn": safeint(turn, currentturnnumber),
                "casualties": {},
            }
            warrecordlookup[normalizedpair] = record
        else:
            if aggressor:
                record["aggressor"] = aggressor
            if defender:
                record["defender"] = defender
            if turn is not None and record.get("startturn") is None:
                record["startturn"] = safeint(turn, currentturnnumber)

        casualties = record.setdefault("casualties", {})
        for country in normalizedpair:
            casualties.setdefault(country, 0)
        return record

    def syncwarrecordswithpairs():
        # mirror console edits so stale war records do not survive peace.
        activepairset = set(warpairset)
        for existingpair in list(warrecordlookup.keys()):
            if existingpair not in activepairset:
                del warrecordlookup[existingpair]

        for firstcountry, secondcountry in activepairset:
            ensurewarrecord(firstcountry, secondcountry)

    def buildwarcountrymetrics():
        totalvplookup = {}
        controlledvplookup = {}
        ownedcontrolledvplookup = {}
        totalprovincelookup = {}
        controlledprovincelookup = {}
        ownedcontrolledprovincelookup = {}
        fieldmanpowerlookup = {}

        for stateshape in playablestateshapelist:
            stateid = stateshape.get("id")
            stateowner = statetocountrylookup.get(stateid) or stateshape.get("ownercountry", stateshape.get("country"))
            statevp = getstatevictorypoints(stateid)
            subdivisions = [
                province for province in stateshape.get("subdivisions", ())
                if isinstance(province, dict)
            ]
            provincecount = max(1, len(subdivisions))

            if stateowner:
                totalvplookup[stateowner] = totalvplookup.get(stateowner, 0.0) + statevp
                totalprovincelookup[stateowner] = totalprovincelookup.get(stateowner, 0) + provincecount

            if subdivisions:
                # split state vp across provinces so partial occupations can count.
                vpperprovince = statevp / provincecount if provincecount else 0.0
                for province in subdivisions:
                    controller = getprovincecontroller(province)
                    if not controller:
                        continue
                    controlledvplookup[controller] = controlledvplookup.get(controller, 0.0) + vpperprovince
                    controlledprovincelookup[controller] = controlledprovincelookup.get(controller, 0) + 1
                    if stateowner:
                        matrixkey = (stateowner, controller)
                        ownedcontrolledvplookup[matrixkey] = ownedcontrolledvplookup.get(matrixkey, 0.0) + vpperprovince
                        ownedcontrolledprovincelookup[matrixkey] = ownedcontrolledprovincelookup.get(matrixkey, 0) + 1
                continue

            controller = stateshape.get("controllercountry", stateshape.get("country"))
            if controller:
                controlledvplookup[controller] = controlledvplookup.get(controller, 0.0) + statevp
                controlledprovincelookup[controller] = controlledprovincelookup.get(controller, 0) + 1
                if stateowner:
                    matrixkey = (stateowner, controller)
                    ownedcontrolledvplookup[matrixkey] = ownedcontrolledvplookup.get(matrixkey, 0.0) + statevp
                    ownedcontrolledprovincelookup[matrixkey] = ownedcontrolledprovincelookup.get(matrixkey, 0) + 1

        for province in playableprovincemap.values():
            controller = getprovincecontroller(province)
            if not controller:
                continue
            fieldmanpowerlookup[controller] = fieldmanpowerlookup.get(controller, 0) + max(0, safeint(province.get("troops", 0), 0))

        # moving orders still represent troops on the field.
        for movementorder in movementorderlist:
            controller = movementorder.get("controllercountry", movementorder.get("country"))
            if not controller:
                continue
            fieldmanpowerlookup[controller] = fieldmanpowerlookup.get(controller, 0) + max(0, safeint(movementorder.get("amount", 0), 0))

        return {
            "totalvp": totalvplookup,
            "controlledvp": controlledvplookup,
            "ownedcontrolledvp": ownedcontrolledvplookup,
            "totalprovinces": totalprovincelookup,
            "controlledprovinces": controlledprovincelookup,
            "ownedcontrolledprovinces": ownedcontrolledprovincelookup,
            "fieldmanpower": fieldmanpowerlookup,
        }

    def selectactivewarrecord():
        syncwarrecordswithpairs()
        if not warrecordlookup:
            return None

        candidaterecords = list(warrecordlookup.values())
        # when possible, show the player's war before unrelated npc wars.
        if playercountry:
            playerrecords = [
                record for record in candidaterecords
                if playercountry in record.get("pair", ())
            ]
            if playerrecords:
                candidaterecords = playerrecords

        candidaterecords.sort(
            key=lambda record: (
                safeint(record.get("startturn"), 0),
                str(record.get("aggressor", "")),
                str(record.get("defender", "")),
            ),
            reverse=True,
        )
        return candidaterecords[0]

    def buildwarprogressdata():
        record = selectactivewarrecord()
        if record is None:
            return {}

        aggressor = record.get("aggressor")
        defender = record.get("defender")
        if not aggressor or not defender:
            firstcountry, secondcountry = record.get("pair", (None, None))
            aggressor = aggressor or firstcountry
            defender = defender or secondcountry
        if not aggressor or not defender:
            return {}

        metrics = buildwarcountrymetrics()
        totalvp = metrics["totalvp"]
        controlledvp = metrics["controlledvp"]
        ownedcontrolledvp = metrics["ownedcontrolledvp"]
        totalprovinces = metrics["totalprovinces"]
        controlledprovinces = metrics["controlledprovinces"]
        ownedcontrolledprovinces = metrics["ownedcontrolledprovinces"]
        fieldmanpower = metrics["fieldmanpower"]
        casualties = record.get("casualties", {})

        aggressorcapturedvp = ownedcontrolledvp.get((defender, aggressor), 0.0)
        defendercapturedvp = ownedcontrolledvp.get((aggressor, defender), 0.0)
        defendertotalvp = totalvp.get(defender, 0.0)
        aggressortotalvp = totalvp.get(aggressor, 0.0)
        # progress is based on enemy-owned vp currently held by the other side.
        progress = 0.0 if defendertotalvp <= 0 else (aggressorcapturedvp / defendertotalvp) * 100.0
        defenderprogress = 0.0 if aggressortotalvp <= 0 else (defendercapturedvp / aggressortotalvp) * 100.0

        return {
            "aggressor": aggressor,
            "defender": defender,
            "progress": max(0.0, min(100.0, progress)),
            "defender_progress": max(0.0, min(100.0, defenderprogress)),
            "active_war_count": len(warpairset),
            "start_turn": record.get("startturn"),
            "aggressor_casualties": max(0, safeint(casualties.get(aggressor, 0), 0)),
            "defender_casualties": max(0, safeint(casualties.get(defender, 0), 0)),
            "aggressor_manpower": max(0, safeint(fieldmanpower.get(aggressor, 0), 0)),
            "defender_manpower": max(0, safeint(fieldmanpower.get(defender, 0), 0)),
            "aggressor_total_vp": aggressortotalvp,
            "defender_total_vp": defendertotalvp,
            "aggressor_controlled_vp": controlledvp.get(aggressor, 0.0),
            "defender_controlled_vp": controlledvp.get(defender, 0.0),
            "aggressor_captured_vp": aggressorcapturedvp,
            "defender_captured_vp": defendercapturedvp,
            "aggressor_total_provinces": totalprovinces.get(aggressor, 0),
            "defender_total_provinces": totalprovinces.get(defender, 0),
            "aggressor_controlled_provinces": controlledprovinces.get(aggressor, 0),
            "defender_controlled_provinces": controlledprovinces.get(defender, 0),
            "aggressor_occupied_enemy_provinces": ownedcontrolledprovinces.get((defender, aggressor), 0),
            "defender_occupied_enemy_provinces": ownedcontrolledprovinces.get((aggressor, defender), 0),
        }

    def nextfrontlineid():
        nonlocal frontlineassignmentcounter
        frontlineassignmentcounter += 1
        countryprefix = playercountry or "frontline"
        return f"{countryprefix}_frontline_{frontlineassignmentcounter}"

    def syncfrontlineoverlays():
        nonlocal frontlineassignmentlist, activefrontlineedgekeyset
        frontlineassignmentlist = [
            assignment for assignment in frontlineassignmentlist
            if assignment.get("active", True)
        ]
        activefrontlineedgekeyset = set()
        for assignment in frontlineassignmentlist:
            activefrontlineedgekeyset.update(assignment.get("frontlineedgekeys", ()))

    def refreshfrontlines():
        nonlocal frontlineassignmentlist, activefrontlineedgekeyset
        if not playercountry or not frontlineassignmentlist:
            frontlineassignmentlist = []
            activefrontlineedgekeyset = set()
            return set()

        activefrontlineidset = {
            assignment.get("frontlineid")
            for assignment in frontlineassignmentlist
            if assignment.get("frontlineid")
        }
        movementmodule.normalizefrontlineassignments(
            playableprovincemap,
            activefrontlineidset=activefrontlineidset,
        )

        routeupdateset = set()
        refreshedassignments = []
        for assignment in frontlineassignmentlist:
            refreshresult = movementmodule.refreshfrontlineassignment(
                assignment,
                playableprovincemap,
                playableprovincegraph,
                movementorderlist,
                emit=eventbus.emit,
                currentturnnumber=currentturnnumber,
            )
            routeupdateset.update(refreshresult.get("routepreviewset", ()))
            if assignment.get("active", True):
                refreshedassignments.append(assignment)

        frontlineassignmentlist = refreshedassignments
        syncfrontlineoverlays()
        return routeupdateset

    def getcombatprovinceidset():
        combatprovinceidset = set()
        # Ebee Super Optimization (ESO) 27/4
        # O(m*m) -> O(m)
        # reuse a current-position order index for combat previews
        movementorderindex = movementmodule.buildmovementordercurrentindex(
            movementorderlist,
            currentturnnumber=currentturnnumber,
        )
        for movementorder in movementorderlist:
            if int(movementorder.get("amount", 0)) <= 0:
                continue

            resumeturn = movementorder.get("_resumeonturn")
            if resumeturn is not None and currentturnnumber is not None:
                if int(currentturnnumber) < int(resumeturn):
                    continue

            pathlist = movementorder.get("path", [])
            currentpathindex = int(movementorder.get("index", 0))
            if currentpathindex >= len(pathlist) - 1:
                continue

            nextprovinceid = pathlist[currentpathindex + 1]
            nextprovince = provincemap.get(nextprovinceid)
            if not nextprovince:
                continue

            movingcountry = movementorder.get("controllercountry", movementorder.get("country"))
            defendingcountry = getprovincecontroller(nextprovince)
            if not movingcountry or not defendingcountry or movingcountry == defendingcountry:
                continue

            basedefenders = int(nextprovince.get("troops", 0))
            movingdefenders = sum(
                int(candidateorder.get("amount", 0))
                for candidateorder in movementorderindex.get((nextprovinceid, defendingcountry), ())
                if candidateorder is not movementorder
            )

            if basedefenders + movingdefenders > 0:
                combatprovinceidset.add(nextprovinceid)

        return combatprovinceidset

    def handlewardeclared(payload):
        attacker = canonicalizecountry(payload.get("attacker")) if isinstance(payload, dict) else None
        defender = canonicalizecountry(payload.get("defender")) if isinstance(payload, dict) else None
        if not attacker or not defender or attacker == defender:
            return

        if isinstance(payload, dict):
            payload["attacker"] = attacker
            payload["defender"] = defender

        normalizedpair = normalizewarpair(attacker, defender)
        if normalizedpair is not None:
            warpairset.add(normalizedpair)
            ensurewarrecord(
                attacker,
                defender,
                aggressor=attacker,
                defender=defender,
                turn=payload.get("turn") if isinstance(payload, dict) else currentturnnumber,
            )

        if playercountry:
            if attacker == playercountry:
                countriesatwarset.add(defender)
            elif defender == playercountry:
                countriesatwarset.add(attacker)

            npcdirector.sync_player_wars(playercountry, countriesatwarset, warpairset=warpairset)



   

    def handlewarended(payload):
        firstcountry = None
        secondcountry = None
        if isinstance(payload, dict):
            firstcountry = payload.get("country1", payload.get("attacker"))
            secondcountry = payload.get("country2", payload.get("defender"))

        firstcountry = canonicalizecountry(firstcountry)
        secondcountry = canonicalizecountry(secondcountry)
        normalizedpair = normalizewarpair(firstcountry, secondcountry)
        if normalizedpair is not None:
            warrecordlookup.pop(normalizedpair, None)

    def handlecombatresolved(payload):
        if not isinstance(payload, dict):
            return

        attackercountry = canonicalizecountry(payload.get("attackerCountry", payload.get("attacker")))
        defendercountry = canonicalizecountry(payload.get("defenderCountry", payload.get("defender")))
        normalizedpair = normalizewarpair(attackercountry, defendercountry)
        if normalizedpair is None or normalizedpair not in warpairset:
            return

        record = ensurewarrecord(normalizedpair[0], normalizedpair[1])
        if record is None:
            return

        # combat events carry before and after counts, so losses can be derived here.
        attackerlost = max(
            0,
            safeint(payload.get("attackersBefore", 0), 0) - safeint(payload.get("attackersAfter", 0), 0),
        )
        defenderlost = max(
            0,
            safeint(payload.get("defendersBefore", 0), 0) - safeint(payload.get("defendersAfter", 0), 0),
        )

        casualties = record.setdefault("casualties", {})
        casualties[attackercountry] = max(0, safeint(casualties.get(attackercountry, 0), 0) + attackerlost)
        casualties[defendercountry] = max(0, safeint(casualties.get(defendercountry, 0), 0) + defenderlost)

    eventbus.subscribe(EngineEventType.WARDECLARED, handlewardeclared)
    eventbus.subscribe("warended", handlewarended)
    eventbus.subscribe(EngineEventType.COMBATRESOLVED, handlecombatresolved)

    scriptengine = apimodule.EbeeEngine(
        statefilepath=statefilepath,
        provincefilepath=provincefilepath,
        countrydatafilepath=countrydatafilepath,
    )
    scriptengine.eventbus = eventbus
    scriptengine.stateshapelist = stateshapelist
    scriptengine.provinceenrichedlist = provinceenrichedlist
    scriptengine.provincemap = provincemap
    scriptengine.provincegraph = provincegraph
    scriptengine.statetocountrylookup = statetocountrylookup
    scriptengine.countrytocolorlookup = countrytocolorlookup

    def scriptgetresource(country, resource):
        if playercountry and country == playercountry:
            if resource == "gold":
                return playergold
            if resource == "population":
                return playerpopulation

        economystate = npcdirector.countryeconomy.get(country)
        if economystate is not None:
            return economystate.get(resource)
        return None

    def scriptsetresource(country, resource, value):
        nonlocal playergold
        nonlocal playerpopulation

        value = max(0, int(value))
        if playercountry and country == playercountry:
            if resource == "gold":
                playergold = value
                return True
            if resource == "population":
                playerpopulation = value
                return True

        economystate = npcdirector.countryeconomy.get(country)
        if economystate is not None:
            economystate[resource] = value
            return True
        return False

    def scriptgetselectedcountry():
        return countrymenutarget or playercountry

    def scriptgetselectedprovince():
        return selectedprovinceid

    def scriptshowmessage(text):
        message = str(text or "")
        print(f"scriptloader@EbeeEngine:~$ {message}", flush=True)
        #eventbus.emit(
        #    "newspopup",
        #    {
        #        "title": "Script",
        #        "description": message,
        #        "imagekey": "placeholder",
        #        "priority": 1,
        #    },
        #)
        return message

    def updatescriptengine():
        scriptengine.playercountry = playercountry
        scriptengine.currentturnnumber = currentturnnumber
        scriptengine.countriesatwarset = set(countriesatwarset)
        scriptengine.warpairset = set(warpairset)
        scriptengine.npcdirector = npcdirector
        scriptengine.selectedcountry = countrymenutarget or playercountry
        scriptengine.selectedprovinceid = selectedprovinceid

    scriptengine.bindscripts(
        scriptgetresource,
        scriptsetresource,
        getselectedcountry=scriptgetselectedcountry,
        getselectedprovince=scriptgetselectedprovince,
        showmessage=scriptshowmessage,
    )
    updatescriptengine()
    # SCRIPT LOADING END!!! (p1)



    def applyconsolecommandstate(commandstate):
        nonlocal playercountry
        nonlocal playergold
        nonlocal playerpopulation
        nonlocal gamephase
        nonlocal currentturnnumber
        nonlocal countriesatwarset
        nonlocal warpairset
        nonlocal selectedprovinceid
        nonlocal selectedprovinceidset
        nonlocal routepreviewset
        nonlocal frontlineplacementmode
        nonlocal activefrontlineedgekeyset
        nonlocal frontlineassignmentlist
        nonlocal frontlinebordersegmentcache
        nonlocal countrymenutarget
        nonlocal countrybordersdirty

        if not isinstance(commandstate, dict):
            return

        previousplayercountry = playercountry
        requestedplayercountry = commandstate.get("playercountry", playercountry)
        if requestedplayercountry is not None:
            requestedplayercountry = canonicalizecountry(requestedplayercountry)

        if "playergold" in commandstate:
            playergold = max(0, int(commandstate.get("playergold", playergold)))
        if "playerpopulation" in commandstate:
            playerpopulation = max(0, int(commandstate.get("playerpopulation", playerpopulation)))
        if "currentturnnumber" in commandstate:
            currentturnnumber = max(1, int(commandstate.get("currentturnnumber", currentturnnumber)))

        if "countriesatwarset" in commandstate:
            updatedwarset = set()
            for rawcountry in commandstate.get("countriesatwarset", set()):
                canonicalcountry = canonicalizecountry(rawcountry)
                if canonicalcountry:
                    updatedwarset.add(canonicalcountry)
            countriesatwarset = updatedwarset

        if "warpairset" in commandstate:
            updatedwarpairset = set()
            for rawwarpair in commandstate.get("warpairset", set()):
                if not isinstance(rawwarpair, (tuple, list)) or len(rawwarpair) != 2:
                    continue
                normalizedpair = normalizewarpair(rawwarpair[0], rawwarpair[1])
                if normalizedpair is not None:
                    updatedwarpairset.add(normalizedpair)
            warpairset = updatedwarpairset
            syncwarrecordswithpairs()

        playercountrychanged = requestedplayercountry != previousplayercountry
        if playercountrychanged:
            playercountry = requestedplayercountry
            countrybordersdirty = True
            selectedprovinceid = None
            selectedprovinceidset = set()
            routepreviewset = set()
            frontlineplacementmode = False
            activefrontlineedgekeyset = set()
            frontlineassignmentlist = []
            frontlinebordersegmentcache = {}
            countrymenutarget = None
            if not playercountry:
                countriesatwarset = set()

            npcdirector.setplayercountry(playercountry)
            npcdirector.sync_player_wars(playercountry, countriesatwarset, warpairset=warpairset)

            if playercountry:
                gamephase = "play"
                updatescriptengine()
                eventbus.emit(
                    EngineEventType.PLAYERCOUNTRYSELECTED,
                    {
                        "country": playercountry,
                    },
                )

        if "gamephase" in commandstate:
            gamephase = commandstate.get("gamephase", gamephase)

        if playercountry and not playercountrychanged:
            npcdirector.sync_player_wars(playercountry, countriesatwarset, warpairset=warpairset)

    devconsole = developmentconsole(enabled=developmentmode)
    newssystem = NewsSystem(eventbus)
    newssystem.start()
    newspopup = NewsPopup()
    scriptmanager = scriptengine.initscripts("scripts", autoload=True)
    # UI chrome + map viewport
    # runtime-owned font/caches (previously stored on EngineUI)
    troopbadgefont = pygame.font.SysFont("Arial", 16)
    countrylabelfont = pygame.font.SysFont("Arial", 18, bold=True)
    countrylabelcache = {}
    current_stats = {}
    dragselectstart = None
    dragselectcurrent = None
    isdragselecting = False
    dragminimumdistance = 8








    isrunning = True
    choosecountry_fit_state = {"done": False, "w": None, "h": None}
    while isrunning:
        elapsedseconds = clock.tick(60) / 1000.0
        updatescriptengine()
        esomodule.updaterollingfpshistory(fpshistory, clock.get_fps(), fpshistorymaxsamples)
        mouseposition_full = pygame.mouse.get_pos()
        #this gives x and y (0 and 1)
        mainwindowwidth, mainwindowheight = screen.get_size()
        runtimeui.setwindowsize((mainwindowwidth, mainwindowheight))
        maprect = runtimeui.map_rect

        screen_main = screen
        screen = screen_main.subsurface(maprect)
        mapscreen = screen
        mouseposition = (mouseposition_full[0] - maprect.x, mouseposition_full[1] - maprect.y)
        windowwidth, windowheight = screen.get_size()
        minimumzoomforframe = cameramodule.getminimumzoomforheight(windowheight, mapbox)

        # choosecountry: focus viewport on playable countries (fit once per viewport size)
        if gamephase == "choosecountry":
            if (
                not choosecountry_fit_state["done"]
                or choosecountry_fit_state["w"] != windowwidth
                or choosecountry_fit_state["h"] != windowheight
            ):
                minx = miny = float("inf")
                maxx = maxy = float("-inf")
                for stateshape in playablestateshapelist:
                    rect = stateshape.get("rectangle")
                    if rect is None:
                        continue
                    minx = min(minx, float(rect.left))
                    miny = min(miny, float(rect.top))
                    maxx = max(maxx, float(rect.right))
                    maxy = max(maxy, float(rect.bottom))

                if minx < float("inf") and maxx > float("-inf"):
                    bbox_w = max(1.0, (maxx - minx))
                    bbox_h = max(1.0, (maxy - miny))
                    margin = 40.0
                    bbox_w += margin * 2
                    bbox_h += margin * 2

                    zoom_x = windowwidth / bbox_w
                    zoom_y = windowheight / bbox_h
                    targetzoom = max(minimumzoomvalue, min(maximumzoomvalue, min(zoom_x, zoom_y)))
                    camerastate.zoom = targetzoom
                    camerastate.targetzoom = targetzoom

                    center_world_x = (minx + maxx) * 0.5
                    center_world_y = (miny + maxy) * 0.5
                    camerastate.x = windowwidth * 0.5 - center_world_x * targetzoom
                    camerastate.y = windowheight * 0.5 - center_world_y * targetzoom
                    cameramodule.clampcamerastate(camerastate, windowheight, mapbox)

                choosecountry_fit_state["done"] = True
                choosecountry_fit_state["w"] = windowwidth
                choosecountry_fit_state["h"] = windowheight
        else:
            choosecountry_fit_state["done"] = False

        # TEMP: disable horizontal edge scrolling (re-enable later)
        # cameramodule.applyedgepan(
        #     camerastate,
        #     mouseposition[0],
        #     windowwidth,
        #     elapsedseconds,
        #     edgepanmargin,
        #     edgepanspeed,
        # )
        #cameramodule.applyverticalpan(
        #    camerastate,
        #    mouseposition[1],
        #    windowheight,
        #    elapsedseconds,
        #    edgepanmargin,
        #    edgepanspeed,
        #)

        """ disabled for now, because everytime i click any button near the edge the camera will pan and itis getting annoying
        if mouseposition[1] <= edgepanmargin:
            cameray += panpixels
        elif mouseposition[1] >= windowheight - edgepanmargin:
            cameray -= panpixels
        """

        cameramodule.enforceminimumzoom(camerastate, windowwidth, windowheight, mapbox)
        cameramodule.updatesmoothzoom(
            camerastate,
            mouseposition[0],
            mouseposition[1],
            elapsedseconds,
        )
        cameramodule.clampcamerastate(camerastate, windowheight, mapbox)

        zoomvalue = camerastate.zoom
        camerax = camerastate.x
        cameray = camerastate.y

        # draw the map inside the viewport subsurface
        screen.fill(backgroundcolor)

        hovertext = None
        hoveredstateid = None
        hoveredprovinceid = None
        screenrectangle = screen.get_rect()
        troopbadgelist = [] # store troop badge info
        troopbadgehitlist = []


        # ESO optimization 22/04
        # O(d*m) --> O(d+m)
        # build moving province id set once per frame
        movingprovinceidset = esomodule.buildmovingprovinceidset(movementorderlist) if movementorderlist else set()
        combatprovinceidset = getcombatprovinceidset() if movementorderlist else set()

        # ESO optimization 22/04
        # O(cp*k) --> O(p*k)
        # skip badge loop entirely when badges are hidden this frame
        showtroopbadges = gui_shouldshowtroopbadges(zoomvalue, minimumzoomforframe)



        tilewidth = mapbox["width"] * zoomvalue
        if tilewidth > 1:
            copieseachside = int(windowwidth / tilewidth) + 2
            copyshiftlist = [copyindex * tilewidth for copyindex in range(-copieseachside, copieseachside + 1)]
        else:
            copyshiftlist = [0]

        if blackedoutworldsurface is not None:
            if zoomvalue <= 1.45:
                zoomstep = 0.03
                currentzoombucket = round(zoomvalue / zoomstep) * zoomstep
                if blackedoutscaledzoombucket is None or abs(blackedoutscaledzoombucket - currentzoombucket) > 1e-9:
                    scaledwidth = max(1, int(blackedoutworldsurface.get_width() * currentzoombucket))
                    scaledheight = max(1, int(blackedoutworldsurface.get_height() * currentzoombucket))
                    blackedoutscaledsurface = pygame.transform.scale(blackedoutworldsurface, (scaledwidth, scaledheight))
                    blackedoutscaledzoombucket = currentzoombucket

                for copyshift in copyshiftlist:
                    drawcamerax = camerax + copyshift
                    blitx = int(mapbox["minimumx"] * currentzoombucket + drawcamerax)
                    blity = int(mapbox["minimumy"] * currentzoombucket + cameray)
                    screen.blit(blackedoutscaledsurface, (blitx, blity))
            else:
                for copyshift in copyshiftlist:
                    drawcamerax = camerax + copyshift
                    blitblackworldslice(screen, blackedoutworldsurface, mapbox, zoomvalue, drawcamerax, cameray)

        staterenderlookup = buildstaterenderlookup(
            playablestateshapelist,
            expandedstateid,
            gamephase,
            defaultshapecolor,
        )
        pendingpulsevalue = None
        if gamephase == "choosecountry" and pendingcountry:
            pendingpulsevalue = 0.35 + 0.45 * (0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.008))

        countrymenupulsevalue = None
        if gamephase == "play" and countrymenutarget:
            countrymenupulsevalue = 0.35 + 0.45 * (0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.008))

        for copyshift in copyshiftlist:
            drawcamerax = camerax + copyshift

            for stateshape in playablestateshapelist:
                staterectanglescreen = getscreenrectangle(stateshape["rectangle"], zoomvalue, drawcamerax, cameray)
                if not staterectanglescreen.colliderect(screenrectangle):
                    continue

                staterenderinfo = staterenderlookup.get(stateshape["id"], {})
                drawitemlist = staterenderinfo.get("drawitems", (stateshape,))
            # FOR QUICK SEARCH: "mixed control state"


                # for quick search: "drawitemlist loop"
                for drawitem in drawitemlist:
                    itemhovered = False
                    drawpolygonlist = []

                    itemrectanglescreen = getscreenrectangle(drawitem["rectangle"], zoomvalue, drawcamerax, cameray)
                    if not itemrectanglescreen.colliderect(screenrectangle):
                        continue



                    for polygon in drawitem["polygons"]:
                        polygonrectanglescreen = getscreenrectangle(polygon["rectangle"], zoomvalue, drawcamerax, cameray)
                        if not polygonrectanglescreen.colliderect(screenrectangle):
                            continue



                        polygonpointsscreen = getscreenpoints(polygon["points"], zoomvalue, drawcamerax, cameray)
                        polygonpointsscreenint = [(int(pointx), int(pointy)) for pointx, pointy in polygonpointsscreen]
                        if len(polygonpointsscreenint) < 3:
                            continue
                        drawpolygonlist.append(polygonpointsscreenint)



                        if not itemhovered and polygonrectanglescreen.collidepoint(mouseposition) and ispointinsidepolygon(mouseposition, polygonpointsscreen):
                            if gamephase == "choosecountry" and not stateshape.get("country"):
                                continue
                            itemhovered = True

                            hoveredstateid = drawitem.get("parentid", stateshape["id"])
                            hoveredprovinceid = drawitem["id"] if "parentid" in drawitem else None

                            if hoveredstateid:

                                # ESO optimization 22/04
                                # O(c*s) --> O(1)
                                # use precomputed state lookup for hover tooltip
                                hovertext = esomodule.getstatedata(hoveredstateid, state_data_lookup)
                                # avoid mutating the shared ESO lookup dict; copy before adding province id
                                if hovertext is not None:
                                    hovertext = dict(hovertext)
                                    if hoveredprovinceid:
                                        hovertext["provinceid"] = hoveredprovinceid
                            
                            else:
                                hovertext = None




                    # determine fill color based on game state and interactions
                    # province color
                    if gamephase == "choosecountry":
                        if stateshape.get("country"):
                            basefillcolor = stateshape.get("countrycolor", defaultshapecolor)

                        else:
                            basefillcolor = (75, 75, 75)

                        if pendingcountry and stateshape.get("country") == pendingcountry:
                            basefillcolor = gui_lightencolor(basefillcolor, pendingpulsevalue)


                    elif drawitem.get("id") in selectedprovinceidset:
                        basefillcolor = (232, 214, 103)


                    elif drawitem.get("id") in routepreviewset:
                        basefillcolor = (95, 145, 255)


                    # ESO optimization 22/04
                    # O(d*m) --> O(d+m)
                    # use set membership instead of scanning movement orders for each draw item
                    
                    
                    elif drawitem.get("id") in movingprovinceidset:
                        basefillcolor = (132, 96, 226)



                    else:
                        if drawitem is stateshape and stateshape.get("subdivisions"):
                            uniformsubdivisioncolor = staterenderinfo.get("uniformsubdivisioncolor")
                            if uniformsubdivisioncolor is not None:
                                basefillcolor = uniformsubdivisioncolor
                            else:
                                basefillcolor = drawitem.get("countrycolor", stateshape.get("countrycolor", defaultshapecolor))
                        else:
                            basefillcolor = drawitem.get("countrycolor", stateshape.get("countrycolor", defaultshapecolor))



                    # Pulse-highlight the whole targeted country on the map (like choose-country phase).
                    if (
                        gamephase == "play"
                        and countrymenutarget
                        and countrymenupulsevalue is not None
                        and drawitem.get("id") not in selectedprovinceidset
                        and drawitem.get("id") not in routepreviewset
                        and drawitem.get("id") not in movingprovinceidset
                    ):
                        drawcountry = drawitem.get("controllercountry", drawitem.get("country"))
                        if drawcountry == countrymenutarget:
                            basefillcolor = gui_lightencolor(basefillcolor, countrymenupulsevalue)

                    finalfillcolor = hovercolor if itemhovered else basefillcolor
                    for drawpolygon in drawpolygonlist:
                        pygame.draw.polygon(screen, finalfillcolor, drawpolygon)
                        pygame.draw.polygon(screen, (50, 50, 50), drawpolygon, 1)

        # ESO optimization 22/04
        # O(cp*k) --> O(p*k)
        # badge pass now runs only when needed and only on playable provinces
        
        if gamephase == "play" and showtroopbadges:

           troopbadgelist_raw = []
           troopbadgehitlist = []

           for copyshift in copyshiftlist:
               drawcamerax = camerax + copyshift

               for provinceid, province in playableprovincemap.items():
                   if int(province.get("troops", 0)) <= 0:
                       continue

                   provincerectanglescreen = getscreenrectangle(
                       province["rectangle"],
                       zoomvalue,
                       drawcamerax,
                       cameray
                   )

                   if not provincerectanglescreen.colliderect(screenrectangle):
                       continue

                   iscombatprovince = provinceid in combatprovinceidset
                   ismovingprovince = provinceid in movingprovinceidset

                   badgebackground = (0, 0, 0)
                   badgeborder = (165, 165, 165)

                   if iscombatprovince:
                       badgebackground = (214, 122, 36)
                       badgeborder = (255, 188, 92)
                   elif ismovingprovince:
                       badgebackground = (214, 194, 64)
                       badgeborder = (255, 238, 132)

                   troopbadgelist_raw.append({
                       "center": provincerectanglescreen.center,
                       "troops": province["troops"],
                       "country": getprovincecontroller(province),
                       "backgroundcolor": badgebackground,
                       "bordercolor": badgeborder,
                   })

                   troopbadgerect = gui_gettroopbadgerect(
                       provincerectanglescreen.center,
                       province["troops"],
                       troopbadgefont
                   )

                   troopbadgehitlist.append({
                       "provinceid": provinceid,
                       "rect": troopbadgerect,
                   })

           troopbadgelist = troopbadgelist_raw
           

        if gamephase == "play" and movementorderlist:
            gui_drawmovementorderpaths(
                screen,
                movementorderlist,
                provincemap,
                zoomvalue,
                camerax,
                cameray,
                copyshiftlist,
                screenrectangle,
            )

        if countrybordersdirty:
            countryborderentrylist = esomodule.buildcountryborderentries(
                playableprovincemap,
                provinceedgepairlist,
                countrybordersegmentcache,
            )
            countrybordersdirty = False

        if gamephase == "play" and zoomvalue >= minimumzoomforframe * 1.08:
            gui_drawcountryborders(
                screen,
                countryborderentrylist,
                zoomvalue,
                camerax,
                cameray,
                copyshiftlist,
                screenrectangle,
            )

        if gui_shouldshowcountrylabels(zoomvalue, minimumzoomforframe):
            gui_drawcountrylabels(
                screen,
                playablestateshapelist,
                zoomvalue,
                camerax,
                cameray,
                copyshiftlist,
                screenrectangle,
                countrylabelfont,
                countrylabelcache,
                gamephase,
            )

        frontlineborderedgelist = []
        frontlineedgebykey = {}
        hoveredfrontlineedgekey = None
        if gamephase == "play" and playercountry and (frontlineplacementmode or activefrontlineedgekeyset):
            frontlineborderedgelist = getcountryborderedges(playableprovincemap, playableprovincegraph, playercountry)
            frontlineedgebykey = {edge["edgekey"]: edge for edge in frontlineborderedgelist}

            currentfrontlineedgekeyset = set(frontlineedgebykey.keys())
            activefrontlineedgekeyset.intersection_update(currentfrontlineedgekeyset)

            frontlineoverlaysegments = []
            nearesthoverdistance = float("inf")
            for copyshift in copyshiftlist:
                drawcamerax = camerax + copyshift
                for borderedge in frontlineborderedgelist:
                    edgekey = borderedge["edgekey"]
                    if not frontlineplacementmode and edgekey not in activefrontlineedgekeyset:
                        continue

                    worldsegmentlist = frontlinebordersegmentcache.get(edgekey)
                    if worldsegmentlist is None:
                        worldsegmentlist = getborderworldsegments(playableprovincemap, borderedge)
                        frontlinebordersegmentcache[edgekey] = worldsegmentlist

                    for worldsegmentstart, worldsegmentend in worldsegmentlist:
                        segmentstart, segmentend = getscreenpoints(
                            [worldsegmentstart, worldsegmentend],
                            zoomvalue,
                            drawcamerax,
                            cameray,
                        )

                        segmentleft = int(min(segmentstart[0], segmentend[0])) - 8
                        segmenttop = int(min(segmentstart[1], segmentend[1])) - 8
                        segmentwidth = int(abs(segmentend[0] - segmentstart[0])) + 16
                        segmentheight = int(abs(segmentend[1] - segmentstart[1])) + 16
                        segmentrect = pygame.Rect(segmentleft, segmenttop, max(1, segmentwidth), max(1, segmentheight))
                        if not segmentrect.colliderect(screenrectangle):
                            continue

                        frontlineoverlaysegments.append((edgekey, segmentstart, segmentend))

                        if frontlineplacementmode:
                            hoverdistance = pointtosegmentdistance(mouseposition, segmentstart, segmentend)
                            if hoverdistance <= 10.0 and hoverdistance < nearesthoverdistance:
                                nearesthoverdistance = hoverdistance
                                hoveredfrontlineedgekey = edgekey

            for edgekey, segmentstart, segmentend in frontlineoverlaysegments:
                isactivefrontline = edgekey in activefrontlineedgekeyset
                ishoveredborder = frontlineplacementmode and edgekey == hoveredfrontlineedgekey

                if frontlineplacementmode:
                    bordercolor = (255, 236, 145) if ishoveredborder else (235, 205, 92)
                    borderwidth = 4 if ishoveredborder else 2
                    pygame.draw.line(screen, bordercolor, segmentstart, segmentend, borderwidth)

                if isactivefrontline:
                    pygame.draw.line(screen, (185, 24, 24), segmentstart, segmentend, 8)
                    pygame.draw.line(screen, (220, 42, 42), segmentstart, segmentend, 5)
                    pygame.draw.line(screen, (255, 96, 96), segmentstart, segmentend, 2)

            if frontlineplacementmode:
                placementsegmentlist = [(segmentstart, segmentend) for _, segmentstart, segmentend in frontlineoverlaysegments]
                placementbridges = getkruskalbridges(placementsegmentlist, maxgapdistance=20.0)
                for bridgestart, bridgeend in placementbridges:
                    pygame.draw.line(screen, (235, 205, 92), bridgestart, bridgeend, 2)

            activefrontlinesegmentlist = [
                (segmentstart, segmentend)
                for edgekey, segmentstart, segmentend in frontlineoverlaysegments
                if edgekey in activefrontlineedgekeyset
            ]
            activefrontlinebridges = getkruskalbridges(activefrontlinesegmentlist, maxgapdistance=20.0)
            for bridgestart, bridgeend in activefrontlinebridges:
                pygame.draw.line(screen, (185, 24, 24), bridgestart, bridgeend, 8)
                pygame.draw.line(screen, (220, 42, 42), bridgestart, bridgeend, 5)
                pygame.draw.line(screen, (255, 96, 96), bridgestart, bridgeend, 2)

        selectedtroopentries = getselectedtroopentries(
            selectedprovinceidset,
            selectedprovinceid,
            provincemap,
            playercountry,
        )

        canrecruit = (
            selectedprovinceid is not None
            and getprovincecontroller(provincemap[selectedprovinceid]) == playercountry
            and getprovinceowner(provincemap[selectedprovinceid]) == playercountry
        )
        recruitgoldcost, recruitpopulationcost = getrecruitcosts(
            recruitamount,
            recruitgoldcostperunit,
            recruitpopulationcostperunit,
        )
        recruitenabled = canrecruit and canrecruittroops(
            playergold,
            playerpopulation,
            recruitgoldcost,
            recruitpopulationcost,
            developmentmode=developmentmode,
        )

        # switch back to the full window surface for UI chrome
        screen = screen_main
        warprogressdata = {}
        if gamephase == "play" and warpairset and runtimeui.warprogressopen:
            warprogressdata = buildwarprogressdata()

            
                
        current_stats = {}
        if runtimeui._selectedmapcountry:
            selected_country = runtimeui._selectedmapcountry
            base_stats = country_stats_lookup.get(selected_country, {})
            
            total_pop = 0
            total_manpower = 0
            for prov in provincemap.values():
                if prov.get("country") == selected_country:
                    total_pop += int(prov.get("population", 0))
                    total_manpower += int(prov.get("troops", 0))
            
            current_stats = {
                "population": total_pop,  
                "manpower": total_manpower,  
                "stability": base_stats.get("stability", 50.0),
                "leader": base_stats.get("leader", "Unknown"),
            }
       
        
        runtimeui.sync(
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
            mouseposition_full,
            troopbadgelist,
            focustree.viewdata(),
            warprogressdata=warprogressdata,
            selected_country_stats=current_stats,
        )
        runtimeui.update(elapsedseconds)
        runtimeui.draw(screen)
        scriptengine.draw_script_ui(screen)
        if developmentmode and gamephase == "play":
            drawdevfpsgraph(screen, smallfont, fpshistory)





        # DRAG SELECT RECTANGLE
        if gamephase == "play" and isdragselecting and dragselectstart and dragselectcurrent:
            selectionrect = makerectfrompoints(dragselectstart, dragselectcurrent)
            if selectionrect.width > 0 or selectionrect.height > 0:
                overlaysurface = pygame.Surface((selectionrect.width or 1, selectionrect.height or 1), pygame.SRCALPHA)
                overlaysurface.fill((95, 145, 255, 45))
                mapscreen.blit(overlaysurface, selectionrect.topleft)
                pygame.draw.rect(mapscreen, (95, 145, 255), selectionrect, width=1)





        #DRAW GUIS, ON TOP
        devconsole.draw(screen, normalfont, smallfont, clock, "dev console") # draw dev console after ui so that it appears on top
        newspopup.draw(screen, (titlefont, normalfont), newssystem.current)





        for event in pygame.event.get():
            if scriptengine.handle_script_ui_event(event):
                continue

            uiaction = runtimeui.process_event(event)
            if uiaction == InGameUI.actionquitgame:
                isrunning = False
                continue

            if uiaction == InGameUI.actionpausemenu:
                continue

            if runtimeui.pausemenuopen:
                if event.type == pygame.QUIT:
                    isrunning = False
                continue

            eventmappos = None
            if hasattr(event, "pos"):
                eventmappos = (event.pos[0] - maprect.x, event.pos[1] - maprect.y)

            if uiaction == InGameUI.actionchoosecountry and gamephase == "choosecountry":
                if pendingcountry:
                    playercountry = pendingcountry
                    gamephase = "play"
                    countrybordersdirty = True
                    expandedstateid = None
                    selectedprovinceid = None
                    selectedprovinceidset = set()
                    routepreviewset = set()
                    frontlineplacementmode = False
                    activefrontlineedgekeyset = set()
                    frontlineassignmentlist = []
                    frontlinebordersegmentcache = {}
                    countriesatwarset = set()
                    warpairset = set()
                    warrecordlookup.clear()
                    countrymenutarget = None
                    npcdirector.setplayercountry(playercountry)
                    npcdirector.sync_player_wars(playercountry, countriesatwarset, warpairset=warpairset)
                    focustree = loadfocustreeforcountry(playercountry)
                    updatescriptengine()
                    eventbus.emit(
                        EngineEventType.PLAYERCOUNTRYSELECTED,
                        {
                            "country": playercountry,
                        },
                    )
                continue

            if uiaction == "declarewar" and gamephase == "play":
                if countrymenutarget and countrymenutarget != playercountry:
                    eventbus.emit(
                        EngineEventType.WARDECLARED,
                        {
                            "attacker": playercountry,
                            "defender": countrymenutarget,
                            "turn": currentturnnumber,
                        },
                    )
                countrymenutarget = None
                continue

            if uiaction == InGameUI.actionrecruit and gamephase == "play":
                if selectedprovinceid:
                    selectedprovince = provincemap[selectedprovinceid]
                    if (
                        getprovincecontroller(selectedprovince) == playercountry
                        and getprovinceowner(selectedprovince) == playercountry
                    ):
                        requiredgold, requiredpopulation = getrecruitcosts(
                            recruitamount,
                            recruitgoldcostperunit,
                            recruitpopulationcostperunit,
                        )
                        if canrecruittroops(
                            playergold,
                            playerpopulation,
                            requiredgold,
                            requiredpopulation,
                            developmentmode=developmentmode,
                        ):
                            selectedprovince["troops"] += recruitamount
                            markprovincetroopactivity(selectedprovince, currentturnnumber)
                            if not developmentmode:
                                playergold -= requiredgold
                                playerpopulation -= requiredpopulation
                            updatescriptengine()
                            eventbus.emit(
                                EngineEventType.TROOPSRECRUITED,
                                {
                                    "country": playercountry,
                                    "provinceId": selectedprovinceid,
                                    "amount": recruitamount,
                                    "turn": currentturnnumber,
                                },
                            )
                continue

            if uiaction == InGameUI.actiontogglefocuspanel and gamephase == "play":
                continue

            if (
                isinstance(uiaction, tuple)
                and len(uiaction) == 2
                and uiaction[0] == InGameUI.actionstartfocus
                and gamephase == "play"
            ):
                focusstartresult = focustree.startfocus(uiaction[1])
                if focusstartresult.success:
                    eventbus.emit(
                        EngineEventType.FOCUSSTARTED,
                        {
                            "country": playercountry,
                            "focusId": focusstartresult.focusid,
                            "turn": currentturnnumber,
                        },
                    )
                continue




            # for quick search: "end turn button"
            # ON END TURN, process movement orders, apply economy, increment turn, emit next turn event
            if uiaction == InGameUI.actionendturn and gamephase == "play":
                processmovementorders(
                    movementorderlist,
                    provincemap,
                    emit=eventbus.emit,
                    currentturnnumber=currentturnnumber,
                )
                countrybordersdirty = True
                focuseffectcontext = FocusEffectContext(
                    gold=playergold,
                    population=playerpopulation,
                    economyconfig=economyconfig,
                    country=playercountry,
                )
                focusturnresult = focustree.advanceturn(focuseffectcontext)
                playergold = max(0, int(focuseffectcontext.gold))
                playerpopulation = max(0, int(focuseffectcontext.population))
                if focusturnresult.completedfocusid:
                    updatescriptengine()
                    eventbus.emit(
                        EngineEventType.FOCUSCOMPLETED,
                        {
                            "country": playercountry,
                            "focusId": focusturnresult.completedfocusid,
                            "turn": currentturnnumber,
                            "appliedEffects": [dict(effect) for effect in focusturnresult.appliedeffects],
                        },
                    )
                playergold,playerpopulation = applyendturneconomy(
                    playercountry,
                    provincemap,
                    playergold,
                    playerpopulation,
                )
                npcdirector.sync_player_wars(playercountry, countriesatwarset, warpairset=warpairset)
                npcdirector.executeturn(
                    movementorderlist,
                    currentturnnumber,
                )
                frontlineupdates = refreshfrontlines()
                currentturnnumber += 1
                routepreviewset = frontlineupdates
                updatescriptengine()
                eventbus.emit(
                    EngineEventType.NEXTTURN,
                    {
                        "turn": currentturnnumber,
                        "playerCountry": playercountry,
                        "playerGold": playergold,
                        "playerPopulation": playerpopulation,
                    },
                )
                continue

            if uiaction == "split" and gamephase == "play":
                selectedids = [entry["provinceid"] for entry in selectedtroopentries]
                splitresult = splitselectedtroops(
                    provincemap,
                    provincegraph,
                    selectedids,
                    playercountry,
                )
                if splitresult["success"]:
                    selectedprovinceidset = set(splitresult["selectedprovinceids"])
                    selectedprovinceid = splitresult["primaryprovinceid"]
                    routepreviewset = set()
                continue

            if uiaction == "merge" and gamephase == "play":
                selectedids = [entry["provinceid"] for entry in selectedtroopentries]
                mergeresult = mergeselectedtroops(
                    provincemap,
                    selectedids,
                    playercountry,
                    targetprovinceid=selectedprovinceid,
                )
                if mergeresult["success"]:
                    selectedprovinceidset = set(mergeresult["selectedprovinceids"])
                    selectedprovinceid = mergeresult["primaryprovinceid"]
                    routepreviewset = set()
                continue

            if uiaction == "frontline" and gamephase == "play":
                hastroopsselected = any(int(entry.get("troops", 0)) > 0 for entry in selectedtroopentries)
                frontlineplacementmode = bool(hastroopsselected) and not frontlineplacementmode
                routepreviewset = set()
                countrymenutarget = None
                continue

            if event.type == pygame.QUIT:
                isrunning = False





            #GUI INTERACTIONS

           # elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # if newssystem.current and newspopup.handleclick(event.pos):
                #     newssystem.closecurrent()
                #     continue
                # if newssystem.current:
                #     continue
                # 
                # if devconsole.handleleftclick(event.pos):
   
   
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if newssystem.current and newspopup.handleclick(event.pos):
                    newssystem.closecurrent()
                    continue

                if devconsole.handleleftclick(event.pos):
                    continue


                #fix issue where choose country button is blocked
                if gamephase != "choosecountry" and runtimeui.ispointeroverui(event.pos):
                    continue

                if gamephase == "choosecountry":

                    if hoveredstateid:
                        selectedstateobject = stateobjectlookup.get(hoveredstateid)
                        if selectedstateobject and selectedstateobject.get("country"):

                            #engine bus

                            pendingcountry = selectedstateobject["country"]
                            eventbus.emit(
                                EngineEventType.COUNTRYCANDIDATESELECTED,
                                {
                                    "country": pendingcountry,
                                    "stateId": selectedstateobject["id"],
                                },
                            )

                    continue

                elif gamephase == "play":
                    if hoveredstateid:
                        selectedstateobject = stateobjectlookup.get(hoveredstateid)
                        if selectedstateobject and selectedstateobject.get("country"):
                            country = selectedstateobject["country"]
                            runtimeui.select_map_country(country)
                            current_stats = country_stats_lookup.get(country, {})
                        else:
                            runtimeui.select_map_country(None)
                            current_stats = {}
                    else:
                        runtimeui.select_map_country(None)
                        current_stats = {}

                if gamephase == "play" and frontlineplacementmode:
                    if hoveredfrontlineedgekey and hoveredfrontlineedgekey in frontlineedgebykey:
                        frontlineresult = createfrontline(
                            playableprovincemap,
                            playableprovincegraph,
                            playercountry,
                            [entry["provinceid"] for entry in selectedtroopentries],
                            frontlineedgebykey[hoveredfrontlineedgekey],
                        )
                        if frontlineresult["success"]:
                            frontlineresult["frontlineid"] = nextfrontlineid()
                            movementmodule.registerfrontlineassignment(
                                playableprovincemap,
                                frontlineresult["frontlineid"],
                                frontlineresult.get("transferplan", ()),
                            )
                            deploymentresult = movementmodule.applyfrontlinetransferplan(
                                frontlineresult,
                                frontlineresult.get("transferplan", ()),
                                playableprovincemap,
                                playableprovincegraph,
                                movementorderlist,
                                emit=eventbus.emit,
                                currentturnnumber=currentturnnumber,
                            )
                            frontlineassignmentlist.append(frontlineresult)
                            syncfrontlineoverlays()
                            selectedprovinceidset = set(frontlineresult["frontlineprovinceids"])
                            selectedprovinceid = frontlineresult["anchorprovinceid"]
                            selectedprovince = provincemap.get(selectedprovinceid) if selectedprovinceid else None
                            if selectedprovince:
                                expandedstateid = selectedprovince.get("parentid", expandedstateid)
                            routepreviewset = deploymentresult["routepreviewset"]
                            countrymenutarget = None
                            frontlineplacementmode = False
                        continue
                    
                    #fix click handlin
                    # clicking away from a valid border cancels frontline placement mode,
                    # then falls through to normal province click handling.
                    frontlineplacementmode = False



                # collidepoint checks button and country menu interacts
                if gamephase == "play":
                    if countrymenutarget:
                        countrymenutarget = None
                        continue

                    if eventmappos is None or not pygame.Rect(0, 0, maprect.width, maprect.height).collidepoint(eventmappos):
                        continue
                    dragselectstart = eventmappos
                    dragselectcurrent = eventmappos
                    isdragselecting = True

            elif event.type == pygame.MOUSEMOTION:
                if isdragselecting:
                    if eventmappos is not None:
                        dragselectcurrent = eventmappos

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if gamephase != "play" or not isdragselecting:
                    continue

                if eventmappos is None:
                    continue
                dragselectcurrent = eventmappos
                selectionrect = makerectfrompoints(dragselectstart, dragselectcurrent)
                isdragselecting = False

                hasdragdistance = max(selectionrect.width, selectionrect.height) >= dragminimumdistance
                if hasdragdistance:
                    selectedids = getdragselectedprovinceids(selectionrect, troopbadgehitlist, provincemap, playercountry)
                    selectedprovinceidset = set(selectedids)

                    if selectedids:
                        selectedprovinceid = selectedids[0]
                        selectedprovince = provincemap.get(selectedprovinceid)
                        expandedstateid = selectedprovince.get("parentid") if selectedprovince else expandedstateid
                        routepreviewset = set()
                        countrymenutarget = None
                        if selectedprovince:
                            eventbus.emit(
                                EngineEventType.PROVINCESELECTED,
                                {
                                    "provinceId": selectedprovinceid,
                                    "stateId": selectedprovince.get("parentid"),
                                    "country": getprovincecontroller(selectedprovince),
                                },
                            )
                    else:
                        selectedprovinceid = None
                        selectedprovinceidset = set()
                        routepreviewset = set()
                    
                    current_stats = {}

                    dragselectstart = None
                    dragselectcurrent = None
                    continue

                clickedbadgeprovinceid = getbadgehitprovinceid(eventmappos, troopbadgehitlist)
                if clickedbadgeprovinceid:
                    selectedprovince = provincemap.get(clickedbadgeprovinceid)
                    if selectedprovince and getprovincecontroller(selectedprovince) == playercountry:
                        selectedprovinceid = clickedbadgeprovinceid
                        selectedprovinceidset = {clickedbadgeprovinceid}
                        expandedstateid = selectedprovince.get("parentid", hoveredstateid)
                        routepreviewset = set()
                        countrymenutarget = None
                        eventbus.emit(
                            EngineEventType.PROVINCESELECTED,
                            {
                                "provinceId": selectedprovinceid,
                                "stateId": selectedprovince.get("parentid"),
                                "country": getprovincecontroller(selectedprovince),
                            },
                        )
                        dragselectstart = None
                        dragselectcurrent = None
                        continue

                if hoveredprovinceid:
                    selectedprovince = provincemap.get(hoveredprovinceid)
                    if selectedprovince and getprovincecontroller(selectedprovince) == playercountry:
                        selectedprovinceid = hoveredprovinceid
                        selectedprovinceidset = {hoveredprovinceid}
                        expandedstateid = selectedprovince.get("parentid", hoveredstateid)
                        routepreviewset = set()
                        countrymenutarget = None
                        eventbus.emit(
                            EngineEventType.PROVINCESELECTED,
                            {
                                "provinceId": selectedprovinceid,
                                "stateId": selectedprovince.get("parentid"),
                                "country": getprovincecontroller(selectedprovince),
                            },
                        )
                        dragselectstart = None
                        dragselectcurrent = None
                        continue

                if hoveredstateid is not None:
                    expandedstateid = hoveredstateid


                    hoveredstateprovince = getprovinceundercursorinstate(
                        eventmappos,
                        hoveredstateid,
                        stateobjectlookup,
                        zoomvalue,
                        camerax,
                        cameray,
                        copyshiftlist,
                    )

                    if hoveredstateprovince and getprovincecontroller(hoveredstateprovince) == playercountry:
                        selectedprovinceid = hoveredstateprovince["id"]
                        selectedprovinceidset = {selectedprovinceid}
                        routepreviewset = set()
                        countrymenutarget = None
                        eventbus.emit(
                            EngineEventType.PROVINCESELECTED,
                            {
                                "provinceId": selectedprovinceid,
                                "stateId": hoveredstateprovince.get("parentid"),
                                "country": getprovincecontroller(hoveredstateprovince),
                            },
                        )

                    eventbus.emit(
                        EngineEventType.STATESELECTED,
                        {
                            "stateId": expandedstateid,
                        },
                    )
                else:
                    expandedstateid = None
                    selectedprovinceid = None
                    selectedprovinceidset = set()
                    routepreviewset = set()







                dragselectstart = None
                dragselectcurrent = None

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3: # right click for move orders
                if devconsole.visible or gamephase != "play" or frontlineplacementmode:
                    continue

                # Only open the country interaction menu when the click is on a state (no hovered province).
                if hoveredprovinceid is None:
                    if hoveredstateid is not None:
                        selectedstateobject = stateobjectlookup.get(hoveredstateid)
                        if selectedstateobject:
                            destinationcountry = selectedstateobject.get("controllercountry", selectedstateobject.get("country"))
                            if playercountry and destinationcountry and destinationcountry != playercountry:
                                countrymenutarget = destinationcountry
                                routepreviewset = set()
                                continue
                    countrymenutarget = None
                    continue

                destinationprovince = provincemap.get(hoveredprovinceid)
                if not destinationprovince:
                    continue

                destinationcountry = getprovincecontroller(destinationprovince)
                if playercountry and destinationcountry and destinationcountry != playercountry:
                    if destinationcountry not in countriesatwarset:
                        countrymenutarget = destinationcountry
                        routepreviewset = set() # set() is an empty set to clear route preview
                        continue

                countrymenutarget = None





                if selectedprovinceid is None:
                    continue
                if hoveredprovinceid == selectedprovinceid:
                    continue

                sourceprovince = provincemap.get(selectedprovinceid)
                if not sourceprovince:
                    continue
                if getprovincecontroller(sourceprovince) != playercountry:
                    continue
                if sourceprovince["troops"] <= 0:
                    continue





                allowedcountryset = {playercountry} | countriesatwarset
                if destinationcountry not in allowedcountryset:
                    continue


                allowedprovinceidset = {
                    provinceid for provinceid, province in provincemap.items() if getprovincecontroller(province) in allowedcountryset
                } # this allows movement thrugh your own province and supposedly the enemy provinces
                # TODO: fix the issue that you cannot move through enemy provinces


                # allows for multiple source provinces if you have multiple selected, prioritizes the hovered province if it is in the selection, then prioritizes the order of selection, then just goes through them in id order
                sourceprovinceidlist = []
                if selectedprovinceidset:
                    sourceprovinceidlist.extend(sorted(provinceid for provinceid in selectedprovinceidset if provinceid in provincemap))
                    if selectedprovinceid in sourceprovinceidlist:
                        sourceprovinceidlist.remove(selectedprovinceid)
                        sourceprovinceidlist.insert(0, selectedprovinceid)
                elif selectedprovinceid:
                    sourceprovinceidlist.append(selectedprovinceid)
                else:
                    continue

                routepreviewset = set()
                for sourceprovinceid in sourceprovinceidlist:
                    if sourceprovinceid == hoveredprovinceid:
                        continue

                    sourceprovince = provincemap.get(sourceprovinceid)
                    if not sourceprovince:
                        continue
                    if getprovincecontroller(sourceprovince) != playercountry:
                        continue
                    if sourceprovince["troops"] <= 0:
                        continue

                    foundpath = findprovincepath(
                        sourceprovinceid,
                        hoveredprovinceid,
                        provincemap,
                        provincegraph,
                        allowedprovinceidset=allowedprovinceidset,
                    )

                    routepreviewset.update(foundpath)
                    if len(foundpath) < 2:
                        continue

                    movingtroopcount = sourceprovince["troops"]
                    sourceprovince["troops"] -= movingtroopcount
                    markprovincetroopactivity(sourceprovince, currentturnnumber)

                    movementorderlist.append(
                        {
                            "amount": movingtroopcount,
                            "path": foundpath, # list of province ids to move through in order per turn
                            "index": 0, # the current provincei n the path list
                            "current": foundpath[0],
                            "speedmodifier": 1.0,
                            "controllercountry": getprovincecontroller(sourceprovince),
                            "country": getprovincecontroller(sourceprovince),
                            "countrycolor": sourceprovince.get("countrycolor"),
                            "ordercreatedturn": currentturnnumber,
                        }
                    )
                    eventbus.emit(
                        EngineEventType.MOVEORDERCREATED,
                        {
                            "sourceProvinceId": sourceprovinceid,
                            "destinationProvinceId": hoveredprovinceid,
                            "path": list(foundpath),
                            "troops": movingtroopcount,
                            "country": getprovincecontroller(sourceprovince),
                            "turn": currentturnnumber,
                        },
                    )


            elif event.type == pygame.MOUSEWHEEL:
                if devconsole.visible:
                    continue
                if runtimeui.focusview.isopen:
                    continue

                
                mousex, mousey = pygame.mouse.get_pos()
                cameramodule.applywheelzoom(camerastate, event.y, windowheight, mapbox, mousex, mousey)
                

            elif event.type == pygame.KEYDOWN:
                # Space = next turn (only in play phase, and not while dev console is capturing input)
                if event.key == pygame.K_SPACE and gamephase == "play" and not devconsole.visible:
                    processmovementorders(
                        movementorderlist,
                        provincemap,
                        emit=eventbus.emit,
                        currentturnnumber=currentturnnumber,
                    )
                    countrybordersdirty = True
                    focuseffectcontext = FocusEffectContext(
                        gold=playergold,
                        population=playerpopulation,
                        economyconfig=economyconfig,
                        country=playercountry,
                    )
                    focusturnresult = focustree.advanceturn(focuseffectcontext)
                    playergold = max(0, int(focuseffectcontext.gold))
                    playerpopulation = max(0, int(focuseffectcontext.population))
                    if focusturnresult.completedfocusid:
                        updatescriptengine()
                        eventbus.emit(
                            EngineEventType.FOCUSCOMPLETED,
                            {
                                "country": playercountry,
                                "focusId": focusturnresult.completedfocusid,
                                "turn": currentturnnumber,
                                "appliedEffects": [dict(effect) for effect in focusturnresult.appliedeffects],
                            },
                        )
                    playergold, playerpopulation = applyendturneconomy(
                        playercountry,
                        provincemap,
                        playergold,
                        playerpopulation,
                    )
                    npcdirector.sync_player_wars(playercountry, countriesatwarset, warpairset=warpairset)
                    npcdirector.executeturn(
                        movementorderlist,
                        currentturnnumber,
                    )
                    frontlineupdates = refreshfrontlines()
                    currentturnnumber += 1
                    routepreviewset = frontlineupdates
                    updatescriptengine()
                    eventbus.emit(
                        EngineEventType.NEXTTURN,
                        {
                            "turn": currentturnnumber,
                            "playerCountry": playercountry,
                            "playerGold": playergold,
                            "playerPopulation": playerpopulation,
                        },
                    )
                    continue


            # (for quick ctrl f: developer console)
                commandcontext = {
                    "playercountry": playercountry,
                    "playergold": playergold,
                    "playerpopulation": playerpopulation,
                    "gamephase": gamephase,
                    "currentturnnumber": currentturnnumber,
                    "countriesatwarset": set(countriesatwarset),
                    "warpairset": set(warpairset),
                    "npcdirector": npcdirector,
                    "economyconfig": economyconfig,
                    "movementorderlist": movementorderlist,
                    "provincegraph": provincegraph,
                }
                if devconsole.handlekeydown(
                    event,
                    provincemap,
                    playercountry,
                    countrytocolorlookup,
                    defaultshapecolor,
                    troopbadgelist,
                    eventbus=eventbus,
                    currentturnnumber=currentturnnumber,
                    commandcontext=commandcontext,
                ):
                    applyconsolecommandstate(commandcontext)
                    continue # handle dev console input




            elif event.type == pygame.VIDEORESIZE:
                if is_fullscreen: 
                    continue
                oldmaprect = maprect
                newwindowwidth = max(400, event.w)
                newwindowheight = max(300, event.h)

                screen = pygame.display.set_mode((newwindowwidth, newwindowheight), pygame.RESIZABLE)
                runtimeui.setwindowsize((newwindowwidth, newwindowheight))
                maprect = runtimeui.map_rect
                cameramodule.resizecamerastate(
                    camerastate,
                    oldmaprect.width,
                    oldmaprect.height,
                    maprect.width,
                    maprect.height,
                    mapbox,
                )
                cameramodule.clampcamerastate(camerastate, maprect.height, mapbox)
                zoomvalue = camerastate.zoom
                camerax = camerastate.x
                cameray = camerastate.y
                continue



        pygame.display.flip()

    newssystem.stop()
    pygame.quit()
# loading screen and main loop ends






























# DEFINITIONS
loadsvgshapes = coremodule.loadsvgshapes
getmapbox = coremodule.getmapbox
getscreenpoints = cameramodule.getscreenpoints
getscreenrectangle = cameramodule.getscreenrectangle
getminimumzoomforheight = cameramodule.getminimumzoomforheight
clampverticalcamera = cameramodule.clampverticalcamera
wraphorizontalcamera = cameramodule.wraphorizontalcamera
ispointinsidepolygon = coremodule.ispointinsidepolygon
loadcountrydata = coremodule.loadcountrydata
groupsubdivisionsbystate = coremodule.groupsubdivisionsbystate

getprovincecontroller = movementmodule.getprovincecontroller
getprovinceowner = movementmodule.getprovinceowner
setprovincecontroller = movementmodule.setprovincecontroller
prepareprovincemetadata = movementmodule.prepareprovincemetadata
buildprovinceadjacencygraph = movementmodule.buildprovinceadjacencygraph
getterrainmovecost = movementmodule.getterrainmovecost
findprovincepath = movementmodule.findprovincepath
processmovementorders = movementmodule.processmovementorders
splitselectedtroops = movementmodule.splitselectedtroops
mergeselectedtroops = movementmodule.mergeselectedtroops
getcountryborderedges = movementmodule.getcountryborderedges
getborderworldsegments = movementmodule.getborderworldsegments
createfrontline = movementmodule.createfrontline
pointtosegmentdistance = movementmodule.pointtosegmentdistance
markprovincetroopactivity = movementmodule.markprovincetroopactivity

getrecruitcosts = economymodule.getrecruitcosts
canrecruittroops = economymodule.canrecruittroops
applyendturneconomy = economymodule.applyendturneconomy
getdefaulteconomyconfig = economymodule.getdefaulteconomyconfig
initializeplayereconomy = economymodule.initializeplayereconomy

