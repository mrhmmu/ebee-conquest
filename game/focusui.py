import os

import pygame


class FocusTreeView:
    headerheight = 150

    def __init__(self):
        self.data = {"name": "National Policy", "focuses": []}
        self.isopen = False
        self.detailid = None
        self.noderects: dict[str, pygame.Rect] = {} # focusid to screen rect
        self.closerect = pygame.Rect(0, 0, 1, 1) # close button rect
        self.startrect = pygame.Rect(0, 0, 1, 1)
        self.detailrect = pygame.Rect(0, 0, 1, 1)
        self.worldrects: dict[str, pygame.Rect] = {} # focusid to world rect
        self.iconcache = {}
        self.imagecache = {}
        self.rootpath = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
        self.zoom = 0.85
        self.minzoom = 0.45
        self.maxzoom = 1.75
        self.panx = 0.0
        self.pany = 0.0
        self.dragging = False
        self.dragbutton = None
        self.dragstart = (0, 0)
        self.panstart = (0.0, 0.0)
        self.layoutready = False
        self.datakey = None
        self.viewsize = None

    def setdata(self, data):
        self.data = data or {"name": "National Policy", "focuses": []} # check for key
        newkey = self.makekey() # make a key based on the focuses data, so we can detect changes and reset layout if needed
        if newkey != self.datakey:
            self.datakey = newkey
            self.layoutready = False
            self.detailid = None
        if self.detailid and self.findfocus(self.detailid) is None:
            self.detailid = None



    def openview(self):
        self.isopen = True

    def closeview(self):
        self.isopen = False
        self.detailid = None

    def toggleview(self):
        if self.isopen:
            self.closeview()
        else:
            self.openview()

    def handleevent(self, event): # EVENT HANDLER
        if not self.isopen:
            return None

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.closeview()
            return None

        if event.type == pygame.MOUSEWHEEL:
            self.zoomat(pygame.mouse.get_pos(), event.y)
            return None

        if event.type == pygame.MOUSEMOTION and self.dragging:
            position = event.pos
            self.panx = self.panstart[0] + position[0] - self.dragstart[0]
            self.pany = self.panstart[1] + position[1] - self.dragstart[1]
            return None

        if event.type == pygame.MOUSEBUTTONUP and self.dragging:
            if event.button == self.dragbutton:
                self.dragging = False
                self.dragbutton = None
            return None

        if event.type == pygame.MOUSEBUTTONDOWN:
            position = event.pos
            if event.button in (2, 3):
                self.begindrag(position, event.button)
                return None

            if event.button != 1:
                return None

            if self.closerect.collidepoint(position):
                self.closeview()
                return None

            focus = self.findfocus(self.detailid)
            if focus and self.detailrect.collidepoint(position):
                if self.startrect.collidepoint(position) and focus.get("canstart"):
                    return ("startfocus", self.detailid)
                return None

            for focusid, rect in self.noderects.items():
                if rect.collidepoint(position):
                    self.detailid = focusid
                    return None

            self.begindrag(position, event.button)
            return None

        return None
    
    def pointerover(self, position):
        return self.isopen













    def makekey(self):
        focuses = []
        for focus in self.data.get("focuses", ()):
            if not isinstance(focus, dict):
                continue
            focuses.append(
                (
                    focus.get("id"),
                    int(focus.get("x", 0) or 0),
                    int(focus.get("y", 0) or 0),
                    focus.get("icon", ""),
                    focus.get("image", ""),
                )
            ) # sample: ('focus_id', 0, 0, 'icon.png')
        return (self.data.get("cover_image", ""), tuple(focuses))


    # dragging and zooming
    def begindrag(self, position, button):
        self.dragging = True
        self.dragbutton = button
        self.dragstart = position
        self.panstart = (self.panx, self.pany)

    def zoomat(self, position, amount):
        oldzoom = self.zoom
        newzoom = oldzoom * (1.14 ** int(amount))
        newzoom = max(self.minzoom, min(self.maxzoom, newzoom))
        if abs(newzoom - oldzoom) < 0.001:
            return

        worldx = (position[0] - self.panx) / oldzoom
        worldy = (position[1] - self.pany) / oldzoom
        self.zoom = newzoom
        self.panx = position[0] - worldx * newzoom
        self.pany = position[1] - worldy * newzoom


    # for the layout
    def centerlayout(self, viewrect):
        bounds = self.worldbounds() #check the bounds of the world rects, so we can center the layout in the view
        focusarea = pygame.Rect(0, self.headerheight + 18, viewrect.width, max(1, viewrect.height - self.headerheight - 54))
        self.panx = focusarea.centerx - bounds.centerx * self.zoom
        self.pany = focusarea.centery - bounds.centery * self.zoom
        screentop = bounds.top * self.zoom + self.pany
        if screentop < focusarea.top:
            self.pany += focusarea.top - screentop

    def worldbounds(self):
        if not self.worldrects:
            return pygame.Rect(0, 0, 1, 1)
        bounds = None
        for rect in self.worldrects.values():
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds or pygame.Rect(0, 0, 1, 1)

    def screentorect(self, rect):
        return pygame.Rect(
            int(rect.x * self.zoom + self.panx),
            int(rect.y * self.zoom + self.pany),
            max(1, int(rect.width * self.zoom)),
            max(1, int(rect.height * self.zoom)),
        )

    def screenpoint(self, point):
        return (
            int(point[0] * self.zoom + self.panx),
            int(point[1] * self.zoom + self.pany),
        )



    # MAIN RENDER METHOD

    def draw(self, surface, titlefont, font, mouse):
        viewrect = surface.get_rect()
        # if the view size has changedneed to redo the layout
        if self.viewsize != viewrect.size:
            self.viewsize = viewrect.size
            self.layoutready = False
        pygame.draw.rect(surface, (0, 0, 0), viewrect)


        self.closerect = pygame.Rect(viewrect.right - 150, 20, 118, 34)

        focuses = [focus for focus in self.data.get("focuses", ()) if isinstance(focus, dict)] # filter out invalid focuses
        if not focuses:
            self.drawheader(surface, viewrect, titlefont, font)
            note = font.render("Cant find any focus data for this country", True, (205, 205, 205))
            surface.blit(note, note.get_rect(center=viewrect.center))
            self.noderects = {}
            return

        self.layoutnodes(viewrect, focuses)
        treeclip = pygame.Rect(0, self.headerheight + 1, viewrect.width, max(1, viewrect.height - self.headerheight - 1))
        previousclip = surface.get_clip()
        surface.set_clip(treeclip)
        self.drawconnectors(surface, focuses)



        for focus in focuses:
            rect = self.noderects.get(focus.get("id"))
            if rect:
                self.drawnode(surface, focus, rect, font, mouse)
        surface.set_clip(previousclip)

        focus = self.findfocus(self.detailid)
        if focus:
            self.drawdetails(surface, focus, titlefont, font) # draw the details panel for the selected focus

        self.drawheader(surface, viewrect, titlefont, font)

    def drawheader(self, surface, viewrect, titlefont, font):
        self.drawcoverbanner(surface, viewrect)
        title = str(self.data.get("name") or "National Policy").replace("Focus Tree", "National Policy")
        title_surface = titlefont.render(title, True, (238, 220, 165))
        shadow_surface = titlefont.render(title, True, (0, 0, 0))
        surface.blit(shadow_surface, (34, 24))
        surface.blit(title_surface, (32, 22))
        self.drawbutton(surface, self.closerect, True, "Back", font)

        message = str(self.data.get("lastmessage") or "")
        if message:
            self.fittext(surface, message, font, (190, 205, 230), pygame.Rect(32, 62, viewrect.width - 220, 22))

    def drawcoverbanner(self, surface, viewrect):
        coverpath = str(self.data.get("cover_image") or "").strip()
        if not coverpath:
            return

        cover = self.loadimage(coverpath)
        if cover is None:
            return

        bannerrect = pygame.Rect(0, 0, viewrect.width, self.headerheight)
        pygame.draw.rect(surface, (0, 0, 0), bannerrect)
        bannerimage = pygame.Surface(bannerrect.size, pygame.SRCALPHA)
        self.drawcroppedimage(bannerimage, cover, bannerimage.get_rect())
        bannerimage.set_alpha(51)
        surface.blit(bannerimage, bannerrect.topleft)
        overlay = pygame.Surface(bannerrect.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 18))
        pygame.draw.rect(overlay, (0, 0, 0, 72), pygame.Rect(0, 0, min(520, bannerrect.width), bannerrect.height))
        pygame.draw.rect(overlay, (0, 0, 0, 42), pygame.Rect(0, bannerrect.bottom - 46, bannerrect.width, 46))
        surface.blit(overlay, bannerrect.topleft)
        pygame.draw.line(surface, (238, 220, 165), (0, bannerrect.bottom - 1), (bannerrect.right, bannerrect.bottom - 1), 1)




    def layoutnodes(self, viewrect, focuses): #world rect for each focus, to make the connecting line thing
        nodew = 190
        nodeh = 108
        spacex = 420
        spacey = 270
        minx = min(int(focus.get("x", 0) or 0) for focus in focuses)
        miny = min(int(focus.get("y", 0) or 0) for focus in focuses)

        self.worldrects = {}
        self.noderects = {} # list of focus rects for mouse interaction, calculated from worldrects and current zoom/pan



        for focus in focuses:
            focusid = focus.get("id")
            if not focusid:
                continue
            focusx = int(focus.get("x", 0) or 0)
            focusy = int(focus.get("y", 0) or 0)
            x = (focusx - minx) * spacex
            y = (focusy - miny) * spacey
            self.worldrects[focusid] = pygame.Rect(x, y, nodew, nodeh)



        if not self.layoutready:
            self.centerlayout(viewrect)
            self.layoutready = True

        for focusid, rect in self.worldrects.items():
            self.noderects[focusid] = self.screentorect(rect)



    # render the conenectors 
    def drawconnectors(self, surface, focuses):

        for focus in focuses:
            target = self.worldrects.get(focus.get("id"))
            if target is None:
                continue


            for prerequisite in focus.get("prerequisites", ()):
                source = self.worldrects.get(prerequisite)
                if source is None:
                    continue
                start = self.screenpoint(source.midbottom)
                end = self.screenpoint(target.midtop)
                bend = (start[0], start[1] + (end[1] - start[1]) // 2)
                bendtwo = (end[0], bend[1])
                linew = max(1, int(3 * self.zoom))
                pygame.draw.lines(surface, (72, 80, 91), False, (start, bend, bendtwo, end), linew + 1)
                pygame.draw.lines(surface, (112, 124, 140), False, (start, bend, bendtwo, end), max(1, linew - 1))




    # to render a focus node with the icon and title and color
    def drawnode(self, surface, focus, rect, font, mouse):
        status = str(focus.get("status", "locked"))
        fill, border = self.statuscolors(status)
        if rect.collidepoint(mouse):
            fill = tuple(min(255, value + 16) for value in fill)


        # draw the node background and border
        pygame.draw.rect(surface, fill, rect, border_radius=4)
        icon = self.loadimage(focus.get("icon"))
        if icon:
            self.drawcroppedimage(surface, icon, rect)
        else:
            pygame.draw.rect(surface, (30, 34, 40), rect.inflate(-8, -8), border_radius=3)

        tint = pygame.Surface(rect.size, pygame.SRCALPHA)
        if status in ("locked", "blocked", "waiting"):
            tint.fill((0, 0, 0, 78))
        elif status == "completed":
            tint.fill((28, 78, 45, 46))
        elif status == "active":
            tint.fill((33, 81, 145, 42))
        elif status == "available":
            tint.fill((118, 86, 24, 30))
        surface.blit(tint, rect.topleft)

        titlebandheight = max(28, int(36 * self.zoom))
        titleband = pygame.Surface((rect.width, titlebandheight), pygame.SRCALPHA)
        titleband.fill((0, 0, 0, 150))
        pygame.draw.line(titleband, (*border, 185), (0, 0), (rect.width, 0), 1)
        surface.blit(titleband, (rect.x, rect.bottom - titlebandheight))
        pygame.draw.rect(surface, border, rect, 2, border_radius=4)
        pygame.draw.rect(surface, border, pygame.Rect(rect.x, rect.y, rect.width, max(4, int(6 * self.zoom))), border_radius=3)

        # draw the title if zoomed in enough
        if self.zoom >= 0.55:
            titlerect = pygame.Rect(rect.x + 8, rect.bottom - titlebandheight + 4, rect.width - 16, titlebandheight - 8)
            self.fittext(surface, str(focus.get("title") or focus.get("id")), font, (244, 244, 244), titlerect)



    # render the detail window 
    def drawdetails(self, surface, focus, titlefont, font):
        width = surface.get_width()
        height = surface.get_height()
        panelw = 410 if width >= 820 else max(320, width - 80)
        panelh = max(320, height - self.headerheight - 48)
        panelx = width - panelw - 34 if width >= 820 else 40
        self.detailrect = pygame.Rect(panelx, self.headerheight + 16, panelw, panelh)


        # draw the panel background and border
        pygame.draw.rect(surface, (20, 24, 31), self.detailrect, border_radius=4)
        pygame.draw.rect(surface, (96, 104, 116), self.detailrect, 2, border_radius=4)

        x = self.detailrect.x + 18
        y = self.detailrect.y + 16
        contentw = self.detailrect.width - 36

        titlelines = self.wraptext(str(focus.get("title") or focus.get("id")), titlefont, contentw)
        for line in titlelines[:2]:
            surface.blit(titlefont.render(line, True, (238, 220, 165)), (x, y))
            y += titlefont.get_height() + 2

        imagepath = str(focus.get("image") or self.data.get("cover_image") or "").strip()
        detailimage = self.loadimage(imagepath)
        if detailimage is not None:
            y += 8
            imagerect = pygame.Rect(x, y, contentw, min(132, max(86, self.detailrect.height // 5)))
            self.drawcroppedimage(surface, detailimage, imagerect)
            shade = pygame.Surface(imagerect.size, pygame.SRCALPHA)
            shade.fill((0, 0, 0, 42))
            surface.blit(shade, imagerect.topleft)
            pygame.draw.rect(surface, (96, 104, 116), imagerect, 1, border_radius=3)
            y = imagerect.bottom

        # decsription
        y += 8
        y = self.drawwrappedblock(surface, str(focus.get("description") or ""), font, (220, 220, 220), x, y, contentw, 5)
        y += 8

        status = str(focus.get("status", "locked"))
        progress = int(focus.get("progress", 0) or 0)
        turns = int(focus.get("turnsrequired", 1) or 1)
        y = self.drawfield(surface, "Status", status, font, x, y, contentw)
        y = self.drawfield(surface, "Turns", str(turns), font, x, y, contentw)
        y = self.drawfield(surface, "Progress", f"{progress}/{turns}", font, x, y, contentw)
        y = self.drawfield(surface, "Prerequisites", self.namelist(focus.get("prerequisites", ())), font, x, y, contentw)
        y = self.drawfield(surface, "Mutually exclusive", self.namelist(focus.get("mutuallyexclusive", ())), font, x, y, contentw)
        y = self.drawfield(surface, "Effects", self.effecttext(focus.get("effects", ())), font, x, y, contentw)



        reason = str(focus.get("blockingreason") or "")
        if reason:
            y += 4
            self.drawwrappedblock(surface, reason, font, (205, 150, 150), x, y, contentw, 3)

        self.startrect = pygame.Rect(x, self.detailrect.bottom - 52, contentw, 34)
        self.drawbutton(surface, self.startrect, bool(focus.get("canstart")), "Start Focus", font)




    #RENDER UTILITIES
    def drawfield(self, surface, label, value, font, x, y, width):
        labeltext = font.render(f"{label}:", True, (185, 195, 210))
        surface.blit(labeltext, (x, y))
        y += labeltext.get_height() + 2
        y = self.drawwrappedblock(surface, value or "None", font, (235, 235, 235), x + 12, y, width - 12, 3)
        return y + 7

    def drawwrappedblock(self, surface, text, font, color, x, y, width, maxlines):
        for line in self.wraptext(str(text), font, width)[:maxlines]:
            surface.blit(font.render(line, True, color), (x, y))
            y += font.get_height() + 2
        return y

    def drawbutton(self, surface, rect, enabled, label, font):
        fill = (62, 126, 82) if enabled else (64, 64, 68)
        border = (154, 210, 165) if enabled else (118, 118, 122)
        textcolor = (245, 245, 245) if enabled else (170, 170, 174)
        pygame.draw.rect(surface, fill, rect, border_radius=3)
        pygame.draw.rect(surface, border, rect, 1, border_radius=3)
        text = font.render(label, True, textcolor)
        surface.blit(text, text.get_rect(center=rect.center))

    def fittext(self, surface, text, font, color, rect):
        original = str(text)
        fitted = original
        while fitted and font.size(fitted)[0] > rect.width:
            fitted = fitted[:-1]
        if not fitted:
            return
        if fitted != original:
            fitted = fitted[:-3] + "..." if len(fitted) > 3 else fitted
        rendered = font.render(fitted, True, color)
        surface.blit(rendered, rendered.get_rect(center=rect.center))

    #stole from console.py
    def wraptext(self, text, font, width):
        words = str(text or "").split()
        if not words:
            return []

        lines = []
        line = ""
        for word in words:
            candidate = word if not line else f"{line} {word}"
            if font.size(candidate)[0] <= width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines



    def loadicon(self, iconpath):
        image = self.loadimage(iconpath)
        if image is None:
            return None

        return pygame.transform.smoothscale(image, (46, 34))

    def loadimage(self, iconpath):
        iconpath = str(iconpath or "").strip()
        if not iconpath:
            return None

        filepath = iconpath
        if not os.path.isabs(filepath):
            filepath = os.path.join(self.rootpath, filepath)
        filepath = os.path.normpath(filepath)

        if filepath in self.imagecache:
            return self.imagecache[filepath]

        image = None
        try:
            loaded = pygame.image.load(filepath)
            try:
                loaded = loaded.convert_alpha()
            except pygame.error:
                pass
            image = loaded
        except (OSError, pygame.error):
            image = None

        self.imagecache[filepath] = image
        return image

    def drawcroppedimage(self, surface, image, rect):
        if image is None or rect.width <= 0 or rect.height <= 0:
            return

        imagew, imageh = image.get_size()
        if imagew <= 0 or imageh <= 0:
            return

        scale = max(rect.width / imagew, rect.height / imageh)
        draww = max(1, int(imagew * scale))
        drawh = max(1, int(imageh * scale))
        scaled = pygame.transform.smoothscale(image, (draww, drawh))
        drawx = rect.centerx - draww // 2
        drawy = rect.centery - drawh // 2
        previousclip = surface.get_clip()
        surface.set_clip(rect)
        surface.blit(scaled, (drawx, drawy))
        surface.set_clip(previousclip)






    def findfocus(self, focusid):
        for focus in self.data.get("focuses", ()):
            if isinstance(focus, dict) and focus.get("id") == focusid:
                return focus
        return None

    def namelist(self, focusids):
        names = [self.focustitle(focusid) for focusid in focusids or ()]
        return ", ".join(names) if names else "None"

    def focustitle(self, focusid):
        focus = self.findfocus(focusid)
        if focus:
            return str(focus.get("title") or focusid)
        return str(focusid)

    def effecttext(self, effects):
        parts = []
        for effect in effects or ():
            if not isinstance(effect, dict):
                continue
            amount = int(effect.get("amount", 0) or 0)
            sign = "+" if amount >= 0 else ""
            effecttype = effect.get("type")
            if effecttype == "modify_gold":
                parts.append(f"Gold {sign}{amount}")
            elif effecttype == "modify_population_growth":
                parts.append(f"Population growth {sign}{amount}")
            else:
                parts.append(str(effecttype))
        return ", ".join(parts) if parts else "None"





    # i have no idea what to name this, it just returns the fill and border colors for a focus node based on its status
    def statuscolors(self, status):
        colors = {
            "completed": ((42, 98, 67), (142, 222, 160)),
            "active": ((43, 82, 137), (140, 190, 255)),
            "available": ((101, 81, 39), (232, 190, 86)),
            "blocked": ((90, 46, 46), (220, 125, 125)),
            "locked": ((52, 54, 59), (122, 126, 136)),
            "waiting": ((50, 54, 62), (122, 132, 145)),
        }
        return colors.get(status, colors["locked"])
