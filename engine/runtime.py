import os
import json
import math
import random
import time
import platform
import pygame
import xml.etree.ElementTree as elementtree
from svgelements import Path
import ctypes
ctypes.windll.user32.SetProcessDPIAware()

select_sound = None

COVID_NEWS_EVENTS = {
    10: {
        "title": "FIRST COVID CASES",
        "description": "Several Southeast Asian countries begin reporting their first COVID-19 cases.",
    },
    20: {
        "title": "BORDER RESTRICTIONS IMPLEMENTED",
        "description": "Governments across Southeast Asia tighten border controls to contain the virus.",
    },
    30: {
        "title": "NATIONAL LOCKDOWNS BEGIN",
        "description": "Movement control measures and lockdowns begin across multiple countries.",
    },
    40: {
        "title": "COVID ENDEMIC IN THAILAND",
        "description": "Thailand begins transitioning toward endemic COVID management policies.",
    },
    50: {
        "title": "HOSPITALS UNDER PRESSURE",
        "description": "Healthcare systems face rising pressure due to increasing infection rates.",
    },
    60: {
        "title": "MASK MANDATES EXPANDED",
        "description": "Public mask mandates are expanded in major cities and transportation hubs.",
    },
    70: {
        "title": "ECONOMIC SLOWDOWN",
        "description": "Regional economies experience major slowdowns due to pandemic restrictions.",
    },
    80: {
        "title": "REMOTE LEARNING INTRODUCED",
        "description": "Schools and universities transition to online learning systems.",
    },
    90: {
        "title": "VACCINE DEVELOPMENT PROGRESSES",
        "description": "Global vaccine development efforts begin showing positive results.",
    },
    100: {
        "title": "SOUTHEAST ASIA ADAPTS TO NEW NORMAL",
        "description": "Countries continue adapting to long-term pandemic management strategies.",
    },
}

LEADERS = {
    "Malaysia": "Mahathir Mohamad",
    "Singapore": "Lawrence Wong",
    "Indonesia": "Prabowo Subianto",
    "Thailand": "Srettha Thavisin",
    "Philippines": "Bongbong Marcos",
    "Vietnam": "To Lam",
    "Myanmar": "Min Aung Hlaing",
    "Cambodia": "Hun Manet",
    "Laos": "Thongloun Sisoulith",
    "Brunei": "Hassanal Bolkiah",
    "Timor_Leste" : "José Ramos-Horta"
}

CAPITAL_PROVINCES = {
    "Malaya_17": "Kuala Lumpur",
    "Singapore_01": "Singapore",
    "Siam_23": "Bangkok",
    "Cambodia_22": "Phnom Penh",
    "Southern_Indochina_19": "Ho Chi Minh",
    "Laos_18": "Vientiane",
    "Pegu_02": "Naypyidaw",
    "Brunei_02": "Brunei",
    "Manila_04": "Manila",
    "Java_03": "Jakarta",
    "Portugese_Timor_03": "Dili",
}

CAPITAL_STABILITY_PENALTY = 3.0


def tacticalmapfill(colorvalue):
    try:
        r, g, b = colorvalue[:3]
    except (TypeError, ValueError):
        return (70, 78, 86)
    average = int((r + g + b) / 3)
    r = int((r * 0.62 + average * 0.18 + 8 * 0.20))
    g = int((g * 0.62 + average * 0.18 + 16 * 0.20))
    b = int((b * 0.62 + average * 0.18 + 28 * 0.20))
    return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))




from game.ingame_ui import InGameUI
from game.animation.motion import PulseLayer, draw_light_sweep, draw_scanlines, draw_soft_glow, ease_out_cubic, exp_lerp, mix_color, pulse
from game.focuseffects import FocusEffectContext
from game.focusloader import loadfocustreeforcountry
from game.researchui import load_research_data as _load_research_data, RESEARCH_RP_PER_TURN
from engine.console import developmentconsole, loaddevmodeflag 
from engine.gui import (
    gui_lightencolor,
    gui_gettroopbadgerect,
    gui_shouldshowtroopbadges,
    gui_shouldshowcountrylabels,
    gui_drawmovementorderpaths,
    gui_drawcountrylabels,
    gui_drawcountryborders,
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
hovercolor = (214, 169, 77)
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
                pygame.draw.polygon(worldsurface, (18, 50, 18, 255), shiftedpoints)

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


def getcapitalhitprovinceid(mouseposition, capitalhitlist):
    for capitalentry in reversed(capitalhitlist):
        if capitalentry["rect"].collidepoint(mouseposition):
            return capitalentry["provinceid"]
    return None


def makecapitalmarkersurface(size=28):
    markersurface = pygame.Surface((size, size), pygame.SRCALPHA)
    center = size // 2
    outerradius = max(8, size // 2 - 2)
    innerradius = max(4, int(outerradius * 0.42))

    pygame.draw.circle(markersurface, (8, 13, 22, 230), (center + 1, center + 2), outerradius)
    pygame.draw.circle(markersurface, (229, 183, 76, 255), (center, center), outerradius)
    pygame.draw.circle(markersurface, (29, 39, 56, 255), (center, center), outerradius - 3)

    starpoints = []
    for pointindex in range(10):
        angle = -math.pi / 2 + pointindex * math.pi / 5
        radius = innerradius if pointindex % 2 else outerradius - 7
        starpoints.append((
            center + math.cos(angle) * radius,
            center + math.sin(angle) * radius,
        ))
    pygame.draw.polygon(markersurface, (255, 235, 151, 255), starpoints)
    pygame.draw.polygon(markersurface, (96, 69, 20, 255), starpoints, 1)
    return markersurface


def loadcapitalflags(size=(34, 22)):
    flags = {}
    flagdirectory = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "flags"))
    if not os.path.isdir(flagdirectory):
        return flags

    for filename in os.listdir(flagdirectory):
        countryname, extension = os.path.splitext(filename)
        if extension.lower() not in (".png", ".jpg", ".jpeg", ".bmp"):
            continue
        filepath = os.path.join(flagdirectory, filename)
        try:
            image = pygame.image.load(filepath).convert_alpha()
            flags[countryname] = pygame.transform.smoothscale(image, size)
        except pygame.error:
            continue
    return flags


def getcapitalflag(capitalflaglookup, countryname):
    if not countryname:
        return None
    countrykey = str(countryname).strip().replace(" ", "_")
    return capitalflaglookup.get(countrykey)


def drawcapitalmarkers(
    surface,
    provincemap,
    zoomvalue,
    camerax,
    cameray,
    copyshiftlist,
    screenrectangle,
    markersurface,
):
    capitalhitlist = []
    if markersurface is None:
        return capitalhitlist

    for copyshift in copyshiftlist:
        drawcamerax = camerax + copyshift
        for provinceid in CAPITAL_PROVINCES:
            province = provincemap.get(provinceid)
            if not province:
                continue

            provincerectanglescreen = getscreenrectangle(province["rectangle"], zoomvalue, drawcamerax, cameray)
            if not provincerectanglescreen.colliderect(screenrectangle):
                continue

            markerrect = markersurface.get_rect(center=provincerectanglescreen.center)
            if not markerrect.colliderect(screenrectangle):
                continue

            surface.blit(markersurface, markerrect)
            capitalhitlist.append({
                "provinceid": provinceid,
                "rect": markerrect,
            })

    return capitalhitlist


def drawcapitalinfopopup(surface, provinceid, provincemap, zoomvalue, camerax, cameray, font, smallfont, capitalflaglookup):
    if not provinceid or provinceid not in CAPITAL_PROVINCES:
        return

    province = provincemap.get(provinceid)
    if not province:
        return

    cityname = CAPITAL_PROVINCES[provinceid]
    ownercountry = getprovinceowner(province)
    controllercountry = getprovincecontroller(province)
    flagimage = getcapitalflag(capitalflaglookup, ownercountry)
    titletext = font.render(cityname, True, (245, 238, 218))
    detailtext = smallfont.render("-3% stability each turn while captured", True, (229, 183, 76))
    status = "Captured" if ownercountry and controllercountry and ownercountry != controllercountry else "Capital"
    statustext = smallfont.render(status, True, (202, 209, 218))

    flagwidth = flagimage.get_width() if flagimage else 0
    contentwidth = max(titletext.get_width(), detailtext.get_width(), statustext.get_width())
    popupwidth = max(240, 28 + flagwidth + (10 if flagimage else 0) + contentwidth + 20)
    popupheight = 78

    provincerectanglescreen = getscreenrectangle(province["rectangle"], zoomvalue, camerax, cameray)
    popuprect = pygame.Rect(
        provincerectanglescreen.centerx + 18,
        provincerectanglescreen.centery - popupheight - 18,
        popupwidth,
        popupheight,
    )
    popuprect.clamp_ip(surface.get_rect())

    shadow = pygame.Surface((popuprect.width + 8, popuprect.height + 8), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 95), shadow.get_rect(), border_radius=6)
    surface.blit(shadow, (popuprect.x - 3, popuprect.y - 2))
    pygame.draw.rect(surface, (14, 22, 35), popuprect, border_radius=6)
    pygame.draw.rect(surface, (229, 183, 76), popuprect, 1, border_radius=6)

    drawx = popuprect.x + 14
    drawy = popuprect.y + 14
    if flagimage:
        flagrect = flagimage.get_rect(topleft=(drawx, drawy + 5))
        surface.blit(flagimage, flagrect)
        drawx = flagrect.right + 10

    surface.blit(titletext, (drawx, drawy))
    surface.blit(statustext, (drawx, drawy + 24))
    surface.blit(detailtext, (drawx, drawy + 44))


def applycapitalstabilitypenalties(provincemap, playercountry, playerstability, countryeconomy):
    penalizedcountries = set()
    for provinceid in CAPITAL_PROVINCES:
        province = provincemap.get(provinceid)
        if not province:
            continue

        ownercountry = getprovinceowner(province)
        controllercountry = getprovincecontroller(province)
        if not ownercountry or not controllercountry or ownercountry == controllercountry:
            continue
        penalizedcountries.add(ownercountry)

    for countryname in penalizedcountries:
        if playercountry and countryname == playercountry:
            playerstability = max(0.0, min(100.0, playerstability - CAPITAL_STABILITY_PENALTY))
            continue

        economystate = countryeconomy.get(countryname) if countryeconomy is not None else None
        if economystate is not None:
            currentstability = float(economystate.get("stability", 50.0))
            economystate["stability"] = max(0.0, min(100.0, currentstability - CAPITAL_STABILITY_PENALTY))

    return playerstability, penalizedcountries




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


def getcachedscreenpolygon(polygon, zoomvalue, offsetx, offsety):
    cachekey = (round(zoomvalue, 4), round(offsetx, 2), round(offsety, 2))
    cache = polygon.get("_screencache")
    if cache is None:
        cache = {}
        polygon["_screencache"] = cache
    cachedentry = cache.get(cachekey)
    if cachedentry is not None:
        return cachedentry

    polygonrectanglescreen = getscreenrectangle(polygon["rectangle"], zoomvalue, offsetx, offsety)
    polygonpointsscreen = getscreenpoints(polygon["points"], zoomvalue, offsetx, offsety)
    polygonpointsscreenint = [(int(pointx), int(pointy)) for pointx, pointy in polygonpointsscreen]
    cachedentry = (polygonrectanglescreen, polygonpointsscreen, polygonpointsscreenint)
    if len(cache) > 8:
        cache.clear()
    cache[cachekey] = cachedentry
    return cachedentry

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
    now = pygame.time.get_ticks() / 1000.0
    lasttick = getattr(drawloadingscreen, "_lasttick", now)
    dt = max(0.0, min(0.12, now - lasttick))
    drawloadingscreen._lasttick = now
    if completedcount <= 0 or not hasattr(drawloadingscreen, "_displayprogress"):
        drawloadingscreen._displayprogress = progressvalue
    else:
        drawloadingscreen._displayprogress = exp_lerp(
            drawloadingscreen._displayprogress,
            progressvalue,
            7.5,
            dt,
        )
    displayprogress = max(progressvalue, min(1.0, drawloadingscreen._displayprogress))

    windowwidth, windowheight = screen.get_size()
    screenrect = screen.get_rect()
    topcolor = (5, 10, 19)
    bottomcolor = (13, 22, 37)
    for y in range(windowheight):
        t = y / max(1, windowheight - 1)
        pygame.draw.line(screen, mix_color(topcolor, bottomcolor, t), (0, y), (windowwidth, y))
    draw_scanlines(screen, screenrect, now, color=(74, 143, 231), alpha=13, spacing=32)

    center = (windowwidth // 2, int(windowheight * 0.33))
    orbitalsurface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    for ring in range(4):
        radius = int(50 + ring * 24 + pulse(now, 1.4 + ring * 0.28, ring) * 8)
        alpha = max(18, 70 - ring * 11)
        pygame.draw.circle(orbitalsurface, (212, 169, 77, alpha), center, radius, 1)
    sweepangle = now * 2.6
    pygame.draw.line(
        orbitalsurface,
        (242, 204, 119, 210),
        center,
        (
            int(center[0] + math.cos(sweepangle) * 110),
            int(center[1] + math.sin(sweepangle) * 110),
        ),
        2,
    )
    for dotindex in range(18):
        angle = sweepangle * 0.45 + dotindex * (math.tau / 18.0)
        orbit = 104 + math.sin(now * 1.6 + dotindex) * 10
        dotx = int(center[0] + math.cos(angle) * orbit)
        doty = int(center[1] + math.sin(angle) * orbit * 0.44)
        pygame.draw.circle(orbitalsurface, (124, 196, 255, 70), (dotx, doty), 2)
    screen.blit(orbitalsurface, (0, 0))

    titletextabovebar = largefont.render("EBEE CONQUEST", True, (242, 204, 119))
    stagesurface = smallfont.render(str(stage).upper(), True, (190, 210, 230))
    screen.blit(titletextabovebar, titletextabovebar.get_rect(center=(windowwidth // 2, windowheight // 2 - 84)))
    screen.blit(stagesurface, stagesurface.get_rect(center=(windowwidth // 2, windowheight // 2 - 48)))

    barwidth = min(760, windowwidth - 120)
    barheight = 20
    barx = (windowwidth - barwidth) // 2
    bary = windowheight // 2 - 10
    barrect = pygame.Rect(barx, bary, barwidth, barheight)

    draw_soft_glow(screen, barrect.inflate(8, 8), (74, 143, 231), 0.36 + 0.18 * pulse(now, 2.0), radius=9, rings=4)
    pygame.draw.rect(screen, (20, 30, 45), barrect, border_radius=9)
    pygame.draw.rect(screen, (67, 82, 105), barrect, 1, border_radius=9)
    fillrect = barrect.copy()
    fillrect.width = max(0, int(barwidth * displayprogress))
    if fillrect.width > 0:
        pygame.draw.rect(screen, (74, 143, 231), fillrect, border_radius=9)
        inner = fillrect.inflate(-4, -6)
        if inner.width > 0 and inner.height > 0:
            pygame.draw.rect(screen, (242, 204, 119), inner, border_radius=5)
    draw_light_sweep(screen, barrect, now * 1.4, (255, 235, 160), alpha=34)

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

    paneltop = bary + 52
    panelheight = min(180, max(100, windowheight - paneltop - 40))
    panelrect = pygame.Rect(barx, paneltop, barwidth, panelheight)

    draw_soft_glow(screen, panelrect, (212, 169, 77), 0.18, radius=8, rings=4)
    pygame.draw.rect(screen, (11, 17, 28), panelrect, border_radius=7)
    pygame.draw.rect(screen, (67, 82, 105), panelrect, 1, border_radius=7)
    pygame.draw.line(screen, (212, 169, 77), (panelrect.x + 16, panelrect.y + 1), (panelrect.right - 16, panelrect.y + 1), 1)

    visibleloglines = list(loglines or ())
    maxvisiblelines = max(1, (panelrect.height - 16) // 18)
    visibleloglines = visibleloglines[-maxvisiblelines:]
    texty = panelrect.y + 8
    for lineindex, logline in enumerate(visibleloglines):
        linealpha = 145 + int(70 * pulse(now, 1.1, lineindex * 0.55))
        loglinesurface = smallfont.render(logline, True, (min(255, linealpha), min(255, linealpha + 18), 230))
        screen.blit(loglinesurface, (panelrect.x + 10, texty))
        texty += 18

    footer = smallfont.render("SYNCHRONIZING MAP DATA", True, (132, 145, 160))
    screen.blit(footer, footer.get_rect(center=(windowwidth // 2, min(windowheight - 26, panelrect.bottom + 28))))

    pygame.display.flip()
    return True





def main(eventbus=None, is_fullscreen=False):
    global select_sound
    
    if eventbus is None:
        eventbus = EventBus()
    startupbegintimestamp = time.perf_counter()
    pygame.init()
    pygame.mixer.init()
    
    select_sound = pygame.mixer.Sound("game/sounds/troop_select.wav")
    select_sound.set_volume(0.5)
    
    move_sound = pygame.mixer.Sound("game/sounds/troop_move.wav")
    move_sound.set_volume(0.5)
    
    mahathir_speech = pygame.mixer.Sound("game/speeches/mahathir_speech.wav")
    mahathir_speech.set_volume(0.7)
    
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
        total_pop = 0
        states_data = entry.get("States", {})
        if isinstance(states_data, dict):
            for sdata in states_data.values():
                if isinstance(sdata, dict):
                    total_pop += parse_population(sdata.get("population", 0))
        country_stats_lookup[name] = {
            "population": total_pop,
            "manpower": parse_population(entry.get("manpower", 0)),
            "stability": float(str(entry.get("stability", 0)).strip() or 0),
            "leader": LEADERS.get(name, "Unknown"),
            "leading_party": str(entry.get("LeadingParty", "")).strip(),
            "parties": entry.get("MajorPoliticalParties", []),
        }
       
    
    statetocountrylookup, countrytocolorlookup = loadcountrydata(countrydatafilepath)
    allowedstateidset = set(statetocountrylookup.keys())
    state_data_lookup = esomodule.buildstatedatalookup(countries_raw)
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
    countrycapitalprovinceidlookup = {}
    for capitalprovinceid in CAPITAL_PROVINCES:
        capitalprovince = provincemap.get(capitalprovinceid)
        if not capitalprovince:
            continue
        capitalcountry = getprovinceowner(capitalprovince)
        if capitalcountry:
            countrycapitalprovinceidlookup[capitalcountry] = capitalprovinceid



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
    if not drawloadingscreen(
        screen,
        loadingtitlefont,
        loadingtextfont,
        1,
        1,
        stage="Ready",
        statusline="Entering command view...",
        loglines=loadingloglines,
    ):
        pygame.quit()
        return


    
    windowwidth, windowheight = screen.get_size()
    runtimeui = InGameUI((windowwidth, windowheight))
    maprect = runtimeui.map_rect
    camerastate = cameramodule.createcamerastate(maprect.width, maprect.height, mapbox)









    clock = pygame.time.Clock()
    fpshistory = []
    fpshistorymaxsamples = 180
    perfautocountry = os.environ.get("EBEE_PERF_AUTO_COUNTRY")
    try:
        perfautoturn = int(os.environ.get("EBEE_PERF_AUTO_TURN", "0") or "0")
    except ValueError:
        perfautoturn = 0
    try:
        perfidleframes = int(os.environ.get("EBEE_PERF_IDLE_FRAMES", "0") or "0")
    except ValueError:
        perfidleframes = 0
    try:
        perfwarturn = int(os.environ.get("EBEE_PERF_WAR_TURN", "0") or "0")
    except ValueError:
        perfwarturn = 0
    try:
        perfmonitorturns = int(os.environ.get("EBEE_PERF_MONITOR_TURNS", "0") or "0")
    except ValueError:
        perfmonitorturns = 0
    perfwarcountries = [
        countryname.strip()
        for countryname in os.environ.get("EBEE_PERF_WAR_COUNTRIES", "").split(",")
        if countryname.strip()
    ]
    perfmonitoractive = perfwarturn > 0 and perfmonitorturns > 0 and bool(perfwarcountries)
    perfmonitorstopturn = perfwarturn + perfmonitorturns
    if perfmonitoractive and perfidleframes <= 0:
        perfidleframes = 30
    perfenabled = bool(perfautocountry or perfautoturn or perfidleframes or perfmonitoractive)
    perfidleframetimes = []
    perfsectiontotals = {}
    perfidlecollecting = False
    perfmonitoridleturn = None
    perfwarspawned = False
    sea_gradient_cache = None
    sea_gradient_cache_size = None
    grid_overlay_cache = None
    grid_overlay_cache_key = None
    movement_path_overlay_cache = None
    movement_path_overlay_cache_key = None
    map_vignette_cache = None
    map_vignette_cache_size = None
    cinematicpulseoverlay = PulseLayer()
    camerashakeamount = 0.0
    ambientphasetimer = 0.0
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
        playerstability,
        playerpp,
        playerap,
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
    frontlineborderedgelistcache = []
    frontlineborderedgesdirty = True
    staterenderlookupcache = {}
    staterenderlookupcachekey = None
    staterenderlookupdirty = True
    countriesatwarset = set() # track countries at war
    warpairset = set()
    warrecordlookup = {}
    occupationtransferlookup = {}
    capitulationtimer = {}
    capitulatedset = set()
    countrymenutarget = None
    researched_set: set[str] = set()
    researching_node_id: str | None = None
    researching_turns_remaining: int = 0
    _research_cost_lookup: dict[str, int] = {}
    _research_raw = _load_research_data()
    for _rcat in _research_raw.values():
        for _rn in _rcat.get("nodes", []):
            _research_cost_lookup[_rn["id"]] = _rn["cost"]

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

            if subdivisions:
                # split state vp across provinces so partial occupations and annexations can count.
                vpperprovince = statevp / provincecount if provincecount else 0.0
                for province in subdivisions:
                    provinceowner = getprovinceowner(province) or stateowner
                    if provinceowner:
                        totalvplookup[provinceowner] = totalvplookup.get(provinceowner, 0.0) + vpperprovince
                        totalprovincelookup[provinceowner] = totalprovincelookup.get(provinceowner, 0) + 1

                    controller = getprovincecontroller(province)
                    if not controller:
                        continue
                    controlledvplookup[controller] = controlledvplookup.get(controller, 0.0) + vpperprovince
                    controlledprovincelookup[controller] = controlledprovincelookup.get(controller, 0) + 1
                    if provinceowner:
                        matrixkey = (provinceowner, controller)
                        ownedcontrolledvplookup[matrixkey] = ownedcontrolledvplookup.get(matrixkey, 0.0) + vpperprovince
                        ownedcontrolledprovincelookup[matrixkey] = ownedcontrolledprovincelookup.get(matrixkey, 0) + 1
                continue

            if stateowner:
                totalvplookup[stateowner] = totalvplookup.get(stateowner, 0.0) + statevp
                totalprovincelookup[stateowner] = totalprovincelookup.get(stateowner, 0) + provincecount

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
        syncwarrecordswithpairs()
        if not warrecordlookup:
            return {"wars": [], "active_war_count": 0}

        recordlist = list(warrecordlookup.values())
        recordlist.sort(
            key=lambda record: (
                0 if playercountry and playercountry in record.get("pair", ()) else 1,
                -safeint(record.get("startturn"), 0),
                str(record.get("aggressor", "")),
                str(record.get("defender", "")),
            )
        )
        metrics = buildwarcountrymetrics()
        totalvp = metrics["totalvp"]
        controlledvp = metrics["controlledvp"]
        ownedcontrolledvp = metrics["ownedcontrolledvp"]
        totalprovinces = metrics["totalprovinces"]
        controlledprovinces = metrics["controlledprovinces"]
        ownedcontrolledprovinces = metrics["ownedcontrolledprovinces"]
        fieldmanpower = metrics["fieldmanpower"]

        def buildcontrollerbreakdown(owner):
            ownerprovincecount = totalprovinces.get(owner, 0)
            ownervp = totalvp.get(owner, 0.0)
            breakdown = []
            for (matrixowner, controller), provincecount in ownedcontrolledprovinces.items():
                if matrixowner != owner or controller == owner:
                    continue
                vpheld = ownedcontrolledvp.get((matrixowner, controller), 0.0)
                breakdown.append({
                    "controller": controller,
                    "provinces": max(0, safeint(provincecount, 0)),
                    "province_percent": 0.0 if ownerprovincecount <= 0 else (provincecount / ownerprovincecount) * 100.0,
                    "vp": vpheld,
                    "vp_percent": 0.0 if ownervp <= 0 else (vpheld / ownervp) * 100.0,
                })
            breakdown.sort(key=lambda item: (item["provinces"], item["vp"]), reverse=True)
            return breakdown

        def buildtransferlist(relevantcountries):
            transferlist = []
            for transfer in occupationtransferlookup.values():
                owner = transfer.get("owner")
                controller = transfer.get("controller")
                previouscontroller = transfer.get("previous_controller")
                if not ({owner, controller, previouscontroller} & relevantcountries):
                    continue
                transferlist.append(dict(transfer))
            transferlist.sort(key=lambda item: safeint(item.get("turn"), 0), reverse=True)
            return transferlist[:8]

        def getrecordcountries(record):
            aggressor = record.get("aggressor")
            defender = record.get("defender")
            if not aggressor or not defender:
                firstcountry, secondcountry = record.get("pair", (None, None))
                aggressor = aggressor or firstcountry
                defender = defender or secondcountry
            return aggressor, defender

        def formatcountrylist(countries, maxnames=2):
            names = [country for country in countries if country]
            if not names:
                return "Unknown"
            if len(names) <= maxnames:
                return " + ".join(names)
            return " + ".join(names[:maxnames]) + f" +{len(names) - maxnames}"

        def getcomponentrecords(componentcountries):
            componentset = set(componentcountries)
            entries = []
            for record in recordlist:
                aggressor, defender = getrecordcountries(record)
                if aggressor in componentset and defender in componentset:
                    entries.append(record)
            entries.sort(
                key=lambda record: (
                    safeint(record.get("startturn"), 0),
                    str(record.get("aggressor", "")),
                    str(record.get("defender", "")),
                )
            )
            return entries

        def assignwarsides(componentcountries, componentrecords):
            sidelookup = {}
            conflictpairs = []
            for record in componentrecords:
                aggressor, defender = getrecordcountries(record)
                if not aggressor or not defender:
                    continue
                if aggressor not in sidelookup and defender not in sidelookup:
                    sidelookup[aggressor] = 0
                    sidelookup[defender] = 1
                elif aggressor in sidelookup and defender not in sidelookup:
                    sidelookup[defender] = 1 - sidelookup[aggressor]
                elif defender in sidelookup and aggressor not in sidelookup:
                    sidelookup[aggressor] = 1 - sidelookup[defender]
                elif sidelookup[aggressor] == sidelookup[defender]:
                    conflictpairs.append((aggressor, defender))

            for country in sorted(componentcountries):
                if country not in sidelookup:
                    sidelookup[country] = 0
            return sidelookup, conflictpairs

        def sumcountrycasualties(country, componentrecords):
            return sum(
                max(0, safeint(record.get("casualties", {}).get(country, 0), 0))
                for record in componentrecords
            )

        def buildcountrywarentry(country, enemycountries, componentrecords):
            enemyset = set(enemycountries or ())
            enemycapturedvp = sum(
                ownedcontrolledvp.get((country, enemycountry), 0.0)
                for enemycountry in enemyset
            )
            enemycapturedprovinces = sum(
                ownedcontrolledprovinces.get((country, enemycountry), 0)
                for enemycountry in enemyset
            )
            countrytotalvp = totalvp.get(country, 0.0)
            countrytotalprovinces = totalprovinces.get(country, 0)
            breakdown = buildcontrollerbreakdown(country)
            foreignprovinces = sum(item["provinces"] for item in breakdown)
            return {
                "country": country,
                "casualties": max(0, sumcountrycasualties(country, componentrecords)),
                "manpower": max(0, safeint(fieldmanpower.get(country, 0), 0)),
                "total_vp": countrytotalvp,
                "controlled_vp": controlledvp.get(country, 0.0),
                "enemy_captured_vp": enemycapturedvp,
                "capitulation_progress": 0.0 if countrytotalvp <= 0 else max(0.0, min(100.0, (enemycapturedvp / countrytotalvp) * 100.0)),
                "total_provinces": countrytotalprovinces,
                "controlled_provinces": controlledprovinces.get(country, 0),
                "enemy_occupied_provinces": enemycapturedprovinces,
                "foreign_occupied_provinces": foreignprovinces,
                "occupied_percent": 0.0 if countrytotalprovinces <= 0 else max(0.0, min(100.0, (foreignprovinces / countrytotalprovinces) * 100.0)),
                "enemy_occupied_percent": 0.0 if countrytotalprovinces <= 0 else max(0.0, min(100.0, (enemycapturedprovinces / countrytotalprovinces) * 100.0)),
                "occupation_breakdown": breakdown,
            }

        def aggregatecontrollerbreakdown(countries):
            aggregate = {}
            sideprovinces = sum(max(0, safeint(totalprovinces.get(country, 0), 0)) for country in countries)
            sidevp = sum(max(0.0, float(totalvp.get(country, 0.0) or 0.0)) for country in countries)
            for country in countries:
                for item in buildcontrollerbreakdown(country):
                    controller = item.get("controller")
                    if not controller:
                        continue
                    entry = aggregate.setdefault(controller, {"controller": controller, "provinces": 0, "vp": 0.0})
                    entry["provinces"] += max(0, safeint(item.get("provinces", 0), 0))
                    entry["vp"] += max(0.0, float(item.get("vp", 0.0) or 0.0))
            breakdown = []
            for entry in aggregate.values():
                provinces = entry["provinces"]
                vpheld = entry["vp"]
                breakdown.append({
                    "controller": entry["controller"],
                    "provinces": provinces,
                    "province_percent": 0.0 if sideprovinces <= 0 else (provinces / sideprovinces) * 100.0,
                    "vp": vpheld,
                    "vp_percent": 0.0 if sidevp <= 0 else (vpheld / sidevp) * 100.0,
                })
            breakdown.sort(key=lambda item: (item["provinces"], item["vp"]), reverse=True)
            return breakdown

        def buildwarcomponents():
            adjacency = {}
            for record in recordlist:
                aggressor, defender = getrecordcountries(record)
                if not aggressor or not defender:
                    continue
                adjacency.setdefault(aggressor, set()).add(defender)
                adjacency.setdefault(defender, set()).add(aggressor)

            components = []
            seen = set()
            for country in sorted(adjacency):
                if country in seen:
                    continue
                stack = [country]
                component = set()
                while stack:
                    current = stack.pop()
                    if current in component:
                        continue
                    component.add(current)
                    stack.extend(adjacency.get(current, set()) - component)
                seen.update(component)
                components.append(component)
            return components

        def buildsideentry(sidecountries, sideentries, enemycountries):
            sidecountries = list(sidecountries)
            totalprovs = sum(max(0, safeint(entry.get("total_provinces", 0), 0)) for entry in sideentries)
            enemyprovs = sum(max(0, safeint(entry.get("enemy_occupied_provinces", 0), 0)) for entry in sideentries)
            totalvps = sum(max(0.0, float(entry.get("total_vp", 0.0) or 0.0)) for entry in sideentries)
            enemyvps = sum(max(0.0, float(entry.get("enemy_captured_vp", 0.0) or 0.0)) for entry in sideentries)
            return {
                "label": formatcountrylist(sidecountries),
                "countries": sidecountries,
                "enemy_countries": list(enemycountries),
                "country_entries": sideentries,
                "casualties": sum(max(0, safeint(entry.get("casualties", 0), 0)) for entry in sideentries),
                "manpower": sum(max(0, safeint(entry.get("manpower", 0), 0)) for entry in sideentries),
                "total_vp": totalvps,
                "enemy_captured_vp": enemyvps,
                "pressure": 0.0 if totalvps <= 0 else max(0.0, min(100.0, (enemyvps / totalvps) * 100.0)),
                "total_provinces": totalprovs,
                "enemy_occupied_provinces": enemyprovs,
                "enemy_occupied_percent": 0.0 if totalprovs <= 0 else max(0.0, min(100.0, (enemyprovs / totalprovs) * 100.0)),
            }

        def buildwarentry(record):
            aggressor = record.get("aggressor")
            defender = record.get("defender")
            if not aggressor or not defender:
                firstcountry, secondcountry = record.get("pair", (None, None))
                aggressor = aggressor or firstcountry
                defender = defender or secondcountry
            if not aggressor or not defender:
                return None

            casualties = record.get("casualties", {})
            aggressorcapturedvp = ownedcontrolledvp.get((defender, aggressor), 0.0)
            defendercapturedvp = ownedcontrolledvp.get((aggressor, defender), 0.0)
            aggressordirectprovinces = ownedcontrolledprovinces.get((defender, aggressor), 0)
            defenderdirectprovinces = ownedcontrolledprovinces.get((aggressor, defender), 0)
            defendertotalvp = totalvp.get(defender, 0.0)
            aggressortotalvp = totalvp.get(aggressor, 0.0)
            defendertotalprovinces = totalprovinces.get(defender, 0)
            aggressortotalprovinces = totalprovinces.get(aggressor, 0)

            aggressorbreakdown = buildcontrollerbreakdown(aggressor)
            defenderbreakdown = buildcontrollerbreakdown(defender)
            aggressorforeignprovinces = sum(item["provinces"] for item in aggressorbreakdown)
            defenderforeignprovinces = sum(item["provinces"] for item in defenderbreakdown)
            progress = 0.0 if defendertotalvp <= 0 else (aggressorcapturedvp / defendertotalvp) * 100.0
            defenderprogress = 0.0 if aggressortotalvp <= 0 else (defendercapturedvp / aggressortotalvp) * 100.0
            defenderoccupiedpercent = 0.0 if defendertotalprovinces <= 0 else (defenderforeignprovinces / defendertotalprovinces) * 100.0
            aggressoroccupiedpercent = 0.0 if aggressortotalprovinces <= 0 else (aggressorforeignprovinces / aggressortotalprovinces) * 100.0

            relevantcountries = {aggressor, defender}
            relevantcountries.update(item["controller"] for item in aggressorbreakdown)
            relevantcountries.update(item["controller"] for item in defenderbreakdown)
            transferlist = buildtransferlist(relevantcountries)

            return {
                "id": "|".join(record.get("pair", (aggressor, defender))),
                "aggressor": aggressor,
                "defender": defender,
                "progress": max(0.0, min(100.0, progress)),
                "defender_progress": max(0.0, min(100.0, defenderprogress)),
                "defender_occupied_percent": max(0.0, min(100.0, defenderoccupiedpercent)),
                "aggressor_occupied_percent": max(0.0, min(100.0, aggressoroccupiedpercent)),
                "active_war_count": len(warpairset),
                "start_turn": record.get("startturn"),
                "aggressor_casualties": max(0, safeint(casualties.get(aggressor, 0), 0)),
                "defender_casualties": max(0, safeint(casualties.get(defender, 0), 0)),
                "total_casualties": max(0, safeint(casualties.get(aggressor, 0), 0)) + max(0, safeint(casualties.get(defender, 0), 0)),
                "aggressor_manpower": max(0, safeint(fieldmanpower.get(aggressor, 0), 0)),
                "defender_manpower": max(0, safeint(fieldmanpower.get(defender, 0), 0)),
                "aggressor_total_vp": aggressortotalvp,
                "defender_total_vp": defendertotalvp,
                "aggressor_controlled_vp": controlledvp.get(aggressor, 0.0),
                "defender_controlled_vp": controlledvp.get(defender, 0.0),
                "aggressor_captured_vp": aggressorcapturedvp,
                "defender_captured_vp": defendercapturedvp,
                "aggressor_total_provinces": aggressortotalprovinces,
                "defender_total_provinces": defendertotalprovinces,
                "aggressor_controlled_provinces": controlledprovinces.get(aggressor, 0),
                "defender_controlled_provinces": controlledprovinces.get(defender, 0),
                "aggressor_occupied_enemy_provinces": aggressordirectprovinces,
                "defender_occupied_enemy_provinces": defenderdirectprovinces,
                "aggressor_foreign_occupied_provinces": aggressorforeignprovinces,
                "defender_foreign_occupied_provinces": defenderforeignprovinces,
                "aggressor_occupation_breakdown": aggressorbreakdown,
                "defender_occupation_breakdown": defenderbreakdown,
                "occupation_transfers": transferlist,
            }

        pairwars = [entry for entry in (buildwarentry(record) for record in recordlist) if entry is not None]
        pairlookup = {entry.get("id"): entry for entry in pairwars}

        wars = []
        for componentcountries in buildwarcomponents():
            componentrecords = getcomponentrecords(componentcountries)
            if not componentrecords:
                continue
            sidelookup, conflictpairs = assignwarsides(componentcountries, componentrecords)
            attackers = sorted(
                [country for country, side in sidelookup.items() if side == 0],
                key=lambda country: (0 if country == playercountry else 1, country),
            )
            defenders = sorted(
                [country for country, side in sidelookup.items() if side == 1],
                key=lambda country: (0 if country == playercountry else 1, country),
            )
            if not attackers or not defenders:
                continue

            countryenemylookup = {country: set() for country in componentcountries}
            for record in componentrecords:
                recordaggressor, recorddefender = getrecordcountries(record)
                if not recordaggressor or not recorddefender:
                    continue
                countryenemylookup.setdefault(recordaggressor, set()).add(recorddefender)
                countryenemylookup.setdefault(recorddefender, set()).add(recordaggressor)

            attackerentries = [
                buildcountrywarentry(country, countryenemylookup.get(country, defenders), componentrecords)
                for country in attackers
            ]
            defenderentries = [
                buildcountrywarentry(country, countryenemylookup.get(country, attackers), componentrecords)
                for country in defenders
            ]
            attackerentries.sort(key=lambda item: (0 if item.get("country") == playercountry else 1, -safeint(item.get("manpower", 0), 0), item.get("country", "")))
            defenderentries.sort(key=lambda item: (0 if item.get("country") == playercountry else 1, -safeint(item.get("manpower", 0), 0), item.get("country", "")))

            attackerside = buildsideentry(attackers, attackerentries, defenders)
            defenderside = buildsideentry(defenders, defenderentries, attackers)
            componentpairwars = []
            for record in componentrecords:
                pair = record.get("pair")
                pairid = "|".join(pair) if pair else None
                if pairid and pairid in pairlookup:
                    componentpairwars.append(pairlookup[pairid])

            relevantcountries = set(componentcountries)
            attackerbreakdown = aggregatecontrollerbreakdown(attackers)
            defenderbreakdown = aggregatecontrollerbreakdown(defenders)
            relevantcountries.update(item["controller"] for item in attackerbreakdown)
            relevantcountries.update(item["controller"] for item in defenderbreakdown)
            startturns = [safeint(record.get("startturn"), currentturnnumber) for record in componentrecords]
            startturn = min(startturns) if startturns else currentturnnumber
            leaderattacker = attackers[0]
            leaderdefender = defenders[0]
            attackersidepressure = defenderside["pressure"]
            defendersidepressure = attackerside["pressure"]
            warentry = {
                "id": "group|" + "|".join(sorted(componentcountries)),
                "name": f"{formatcountrylist(attackers)} vs {formatcountrylist(defenders)}",
                "aggressor": leaderattacker,
                "defender": leaderdefender,
                "attacker_label": attackerside["label"],
                "defender_label": defenderside["label"],
                "attackers": attackerentries,
                "defenders": defenderentries,
                "attacker_side": attackerside,
                "defender_side": defenderside,
                "war_pairs": componentpairwars,
                "pair_count": len(componentpairwars),
                "active_war_count": len(warpairset),
                "start_turn": startturn,
                "progress": attackersidepressure,
                "defender_progress": defendersidepressure,
                "defender_occupied_percent": defenderside["enemy_occupied_percent"],
                "aggressor_occupied_percent": attackerside["enemy_occupied_percent"],
                "aggressor_casualties": attackerside["casualties"],
                "defender_casualties": defenderside["casualties"],
                "total_casualties": attackerside["casualties"] + defenderside["casualties"],
                "aggressor_manpower": attackerside["manpower"],
                "defender_manpower": defenderside["manpower"],
                "aggressor_total_vp": attackerside["total_vp"],
                "defender_total_vp": defenderside["total_vp"],
                "aggressor_captured_vp": defenderside["enemy_captured_vp"],
                "defender_captured_vp": attackerside["enemy_captured_vp"],
                "aggressor_total_provinces": attackerside["total_provinces"],
                "defender_total_provinces": defenderside["total_provinces"],
                "aggressor_occupied_enemy_provinces": defenderside["enemy_occupied_provinces"],
                "defender_occupied_enemy_provinces": attackerside["enemy_occupied_provinces"],
                "aggressor_foreign_occupied_provinces": attackerside["enemy_occupied_provinces"],
                "defender_foreign_occupied_provinces": defenderside["enemy_occupied_provinces"],
                "aggressor_occupation_breakdown": attackerbreakdown,
                "defender_occupation_breakdown": defenderbreakdown,
                "occupation_transfers": buildtransferlist(relevantcountries),
                "side_conflicts": conflictpairs,
            }
            wars.append(warentry)

        if not wars:
            wars = pairwars
        if not wars:
            return {"wars": [], "active_war_count": 0}

        wars.sort(
            key=lambda war: (
                0 if playercountry and any(entry.get("country") == playercountry for entry in war.get("attackers", []) + war.get("defenders", [])) else 1,
                -safeint(war.get("pair_count", 1), 1),
                -safeint(war.get("start_turn"), 0),
                str(war.get("name", "")),
            )
        )
        data = dict(wars[0])
        data["wars"] = wars
        data["active_war_count"] = len(wars)
        data["active_pair_count"] = len(pairwars)
        return data

    def executecapitulation(defeatedcountry, victoriouscountry):
        if defeatedcountry in capitulatedset:
            return
        capitulatedset.add(defeatedcountry)

        aggressorcolor = countrytocolorlookup.get(victoriouscountry, (85, 85, 85))
        for province in provincemap.values():
            owner = getprovinceowner(province)
            prevcontroller = getprovincecontroller(province)

            if owner == defeatedcountry:
                setprovincecontroller(province, victoriouscountry, aggressorcolor)
            elif prevcontroller == defeatedcountry:
                actualowner = getprovinceowner(province)
                ownercolor = countrytocolorlookup.get(actualowner, (85, 85, 85))
                setprovincecontroller(province, actualowner, ownercolor)
            else:
                continue

            eventbus.emit(EngineEventType.PROVINCECONTROLCHANGED, {
                "provinceId": province.get("id"),
                "previousController": prevcontroller,
                "newController": getprovincecontroller(province),
            })

        for pair in list(warpairset):
            if defeatedcountry in pair:
                warrecordlookup.pop(pair, None)
                warpairset.discard(pair)

        countriesatwarset.discard(defeatedcountry)
        capitulationtimer.pop(defeatedcountry, None)
        nonlocal countrybordersdirty
        countrybordersdirty = True

        eventbus.emit(EngineEventType.CAPITULATED, {
            "defender": defeatedcountry,
            "aggressor": victoriouscountry,
            "turn": currentturnnumber,
        })

        pushnotification(
            "CAPITULATION",
            f"{defeatedcountry} has capitulated to {victoriouscountry}!",
        )

    def checkcapitulations():
        metrics = buildwarcountrymetrics()
        totalvp = metrics["totalvp"]
        ownedcontrolledvp = metrics["ownedcontrolledvp"]

        def check_victim_capitulation(victimpairs):
            for victim, enemies in victimpairs.items():
                victimtotalvp = totalvp.get(victim, 0.0)
                if victimtotalvp <= 0:
                    continue
                totalcapturedvp = 0.0
                leader = None
                leadercapturedvp = 0.0
                for enemy in enemies:
                    capturedvp = ownedcontrolledvp.get((victim, enemy), 0.0)
                    totalcapturedvp += capturedvp
                    if capturedvp > leadercapturedvp:
                        leadercapturedvp = capturedvp
                        leader = enemy
                progress = (totalcapturedvp / victimtotalvp) * 100.0
                if progress >= 80.0 and leader:
                    if victim not in capitulationtimer:
                        stability = playerstability if victim == playercountry else npcdirector.countryeconomy.get(victim, {}).get("stability", 50.0)
                        graceturns = int(10 + (stability / 100.0) * 10)
                        capitulationtimer[victim] = {
                            "capitulateturn": currentturnnumber + graceturns,
                            "aggressor": leader,
                        }
                        pushnotification(
                            "CAPITULATION RISK",
                            f"{victim} is at risk of capitulation in {graceturns} turns.",
                        )
                    elif currentturnnumber >= capitulationtimer[victim]["capitulateturn"]:
                        executecapitulation(victim, capitulationtimer[victim]["aggressor"])

        defenderpairs = {}
        aggressorpairs = {}
        for pair in list(warpairset):
            record = warrecordlookup.get(pair)
            if not record:
                continue
            aggressor = record.get("aggressor")
            defender = record.get("defender")
            if not aggressor or not defender:
                continue
            if defender not in capitulatedset:
                defenderpairs.setdefault(defender, []).append(aggressor)
            if aggressor not in capitulatedset:
                aggressorpairs.setdefault(aggressor, []).append(defender)

        check_victim_capitulation(defenderpairs)
        check_victim_capitulation(aggressorpairs)

    def nextfrontlineid():
        nonlocal frontlineassignmentcounter
        frontlineassignmentcounter += 1
        countryprefix = playercountry or "frontline"
        return f"{countryprefix}_frontline_{frontlineassignmentcounter}"

    def getdivisiondisplayname():
        return f"Division {frontlineassignmentcounter}"

    def getfrontlineassignment(frontlineid):
        if not frontlineid:
            return None
        for assignment in frontlineassignmentlist:
            if assignment.get("frontlineid") == frontlineid:
                return assignment
        return None

    def getdivisiontroopcount(frontlineid):
        if not frontlineid:
            return 0
        stationarytroops = sum(
            movementmodule.getprovincefrontlinetroops(province, frontlineid)
            for province in playableprovincemap.values()
        )
        movingtroops = sum(
            max(0, int(order.get("amount", 0)))
            for order in movementorderlist
            if order.get("frontlineid") == frontlineid
        )
        return stationarytroops + movingtroops

    def annotateselectedtroopentries(selectedentries):
        assignmentlookup = {
            assignment.get("frontlineid"): assignment
            for assignment in frontlineassignmentlist
            if assignment.get("frontlineid")
        }
        annotatedentries = []
        for entry in selectedentries:
            annotatedentry = dict(entry)
            province = provincemap.get(entry.get("provinceid"))
            annotatedentry["regimentname"] = f"Regiment {len(annotatedentries) + 1}"
            if province:
                frontlineassignments = province.get("frontlineassignments")
                if isinstance(frontlineassignments, dict):
                    assignedfrontlineids = sorted(
                        frontlineid
                        for frontlineid, amount in frontlineassignments.items()
                        if max(0, int(amount)) > 0
                    )
                    if assignedfrontlineids:
                        frontlineid = assignedfrontlineids[0]
                        assignment = assignmentlookup.get(frontlineid, {})
                        annotatedentry["divisionid"] = frontlineid
                        annotatedentry["divisionname"] = assignment.get("divisionname") or str(frontlineid)
                        annotatedentry["divisionautoadvance"] = bool(assignment.get("autoadvance", False))
                        annotatedentry["frontlineassignedtroops"] = movementmodule.getprovincefrontlinetroops(
                            province,
                            frontlineid,
                        )
            annotatedentries.append(annotatedentry)
        return annotatedentries

    def detachregimentfromdivision(provinceid):
        province = provincemap.get(provinceid)
        if not province:
            return False

        frontlineassignments = province.get("frontlineassignments")
        if not isinstance(frontlineassignments, dict):
            return False

        assignedfrontlineids = sorted(
            frontlineid
            for frontlineid, amount in frontlineassignments.items()
            if max(0, int(amount)) > 0
        )
        if not assignedfrontlineids:
            return False

        frontlineid = assignedfrontlineids[0]
        movementmodule.setprovincefrontlinetroops(province, frontlineid, 0)
        for movementorder in movementorderlist:
            if movementorder.get("frontlineid") != frontlineid:
                continue
            if movementorder.get("current") != provinceid:
                continue
            movementorder.pop("frontlineid", None)
            movementorder.pop("divisionid", None)

        assignment = getfrontlineassignment(frontlineid)
        if assignment is not None and getdivisiontroopcount(frontlineid) <= 0:
            assignment["active"] = False
            assignment["frontlineedgekeys"] = set()
            assignment["frontlineedges"] = []
        syncfrontlineoverlays()
        return True

    def syncfrontlineoverlays():
        nonlocal frontlineassignmentlist, activefrontlineedgekeyset
        frontlineassignmentlist = [
            assignment for assignment in frontlineassignmentlist
            if assignment.get("active", True)
        ]
        activefrontlineedgekeyset = set()
        for assignment in frontlineassignmentlist:
            activefrontlineedgekeyset.update(assignment.get("frontlineedgekeys", ()))

    def haspendingautoadvanceorder(frontlineid):
        if not frontlineid:
            return False
        for movementorder in movementorderlist:
            if movementorder.get("frontlineid") != frontlineid:
                continue
            if not movementorder.get("autoadvance"):
                continue
            if movementorder.get("ordercreatedturn") == currentturnnumber:
                return True
        return False

    def refreshfrontlines(allowautoadvance=True):
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
                frontlineid = assignment.get("frontlineid")
                if (
                    allowautoadvance
                    and assignment.get("autoadvance", False)
                    and not haspendingautoadvanceorder(frontlineid)
                ):
                    advanceresult = movementmodule.autoadvancefrontlineassignment(
                        assignment,
                        playableprovincemap,
                        movementorderlist,
                        emit=eventbus.emit,
                        currentturnnumber=currentturnnumber,
                        hostilecountryset=countriesatwarset,
                    )
                    routeupdateset.update(advanceresult.get("routepreviewset", ()))
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

    def handleprovincecontrolchanged(payload):
        if not isinstance(payload, dict):
            return

        provinceid = payload.get("provinceId")
        province = provincemap.get(provinceid)
        if not province:
            return

        owner = canonicalizecountry(getprovinceowner(province))
        previouscontroller = canonicalizecountry(payload.get("previousController"))
        newcontroller = canonicalizecountry(payload.get("newController"))
        if not owner or not previouscontroller or not newcontroller or previouscontroller == newcontroller:
            return

        if newcontroller == owner:
            occupationtransferlookup.pop(provinceid, None)
            return

        occupationtransferlookup[provinceid] = {
            "provinceid": provinceid,
            "owner": owner,
            "previous_controller": previouscontroller,
            "controller": newcontroller,
            "turn": currentturnnumber,
            "from_occupation": previouscontroller != owner,
        }

    def perfspawnwarsforsources(sourcecountries):
        createdpairs = []
        for rawsourcecountry in sourcecountries:
            sourcecountry = canonicalizecountry(rawsourcecountry)
            if not sourcecountry:
                continue

            targetcountryset = set()
            for provinceid, province in provincemap.items():
                if getprovincecontroller(province) != sourcecountry:
                    continue
                for neighborid in provincegraph.get(provinceid, ()):
                    neighborprovince = provincemap.get(neighborid)
                    if not neighborprovince:
                        continue
                    neighborcountry = canonicalizecountry(getprovincecontroller(neighborprovince))
                    if neighborcountry and neighborcountry != sourcecountry:
                        targetcountryset.add(neighborcountry)

            if not targetcountryset:
                targetcountryset = {
                    canonicalizecountry(province.get("country"))
                    for province in provincemap.values()
                    if province.get("country")
                }
                targetcountryset.discard(sourcecountry)

            for targetcountry in sorted(targetcountryset):
                normalizedpair = normalizewarpair(sourcecountry, targetcountry)
                if normalizedpair is None or normalizedpair in warpairset:
                    continue
                eventbus.emit(
                    EngineEventType.WARDECLARED,
                    {
                        "attacker": sourcecountry,
                        "defender": targetcountry,
                        "turn": currentturnnumber,
                        "source": "perfspawnwar",
                    },
                )
                createdpairs.append((sourcecountry, targetcountry))

        npcdirector.sync_player_wars(playercountry, countriesatwarset, warpairset=warpairset)
        print(
            "EBEE_PERF_SPAWNWAR "
            f"turn={currentturnnumber} sources={','.join(sourcecountries)} "
            f"created={len(createdpairs)} active_wars={len(warpairset)} "
            f"pairs={createdpairs[:12]}",
            flush=True,
        )
        return createdpairs

    eventbus.subscribe(EngineEventType.WARDECLARED, handlewardeclared)
    eventbus.subscribe("warended", handlewarended)
    eventbus.subscribe(EngineEventType.COMBATRESOLVED, handlecombatresolved)
    eventbus.subscribe(EngineEventType.PROVINCECONTROLCHANGED, handleprovincecontrolchanged)

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
            if resource == "stability":
                return playerstability
            if resource == "pp":
                return playerpp
            if resource == "political_power":
                return playerpp
            if resource == "ap":
                return playerap
            if resource == "action_points":
                return playerap

        economystate = npcdirector.countryeconomy.get(country)
        if economystate is not None:
            return economystate.get(resource)
        return None

    def scriptsetresource(country, resource, value):
        nonlocal playergold
        nonlocal playerpopulation
        nonlocal playerstability
        nonlocal playerpp
        nonlocal playerap

        value = max(0, int(value))
        if playercountry and country == playercountry:
            if resource == "gold":
                playergold = value
                return True
            if resource == "population":
                playerpopulation = value
                return True
            if resource in ("stability",):
                playerstability = max(0.0, min(100.0, float(value)))
                return True
            if resource in ("pp", "political_power"):
                playerpp = value
                return True
            if resource in ("ap", "action_points"):
                playerap = value
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
        nonlocal playerstability
        nonlocal playerpp
        nonlocal playerap
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
        if "playerstability" in commandstate:
            playerstability = max(0.0, min(100.0, float(commandstate.get("playerstability", playerstability))))
        if "playerpp" in commandstate:
            playerpp = max(0, int(commandstate.get("playerpp", playerpp)))
        if "playerap" in commandstate:
            playerap = max(0, int(commandstate.get("playerap", playerap)))
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

        if commandstate.get("mapdirty"):
            countrybordersdirty = True

        if playercountry and not playercountrychanged:
            npcdirector.sync_player_wars(playercountry, countriesatwarset, warpairset=warpairset)

    devconsole = developmentconsole(enabled=developmentmode)
    notifications = []
    _notif_id_counter = 0

    def emitmappulse(position, color=(212, 169, 77), radius=110, duration=0.75, width=2):
        if position is None:
            return
        cinematicpulseoverlay.emit(position, color, radius=radius, duration=duration, width=width)

    def pushnotification(title, description):
        nonlocal _notif_id_counter
        _notif_id_counter += 1
        notifications.append({
            "id": _notif_id_counter,
            "title": str(title),
            "description": str(description),
            "turn": currentturnnumber,
            "read": False,
        })
        emitmappulse((maprect.width * 0.5, maprect.height * 0.18), (212, 169, 77), radius=170, duration=0.9, width=3)
    eventbus.subscribe(EngineEventType.WARDECLARED, lambda p: pushnotification(
        "WAR DECLARED",
        f"{p.get('attacker', '?')} declared war on {p.get('defender', '?')}!"
    ))
    eventbus.subscribe("newspopup", lambda p: pushnotification(
        p.get("title", "NEWS UPDATE"),
        p.get("description", "No description."),
    ))
    eventbus.subscribe("countrycollapsed", lambda p: pushnotification(
        "COUNTRY COLLAPSED",
        p.get("description", f"{p.get('country', '?')} has collapsed."),
    ))
    scriptmanager = scriptengine.initscripts("scripts", autoload=True)
    # UI chrome + map viewport
    # runtime-owned font/caches (previously stored on EngineUI)
    troopbadgefont = pygame.font.SysFont("Arial", 16)
    countrylabelfont = pygame.font.SysFont("Arial", 18, bold=True)
    countrylabelcache = {}
    capitalmarkersurface = makecapitalmarkersurface()
    capitalflaglookup = loadcapitalflags()
    current_stats = {}
    selectedcapitalprovinceid = None
    dragselectstart = None
    dragselectcurrent = None
    isdragselecting = False
    dragminimumdistance = 8








    isrunning = True
    choosecountry_fit_state = {"done": False, "w": None, "h": None}
    choosecountry_intro_progress = 0.0
    while isrunning:
        if perfenabled:
            perf_frame_start = time.perf_counter()
            perf_section_start = perf_frame_start
            perf_sections_frame = {}
        else:
            perf_frame_start = 0.0
            perf_section_start = 0.0
            perf_sections_frame = {}
        elapsedseconds = clock.tick(60) / 1000.0
        ambientphasetimer += elapsedseconds
        camerashakeamount = max(0.0, camerashakeamount - elapsedseconds * 18.0)
        cinematicpulseoverlay.update(elapsedseconds)
        if gamephase == "choosecountry":
            choosecountry_intro_progress = min(1.0, choosecountry_intro_progress + elapsedseconds * 0.62)
        else:
            choosecountry_intro_progress = 1.0
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
        pointerovergameui = gamephase != "choosecountry" and runtimeui.ispointeroverui(mouseposition_full)
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

        if perfautocountry and gamephase == "choosecountry":
            playercountry = perfautocountry
            gamephase = "play"
            pendingcountry = None
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
            occupationtransferlookup.clear()
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
            perfautocountry = None
        if perfmonitoractive and gamephase == "play":
            if currentturnnumber < perfwarturn:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            elif currentturnnumber <= perfmonitorstopturn:
                if not perfwarspawned:
                    perfspawnwarsforsources(perfwarcountries)
                    perfwarspawned = True
                    countrybordersdirty = True
                perfidlecollecting = True
            else:
                isrunning = False
        elif perfautoturn and gamephase == "play" and currentturnnumber < perfautoturn:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        elif perfautoturn and perfidleframes and not perfidlecollecting and currentturnnumber >= perfautoturn:
            perfidlecollecting = True

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
        shakephase = ambientphasetimer * 42.0
        shakefalloff = camerashakeamount * camerashakeamount
        camerax = camerastate.x + math.sin(shakephase) * shakefalloff
        cameray = camerastate.y + math.cos(shakephase * 1.21) * shakefalloff * 0.72

        # draw the map inside the viewport subsurface
        map_w, map_h = screen.get_size()
        if sea_gradient_cache is None or sea_gradient_cache_size != (map_w, map_h):
            sea_gradient_cache_size = (map_w, map_h)
            top_color = (8, 24, 42)
            bottom_color = (2, 9, 22)
            strip = pygame.Surface((1, map_h))
            for y in range(map_h):
                t = y / max(1, map_h - 1)
                r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
                g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
                b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
                strip.set_at((0, y), (r, g, b))
            sea_gradient_cache = pygame.transform.scale(strip, (map_w, map_h))
        screen.blit(sea_gradient_cache, (0, 0))

        hovertext = None
        hoveredstateid = None
        hoveredprovinceid = None
        screenrectangle = screen.get_rect()
        troopbadgelist = [] # store troop badge info
        troopbadgehitlist = []
        capitalhitlist = []


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

        gridworldspacing = 64.0 / max(0.01, minimumzoomforframe)
        current_grid_key = (
            map_w,
            map_h,
            round(zoomvalue, 4),
            round(camerax, 2),
            round(cameray, 2),
            tuple(round(copyshift, 2) for copyshift in copyshiftlist),
            round(gridworldspacing, 4),
        )
        if grid_overlay_cache is None or grid_overlay_cache_key != current_grid_key:
            grid_overlay_cache_key = current_grid_key
            grid_overlay_cache = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
            for copyshift in copyshiftlist:
                drawcamerax = camerax + copyshift
                visibleworldleft = (0 - drawcamerax) / zoomvalue
                visibleworldright = (map_w - drawcamerax) / zoomvalue
                firstgridx = math.floor(visibleworldleft / gridworldspacing) * gridworldspacing
                gridx = firstgridx
                while gridx <= visibleworldright:
                    screenx = int(gridx * zoomvalue + drawcamerax)
                    gridindex = int(round(gridx / gridworldspacing))
                    color = (90, 128, 160, 38) if gridindex % 4 == 0 else (74, 143, 231, 24)
                    pygame.draw.line(grid_overlay_cache, color, (screenx, 0), (screenx, map_h), 1)
                    gridx += gridworldspacing

            visibleworldtop = (0 - cameray) / zoomvalue
            visibleworldbottom = (map_h - cameray) / zoomvalue
            firstgridy = math.floor(visibleworldtop / gridworldspacing) * gridworldspacing
            gridy = firstgridy
            while gridy <= visibleworldbottom:
                screeny = int(gridy * zoomvalue + cameray)
                gridindex = int(round(gridy / gridworldspacing))
                color = (90, 128, 160, 38) if gridindex % 4 == 0 else (74, 143, 231, 24)
                pygame.draw.line(grid_overlay_cache, color, (0, screeny), (map_w, screeny), 1)
                gridy += gridworldspacing
        screen.blit(grid_overlay_cache, (0, 0))
        if perfidlecollecting:
            now = time.perf_counter()
            perf_sections_frame["background_grid"] = (now - perf_section_start) * 1000.0
            perf_section_start = now

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

        if countrybordersdirty:
            staterenderlookupdirty = True
        currentstaterenderkey = (expandedstateid, gamephase)
        if staterenderlookupdirty or staterenderlookupcachekey != currentstaterenderkey:
            staterenderlookupcache = buildstaterenderlookup(
                playablestateshapelist,
                expandedstateid,
                gamephase,
                defaultshapecolor,
            )
            staterenderlookupcachekey = currentstaterenderkey
            staterenderlookupdirty = False
        staterenderlookup = staterenderlookupcache
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
                        polygonrectanglescreen, polygonpointsscreen, polygonpointsscreenint = getcachedscreenpolygon(
                            polygon,
                            zoomvalue,
                            drawcamerax,
                            cameray,
                        )
                        if not polygonrectanglescreen.colliderect(screenrectangle):
                            continue



                        if len(polygonpointsscreenint) < 3:
                            continue
                        drawpolygonlist.append(polygonpointsscreenint)



                        if (
                            not pointerovergameui
                            and not itemhovered
                            and polygonrectanglescreen.collidepoint(mouseposition)
                            and ispointinsidepolygon(mouseposition, polygonpointsscreen)
                        ):
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
                        basefillcolor = mix_color(
                            (232, 214, 103),
                            (255, 241, 166),
                            0.38 * pulse(ambientphasetimer, 3.4, itemrectanglescreen.centerx * 0.01),
                        )


                    elif drawitem.get("id") in routepreviewset:
                        basefillcolor = mix_color(
                            (95, 145, 255),
                            (160, 210, 255),
                            0.45 * pulse(ambientphasetimer, 4.6, itemrectanglescreen.centery * 0.014),
                        )


                    # ESO optimization 22/04
                    # O(d*m) --> O(d+m)
                    # use set membership instead of scanning movement orders for each draw item
                    
                    
                    elif drawitem.get("id") in movingprovinceidset:
                        basefillcolor = mix_color(
                            (132, 96, 226),
                            (198, 165, 255),
                            0.42 * pulse(ambientphasetimer, 5.0, itemrectanglescreen.centerx * 0.018),
                        )



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

                    if (
                        gamephase == "play"
                        and drawitem.get("id") not in selectedprovinceidset
                        and drawitem.get("id") not in routepreviewset
                        and drawitem.get("id") not in movingprovinceidset
                    ):
                        basefillcolor = tacticalmapfill(basefillcolor)

                    finalfillcolor = mix_color(hovercolor, (255, 226, 138), 0.25 * pulse(ambientphasetimer, 6.0)) if itemhovered else basefillcolor
                    for drawpolygon in drawpolygonlist:
                        pygame.draw.polygon(screen, finalfillcolor, drawpolygon)
                        pygame.draw.polygon(screen, (18, 27, 34), drawpolygon, 1)
        if perfidlecollecting:
            now = time.perf_counter()
            perf_sections_frame["map_polygons"] = (now - perf_section_start) * 1000.0
            perf_section_start = now

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

                   badgebackground = (10, 14, 20)
                   badgeborder = (132, 145, 160)

                   if iscombatprovince:
                       badgebackground = (16, 16, 22)
                       badgeborder = (224, 93, 93)
                   elif ismovingprovince:
                       badgebackground = (16, 18, 24)
                       badgeborder = (212, 169, 77)

                   isentrenchedprovince = movementmodule.isprovinceentrenched(province, currentturnnumber)
                   troopbadgelist_raw.append({
                       "center": provincerectanglescreen.center,
                       "troops": province["troops"],
                       "country": getprovincecontroller(province),
                       "backgroundcolor": badgebackground,
                       "bordercolor": badgeborder,
                       "entrenched": isentrenchedprovince,
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
           
        if perfidlecollecting:
            now = time.perf_counter()
            perf_sections_frame["troop_badges"] = (now - perf_section_start) * 1000.0
            perf_section_start = now

        if gamephase == "play" and movementorderlist:
            current_movement_path_key = (
                map_w,
                map_h,
                round(zoomvalue, 4),
                round(camerax, 2),
                round(cameray, 2),
                tuple(round(copyshift, 2) for copyshift in copyshiftlist),
                tuple(
                    (
                        id(order.get("path")),
                        int(order.get("index", 0)),
                        order.get("current"),
                        int(order.get("amount", 0)),
                        order.get("_resumeonturn"),
                        tuple(order.get("countrycolor") or ()),
                    )
                    for order in movementorderlist
                ),
            )
            if movement_path_overlay_cache is None or movement_path_overlay_cache_key != current_movement_path_key:
                movement_path_overlay_cache_key = current_movement_path_key
                movement_path_overlay_cache = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
                gui_drawmovementorderpaths(
                    movement_path_overlay_cache,
                    movementorderlist,
                    provincemap,
                    zoomvalue,
                    camerax,
                    cameray,
                    copyshiftlist,
                    screenrectangle,
                )
            screen.blit(movement_path_overlay_cache, (0, 0))
        else:
            movement_path_overlay_cache = None
            movement_path_overlay_cache_key = None
        if perfidlecollecting:
            now = time.perf_counter()
            perf_sections_frame["movement_paths"] = (now - perf_section_start) * 1000.0
            perf_section_start = now

        if countrybordersdirty:
            countryborderentrylist = esomodule.buildcountryborderentries(
                playableprovincemap,
                provinceedgepairlist,
                countrybordersegmentcache,
            )
            countrybordersdirty = False
            frontlineborderedgesdirty = True

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
        if perfidlecollecting:
            now = time.perf_counter()
            perf_sections_frame["borders_labels_capitals"] = (now - perf_section_start) * 1000.0
            perf_section_start = now

        if gamephase == "play":
            capitalhitlist = drawcapitalmarkers(
                screen,
                playableprovincemap,
                zoomvalue,
                camerax,
                cameray,
                copyshiftlist,
                screenrectangle,
                capitalmarkersurface,
            )
            if selectedcapitalprovinceid in CAPITAL_PROVINCES:
                drawcapitalinfopopup(
                    screen,
                    selectedcapitalprovinceid,
                    playableprovincemap,
                    zoomvalue,
                    camerax,
                    cameray,
                    normalfont,
                    smallfont,
                    capitalflaglookup,
                )

        frontlineborderedgelist = []
        frontlineedgebykey = {}
        hoveredfrontlineedgekey = None
        if gamephase == "play" and playercountry and (frontlineplacementmode or activefrontlineedgekeyset):
            if frontlineborderedgesdirty:
                frontlineborderedgelistcache = getcountryborderedges(
                    playableprovincemap,
                    playableprovincegraph,
                    playercountry,
                )
                frontlineborderedgesdirty = False
            frontlineborderedgelist = frontlineborderedgelistcache
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
                    activepulse = pulse(ambientphasetimer, 5.5, segmentstart[0] * 0.02)
                    bordercolor = (255, 236, 145) if ishoveredborder else mix_color((235, 205, 92), (255, 244, 169), activepulse * 0.35)
                    borderwidth = 4 if ishoveredborder else (2 + int(activepulse > 0.78))
                    pygame.draw.line(screen, bordercolor, segmentstart, segmentend, borderwidth)

                if isactivefrontline:
                    frontpulse = pulse(ambientphasetimer, 4.8, segmentstart[1] * 0.017)
                    pygame.draw.line(screen, mix_color((185, 24, 24), (255, 72, 72), frontpulse * 0.24), segmentstart, segmentend, 8)
                    pygame.draw.line(screen, mix_color((220, 42, 42), (255, 110, 110), frontpulse * 0.28), segmentstart, segmentend, 5)
                    pygame.draw.line(screen, (255, 126, 126) if frontpulse > 0.78 else (255, 96, 96), segmentstart, segmentend, 2)

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
        if perfidlecollecting:
            now = time.perf_counter()
            perf_sections_frame["frontline_overlay"] = (now - perf_section_start) * 1000.0
            perf_section_start = now
        cinematicpulseoverlay.draw(screen)

        selectedtroopentries = getselectedtroopentries(
            selectedprovinceidset,
            selectedprovinceid,
            provincemap,
            playercountry,
        )
        selectedtroopentries = annotateselectedtroopentries(selectedtroopentries)

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
        if gamephase == "play" and warpairset and (runtimeui.warprogressopen or runtimeui.active_left_tab == "COMBAT"):
            warprogressdata = buildwarprogressdata()

            
                
        current_stats = {}
        if runtimeui._selectedmapcountry:
            selected_country = runtimeui._selectedmapcountry
            
            total_manpower = 0
            for prov in provincemap.values():
                if prov.get("country") == selected_country:
                    total_manpower += int(prov.get("troops", 0))

            base_stats = country_stats_lookup.get(selected_country, {})
            if playercountry and selected_country == playercountry:
                stability = playerstability
                population = playerpopulation
            else:
                npc_economy = getattr(npcdirector, "countryeconomy", {}).get(selected_country, {})
                stability = npc_economy.get("stability", base_stats.get("stability", 50.0))
                population = npc_economy.get("population", base_stats.get("population", 0))
            
            current_stats = {
                "population": population,
                "manpower": total_manpower,
                "stability": stability,
                "leader": base_stats.get("leader", "Unknown"),
            }
        if perfidlecollecting:
            now = time.perf_counter()
            perf_sections_frame["ui_state_prep"] = (now - perf_section_start) * 1000.0
            perf_section_start = now
        
        runtimeui.sync(
            gamephase,
            pendingcountry,
            playercountry,
            currentturnnumber,
            playergold,
            playerpopulation,
            playerstability,
            playerpp,
            playerap,
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
            researchdata={
                "researched": frozenset(researched_set),
                "researching_id": researching_node_id,
                "researching_turns_remaining": researching_turns_remaining,
            },
            warprogressdata=warprogressdata,
            selected_country_stats=current_stats,
            systemstatus={
                "fps": clock.get_fps(),
                "latency_ms": elapsedseconds * 1000.0,
            },
            notifications=notifications,
        )
        runtimeui.update(elapsedseconds)
        runtimeui.draw(screen)
        scriptengine.draw_script_ui(screen)
        if perfidlecollecting:
            now = time.perf_counter()
            perf_sections_frame["runtime_ui_draw"] = (now - perf_section_start) * 1000.0
            perf_section_start = now





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

        if perfidlecollecting:
            now = time.perf_counter()
            perf_sections_frame["overlays_console"] = (now - perf_section_start) * 1000.0
            if perfmonitoractive:
                if perfmonitoridleturn != currentturnnumber:
                    perfmonitoridleturn = currentturnnumber
                    perfidleframetimes = []
                    perfsectiontotals = {}
                perfidleframetimes.append((now - perf_frame_start) * 1000.0)
                for sectionname, sectionms in perf_sections_frame.items():
                    perfsectiontotals[sectionname] = perfsectiontotals.get(sectionname, 0.0) + sectionms
                if len(perfidleframetimes) >= perfidleframes:
                    ordered = sorted(perfidleframetimes)
                    avg = sum(perfidleframetimes) / len(perfidleframetimes)
                    p95 = ordered[int(len(ordered) * 0.95) - 1]
                    print(
                        "EBEE_PERF_TURN_IDLE "
                        f"turn={currentturnnumber} frames={len(perfidleframetimes)} "
                        f"avg_ms={avg:.3f} p95_ms={p95:.3f} "
                        f"fps_est={1000.0 / max(0.001, avg):.1f} "
                        f"orders={len(movementorderlist)} active_wars={len(warpairset)}",
                        flush=True,
                    )
                    for sectionname, totalms in sorted(perfsectiontotals.items(), key=lambda item: item[1], reverse=True):
                        print(
                            f"EBEE_PERF_TURN_SECTION turn={currentturnnumber} "
                            f"{sectionname} avg_ms={totalms / len(perfidleframetimes):.3f}",
                            flush=True,
                        )
                    perfidlecollecting = False
                    if currentturnnumber < perfmonitorstopturn:
                        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
                    else:
                        isrunning = False
            else:
                perfidleframetimes.append((now - perf_frame_start) * 1000.0)
                for sectionname, sectionms in perf_sections_frame.items():
                    perfsectiontotals[sectionname] = perfsectiontotals.get(sectionname, 0.0) + sectionms
                if len(perfidleframetimes) >= perfidleframes:
                    ordered = sorted(perfidleframetimes)
                    avg = sum(perfidleframetimes) / len(perfidleframetimes)
                    p95 = ordered[int(len(ordered) * 0.95) - 1]
                    print(
                        "EBEE_PERF_IDLE "
                        f"turn={currentturnnumber} frames={len(perfidleframetimes)} "
                        f"avg_ms={avg:.3f} p95_ms={p95:.3f} "
                        f"fps_est={1000.0 / max(0.001, avg):.1f} "
                        f"orders={len(movementorderlist)}",
                        flush=True,
                    )
                    for sectionname, totalms in sorted(perfsectiontotals.items(), key=lambda item: item[1], reverse=True):
                        print(f"EBEE_PERF_SECTION {sectionname} avg_ms={totalms / len(perfidleframetimes):.3f}", flush=True)
                    isrunning = False





        for event in pygame.event.get():
            if scriptengine.handle_script_ui_event(event):
                continue

            uiaction = runtimeui.process_event(event)
            if uiaction == InGameUI.actionquitgame:
                isrunning = False
                continue

            if uiaction == InGameUI.actionpausemenu:
                continue

            if uiaction == "warprogress":
                continue

            if uiaction == "notification_scroll":
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
                    occupationtransferlookup.clear()
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
                    camerashakeamount = max(camerashakeamount, 1.15)
                    emitmappulse(mouseposition, (212, 169, 77), radius=220, duration=1.0, width=3)
                continue

            if uiaction == "declarewar" and gamephase == "play":
                targetcountry = countrymenutarget or runtimeui._selectedmapcountry
                if targetcountry and targetcountry != playercountry and targetcountry not in countriesatwarset:
                    declarewarcost = economyconfig.get("declarewarcost", 75)
                    if not developmentmode and playerpp < declarewarcost:
                        runtimeui._hovertext = {"text": f"Not enough PP ({playerpp}/{declarewarcost})"}
                    else:
                        if not developmentmode:
                            playerpp -= declarewarcost
                        eventbus.emit(
                            EngineEventType.WARDECLARED,
                            {
                                "attacker": playercountry,
                                "defender": targetcountry,
                                "turn": currentturnnumber,
                            },
                        )
                        camerashakeamount = max(camerashakeamount, 1.75)
                        emitmappulse((maprect.width * 0.5, maprect.height * 0.5), (224, 93, 93), radius=260, duration=1.05, width=4)
                runtimeui.select_map_country(None)
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
                            recruitrect = getscreenrectangle(selectedprovince["rectangle"], zoomvalue, camerax, cameray)
                            emitmappulse(recruitrect.center, (67, 181, 129), radius=120, duration=0.75, width=3)
                            camerashakeamount = max(camerashakeamount, 0.75)
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


            if (
                isinstance(uiaction, tuple)
                and len(uiaction) == 2
                and uiaction[0] == "research_node"
                and gamephase == "play"
            ):
                node_id = uiaction[1]
                if node_id not in researched_set and node_id in _research_cost_lookup:
                    researching_node_id = node_id
                    researching_turns_remaining = max(1, _research_cost_lookup[node_id] // RESEARCH_RP_PER_TURN)
                continue




            # for quick search: "end turn button"
            # ON END TURN, process movement orders, apply economy, increment turn, emit next turn event
            if uiaction == InGameUI.actionendturn and gamephase == "play":
                frontlineupdates = refreshfrontlines(allowautoadvance=True)
                processmovementorders(
                    movementorderlist,
                    provincemap,
                    emit=eventbus.emit,
                    currentturnnumber=currentturnnumber,
                    provincegraph=provincegraph,
                    countrycapitalprovinceidlookup=countrycapitalprovinceidlookup,
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
                playergold, playerpopulation, playerstability, playerpp, playerap = applyendturneconomy(
                    playercountry,
                    provincemap,
                    playergold,
                    playerpopulation,
                    playerstability,
                    playerpp,
                    playerap,
                )
                npcdirector.sync_player_wars(playercountry, countriesatwarset, warpairset=warpairset)
                npcdirector.executeturn(
                    movementorderlist,
                    currentturnnumber,
                )
                checkcapitulations()
                playerstability, _ = applycapitalstabilitypenalties(
                    provincemap,
                    playercountry,
                    playerstability,
                    npcdirector.countryeconomy,
                )
                if researching_node_id and researching_turns_remaining > 0:
                    researching_turns_remaining -= 1
                    if researching_turns_remaining <= 0:
                        researched_set.add(researching_node_id)
                        eventbus.emit("research_completed", {
                            "country": playercountry,
                            "node_id": researching_node_id,
                            "turn": currentturnnumber,
                        })
                        researching_node_id = None
                frontlineupdates.update(refreshfrontlines(allowautoadvance=False))
                currentturnnumber += 1
                
                if currentturnnumber in COVID_NEWS_EVENTS:
                    news = COVID_NEWS_EVENTS[currentturnnumber]

                    pushnotification(
                        news["title"],
                        news["description"],
                    )
                
                if currentturnnumber == 2 and playercountry.lower() == "malaysia":
                    mahathir_speech.play()
                                      
                routepreviewset = frontlineupdates
                updatescriptengine()
                eventbus.emit(
                    EngineEventType.NEXTTURN,
                    {
                        "turn": currentturnnumber,
                        "playerCountry": playercountry,
                        "playerGold": playergold,
                        "playerPopulation": playerpopulation,
                        "playerStability": playerstability,
                        "playerPP": playerpp,
                        "playerAP": playerap,
                    },
                )
                emitmappulse((maprect.width * 0.5, maprect.height * 0.5), (67, 181, 129), radius=240, duration=0.92, width=3)
                camerashakeamount = max(camerashakeamount, 1.0)
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
                    emitmappulse(mouseposition, (74, 143, 231), radius=110, duration=0.65, width=2)
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
                    emitmappulse(mouseposition, (212, 169, 77), radius=120, duration=0.7, width=2)
                continue

            if uiaction == "frontline" and gamephase == "play":
                hastroopsselected = any(int(entry.get("troops", 0)) > 0 for entry in selectedtroopentries)
                frontlineplacementmode = bool(hastroopsselected) and not frontlineplacementmode
                routepreviewset = set()
                countrymenutarget = None
                emitmappulse(mouseposition, (235, 205, 92), radius=140, duration=0.75, width=2)
                continue

            if (
                isinstance(uiaction, tuple)
                and len(uiaction) == 2
                and uiaction[0] == InGameUI.actionautoadvance
                and gamephase == "play"
            ):
                assignment = getfrontlineassignment(uiaction[1])
                if assignment is not None:
                    assignment["autoadvance"] = not bool(assignment.get("autoadvance", False))
                    if assignment["autoadvance"]:
                        routepreviewset = refreshfrontlines(allowautoadvance=True)
                    else:
                        routepreviewset = set()
                    emitmappulse(mouseposition, (224, 93, 93), radius=130, duration=0.7, width=2)
                continue

            if (
                isinstance(uiaction, tuple)
                and len(uiaction) == 2
                and uiaction[0] == InGameUI.actiondetachregiment
                and gamephase == "play"
            ):
                if detachregimentfromdivision(uiaction[1]):
                    routepreviewset = set()
                    frontlineplacementmode = False
                    emitmappulse(mouseposition, (224, 93, 93), radius=90, duration=0.55, width=2)
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
                            emitmappulse(eventmappos, (212, 169, 77), radius=150, duration=0.72, width=2)

                    continue

                elif gamephase == "play":
                    runtimeui.select_map_country(None)
                    current_stats = {}
                    selectedcapitalprovinceid = None

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
                            frontlineresult["divisionid"] = frontlineresult["frontlineid"]
                            frontlineresult["divisionname"] = getdivisiondisplayname()
                            frontlineresult["autoadvance"] = False
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
                            emitmappulse(eventmappos, (224, 93, 93), radius=180, duration=0.9, width=3)
                            camerashakeamount = max(camerashakeamount, 1.05)
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
                    clickedcapitalprovinceid = getcapitalhitprovinceid(eventmappos, capitalhitlist)
                    if clickedcapitalprovinceid:
                        select_sound.play()
                        selectedcapitalprovinceid = clickedcapitalprovinceid
                        selectedprovinceid = clickedcapitalprovinceid
                        selectedprovinceidset = {clickedcapitalprovinceid}
                        selectedprovince = provincemap.get(clickedcapitalprovinceid)
                        expandedstateid = selectedprovince.get("parentid", hoveredstateid) if selectedprovince else hoveredstateid
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
                            emitmappulse(eventmappos, (212, 169, 77), radius=140, duration=0.72, width=2)
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
                            emitmappulse(selectionrect.center, (74, 143, 231), radius=max(90, max(selectionrect.width, selectionrect.height)), duration=0.72, width=2)
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
                    select_sound.play()
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
                        emitmappulse(eventmappos, (212, 169, 77), radius=105, duration=0.62, width=2)
                        dragselectstart = None
                        dragselectcurrent = None
                        continue

                if hoveredprovinceid:
                    select_sound.play()
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
                        emitmappulse(eventmappos, (212, 169, 77), radius=105, duration=0.62, width=2)
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
                        emitmappulse(eventmappos, (212, 169, 77), radius=110, duration=0.62, width=2)

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


                if hoveredstateid is not None and hoveredprovinceid is None:
                    selectedstateobject = stateobjectlookup.get(hoveredstateid)
                    if selectedstateobject:
                        destinationcountry = selectedstateobject.get("controllercountry", selectedstateobject.get("country"))
                        if destinationcountry:
                            runtimeui.select_map_country(destinationcountry)
                            countrymenutarget = None
                            emitmappulse(eventmappos, (74, 143, 231), radius=120, duration=0.65, width=2)
                            continue

                if hoveredstateid is None and hoveredprovinceid is None:
                    runtimeui.select_map_country(None)
                    countrymenutarget = None

                # Only open the country interaction menu when the click is on a state (no hovered province).
                if hoveredprovinceid is None:
                    if hoveredstateid is not None:
                        selectedstateobject = stateobjectlookup.get(hoveredstateid)
                        if selectedstateobject:
                            destinationcountry = selectedstateobject.get("controllercountry", selectedstateobject.get("country"))
                            if playercountry and destinationcountry and destinationcountry != playercountry:
                                countrymenutarget = destinationcountry
                                routepreviewset = set()
                                emitmappulse(eventmappos, (212, 169, 77), radius=140, duration=0.7, width=2)
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
                        emitmappulse(eventmappos, (212, 169, 77), radius=140, duration=0.7, width=2)
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
                
                if sourceprovinceidlist:
                    move_sound.play()
                    
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

                    moveorderapcost = economyconfig.get("moveorderapcost", 10)
                    if not developmentmode:
                        playerap = max(0, playerap - moveorderapcost)
                        
                    move_sound.play()
                    
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
                    emitmappulse(eventmappos, (124, 196, 255), radius=135, duration=0.78, width=3)
                    camerashakeamount = max(camerashakeamount, 0.55)


            elif event.type == pygame.MOUSEWHEEL:
                if devconsole.visible:
                    continue
                if runtimeui.focusview.isopen or runtimeui.researchview.isopen:
                    continue

                
                mousex, mousey = pygame.mouse.get_pos()
                cameramodule.applywheelzoom(camerastate, event.y, windowheight, mapbox, mousex, mousey)
                

            elif event.type == pygame.KEYDOWN:
                # Space = next turn (only in play phase, and not while dev console is capturing input)
                if event.key == pygame.K_SPACE and gamephase == "play" and not devconsole.visible:
                    perfturnstart = time.perf_counter() if perfmonitoractive and currentturnnumber >= perfwarturn else None
                    perfturnfrom = currentturnnumber
                    frontlineupdates = refreshfrontlines(allowautoadvance=True)
                    processmovementorders(
                        movementorderlist,
                        provincemap,
                        emit=eventbus.emit,
                        currentturnnumber=currentturnnumber,
                        provincegraph=provincegraph,
                        countrycapitalprovinceidlookup=countrycapitalprovinceidlookup,
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
                    playergold, playerpopulation, playerstability, playerpp, playerap = applyendturneconomy(
                        playercountry,
                        provincemap,
                        playergold,
                        playerpopulation,
                        playerstability,
                        playerpp,
                        playerap,
                    )
                    npcdirector.sync_player_wars(playercountry, countriesatwarset, warpairset=warpairset)
                    npcdirector.executeturn(
                        movementorderlist,
                        currentturnnumber,
                    )
                    checkcapitulations()
                    playerstability, _ = applycapitalstabilitypenalties(
                        provincemap,
                        playercountry,
                        playerstability,
                        npcdirector.countryeconomy,
                    )
                    if researching_node_id and researching_turns_remaining > 0:
                        researching_turns_remaining -= 1
                        if researching_turns_remaining <= 0:
                            researched_set.add(researching_node_id)
                            eventbus.emit("research_completed", {
                                "country": playercountry,
                                "node_id": researching_node_id,
                                "turn": currentturnnumber,
                            })
                            researching_node_id = None
                    frontlineupdates.update(refreshfrontlines(allowautoadvance=False))
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
                            "playerStability": playerstability,
                            "playerPP": playerpp,
                            "playerAP": playerap,
                        },
                    )
                    emitmappulse((maprect.width * 0.5, maprect.height * 0.5), (67, 181, 129), radius=240, duration=0.92, width=3)
                    camerashakeamount = max(camerashakeamount, 1.0)
                    if perfturnstart is not None:
                        print(
                            "EBEE_PERF_TURN_ADVANCE "
                            f"from={perfturnfrom} to={currentturnnumber} "
                            f"ms={(time.perf_counter() - perfturnstart) * 1000.0:.3f} "
                            f"orders={len(movementorderlist)} active_wars={len(warpairset)}",
                            flush=True,
                        )
                    continue


            # (for quick ctrl f: developer console)
                commandcontext = {
                    "playercountry": playercountry,
                    "playergold": playergold,
                    "playerpopulation": playerpopulation,
                    "playerstability": playerstability,
                    "playerpp": playerpp,
                    "playerap": playerap,
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
                sea_gradient_cache = None
                sea_gradient_cache_size = None
                map_vignette_cache = None
                map_vignette_cache_size = None
                continue



        if gamephase == "choosecountry" and choosecountry_intro_progress < 1.0:
            intro = ease_out_cubic(choosecountry_intro_progress)
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(238 * (1.0 - intro))))
            screen.blit(overlay, (0, 0))
            radius = int(80 + intro * max(screen.get_size()) * 0.45)
            pulse_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            pygame.draw.circle(
                pulse_surface,
                (212, 169, 77, int(96 * (1.0 - intro))),
                (screen.get_width() // 2, screen.get_height() // 2),
                radius,
                2,
            )
            screen.blit(pulse_surface, (0, 0))

        pygame.display.flip()

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

