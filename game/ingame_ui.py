import ctypes
import os

import pygame

from .focusui import FocusTreeView

ctypes.windll.user32.SetProcessDPIAware()

def _badge_text_color(backgroundcolor):
    r, g, b = (backgroundcolor + (0, 0, 0))[:3] if isinstance(backgroundcolor, tuple) else (0, 0, 0)

    yellowish = r >= 200 and g >= 180 and b <= 90
    orangish = r >= 200 and 100 <= g <= 190 and b <= 90

    if yellowish or orangish:
        return (0, 0, 0)

    brightness = (r * 0.299 + g * 0.587 + b * 0.114)
    return (0, 0, 0) if brightness > 186 else (255, 255, 255)



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

    def set_items(self, items: list[str]):
        self.items = list(items)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, mouse_pos):
        pygame.draw.rect(surface, (50, 50, 50), self.rect)
        pygame.draw.rect(surface, (25, 25, 25), self.rect, 1)

        self.item_rects = {}
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

            if "CLEAR ALL" in item:
                color = (0, 120, 0) if rect.collidepoint(mouse_pos) else (0, 220, 0)
            else:
                color = (0, 200, 0) if rect.collidepoint(mouse_pos) else (30, 30, 30)

            pygame.draw.rect(surface, color, rect)
            text_color = (0, 0, 0) if "CLEAR ALL" in item else (255, 255, 255)
            text = font.render(item, True, text_color)
            surface.blit(text, (x + 10, y + 10))


class BottomButtons:
    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.items: list[str] = []
        self.item_rects: dict[str, pygame.Rect] = {}
        self.selected: str | None = None

    def set_items(self, items: list[str]):
        self.items = list(items)
        if self.selected not in self.items:
            self.selected = (self.items[-1] if self.items else None)

    def set_selected(self, item: str | None):
        if item in self.items:
            self.selected = item

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, mouse_pos):
        w = 120
        h = 30
        spacing = 10
        total_width = len(self.items) * w + (len(self.items) - 1) * spacing if self.items else 0
        available_width = max(0, self.rect.width)
        start_x = self.rect.x + max(0, (available_width - total_width) // 2)

        self.item_rects = {}
        for i, item in enumerate(self.items):
            x = start_x + (i * (w + spacing))
            y = self.rect.y + 10
            rect = pygame.Rect(x, y, w, h)
            self.item_rects[item] = rect

            if item == self.selected:
                color = (0, 220, 0)
            else:
                color = (0, 200, 0) if rect.collidepoint(mouse_pos) else (30, 30, 30)
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, (25, 25, 25), rect, 1)

            text = font.render(item, True, (255, 255, 255))
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

    def __init__(self, window_size):
        self.window_size = window_size
        self.title_font = pygame.font.SysFont("Verdana", 16, bold=True)
        self.font = pygame.font.SysFont("Verdana", 14)

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
        self._active_manpower = 0
        self._manpower_cache_key = None

        self.recruitamount = 0
        self.recruitenabled = False
        self._countrymenutarget = None
        self._selectedmapcountry = None
        self._bigflags = {}
        self._countriesatwarset = set()
        self._selectedtroopentries = []
        self._frontlineplacementmode = False
        self._troopbadgelist = []
        self._hovertext = None
        self._hovermousepos = (0, 0)
        self.focusview = FocusTreeView()
        self.pausemenuopen = False
        self.active_left_tab = None
        self.warprogressopen = False
        self._warprogressdata = {}
        self.actionwarprogress = "warprogress"

        self._flags = self._load_flags()

        self._choose_rect = pygame.Rect(0, 0, 160, 34)
        self._endturn_rect = pygame.Rect(0, 0, 10, 10)  # placed near map bottom-right

        # right panel interactive rects (computed in applylayout)
        self._recruit_action_rect = pygame.Rect(0, 0, 10, 10)
        self._declarewar_rect = pygame.Rect(0, 0, 10, 10)
        self._split_rect = pygame.Rect(0, 0, 10, 10)
        self._merge_rect = pygame.Rect(0, 0, 10, 10)
        self._frontline_rect = pygame.Rect(0, 0, 10, 10)

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
        self.bottom_buttons.set_selected("RESEARCH")

        self.topbar = Panel(pygame.Rect(0, 0, 10, 10), (0, 0, 0))
        self.rightbar = Panel(pygame.Rect(0, 0, 10, 10), (0, 0, 0))
        self.bottombar = Panel(pygame.Rect(0, 0, 10, 10), (29, 29, 29))
        self.pause_menu = pygame.Rect(0,0,10,10)
        self.quit_menu = pygame.Rect(0,0,10,10)
        self.map_rect = pygame.Rect(0, 0, 10, 10)
        self.applylayout()

    def _load_flags(self):
        flags = {}
        flag_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "flags"))
        if not os.path.isdir(flag_path):
            return flags

        for filename in os.listdir(flag_path):
            if not filename.lower().endswith(".png"):
                continue
            filepath = os.path.join(flag_path, filename)
            if not os.path.isfile(filepath):
                continue

            country_key = os.path.splitext(filename)[0].strip().lower().replace(" ", "_").replace("-", "_")
            if not country_key:
                continue

            try:
                img = pygame.image.load(filepath).convert_alpha()
            except pygame.error:
                continue

            flags[country_key] = pygame.transform.scale(img, (20, 14))

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

        # chrome visibility depends on phase + whether right tab has content
        if self.gamephase == "choosecountry":
            show_left = False
            show_bottom = False
            show_right = False
        else:
            show_left = True
            show_bottom = True
            show_right = bool(
                self._countrymenutarget
                or self._selectedtroopentries
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
        btn_h = 34
        btn_y = (self.rightbar.rect.bottom - 12 - btn_h) if self.rightbar.rect.width else (self.map_rect.bottom - 12 - btn_h)
        self._split_rect = pygame.Rect(content_x, btn_y, btn_w, btn_h)
        self._merge_rect = pygame.Rect(content_x + btn_w + 10, btn_y, btn_w, btn_h)
        self._frontline_rect = pygame.Rect(content_x + (btn_w + 10) * 2, btn_y, btn_w, btn_h)
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

    def _get_big_flag(self, country_name, size=(200, 150)):
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
        warprogressdata=None,
    ):
        self.gamephase = gamephase
        self.pendingcountry = pendingcountry
        self.playercountry = playercountry
        self.currentturnnumber = currentturnnumber
        self.playergold = playergold
        self.playerpopulation = playerpopulation
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
        # reflow after state changes (tab visibility depends on selection/menu)
        if warprogressdata is not None:
            self._warprogressdata = warprogressdata
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
            return self.focusview.handleevent(event)

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

        # bottom tabs
        for item, rect in (self.bottom_buttons.item_rects or {}).items():
            if rect.collidepoint(pos):
        
                self.bottom_buttons.set_selected(item)
                return None

        # bottom end turn
        if self._endturn_rect.collidepoint(pos):
            return self.actionendturn

        selected_tab = self.bottom_buttons.selected

        # right panel: country menu overrides all tabs
        if self._countrymenutarget:
            if self._declarewar_rect.collidepoint(pos):
                alreadyatwar = self._countrymenutarget in self._countriesatwarset
                if not alreadyatwar:
                    return self.actiondeclarewar
            return None

        # right panel: recruit action only visible in RECRUIT tab

        if self.active_left_tab == "COMBAT" and not self._countrymenutarget:
            if self._war_progress_rect.collidepoint(pos):
                self.warprogressopen = not self.warprogressopen
                return self.actionwarprogress
        if selected_tab == "RECRUIT":
            if self._recruit_action_rect.collidepoint(pos):
                if self.recruitenabled:
                    return self.actionrecruit
                return None

        # troop selection actions (only in RECRUIT tab and only when troops > 0)
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
            self.leftbar.draw(surface, self.font, mouse)
        if self.rightbar.rect.width:
            self.rightbar.draw(surface)
        if self.bottombar.rect.height:
            self.bottombar.draw(surface)
            self.bottom_buttons.draw(surface, self.font, mouse)
        self.topbar.draw(surface)

        # end turn button (bottom-right of map)
        pygame.draw.rect(surface, (0, 200, 0), self._endturn_rect)
        pygame.draw.rect(surface, (25, 25, 25), self._endturn_rect, 1)
        end_label = self.font.render("END TURN", True, (0, 0, 0))
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
            flag_img = self._flags.get(key)
        stats_x = info_x + title_surface.get_width() + 18
        stats_y = info_y + 2
        if flag_img:
            surface.blit(flag_img, (stats_x, stats_y + 1))
            stats_x += flag_img.get_width() + 8

        country_text = str(self.playercountry or "None")
        stats_text = (
            f"{country_text} | Gold {int(self.playergold)} | Turn {int(self.currentturnnumber)} | "
            f"Pop {int(self.playerpopulation)} | Active MP {int(self._active_manpower)} | "
            f"Stability -- | PP -- | AP --"
        )
        surface.blit(self.font.render(stats_text, True, (220, 220, 220)), (stats_x, stats_y + 2))

        # troop badges on top of the map (map-local centers need viewport offset)
        for entry in self._troopbadgelist:
            if not isinstance(entry, dict):
                continue
            center = entry.get("center")
            if not center:
                continue
            cx = int(center[0] + self.map_rect.x)
            cy = int(center[1] + self.map_rect.y)
            troops = int(entry.get("troops", 0))
            country_name = entry.get("country")
            country_key = str(country_name or "").strip().lower().replace(" ", "_").replace("-", "_")
            flag_img = self._flags.get(country_key) if country_key else None

            background = entry.get("backgroundcolor", (0, 0, 0))
            text_color = _badge_text_color(background)
            label = self.font.render(str(troops), True, text_color)
            pad_x, pad_y = 6, 4
            spacing = 4
            content_w = label.get_width() + (flag_img.get_width() + spacing if flag_img else 0)
            content_h = max(label.get_height(), flag_img.get_height() if flag_img else 0)
            rect = pygame.Rect(0, 0, content_w + pad_x * 2, content_h + pad_y * 2)
            rect.center = (cx, cy)
            background = entry.get("backgroundcolor", (0, 0, 0))
            border = entry.get("bordercolor", (165, 165, 165))
            pygame.draw.rect(surface, background, rect, border_radius=4)
            pygame.draw.rect(surface, border, rect, 1, border_radius=4)

            draw_x = rect.x + pad_x
            center_y = rect.y + rect.height // 2
            if flag_img:
                surface.blit(flag_img, (draw_x, center_y - flag_img.get_height() // 2))
                draw_x += flag_img.get_width() + spacing
            surface.blit(label, (draw_x, center_y - label.get_height() // 2))

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


        selected_tab = self.bottom_buttons.selected
        if not self.rightbar.rect.width:
            if self.pausemenuopen:
                self._draw_pausemenu(surface)
            return
                
       

        content_rect = self.rightbar.rect.inflate(-24, -24)
        content_rect.topleft = (self.rightbar.rect.x + 12, self.rightbar.rect.y + 12)

        # base panel
        pygame.draw.rect(surface, (18, 18, 18), content_rect, border_radius=2)
        pygame.draw.rect(surface, (25, 25, 25), content_rect, 1, border_radius=2)

        header = self.font.render(str(selected_tab or ""), True, (210, 210, 210))
        surface.blit(header, (content_rect.x, content_rect.y))

        def draw_btn(rect, enabled, label, primary=False):
            if primary:
                color = (0, 200, 0) if enabled else (70, 70, 70)
                text_color = (0, 0, 0) if enabled else (170, 170, 170)
            else:
                color = (56, 116, 198) if enabled else (70, 70, 70)
                text_color = (240, 240, 240) if enabled else (170, 170, 170)
            pygame.draw.rect(surface, color, rect, border_radius=1)
            pygame.draw.rect(surface, (35, 35, 35), rect, 1, border_radius=1)
            txt = self.font.render(label, True, text_color)
            surface.blit(txt, txt.get_rect(center=rect.center))

        y_cursor = content_rect.y + 24

        # Country menu overrides all tabs (only shown when needed)
        if self._countrymenutarget:
            alreadyatwar = self._countrymenutarget in self._countriesatwarset
            surface.blit(self.font.render("Country actions", True, (240, 240, 240)), (content_rect.x, y_cursor + 6))
            # country identity (no glow; map highlight handles the emphasis)
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
            # button gets its own row (no overlap)
            self._declarewar_rect.topleft = (content_rect.x, y_cursor + 82)
            draw_btn(
                self._declarewar_rect,
                not alreadyatwar,
                "Declare War" if not alreadyatwar else "Already at war!",
                primary=False,
            )
            y_cursor += 130

        # Recruit action only shows in RECRUIT tab (and only when no country menu)

        elif self.active_left_tab == "COMBAT" and not self._countrymenutarget:
            surface.blit(self.font.render("War Operations", True, (240, 240, 240)), (content_rect.x, y_cursor))
            self._war_progress_rect.topleft = (content_rect.x, y_cursor + 30)
            draw_btn(
                self._war_progress_rect, 
                True, 
                "WAR PROGRESS", 
                primary=False
            )
            y_cursor += 80

        elif self._selectedmapcountry and not self._countrymenutarget:
            big_flag = self._get_big_flag(self._selectedmapcountry, size=(200, 150))
            y_cursor = content_rect.y + 12
            if big_flag:
                flag_x = content_rect.x + (content_rect.width - big_flag.get_width()) // 2
                surface.blit(big_flag, (flag_x, y_cursor))
                y_cursor += big_flag.get_height() + 16
            name_surf = self.title_font.render(str(self._selectedmapcountry), True, (240, 240, 240))
            surface.blit(name_surf, (content_rect.x, y_cursor))
        elif selected_tab == "RECRUIT":
            # place recruit action near troop decision buttons
            self._recruit_action_rect.topleft = (content_rect.x, self._split_rect.y - 44)
            recruit_label = f"RECRUIT +{int(self.recruitamount)}"
            draw_btn(self._recruit_action_rect, self.recruitenabled, recruit_label, primary=True)
            y_cursor = max(y_cursor, content_rect.y + 24)

        # Troop info + decision buttons only show in RECRUIT tab, and only when troops > 0
        if selected_tab == "RECRUIT" and not self._countrymenutarget:
            selected = [e for e in (self._selectedtroopentries or []) if isinstance(e, dict)]
            totaltroops = sum(max(0, int(e.get("troops", 0))) for e in selected)
            if totaltroops > 0:
                # fixed layout: header/list region above recruit+buttons
                header_y = content_rect.y + 60
                surface.blit(self.font.render("Troops", True, (240, 240, 240)), (content_rect.x, header_y))
                surface.blit(
                    self.font.render(f"{len(selected)} selected (Total: {totaltroops})", True, (210, 210, 210)),
                    (content_rect.x, header_y + 22),
                )

                list_top = header_y + 46
                list_bottom = min(self._recruit_action_rect.y, self._split_rect.y) - 10
                maxrows = max(0, (list_bottom - list_top) // 20)
                maxrows = min(10, maxrows)
                for i in range(maxrows):
                    if i >= len(selected):
                        break
                    prov = selected[i].get("provinceid", "unknown")
                    troops = int(selected[i].get("troops", 0))
                    line = f"{prov}: {troops}"
                    surface.blit(self.font.render(line, True, (210, 210, 210)), (content_rect.x, list_top + i * 20))
                if len(selected) > maxrows and maxrows > 0:
                    overflow = len(selected) - maxrows
                    surface.blit(self.font.render(f"... +{overflow} more", True, (170, 170, 170)), (content_rect.x, list_top + (maxrows - 1) * 20))

                split_enabled = totaltroops > 1
                merge_enabled = len(selected) > 1
                draw_btn(self._split_rect, split_enabled, "split")
                draw_btn(self._merge_rect, merge_enabled, "merge")
                draw_btn(self._frontline_rect, True, "CANCEL" if self._frontlineplacementmode else "frontline")

           
            if self.pausemenuopen:
                self._draw_pausemenu(surface)
    
        elif self.pausemenuopen:
            self._draw_pausemenu(surface)


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
