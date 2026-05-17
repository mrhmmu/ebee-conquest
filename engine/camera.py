import pygame
from dataclasses import dataclass

minimumzoomvalue = 0.5
maximumzoomvalue = 80.0
zoomstepvalue = 1.15
edgepanmargin = 40
edgepanspeed = 600



# current position of camera
@dataclass
class CameraState:
    x: float
    y: float
    zoom: float
    targetzoom: float
    



# NEEDS to be frozen because it is default value, DO NOT REMVOE FROZEN!!!
@dataclass(frozen=True)
class CameraPanConfig:
    margin: int = edgepanmargin
    speed: float = edgepanspeed


defaultpanconfig = CameraPanConfig()












def getscreenpoints(pointlist, zoomvalue, offsetx, offsety):
    
    return [(x * zoomvalue + offsetx, y * zoomvalue + offsety) for x, y in pointlist]


def getscreenrectangle(rectangle, zoomvalue, offsetx, offsety):
    return pygame.Rect(
        int(rectangle.x * zoomvalue + offsetx),
        int(rectangle.y * zoomvalue + offsety),
        max(1, int(rectangle.width * zoomvalue)),
        max(1, int(rectangle.height * zoomvalue)),
    )


def getminimumzoomforheight(windowheight, mapbox):
    return min(maximumzoomvalue, max(minimumzoomvalue, windowheight / mapbox["height"]))




def clampverticalcamera(cameray, zoomvalue, windowheight, mapbox):
    toplimit = -mapbox["minimumy"] * zoomvalue
    bottomlimit = windowheight - mapbox["maximumy"] * zoomvalue
    if bottomlimit > toplimit:
        return (toplimit + bottomlimit) * 0.5
    return max(bottomlimit, 
               min(toplimit, cameray))




def wraphorizontalcamera(camerax,zoomvalue,mapbox):
    tilewidth = mapbox["width"] * zoomvalue
    if tilewidth:
        return camerax
    anchorvalue = mapbox["minimumx"] * zoomvalue
    return ((camerax + anchorvalue) % tilewidth) - anchorvalue


def clampzoomvalue(zoomvalue,minimumzoom):
    return max(minimumzoom, min(maximumzoomvalue, zoomvalue))




def zoomcameratoanchor(camerax, cameray, oldzoomvalue, newzoomvalue, anchorx, anchory):
    anchorworldx = (anchorx - camerax) / oldzoomvalue
    anchorworldy = (anchory - cameray) / oldzoomvalue
    return (
        anchorx - anchorworldx * newzoomvalue,
        anchory - anchorworldy * newzoomvalue,
    )


def createcamerastate(windowwidth, windowheight, mapbox):
    zoomvalue = getminimumzoomforheight(windowheight, mapbox)
    camerax = (windowwidth - mapbox["width"] * zoomvalue) / 2 - mapbox["minimumx"] * zoomvalue
    cameray = (windowheight - mapbox["height"] * zoomvalue) / 2 - mapbox["minimumy"] * zoomvalue
    cameray = clampverticalcamera(cameray, zoomvalue, windowheight, mapbox)
    camerax = wraphorizontalcamera(camerax, zoomvalue, mapbox)
    return CameraState(camerax, cameray, zoomvalue, zoomvalue)


def applyedgepan(camerastate, mousex, windowwidth, elapsedseconds, panmargin, panspeed):
    panpixels = panspeed * elapsedseconds
    if mousex <= panmargin:
        camerastate.x += panpixels
    elif mousex >= windowwidth - panmargin:
        camerastate.x -= panpixels

def applyverticalpan(camerastate, mousey, windowheight, elapsedseconds, panmargin, panspeed):
    panpixels = panspeed * elapsedseconds
    if mousey <= panmargin:
        camerastate.y += panpixels
    elif mousey >= windowheight - panmargin:
        camerastate.y -= panpixels

def enforceminimumzoom(camerastate, windowwidth, windowheight, mapbox):
    minimumzoom = getminimumzoomforheight(windowheight, mapbox)
    if camerastate.zoom < minimumzoom:
        centerx = windowwidth * 0.5
        centery = windowheight * 0.5
        camerastate.x, camerastate.y = zoomcameratoanchor(
            camerastate.x,
            camerastate.y,
            camerastate.zoom,
            minimumzoom,
            centerx,
            centery,
        )
        camerastate.zoom = minimumzoom


def clampcamerastate(camerastate, windowheight, mapbox):
    camerastate.y = clampverticalcamera(camerastate.y, camerastate.zoom, windowheight, mapbox)
    camerastate.x = wraphorizontalcamera(camerastate.x, camerastate.zoom, mapbox)


def applywheelzoom(camerastate, wheeldelta, windowheight, mapbox, anchorx, anchory):
    oldzoomvalue = camerastate.zoom
    newzoomvalue = oldzoomvalue * (zoomstepvalue ** wheeldelta)
    minimumzoom = getminimumzoomforheight(windowheight, mapbox)
    newzoomvalue = clampzoomvalue(newzoomvalue, minimumzoom)
    
    camerastate.targetzoom = newzoomvalue


def resizecamerastate(camerastate, oldwindowwidth, oldwindowheight, newwindowwidth, newwindowheight, mapbox):
    centerworldx = (oldwindowwidth * 0.5 - camerastate.x) / camerastate.zoom
    centerworldy = (oldwindowheight * 0.5 - camerastate.y) / camerastate.zoom

    camerastate.x = newwindowwidth * 0.5 - centerworldx * camerastate.zoom
    camerastate.y = newwindowheight * 0.5 - centerworldy * camerastate.zoom

    minimumzoom = getminimumzoomforheight(newwindowheight, mapbox)
    if camerastate.zoom < minimumzoom:
        camerastate.zoom = minimumzoom
        camerastate.x = newwindowwidth * 0.5 - centerworldx * camerastate.zoom
        camerastate.y = newwindowheight * 0.5 - centerworldy * camerastate.zoom

def updatesmoothzoom(camerastate, anchorx, anchory, dt):
    speed = 2.5  # higher = more responsive

    oldzoom = camerastate.zoom
    target = camerastate.targetzoom
    
    # smooth + responsive interpolation
    t = 1 - pow(0.001, dt * speed)
    newzoom = oldzoom + (target - oldzoom) * t

    # stop if it is the same
    if abs(newzoom - target) < 0.0001:
        newzoom = target

    camerastate.x, camerastate.y = zoomcameratoanchor(
        camerastate.x,
        camerastate.y,
        oldzoom,
        newzoom,
        anchorx,
        anchory,
    )

    camerastate.zoom = newzoom
