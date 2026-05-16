import ctypes
import os

import pygame

from engine.gui import gui_drawtroopcountbadge, gui_mergetroopbadgeentries
from .focusui import FocusTreeView
from .researchui import ResearchTreeView

ctypes.windll.user32.SetProcessDPIAware()


class Panel:
    def __init__(self, rect: pygame.Rect, color=(40, 40, 40)):
        self.rect = rect
        self.color = color

    def draw(self, surface: pygame.Surface):
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.rect(surface, (25, 25, 25), self.rect, 1)


class LeftBar:
    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.items: list[str] = []
        self.item_rects: dict[str, pygame.Rect] = {}
        self._hover_glow = {}

    def set_items(self, items: list[str]):
        self.items = list(items)
        self._hover_glow = {}

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, mouse_pos, font_bold=None):
        pygame.draw.rect(surface, (50, 50, 50), self.rect)
        pygame.draw.rect(surface, (25, 25, 25), self.rect, 1)

        self.item_rects = {}
        radius = 8
        for i, item in enumerate(self.items):
            if not str(item).strip():
                continue

            x = self.rect.x + 10
            y = self.rect.y + 60 + (i * 50)
            w = self.rect.width - 20
            h = 40
            rect = pygame.Rect(x, y, w, h)
            item_key = str(item).strip().upper()
            self.item_rects[item_key] = rect

            hovered = rect.collidepoint(mouse_pos)
            glow = self._hover_glow.get(item_key, 0.0)
            if hovered:
                glow = min(1.0, glow + 0.12)
            else:
                glow = max(0.0, glow - 0.08)
            self._hover_glow[item_key] = glow

            if "CLEAR ALL" in item:
                color = (0, 120, 0) if hovered else (0, 220, 0)
            else:
                if hovered:
                    color = (60, 230, 60)
                else:
                    color = (30, 30, 30)

            pygame.draw.rect(surface, color, rect, border_radius=radius)

            if glow > 0.01:
                glow_surf = pygame.Surface((w + 24, h + 24), pygame.SRCALPHA)
                for ring in range(5):
                    ring_alpha = int(glow * (40 - ring * 7))
                    if ring_alpha <= 0:
                        continue
                    offset = ring * 2 + 2
                    gw = w + offset * 2
                    gh = h + offset * 2
                    pygame.draw.rect(glow_surf, (60, 255, 60, ring_alpha),
                        (12 - offset, 12 - offset, gw, gh),
                        border_radius=radius + offset, width=2)
                surface.blit(glow_surf, (x - 12, y - 12))

            text_color = (0, 0, 0) if hovered else (200, 200, 200)
            if "CLEAR ALL" in item:
                text_color = (0, 0, 0)
            active_font = font_bold if (hovered and font_bold) else font
            text = active_font.render(item, True, text_color)
            surface.blit(text, (x + 10, y + 10))


class BottomButtons:
    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.items: list[str] = []
        self.item_rects: dict[str, pygame.Rect] = {}
        self.selected: str | None = None
        self._hover_glow = {}

    def set_items(self, items: list[str]):
        self.items = list(items)
        if self.selected not in self.items:
            self.selected = (self.items[-1] if self.items else None)
        self._hover_glow = {}

    def set_selected(self, item: str | None):
        if item is None or item in self.items:
            self.selected = item

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, mouse_pos, font_bold=None):
        w = 120
        h = 30
        spacing = 10
        radius = 8
        total_width = len(self.items) * w + (len(self.items) - 1) * spacing if self.items else 0
        available_width = max(0, self.rect.width)
        start_x = self.rect.x + max(0, (available_width - total_width) // 2)

        self.item_rects = {}
        for i, item in enumerate(self.items):
            x = start_x + (i * (w + spacing))
            y = self.rect.y + 10
            rect = pygame.Rect(x, y, w, h)
            self.item_rects[item] = rect

            hovered = rect.collidepoint(mouse_pos)
            glow = self._hover_glow.get(item, 0.0)
            if hovered:
                glow = min(1.0, glow + 0.12)
            else:
                glow = max(0.0, glow - 0.08)
            self._hover_glow[item] = glow

            if item == self.selected:
                color = (0, 220, 0) if not hovered else (60, 230, 60)
            else:
                color = (60, 230, 60) if hovered else (30, 30, 30)

            pygame.draw.rect(surface, color, rect, border_radius=radius)

            if glow > 0.01:
                glow_surf = pygame.Surface((w + 24, h + 24), pygame.SRCALPHA)
                for ring in range(5):
                    ring_alpha = int(glow * (40 - ring * 7))
                    if ring_alpha <= 0:
                        continue
                    offset = ring * 2 + 2
                    gw = w + offset * 2
                    gh = h + offset * 2
                    pygame.draw.rect(glow_surf, (60, 255, 60, ring_alpha),
                        (12 - offset, 12 - offset, gw, gh),
                        border_radius=radius + offset, width=2)
                surface.blit(glow_surf, (x - 12, y - 12))

            text_color = (0, 0, 0) if hovered else (200, 200, 200)
            if item == self.selected and not hovered:
                text_color = (0, 0, 0)
            active_font = font_bold if (hovered and font_bold) else font
            text = active_font.render(item, True, text_color)
            text_rect = text.get_rect(center=rect.center)
            surface.blit(text, text_rect)


class InGameUI:
    actionchoosecountry = "choosecountry"
    actionrecruit = "recruit"
    actionendturn = "endturn"
    actiondeclarewar = "declarewar"
    actionsplit = "split"
    actionmerge = "merge"
    actionfrontline = "frontline"
    actiontogglefocuspanel = "togglefocuspanel"
    actionstartfocus = "startfocus"
    actionpausemenu = "pausemenu"
    actionquitgame = "quitgame"
    actionweapon1 = "weapon_1"
    actionweapon2 = "weapon_2"
    actionweapon3 = "weapon_3"
    actionweapon4 = "weapon_4"

    def __init__(self, window_size):
        self.window_size = window_size
        self.title_font = pygame.font.SysFont("Verdana", 16, bold=True)
        self.font = pygame.font.SysFont("Verdana", 14)
        self.font_bold = pygame.font.SysFont("Verdana", 14, bold=True)

        self.leftbar_width = 180
        self.topbar_height = 50
        # widened so troop/country panels fit "seamlessly" in the right tab
        self.rightbar_width = 356
        self.bottombar_height = 43

        self.gamephase = "choosecountry"
        self.pendingcountry = None
        self.playercountry = None
        self.currentturnnumber = 1
        self.playergold = 0
        self.playerpopulation = 0
        self.playerstability = 50.0
        self.playerpp = 0
        self.playerap = 0
        self._active_manpower = 0
        self._manpower_cache_key = None

        self.recruitamount = 0
        self.recruitenabled = False
        self._countrymenutarget = None
        self._selectedmapcountry = None
        self._selected_country_stats = {}
        self._bigflags = {}
        self._countriesatwarset = set()
        self._selectedtroopentries = []
        self._frontlineplacementmode = False
        self._troopbadgelist = []
        self._hovertext = None
        self._hovermousepos = (0, 0)
        self.focusview = FocusTreeView()
        self.researchview = ResearchTreeView()
        self.pausemenuopen = False
        self.active_left_tab = None
        self.warprogressopen = False
        self._warprogressdata = {}
        self.actionwarprogress = "warprogress"

        self._flags = self._load_flags()
        self._badge_flags = {
            key: pygame.transform.scale(img, (20, 14))
            for key, img in self._flags.items()
        }

        self._choose_rect = pygame.Rect(0, 0, 160, 34)
        self._endturn_rect = pygame.Rect(0, 0, 10, 10)  # placed near map bottom-right
        self._endturn_glow = 0.0
        self._button_glows: dict[str, float] = {}

        # right panel interactive rects (computed in applylayout)
        self._recruit_action_rect = pygame.Rect(0, 0, 10, 10)
        self._declarewar_rect = pygame.Rect(0, 0, 10, 10)
        self._split_rect = pygame.Rect(0, 0, 10, 10)
        self._merge_rect = pygame.Rect(0, 0, 10, 10)
        self._frontline_rect = pygame.Rect(0, 0, 10, 10)
        self._research_btn_rects = [pygame.Rect(0, 0, 10, 10) for _ in range(4)]
        self._research_back_rect = pygame.Rect(0, 0, 10, 10)

        self.leftbar = LeftBar(pygame.Rect(0, 0, 10, 10))
        self.bottom_buttons = BottomButtons(pygame.Rect(0, 0, 10, 10))

        self.leftbar.set_items(
            [
                "      CLEAR ALL    ",
                "",
                "NOTIFICATIONS",
                "LOGISTICS",
                "COMBAT",
                "INTEL",
                "FOCUS TREE"
            ]
        )
        self.bottom_buttons.set_items(
            [
                "RESEARCH",
                "DIPLOMACY",
                "TRADE",
                "PRODUCTION",
                "CONSTRUCTION",
                "RECRUIT",
            ]
        )
        self.bottom_buttons.set_selected(None)

        self.topbar = Panel(pygame.Rect(0, 0, 10, 10), (0, 0, 0))
        self.rightbar = Panel(pygame.Rect(0, 0, 10, 10), (0, 0, 0))
        self.bottombar = Panel(pygame.Rect(0, 0, 10, 10), (29, 29, 29))
        self.pause_menu = pygame.Rect(0,0,10,10)
        self.quit_menu = pygame.Rect(0,0,10,10)
        self.map_rect = pygame.Rect(0, 0, 10, 10)
        self.applylayout()


    

    def _load_flags(self):
        flags = {}
        flag_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "flags")
        )

        if not os.path.isdir(flag_path):
            return flags

        for filename in os.listdir(flag_path):
            if not filename.lower().endswith(".png"):
                continue

            filepath = os.path.join(flag_path, filename)

            country_key = (
                os.path.splitext(filename)[0]
                .strip()
                .lower()
                .replace(" ", "_")
                .replace("-", "_")
            )

            try:
                img = pygame.image.load(filepath).convert_alpha()

                # Store ORIGINAL high-resolution image
                flags[country_key] = img

            except pygame.error:
                continue

        return flags

    @staticmethod
    def _format_number(value):
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return "0"

    @staticmethod
    def _format_decimal(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        if abs(number - int(number)) < 0.05:
            return f"{int(number):,}"
        return f"{number:,.1f}"

    @staticmethod
    def _fit_text(font, text, max_width):
        # trim long labels before they enter fixed-width war columns.
        text = str(text)
        if font.size(text)[0] <= max_width:
            return text

        suffix = "..."
        available_width = max(0, max_width - font.size(suffix)[0])
        fitted = ""
        for char in text:
            candidate = fitted + char
            if font.size(candidate)[0] > available_width:
                break
            fitted = candidate
        return fitted.rstrip() + suffix if fitted else suffix

    def _draw_text_fit(self, surface, text, color, x, y, max_width, font=None):
        font = font or self.font
        fitted = self._fit_text(font, text, max_width)
        surface.blit(font.render(fitted, True, color), (x, y))

    def applylayout(self):
        window_width, window_height = self.window_size

        self.topbar.rect = pygame.Rect(0, 0, window_width, self.topbar_height)

        
        if self.gamephase == "choosecountry":
            show_left = False
            show_bottom = False
            show_right = False
        else:
            show_left = True
            show_bottom = True
            show_right = bool(
                self._countrymenutarget
                or self.bottom_buttons.selected == "RECRUIT"
                or self.active_left_tab == "COMBAT"
                or self._selectedmapcountry
            )

        left_w = self.leftbar_width if show_left else 0
        bottom_h = self.bottombar_height if show_bottom else 0
        right_w = self.rightbar_width if show_right else 0

        self.leftbar.rect = pygame.Rect(0, 0, left_w, window_height)

        right_x = max(0, window_width - right_w)
        self.rightbar.rect = pygame.Rect(
            right_x,
            self.topbar_height,
            right_w,
            max(0, window_height - self.topbar_height - bottom_h),
        )

        bottom_y = max(0, window_height - bottom_h)
        self.bottombar.rect = pygame.Rect(0, bottom_y, window_width, bottom_h)
        self.bottom_buttons.rect = self.bottombar.rect

        center_x = left_w
        center_y = self.topbar_height
        center_w = max(1, window_width - left_w - right_w)
        center_h = max(1, window_height - self.topbar_height - bottom_h)
        self.map_rect = pygame.Rect(center_x, center_y, center_w, center_h)

        # End turn on the bottom-right side of the map viewport
        end_w = 140
        end_h = 30
        end_x = self.map_rect.right - end_w - 12
        end_y = self.map_rect.bottom - end_h - 12
        self._endturn_rect = pygame.Rect(end_x, end_y, end_w, end_h)

        # choose button near bottom-right of map in choosecountry (draw will override)

        # right panel content layout (play phase; safe even if right panel hidden)
        content_x = self.rightbar.rect.x + 12
        content_y = self.rightbar.rect.y + 12
        content_w = max(1, self.rightbar.rect.width - 24)
        self._recruit_action_rect = pygame.Rect(content_x, content_y + 40, content_w, 34)
        self._declarewar_rect = pygame.Rect(content_x, content_y + 82, content_w, 34)

        # troop decision buttons at the bottom of right panel
        btn_w = (content_w - 20) // 3
        btn_h = 50
        btn_y = (self.rightbar.rect.bottom - 12 - btn_h) if self.rightbar.rect.width else (self.map_rect.bottom - 12 - btn_h)
        self._split_rect = pygame.Rect(content_x, btn_y, btn_w, btn_h)
        self._merge_rect = pygame.Rect(content_x + btn_w + 10, btn_y, btn_w, btn_h)
        self._frontline_rect = pygame.Rect(content_x + (btn_w + 10) * 2, btn_y, btn_w, btn_h)
        btn_w = 400
        btn_h = 60
        btn_gap = 20
        total_h = 4 * btn_h + 3 * btn_gap
        start_x = (window_width - btn_w) // 2
        start_y = (window_height - total_h) // 2
        for i in range(4):
            self._research_btn_rects[i] = pygame.Rect(
                start_x,
                start_y + i * (btn_h + btn_gap),
                btn_w,
                btn_h
            )

        last_weapon_rect = self._research_btn_rects[3]

        back_w = 120
        back_h = 40
        back_x = start_x + (btn_w - back_w) // 2 
        back_y = last_weapon_rect.bottom + 20

        self._research_back_rect = pygame.Rect(back_x, back_y, back_w, back_h)
        menu_w = min(320, max(220, window_width - 80))
        menu_h = 170
        menu_x = max(0, (window_width - menu_w) // 2)
        menu_y = max(0, (window_height - menu_h) // 2)
        self._pausemenu_rect = pygame.Rect(menu_x, menu_y, menu_w, menu_h)
        self._pausequit_rect = pygame.Rect(menu_x + (menu_w - 150) // 2, menu_y + menu_h - 52, 150, 40)
        self._war_progress_rect = pygame.Rect(content_x, content_y + 40, content_w, 34)


    def select_map_country(self, country_name: str | None):
        self._selectedmapcountry = country_name
        if country_name:
            self._countrymenutarget = None
            self._selectedtroopentries = []
        self.applylayout()

    def _get_big_flag(self, country_name, size=(240, 144)):
        if not country_name:
            return None
        key = str(country_name).strip().lower().replace(" ", "_").replace("-", "_")
        cache_key = (key, size)
        if cache_key in self._bigflags:
            return self._bigflags[cache_key]
        small_flag = self._flags.get(key)
        if not small_flag:
            return None
        big_flag = pygame.transform.smoothscale(small_flag, size)
        self._bigflags[cache_key] = big_flag
        return big_flag

    def setwindowsize(self, window_size):
        self.window_size = window_size
        self.applylayout()

    def sync(
        self,
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
        mouseposition,
        troopbadgelist,
        focusview=None,
        researchdata=None,
        warprogressdata=None,
        selected_country_stats=None,
    ):
        self.gamephase = gamephase
        self.pendingcountry = pendingcountry
        self.playercountry = playercountry
        self.currentturnnumber = currentturnnumber
        self.playergold = playergold
        self.playerpopulation = playerpopulation
        self.playerstability = playerstability
        self.playerpp = playerpp
        self.playerap = playerap
        self.recruitamount = recruitamount
        self.recruitenabled = bool(recruitenabled)
        self._countrymenutarget = countrymenutarget
        self._countriesatwarset = set(countriesatwarset or ())
        self._selectedtroopentries = list(selectedtroopentries or [])
        self._frontlineplacementmode = bool(frontlineplacementmode)
        self._troopbadgelist = list(troopbadgelist or [])
        self._hovertext = hovertext
        self._hovermousepos = tuple(mouseposition or (0, 0))
        if focusview is not None:
            self.focusview.setdata(focusview)
        if researchdata is not None:
            self.researchview.setdata(
                researchdata.get("researched", frozenset()),
                researchdata.get("researching_id"),
                researchdata.get("researching_turns_remaining", 0),
            )
        # reflow after state changes (tab visibility depends on selection/menu)
        if warprogressdata is not None:
            self._warprogressdata = warprogressdata
        if selected_country_stats is not None:
            self._selected_country_stats = selected_country_stats

        self.applylayout()

        # cache active manpower (sum troops controlled by player) only when inputs change
        cache_key = (id(provincemap), self.playercountry, int(currentturnnumber or 0))
        if cache_key != self._manpower_cache_key:
            self._manpower_cache_key = cache_key
            manpower = 0
            if self.playercountry and isinstance(provincemap, dict):
                for province in provincemap.values():
                    if not isinstance(province, dict):
                        continue
                    controller = province.get("controllercountry", province.get("country"))
                    if controller == self.playercountry:
                        manpower += int(province.get("troops", 0) or 0)
            self._active_manpower = manpower

    def update(self, elapsedseconds: float):
        # retained for runtime compatibility
        return



    def process_event(self, event):

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.warprogressopen:
                self.warprogressopen = False
                return None
            self.pausemenuopen = not self.pausemenuopen
            return self.actionpausemenu

        if self.pausemenuopen:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._pausequit_rect.collidepoint(event.pos):
                    return self.actionquitgame
            return None
        
        if self.focusview.isopen:
            result = self.focusview.handleevent(event)
            if not self.focusview.isopen:
                self.active_left_tab = None
                self.applylayout()
            return result

        if self.researchview.isopen:
            result = self.researchview.handleevent(event)
            if not self.researchview.isopen:
                self.bottom_buttons.set_selected(None)
                self.applylayout()
            return result

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None

        pos = event.pos
        if self.gamephase == "choosecountry":
            if self.pendingcountry and self._choose_rect.collidepoint(pos):
                return self.actionchoosecountry
            return None

        for item, rect in (self.leftbar.item_rects or {}).items():
            if rect.collidepoint(pos):

                self.active_left_tab = item
                self.applylayout()
                if item == "FOCUS TREE":
                    self.focusview.toggleview()
                    return self.actiontogglefocuspanel
                return None

        for item, rect in (self.bottom_buttons.item_rects or {}).items():
            if rect.collidepoint(pos):
                self.bottom_buttons.set_selected(item)
                self.applylayout()
                if item == "RESEARCH":
                    self.researchview.toggleview()
                return None

      
        if self._endturn_rect.collidepoint(pos):
            return self.actionendturn

        selected_tab = self.bottom_buttons.selected

        if selected_tab == "RESEARCH" and not self._countrymenutarget:

            if self._research_back_rect.collidepoint(pos):
                self.bottom_buttons.set_selected(None)
                self.applylayout()
                return "back_from_research"

            for i in range(4):
                if self._research_btn_rects[i].collidepoint(pos):
                    return getattr(self, f"actionweapon{i+1}")

            return None


        if self.active_left_tab == "COMBAT" and not self._countrymenutarget:
            if self._war_progress_rect.collidepoint(pos):
                self.warprogressopen = not self.warprogressopen
                return self.actionwarprogress
        if selected_tab == "RECRUIT":
            if self._recruit_action_rect.collidepoint(pos):
                if self.recruitenabled:
                    return self.actionrecruit
                return None

      
        if selected_tab == "RECRUIT" and self._selectedtroopentries:
            selected = [e for e in self._selectedtroopentries if isinstance(e, dict)]
            totaltroops = sum(max(0, int(e.get("troops", 0))) for e in selected)
            if totaltroops > 0:
                if self._split_rect.collidepoint(pos) and totaltroops > 1:
                    return self.actionsplit
                if self._merge_rect.collidepoint(pos) and len(selected) > 1:
                    return self.actionmerge
                if self._frontline_rect.collidepoint(pos):
                    return self.actionfrontline

            return None
       
    def ispointeroverui(self, mouseposition):
        if self.warprogressopen:
            return True
       
        if self.focusview.pointerover(mouseposition):
            return True
        if self.researchview.pointerover(mouseposition):
            return True
        if self._endturn_rect.collidepoint(mouseposition):
            return True
        if self.leftbar.rect.collidepoint(mouseposition):
            return True
        if self.topbar.rect.collidepoint(mouseposition):
            return True
        if self.rightbar.rect.collidepoint(mouseposition):
            return True
        if self.bottombar.rect.collidepoint(mouseposition):
            return True
        return False

    def draw(self, surface: pygame.Surface):
        mouse = pygame.mouse.get_pos()



    

        if self.gamephase == "choosecountry":
            # minimal UI only during choosecountry
            self.topbar.draw(surface)
            title = self.title_font.render("OPERATIONAL COMMAND", True, (200, 170, 80))
            surface.blit(title, (20, 15))

            # clear non-map areas so the screen doesn't keep old UI pixels
            bg = (10, 10, 10)
            if self.map_rect.x > 0:
                pygame.draw.rect(surface, bg, pygame.Rect(0, self.topbar_height, self.map_rect.x, surface.get_height() - self.topbar_height))
            if self.map_rect.right < surface.get_width():
                pygame.draw.rect(surface, bg, pygame.Rect(self.map_rect.right, self.topbar_height, surface.get_width() - self.map_rect.right, surface.get_height() - self.topbar_height))
            if self.map_rect.bottom < surface.get_height():
                pygame.draw.rect(surface, bg, pygame.Rect(0, self.map_rect.bottom, surface.get_width(), surface.get_height() - self.map_rect.bottom))

            # place choose button near bottom-right of the map viewport
            bw = 220
            bh = 34
            bx = self.map_rect.right - bw - 12
            by = self.map_rect.bottom - bh - 12
            self._choose_rect = pygame.Rect(bx, by, bw, bh)

            enabled = bool(self.pendingcountry)
            color = (0, 200, 0) if enabled else (50, 50, 50)
            pygame.draw.rect(surface, color, self._choose_rect)
            pygame.draw.rect(surface, (25, 25, 25), self._choose_rect, 1)
            label = self.font.render("choose country", True, (0, 0, 0) if enabled else (210, 210, 210))
            surface.blit(label, label.get_rect(center=self._choose_rect.center))
            if self.pendingcountry:
                selected = self.font.render(f"Selected: {self.pendingcountry}", True, (230, 230, 230))
                surface.blit(selected, (self._choose_rect.x, self._choose_rect.y - 22))

            return

                
        if self.warprogressopen:
            popup_w = min(560, max(360, surface.get_width() - 40))
            popup_h = min(380, max(300, surface.get_height() - 60))
            popup_rect = pygame.Rect(0, 0, popup_w, popup_h)
            popup_rect.center = surface.get_rect().center

            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            surface.blit(overlay, (0, 0))

            pygame.draw.rect(surface, (28, 28, 28), popup_rect, border_radius=4)
            pygame.draw.rect(surface, (25, 25, 25), popup_rect, 1, border_radius=4)

            title = self.title_font.render("WAR PROGRESS", True, (230, 230, 230))
            surface.blit(title, title.get_rect(center=(popup_rect.centerx, popup_rect.y + 30)))

            data = self._warprogressdata or {}
            aggressor = data.get("aggressor")
            defender = data.get("defender") 
            progress = data.get("progress")
            defender_progress = data.get("defender_progress", 0)

            content_x = popup_rect.x + 30
            content_w = popup_rect.width - 60

            if aggressor and defender and progress is not None:
                progress_value = max(0.0, min(100.0, float(progress)))
                defender_progress_value = max(0.0, min(100.0, float(defender_progress or 0)))

                subtitle = f"{aggressor} vs {defender}"
                self._draw_text_fit(surface, subtitle, (235, 235, 235), content_x, popup_rect.y + 60, content_w, self.title_font)

                progress_line = f"{aggressor} holds {progress_value:.1f}% of {defender} victory points"
                self._draw_text_fit(surface, progress_line, (215, 215, 215), content_x, popup_rect.y + 88, content_w)

                bar_rect = pygame.Rect(content_x, popup_rect.y + 114, content_w, 20)
                pygame.draw.rect(surface, (60, 60, 60), bar_rect)
                fill_w = int(bar_rect.width * (progress_value / 100.0))
                counter_w = int(bar_rect.width * (defender_progress_value / 100.0))
                if fill_w > 0:
                    pygame.draw.rect(surface, (0, 190, 95), pygame.Rect(bar_rect.x, bar_rect.y, fill_w, bar_rect.height))
                if counter_w > 0:
                    # draw defender counter-progress from the right edge.
                    pygame.draw.rect(surface, (180, 60, 60), pygame.Rect(bar_rect.right - counter_w, bar_rect.y, counter_w, bar_rect.height))
                pygame.draw.rect(surface, (25, 25, 25), bar_rect, 1)

                col_gap = 24
                col_w = (content_w - col_gap) // 2
                left_x = content_x
                right_x = content_x + col_w + col_gap
                top_y = popup_rect.y + 152

                def draw_war_column(x, y, role, country, manpower, casualties, controlled_vp, total_vp, captured_vp, occupied_provinces):
                    self._draw_text_fit(surface, role, (200, 170, 80), x, y, col_w, self.title_font)
                    self._draw_text_fit(surface, country, (235, 235, 235), x, y + 24, col_w)
                    lines = [
                        f"Manpower: {self._format_number(manpower)}",
                        f"Casualties: {self._format_number(casualties)}",
                        f"VP held: {self._format_decimal(controlled_vp)} / {self._format_decimal(total_vp)}",
                        f"Enemy VP held: {self._format_decimal(captured_vp)}",
                        f"Enemy provinces: {self._format_number(occupied_provinces)}",
                    ]
                    line_y = y + 50
                    for line in lines:
                        self._draw_text_fit(surface, line, (212, 212, 212), x, line_y, col_w)
                        line_y += 22

                draw_war_column(
                    left_x,
                    top_y,
                    "Aggressor",
                    str(aggressor),
                    data.get("aggressor_manpower", 0),
                    data.get("aggressor_casualties", 0),
                    data.get("aggressor_controlled_vp", 0),
                    data.get("aggressor_total_vp", 0),
                    data.get("aggressor_captured_vp", 0),
                    data.get("aggressor_occupied_enemy_provinces", 0),
                )
                draw_war_column(
                    right_x,
                    top_y,
                    "Defender",
                    str(defender),
                    data.get("defender_manpower", 0),
                    data.get("defender_casualties", 0),
                    data.get("defender_controlled_vp", 0),
                    data.get("defender_total_vp", 0),
                    data.get("defender_captured_vp", 0),
                    data.get("defender_occupied_enemy_provinces", 0),
                )

                status_parts = [f"Active wars: {self._format_number(data.get('active_war_count', 1))}"]
                if data.get("start_turn"):
                    status_parts.append(f"Since turn {self._format_number(data.get('start_turn'))}")
                self._draw_text_fit(
                    surface,
                    " | ".join(status_parts),
                    (170, 170, 170),
                    content_x,
                    popup_rect.bottom - 48,
                    content_w,
                )
            else:
                txt = self.font.render("No active war", True, (200, 200, 200))
                surface.blit(txt, txt.get_rect(center=(popup_rect.centerx, popup_rect.centery)))

            hint = self.font.render("Press ESC to close", True, (170, 170, 170))
            surface.blit(hint, hint.get_rect(center=(popup_rect.centerx, popup_rect.bottom - 20)))

            if self.pausemenuopen:
                self._draw_pausemenu(surface)
            return
                

        # full UI chrome (play)
        if self.leftbar.rect.width:
            self.leftbar.draw(surface, self.font, mouse, font_bold=self.font_bold)
        self.topbar.draw(surface)
        self.bottombar.draw(surface)
        self.bottom_buttons.draw(surface, self.font, mouse, font_bold=self.font_bold)
        self.topbar.draw(surface)

        # end turn button (bottom-right of map)
        hovered = self._endturn_rect.collidepoint(mouse)
        if hovered:
            self._endturn_glow = min(1.0, self._endturn_glow + 0.12)
        else:
            self._endturn_glow = max(0.0, self._endturn_glow - 0.08)
        glow = self._endturn_glow
        radius = 8
        color = (60, 230, 60) if hovered else (0, 200, 0)
        pygame.draw.rect(surface, color, self._endturn_rect, border_radius=radius)
        if glow > 0.01:
            ew, eh = self._endturn_rect.size
            ex, ey = self._endturn_rect.topleft
            glow_surf = pygame.Surface((ew + 24, eh + 24), pygame.SRCALPHA)
            for ring in range(5):
                ring_alpha = int(glow * (40 - ring * 7))
                if ring_alpha <= 0:
                    continue
                offset = ring * 2 + 2
                pygame.draw.rect(glow_surf, (60, 255, 60, ring_alpha),
                    (12 - offset, 12 - offset, ew + offset * 2, eh + offset * 2),
                    border_radius=radius + offset, width=2)
            surface.blit(glow_surf, (ex - 12, ey - 12))
        end_font = self.font_bold if hovered else self.font
        end_label = end_font.render("END TURN", True, (0, 0, 0))
        surface.blit(end_label, end_label.get_rect(center=self._endturn_rect.center))

        # top title + stats line (with mini flag)
        base_title = "OPERATIONAL COMMAND"
        info_x = 20
        info_y = 15
        title_surface = self.title_font.render(base_title, True, (200, 170, 80))
        surface.blit(title_surface, (info_x, info_y))

        flag_img = None
        if self.playercountry:
            key = str(self.playercountry).strip().lower().replace(" ", "_").replace("-", "_")
            flag_img = pygame.transform.smoothscale(
                self._flags.get(key),
                (20, 14)
            ) if self._flags.get(key) else None
        stats_x = info_x + title_surface.get_width() + 18
        stats_y = info_y + 2
        if flag_img:
            surface.blit(flag_img, (stats_x, stats_y + 1))
            stats_x += flag_img.get_width() + 8

        country_text = str(self.playercountry or "None")
        stats_text = (
            f"{country_text} | Gold {int(self.playergold)} | Turn {int(self.currentturnnumber)} | "
            f"Pop {int(self.playerpopulation)} | Active MP {int(self._active_manpower)} | "
            f"Stability {self.playerstability:.0f} | PP {int(self.playerpp)} | AP {int(self.playerap)}"
        )
        surface.blit(self.font.render(stats_text, True, (220, 220, 220)), (stats_x, stats_y + 2))

        # troop badges on top of the map (map-local centers need viewport offset)
        visiblebadgelist = gui_mergetroopbadgeentries(self._troopbadgelist, self.font, self._badge_flags)
        for entry in visiblebadgelist:
            if not isinstance(entry, dict):
                continue
            center = entry.get("center")
            if not center:
                continue
            cx = int(center[0] + self.map_rect.x)
            cy = int(center[1] + self.map_rect.y)
            gui_drawtroopcountbadge(
                surface,
                (cx, cy),
                entry.get("troops", 0),
                self.font,
                self._badge_flags,
                entry.get("country"),
                backgroundcolor=entry.get("backgroundcolor", (0, 0, 0)),
                bordercolor=entry.get("bordercolor", (165, 165, 165)),
                rows=entry.get("rows"),
            )

        # hover tooltip (full-window coords) must be on top of badges
        if self._hovertext:
            tooltip_lines = []
            if isinstance(self._hovertext, dict):
                name = self._hovertext.get("name", "unknown")
                provinceid = self._hovertext.get("provinceid", "unknown")
                population = self._hovertext.get("population", "unknown")
                country = self._hovertext.get("country", "unknown")
                terrain = self._hovertext.get("terrain", "unknown")
                province_count = self._hovertext.get("province_count", "unknown")
                vp = self._hovertext.get("victory_points", 0)
                
                tooltip_lines = [
                    f"State: {name}",
                    f"Province: {provinceid}",
                    f"Population: {population}",
                    f"Country: {country}",
                    f"Terrain Type: {terrain}",
                    f"Number of states: {province_count}",
                ]
                
                if vp > 0:
                    tooltip_lines.append(f"Victory Points: {vp}")
                
            else:
                tooltip_lines = [str(self._hovertext)]

            padding = 8
            text_surfs = [self.font.render(line, True, (255, 255, 255)) for line in tooltip_lines]
            box_w = max(ts.get_width() for ts in text_surfs) + padding * 2
            box_h = sum(ts.get_height() for ts in text_surfs) + padding * 2

            mx, my = self._hovermousepos
            x = int(mx + 16)
            y = int(my + 16)
            x = max(0, min(surface.get_width() - box_w, x))
            y = max(0, min(surface.get_height() - box_h, y))
            rect = pygame.Rect(x, y, box_w, box_h)

            pygame.draw.rect(surface, (20, 20, 20), rect)
            pygame.draw.rect(surface, (255, 200, 0), rect, 2)
            ty = rect.y + padding
            for ts in text_surfs:
                surface.blit(ts, (rect.x + padding, ty))
                ty += ts.get_height()

        if self.focusview.isopen:
            self.focusview.draw(surface, self.title_font, self.font, mouse)
            if self.pausemenuopen:
                self._draw_pausemenu(surface)
            return

        if self.researchview.isopen:
            self.researchview.draw(surface, self.title_font, self.font, mouse)
            if self.pausemenuopen:
                self._draw_pausemenu(surface)
            return

        selected_tab = self.bottom_buttons.selected
        if not self.rightbar.rect.width:
            if self.pausemenuopen:
                self._draw_pausemenu(surface)
            return
                
       

        content_rect = self.rightbar.rect.inflate(-24, -24)
        content_rect.topleft = (self.rightbar.rect.x + 12, self.rightbar.rect.y + 12)

        # base panel — fill full rect first so padding isn't transparent under overlays
        pygame.draw.rect(surface, (18, 18, 18), self.rightbar.rect, border_radius=2)
        pygame.draw.rect(surface, (25, 25, 25), self.rightbar.rect, 1, border_radius=2)
        pygame.draw.rect(surface, (18, 18, 18), content_rect, border_radius=2)

        header = self.font.render(str(selected_tab or ""), True, (210, 210, 210))
        surface.blit(header, (content_rect.x, content_rect.y))

        y_cursor = content_rect.y + 24

        # Country menu overrides all tabs (only shown when needed)
        if self._countrymenutarget:
            alreadyatwar = self._countrymenutarget in self._countriesatwarset
            surface.blit(self.font.render("Country actions", True, (240, 240, 240)), (content_rect.x, y_cursor + 6))
            country_key = str(self._countrymenutarget or "").strip().lower().replace(" ", "_").replace("-", "_")
            flag_img = self._flags.get(country_key) if country_key else None
            draw_x = content_rect.x
            draw_y = y_cursor + 30
            if flag_img:
                surface.blit(flag_img, (draw_x, draw_y + 2))
                draw_x += flag_img.get_width() + 6
            surface.blit(self.font.render(str(self._countrymenutarget), True, (220, 220, 220)), (draw_x, draw_y))
            status = "Status: at war" if alreadyatwar else "Status: peace"
            surface.blit(self.font.render(status, True, (205, 205, 215)), (content_rect.x, y_cursor + 52))
            self._declarewar_rect.topleft = (content_rect.x, y_cursor + 82)
            self._draw_glow_btn(
                surface, "declarewar", self._declarewar_rect,
                not alreadyatwar,
                "Declare War" if not alreadyatwar else "Already at war!",
                mouse=mouse,
            )
            y_cursor += 130

        elif self.active_left_tab == "COMBAT" and not self._countrymenutarget:
            surface.blit(self.font.render("War Operations", True, (240, 240, 240)), (content_rect.x, y_cursor))
            self._war_progress_rect.topleft = (content_rect.x, y_cursor + 30)
            self._draw_glow_btn(
                surface, "warprogress", self._war_progress_rect,
                True, "WAR PROGRESS", mouse=mouse,
            )
            y_cursor += 80

        elif self._selectedmapcountry and not self._countrymenutarget:
            big_flag = self._get_big_flag(self._selectedmapcountry, size=(240, 144))
            y_cursor = content_rect.y + 45
            if big_flag:
                flag_x = content_rect.x + (content_rect.width - big_flag.get_width()) // 2
                surface.blit(big_flag, (flag_x, y_cursor))
                y_cursor += big_flag.get_height() + 16

            name_surf = self.title_font.render(str(self._selectedmapcountry), True, (240, 240, 240))
            surface.blit(name_surf, (content_rect.x, y_cursor))
            y_cursor += name_surf.get_height() + 8

            stats = self._selected_country_stats or {}
            lines = [
                f"Population: {self._format_number(stats.get('population', 0))}",
                f"Manpower:   {self._format_number(stats.get('manpower', 0))}",
                f"Stability:  {self._format_decimal(stats.get('stability', 0))}%",
                f"Leader:     {stats.get('leader', 'Unknown')}",
            ]
            for line in lines:
                surface.blit(self.font.render(line, True, (212, 212, 212)), (content_rect.x, y_cursor))
                y_cursor += 20

        
        elif selected_tab == "RECRUIT":
           
            self._recruit_action_rect.topleft = (content_rect.x, self._split_rect.y - 44)
            recruit_label = f"RECRUIT +{int(self.recruitamount)}"
            self._draw_glow_btn(
                surface, "recruit", self._recruit_action_rect,
                self.recruitenabled, recruit_label, primary=True, mouse=mouse,
            )
            y_cursor = max(y_cursor, content_rect.y + 24)

        # Troop info + decision buttons only show in RECRUIT tab, and only when troops > 0
        if selected_tab == "RECRUIT" and not self._countrymenutarget and self.active_left_tab != "COMBAT" and not self._selectedmapcountry:
            selected = [e for e in (self._selectedtroopentries or []) if isinstance(e, dict)]
            totaltroops = sum(max(0, int(e.get("troops", 0))) for e in selected)
            if totaltroops > 0:
                header_y = content_rect.y + 60
                surface.blit(self.font.render("Selected Troops", True, (240, 240, 240)), (content_rect.x, header_y))
                summary = self.font.render(
                    f"{len(selected)} province{'s' if len(selected) != 1 else ''}  |  Total: {totaltroops}",
                    True, (210, 210, 210),
                )
                surface.blit(summary, (content_rect.x, header_y + 22))

                list_top = header_y + 46
                list_bottom = min(self._recruit_action_rect.y, self._split_rect.y) - 10
                maxrows = max(0, (list_bottom - list_top) // 22)
                maxrows = min(10, maxrows)

                col_x = content_rect.x
                row_h = 20
                for i in range(maxrows):
                    if i >= len(selected):
                        break
                    if i % 2 == 1:
                        pygame.draw.rect(surface, (24, 24, 24),
                            (col_x, list_top + i * (row_h + 2), content_rect.width, row_h),
                            border_radius=2)
                    prov = selected[i].get("provinceid", "unknown")
                    troops = int(selected[i].get("troops", 0))
                    troop_str = self.font.render(f"{troops:,}", True, (200, 220, 200))
                    prov_str = self.font.render(prov, True, (210, 210, 210))
                    surface.blit(prov_str, (col_x, list_top + i * (row_h + 2)))
                    surface.blit(troop_str,
                        (content_rect.right - troop_str.get_width(), list_top + i * (row_h + 2)))

                if len(selected) > maxrows and maxrows > 0:
                    overflow = len(selected) - maxrows
                    surface.blit(self.font.render(f"... +{overflow} more", True, (170, 170, 170)),
                        (col_x, list_top + (maxrows - 1) * (row_h + 2) + row_h))

                split_enabled = totaltroops > 1
                merge_enabled = len(selected) > 1
                frontline_label = "CANCEL" if self._frontlineplacementmode else "frontline"
                self._draw_glow_btn(surface, "split", self._split_rect, split_enabled, "split", mouse=mouse)
                self._draw_glow_btn(surface, "merge", self._merge_rect, merge_enabled, "merge", mouse=mouse)
                self._draw_glow_btn(surface, "frontline", self._frontline_rect, True, frontline_label, mouse=mouse)

           
            if self.pausemenuopen:
                self._draw_pausemenu(surface)
    
        elif self.pausemenuopen:
            self._draw_pausemenu(surface)


    def _draw_glow_btn(self, surface, key, rect, enabled, label, primary=False, mouse=None):
        if mouse is None:
            mouse = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse) and enabled
        glow = self._button_glows.get(key, 0.0)
        if hovered:
            glow = min(1.0, glow + 0.12)
        else:
            glow = max(0.0, glow - 0.08)
        self._button_glows[key] = glow

        radius = 8
        if primary:
            color = (60, 230, 60) if hovered else ((0, 200, 0) if enabled else (70, 70, 70))
        else:
            color = (80, 160, 240) if hovered else ((56, 116, 198) if enabled else (70, 70, 70))

        pygame.draw.rect(surface, color, rect, border_radius=radius)

        if glow > 0.01 and enabled:
            w, h = rect.size
            glow_surf = pygame.Surface((w + 24, h + 24), pygame.SRCALPHA)
            for ring in range(5):
                ring_alpha = int(glow * (40 - ring * 7))
                if ring_alpha <= 0:
                    continue
                offset = ring * 2 + 2
                gw = w + offset * 2
                gh = h + offset * 2
                pygame.draw.rect(glow_surf, (60, 255, 60, ring_alpha),
                    (12 - offset, 12 - offset, gw, gh),
                    border_radius=radius + offset, width=2)
            surface.blit(glow_surf, (rect.x - 12, rect.y - 12))

        if hovered:
            text_color = (0, 0, 0)
            fnt = self.font_bold
        elif primary and enabled:
            text_color = (0, 0, 0)
            fnt = self.font
        else:
            text_color = (240, 240, 240) if enabled else (170, 170, 170)
            fnt = self.font
        txt = fnt.render(label, True, text_color)
        surface.blit(txt, txt.get_rect(center=rect.center))

    def _draw_pausemenu(self, surface: pygame.Surface):
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, 0))

        pygame.draw.rect(surface, (28, 28, 28), self._pausemenu_rect, border_radius=4)
        pygame.draw.rect(surface, (25, 25, 25), self._pausemenu_rect, 1, border_radius=4)

        title = self.title_font.render("PAUSED", True, (230, 230, 230))
        surface.blit(title, title.get_rect(center=(self._pausemenu_rect.centerx, self._pausemenu_rect.y + 34)))

        info = self.font.render("Press ESC to resume", True, (200, 200, 200))
        surface.blit(info, info.get_rect(center=(self._pausemenu_rect.centerx, self._pausemenu_rect.y + 72)))

        pygame.draw.rect(surface, (180, 60, 60), self._pausequit_rect)
        pygame.draw.rect(surface, (25, 25, 25), self._pausequit_rect, 1)
        quit_label = self.font.render("QUIT GAME", True, (255, 255, 255))
        surface.blit(quit_label, quit_label.get_rect(center=self._pausequit_rect.center))
