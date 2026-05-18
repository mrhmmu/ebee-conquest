import ctypes
import math
import os
from datetime import date, timedelta

import pygame

from engine.gui import gui_drawtroopcountbadge, gui_mergetroopbadgeentries
from .focusui import FocusTreeView
from .researchui import ResearchTreeView

ctypes.windll.user32.SetProcessDPIAware()

_C_BG0 = (11, 18, 32)
_C_BG1 = (17, 24, 39)
_C_PANEL = (23, 32, 51)
_C_PANEL_DARK = (12, 18, 29)
_C_PANEL_HOVER = (28, 39, 59)
_C_GOLD = (212, 169, 77)
_C_GOLD_BRIGHT = (240, 198, 116)
_C_STEEL = (132, 145, 160)
_C_TEXT = (229, 231, 235)
_C_TEXT_MUTED = (156, 163, 175)
_C_SUCCESS = (67, 181, 129)
_C_DANGER = (224, 93, 93)
_C_INFO = (74, 143, 231)


class Panel:
    def __init__(self, rect: pygame.Rect, color=(40, 40, 40)):
        self.rect = rect
        self.color = color

    def draw(self, surface: pygame.Surface):
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.rect(surface, (45, 56, 70), self.rect, 1)


class LeftBar:
    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.items: list[str] = []
        self.item_rects: dict[str, pygame.Rect] = {}
        self._hover_glow = {}
        # rolling FPS history for status graph (42 samples)
        self._fps_history: list[float] = [0.0] * 42

    def set_items(self, items: list[str]):
        self.items = list(items)
        self._hover_glow = {}

    @staticmethod
    def _fit_text(font, text, max_width):
        text = str(text)
        if font.size(text)[0] <= max_width:
            return text
        suffix = "..."
        available_width = max(0, max_width - font.size(suffix)[0])
        fitted = ""
        for character in text:
            candidate = fitted + character
            if font.size(candidate)[0] > available_width:
                break
            fitted = candidate
        return fitted.rstrip() + suffix if fitted else suffix

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        mouse_pos,
        font_bold=None,
        icons=None,
        selected=None,
        statusdata=None,
        notification_count=0,
    ):
        icons = icons or {}
        statusdata = statusdata or {}
        notification_count = max(0, int(notification_count or 0))
        pygame.draw.rect(surface, _C_PANEL_DARK, self.rect)
        pygame.draw.rect(surface, (28, 38, 52), self.rect, 1)
        pygame.draw.line(surface, (76, 64, 38), self.rect.topright, self.rect.bottomright, 1)

        self.item_rects = {}
        radius = 6
        item_index = 0
        for item in self.items:
            item_text = str(item).strip()
            if not item_text:
                divider_y = self.rect.y + 22 + item_index * 60
                pygame.draw.line(
                    surface,
                    (76, 64, 38),
                    (self.rect.x + 14, divider_y),
                    (self.rect.right - 14, divider_y),
                    1,
                )
                continue

            x = self.rect.x + 14
            y = self.rect.y + 16 + item_index * 66
            w = self.rect.width - 28
            h = 52
            rect = pygame.Rect(x, y, w, h)
            item_key = item_text.upper()
            self.item_rects[item_key] = rect
            item_index += 1

            hovered = rect.collidepoint(mouse_pos)
            glow = self._hover_glow.get(item_key, 0.0)
            if hovered:
                glow = min(1.0, glow + 0.16)
            else:
                glow = max(0.0, glow - 0.10)
            self._hover_glow[item_key] = glow

            is_selected = item_key == selected
            if "CLEAR ALL" in item_text:
                color = (35, 45, 47) if hovered else (20, 30, 36)
            elif is_selected:
                color = (37, 35, 28) if not hovered else (50, 44, 30)
            else:
                color = _C_PANEL_HOVER if hovered else (14, 22, 33)

            shadow = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
            pygame.draw.rect(shadow, (0, 0, 0, 75), shadow.get_rect(), border_radius=radius + 2)
            surface.blit(shadow, (x - 3, y - 1))
            pygame.draw.rect(surface, color, rect, border_radius=radius)
            if "CLEAR ALL" in item_text:
                bordercolor = (89, 110, 105) if hovered else (45, 61, 66)
            elif is_selected:
                bordercolor = _C_GOLD
            elif hovered:
                bordercolor = (88, 101, 118)
            else:
                bordercolor = (42, 55, 72)
            pygame.draw.rect(surface, bordercolor, rect, 1, border_radius=radius)

            if glow > 0.01:
                glowcolor = _C_GOLD if (is_selected or "CLEAR ALL" in item_text) else (92, 116, 144)
                glow_surf = pygame.Surface((w + 20, h + 20), pygame.SRCALPHA)
                for ring in range(4):
                    alpha = int(glow * (36 - ring * 7))
                    if alpha <= 0:
                        continue
                    offset = ring * 2 + 2
                    pygame.draw.rect(
                        glow_surf,
                        (*glowcolor, alpha),
                        (10 - offset, 10 - offset, w + offset * 2, h + offset * 2),
                        border_radius=radius + offset,
                        width=2,
                    )
                surface.blit(glow_surf, (x - 10, y - 10))

            if is_selected:
                pygame.draw.rect(surface, _C_GOLD, pygame.Rect(rect.x, rect.y + 8, 3, rect.height - 16), border_radius=2)

            icon = icons.get(item_key)
            icon_x = x + 18
            text_x = x + 54
            if icon is not None:
                icon_rect = icon.get_rect()
                icon_rect.topleft = (icon_x, y + (h - icon_rect.height) // 2)
                surface.blit(icon, icon_rect)
            else:
                text_x = x + 18

            badge_text = None
            badge_rect = None
            badge_reserved_width = 0
            if item_key == "NOTIFICATIONS" and notification_count > 0:
                badge_label = "99+" if notification_count > 99 else str(notification_count)
                badge_text = font_bold.render(badge_label, True, (11, 18, 32)) if font_bold else font.render(badge_label, True, (11, 18, 32))
                badge_rect = pygame.Rect(0, 0, max(20, badge_text.get_width() + 8), 20)
                badge_rect.center = (rect.right - 20, rect.centery)
                badge_reserved_width = badge_rect.width + 12

            text_color = (224, 228, 231) if hovered else (202, 207, 211)
            if "CLEAR ALL" in item_text:
                text_color = (224, 228, 216)
            if is_selected:
                text_color = (239, 224, 185)
            active_font = font_bold if (is_selected and font_bold) else font
            fitted_text = self._fit_text(active_font, item_text, rect.right - text_x - 12 - badge_reserved_width)
            text = active_font.render(fitted_text, True, text_color)
            surface.blit(text, (text_x, y + (h - text.get_height()) // 2))

            if badge_text is not None and badge_rect is not None:
                pygame.draw.rect(surface, _C_GOLD_BRIGHT, badge_rect, border_radius=4)
                surface.blit(badge_text, badge_text.get_rect(center=badge_rect.center))

        status_rect = pygame.Rect(self.rect.x + 14, self.rect.bottom - 202, self.rect.width - 28, 184)
        if status_rect.height > 0 and status_rect.top > self.rect.y + 430:
            shadow = pygame.Surface((status_rect.width + 8, status_rect.height + 8), pygame.SRCALPHA)
            pygame.draw.rect(shadow, (0, 0, 0, 90), shadow.get_rect(), border_radius=6)
            surface.blit(shadow, (status_rect.x - 3, status_rect.y - 2))
            pygame.draw.rect(surface, (9, 15, 24), status_rect, border_radius=6)
            pygame.draw.rect(surface, (42, 55, 72), status_rect, 1, border_radius=6)
            title = font.render("SYSTEM STATUS", True, _C_TEXT_MUTED)
            surface.blit(title, (status_rect.x + 14, status_rect.y + 14))
            graph_rect = pygame.Rect(status_rect.x + 14, status_rect.y + 46, status_rect.width - 28, 76)
            pygame.draw.rect(surface, (7, 12, 20), graph_rect, border_radius=4)
            for offset in range(1, 4):
                gy = graph_rect.y + offset * graph_rect.height // 4
                pygame.draw.line(surface, (26, 37, 51), (graph_rect.x, gy), (graph_rect.right, gy), 1)
            # update fps history from statusdata then draw graph from samples
            try:
                fps_sample = float(statusdata.get("fps", 0.0) or 0.0)
            except Exception:
                fps_sample = 0.0
            self._fps_history.append(fps_sample)
            if len(self._fps_history) > 42:
                self._fps_history = self._fps_history[-42:]

            samples = list(self._fps_history or [])
            if not samples:
                samples = [0.0] * 42
            # autoscale: at least 60 FPS range so small variations are visible
            max_scale = max(60.0, max(samples) if samples else 60.0)
            points = []
            sample_count = max(2, len(samples))
            for idx, sample in enumerate(samples):
                px = graph_rect.x + int(idx * graph_rect.width / (sample_count - 1))
                normalized = min(1.0, max(0.0, float(sample) / max_scale))
                # map normalized (0..1) so 0 is bottom, 1 is top of graph rect
                py = graph_rect.bottom - int(normalized * graph_rect.height)
                points.append((px, py))
            if len(points) >= 2:
                pygame.draw.lines(surface, _C_SUCCESS, False, points, 2)
            fps_value = float(statusdata.get("fps", 0.0) or 0.0)
            latency_value = float(statusdata.get("latency_ms", 0.0) or 0.0)
            fps_text = font.render(f"FPS {fps_value:4.1f}", True, _C_TEXT)
            latency_text = font.render(f"Frame {latency_value:4.1f} ms", True, _C_TEXT_MUTED)
            surface.blit(fps_text, (status_rect.x + 14, status_rect.bottom - 48))
            surface.blit(latency_text, (status_rect.x + 14, status_rect.bottom - 25))


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

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, mouse_pos, font_bold=None, icons=None):
        icons = icons or {}
        w = 142
        h = 64
        spacing = 8
        radius = 6
        total_width = len(self.items) * w + (len(self.items) - 1) * spacing if self.items else 0
        available_width = max(0, self.rect.width)
        start_x = self.rect.x + max(0, (available_width - total_width) // 2)
        dock_rect = pygame.Rect(start_x - 14, self.rect.y + 9, total_width + 28, h + 18)

        dock_shadow = pygame.Surface((dock_rect.width + 14, dock_rect.height + 14), pygame.SRCALPHA)
        pygame.draw.rect(dock_shadow, (0, 0, 0, 88), dock_shadow.get_rect(), border_radius=10)
        surface.blit(dock_shadow, (dock_rect.x - 7, dock_rect.y - 3))
        dock_surface = pygame.Surface(dock_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(dock_surface, (10, 15, 23, 176), dock_surface.get_rect(), border_radius=8)
        pygame.draw.rect(dock_surface, (44, 58, 76, 150), dock_surface.get_rect(), 1, border_radius=8)
        surface.blit(dock_surface, dock_rect.topleft)

        self.item_rects = {}
        for i, item in enumerate(self.items):
            x = start_x + (i * (w + spacing))
            y = self.rect.y + 18
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
                color = (36, 34, 27) if not hovered else (48, 42, 30)
            else:
                color = (26, 36, 52) if hovered else (15, 23, 35)

            card_shadow = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
            pygame.draw.rect(card_shadow, (0, 0, 0, 80), card_shadow.get_rect(), border_radius=radius + 2)
            surface.blit(card_shadow, (x - 3, y - 1))
            pygame.draw.rect(surface, color, rect, border_radius=radius)
            bordercolor = (177, 145, 70) if item == self.selected else ((82, 91, 101) if hovered else (58, 63, 70))
            pygame.draw.rect(surface, bordercolor, rect, 1, border_radius=radius)
            if item == self.selected:
                pygame.draw.line(surface, _C_GOLD_BRIGHT, (rect.x + 16, rect.y + 2), (rect.right - 16, rect.y + 2), 2)

            if glow > 0.01:
                glow_surf = pygame.Surface((w + 22, h + 22), pygame.SRCALPHA)
                for ring in range(5):
                    ring_alpha = int(glow * (28 - ring * 5))
                    if ring_alpha <= 0:
                        continue
                    offset = ring * 2 + 2
                    gw = w + offset * 2
                    gh = h + offset * 2
                    pygame.draw.rect(glow_surf, (*_C_GOLD, ring_alpha),
                        (11 - offset, 11 - offset, gw, gh),
                        border_radius=radius + offset, width=2)
                surface.blit(glow_surf, (x - 11, y - 11))

            text_color = (226, 230, 234) if hovered else (200, 205, 210)
            if item == self.selected and not hovered:
                text_color = (239, 224, 185)
            active_font = font_bold if (hovered and font_bold) else font
            icon = icons.get(item)
            if icon is not None:
                icon_rect = icon.get_rect(center=(rect.centerx, rect.y + 22))
                surface.blit(icon, icon_rect)
            text = active_font.render(item, True, text_color)
            text_rect = text.get_rect(center=(rect.centerx, rect.y + 48))
            surface.blit(text, text_rect)


class InGameUI:
    actionchoosecountry = "choosecountry"
    actionrecruit = "recruit"
    actionendturn = "endturn"
    actiondeclarewar = "declarewar"
    actionsplit = "split"
    actionmerge = "merge"
    actionfrontline = "frontline"
    actionautoadvance = "autoadvance"
    actiondetachregiment = "detachregiment"
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
        self.title_font = pygame.font.SysFont("bahnschrift", 22, bold=True)
        self.font = pygame.font.SysFont("segoeui", 14)
        self.font_bold = pygame.font.SysFont("segoeui", 14, bold=True)
        self.small_font = pygame.font.SysFont("segoeui", 11)
        self.small_font_bold = pygame.font.SysFont("segoeui", 11, bold=True)
        self.number_font = pygame.font.SysFont("bahnschrift", 17, bold=True)
        
        self.ui_click_sound = pygame.mixer.Sound("game/sounds/click.wav")
        self.ui_click_sound.set_volume(0.4)

        self.leftbar_width = 256
        self.topbar_height = 80
        # widened so troop/country panels fit "seamlessly" in the right tab
        self.rightbar_width = 380
        self.bottombar_height = 104

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
        self._systemstatus = {"fps": 0.0, "latency_ms": 0.0}
        self._notificationcount = 0
        self._startdate = date(2020, 1, 1)
        self._daysperturn = 5
        

        # rolling FPS history for status graph (42 samples)
        self._fps_history: list[float] = [0.0] * 42

        self._flags = self._load_flags()
        self._badge_flags = {
            key: pygame.transform.scale(img, (20, 14))
            for key, img in self._flags.items()
        }
        self._topbar_icons = self._load_topbar_icons()

        self._choose_rect = pygame.Rect(0, 0, 160, 34)
        self._endturn_rect = pygame.Rect(0, 0, 10, 10)  # placed near map bottom-right
        self._endturn_glow = 0.0
        self._button_glows: dict[str, float] = {}
        self._topbar_metric_rects = {}
        self._topbar_metric_data = {}
        self._topbar_metric_glows = {}
        self._active_topbar_metric = None
        self._topbar_metric_popup_rect = pygame.Rect(0, 0, 10, 10)
        self._topbar_metric_snapshot = {}
        self._topbar_metric_rates = {}
        self._topbar_metric_rate_turn = None

        # right panel interactive rects (computed in applylayout)
        self._recruit_action_rect = pygame.Rect(0, 0, 10, 10)
        self._declarewar_rect = pygame.Rect(0, 0, 10, 10)
        self._split_rect = pygame.Rect(0, 0, 10, 10)
        self._merge_rect = pygame.Rect(0, 0, 10, 10)
        self._frontline_rect = pygame.Rect(0, 0, 10, 10)
        self._auto_advance_rect = pygame.Rect(0, 0, 10, 10)
        self._detach_regiment_rects = {}
        self._research_btn_rects = [pygame.Rect(0, 0, 10, 10) for _ in range(4)]
        self._research_back_rect = pygame.Rect(0, 0, 10, 10)
        self._warprogress_popup_rect = pygame.Rect(0, 0, 10, 10)
        self._warprogress_close_rect = pygame.Rect(0, 0, 10, 10)
        self._warprogress_header_rect = pygame.Rect(0, 0, 10, 10)
        self._warprogress_tab_rects = []
        self._warprogress_popup_pos = None
        self._warprogress_dragging = False
        self._warprogress_drag_offset = (0, 0)
        self._warprogress_active_index = 0
        self.production_popup_open = False
        self._production_popup_back_rect = pygame.Rect(0, 0, 10,10)
        self._production_selection_rects = [pygame.Rect(0, 0, 10,10) for _ in range(4)]
        self.production_selected = None
        self._recruit_action_rect = pygame.Rect(0, 0, 10, 10)
        self._declarewar_rect = pygame.Rect(0, 0, 10, 10)
        self._split_rect = pygame.Rect(0, 0, 10, 10)
        self._merge_rect = pygame.Rect(0, 0, 10, 10)
        self._frontline_rect = pygame.Rect(0, 0, 10, 10)
        self._production_blank_rect = pygame.Rect(0, 0, 10, 10)
        self._research_btn_rects = [pygame.Rect(0, 0, 10, 10) for _ in range(4)]

        self.leftbar = LeftBar(pygame.Rect(0, 0, 10, 10))
        self.bottom_buttons = BottomButtons(pygame.Rect(0, 0, 10, 10))

        self.leftbar.set_items(
            [
                "CLEAR ALL",
                "",
                "NOTIFICATIONS",
                "LOGISTICS",
                "COMBAT",
                "INTEL",
                "NATIONAL POLICY"
            ]
        )
        self.bottom_buttons.set_items(
            [
                "RESEARCH",
                "DIPLOMACY",
                "TRADE",
                "PRODUCTION",
                "CONSTRUCTION",
                "TROOPS",
            ]
        )
        self.bottom_buttons.set_selected(None)

        self.topbar = Panel(pygame.Rect(0, 0, 10, 10), _C_PANEL_DARK)
        self.rightbar = Panel(pygame.Rect(0, 0, 10, 10), _C_PANEL_DARK)
        self.bottombar = Panel(pygame.Rect(0, 0, 10, 10), (5, 10, 17))
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

    def _load_topbar_icons(self):
        icons = {}
        icon_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "images", "ui_icons")
        )
        icon_files = {
            "turn": "turn.svg",
            "date": "date.svg",
            "gold": "gold.svg",
            "population": "population.svg",
            "manpower": "manpower.svg",
            "stability": "stability.svg",
            "political_power": "political_power.svg",
            "action_points": "action_points.svg",
            "CLEAR ALL": "clear_all.svg",
            "NOTIFICATIONS": "notifications.svg",
            "LOGISTICS": "logistics.svg",
            "COMBAT": "combat.svg",
            "INTEL": "intel.svg",
            "NATIONAL POLICY": "national_policy.svg",
            "notifications": "notifications.svg",
            "logistics": "logistics.svg",
            "combat": "combat.svg",
            "intel": "intel.svg",
            "national_policy": "national_policy.svg",
            "RESEARCH": "research.svg",
            "DIPLOMACY": "diplomacy.svg",
            "TRADE": "trade.svg",
            "PRODUCTION": "production.svg",
            "CONSTRUCTION": "construction.svg",
            "TROOPS": "recruit.svg",
            "research": "research.svg",
            "diplomacy": "diplomacy.svg",
            "trade": "trade.svg",
            "production": "production.svg",
            "construction": "construction.svg",
            "recruit": "recruit.svg",
            "war_progress": "war_progress.svg",
            "occupation": "occupation.svg",
            "close": "close.svg",
        }

        for key, filename in icon_files.items():
            filepath = os.path.join(icon_path, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                image = pygame.image.load(filepath).convert_alpha()
                icons[key] = pygame.transform.smoothscale(image, (20, 20))
            except pygame.error:
                continue

        return icons

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
    def _format_compact_number(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0

        sign = "-" if number < 0 else ""
        number = abs(number)
        for suffix, divisor in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
            if number >= divisor:
                compact = number / divisor
                text = f"{compact:.1f}".rstrip("0").rstrip(".")
                return f"{sign}{text}{suffix}"
        return f"{sign}{int(number):,}"

    @staticmethod
    def _format_signed_compact_number(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        if abs(number) < 0.05:
            return "0"
        prefix = "+" if number > 0 else ""
        return f"{prefix}{InGameUI._format_compact_number(number)}"

    def _format_ingame_date(self):
        try:
            turnnumber = max(1, int(self.currentturnnumber))
        except (TypeError, ValueError):
            turnnumber = 1
        currentdate = self._startdate + timedelta(days=(turnnumber - 1) * self._daysperturn)
        return currentdate.strftime("%d/%m/%Y")

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

    def _draw_vertical_gradient_rect(self, surface, rect, top_color, bottom_color, radius=0):
        if rect.width <= 0 or rect.height <= 0:
            return
        gradient = pygame.Surface(rect.size, pygame.SRCALPHA)
        for y in range(rect.height):
            t = y / max(1, rect.height - 1)
            color = tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * t) for i in range(3))
            pygame.draw.line(gradient, (*color, 255), (0, y), (rect.width, y))
        if radius:
            mask = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
            gradient.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(gradient, rect.topleft)

    def _draw_glass_panel(self, surface, rect, radius=6, border=(58, 71, 89), glow=False):
        if glow:
            glow_surface = pygame.Surface((rect.width + 24, rect.height + 24), pygame.SRCALPHA)
            pygame.draw.rect(glow_surface, (212, 169, 77, 35), glow_surface.get_rect(), border_radius=radius + 8)
            surface.blit(glow_surface, (rect.x - 12, rect.y - 12))
        shadow = pygame.Surface((rect.width + 10, rect.height + 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 105), shadow.get_rect(), border_radius=radius + 2)
        surface.blit(shadow, (rect.x - 4, rect.y - 2))
        self._draw_vertical_gradient_rect(surface, rect, (22, 31, 48), (9, 15, 24), radius=radius)
        pygame.draw.rect(surface, border, rect, 1, border_radius=radius)
        pygame.draw.line(surface, (41, 49, 60), (rect.x + 8, rect.y + 1), (rect.right - 8, rect.y + 1), 1)

    def _draw_bottombar_background(self, surface):
        rect = self.bottombar.rect
        if rect.width <= 0 or rect.height <= 0:
            return
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(overlay, (4, 9, 16, 158), overlay.get_rect())
        pygame.draw.line(overlay, (212, 169, 77, 80), (0, 0), (rect.width, 0), 1)
        pygame.draw.line(overlay, (74, 143, 231, 35), (0, 1), (rect.width, 1), 1)
        surface.blit(overlay, rect.topleft)

    def _draw_topbar_background(self, surface):
        rect = self.topbar.rect
        if rect.width <= 0 or rect.height <= 0:
            return

        self._draw_vertical_gradient_rect(surface, rect, (13, 22, 36), (6, 10, 18))
        pygame.draw.line(surface, (25, 34, 47), rect.topleft, rect.topright, 1)
        pygame.draw.line(surface, (76, 64, 38), (rect.x, rect.bottom - 2), (rect.right, rect.bottom - 2), 1)
        pygame.draw.line(surface, _C_GOLD, (rect.x, rect.bottom - 1), (rect.right, rect.bottom - 1), 1)

    def _draw_map_edge_shadows(self, surface):
        rect = self.map_rect.clip(surface.get_rect())
        if rect.width <= 0 or rect.height <= 0:
            return

        edge_w = max(96, int(rect.width * 0.11))
        edge_w = max(1, min(rect.width // 2, edge_w))
        shadow = pygame.Surface((edge_w, rect.height), pygame.SRCALPHA)
        for step in range(edge_w):
            t = step / max(1, edge_w - 1)
            alpha = int(92 * (1.0 - t) ** 2.4)
            pygame.draw.line(shadow, (0, 0, 0, alpha), (step, 0), (step, rect.height))

        surface.blit(shadow, rect.topleft)
        right_shadow = pygame.transform.flip(shadow, True, False)
        surface.blit(right_shadow, (rect.right - edge_w, rect.y))

        # A narrow contact shadow under fixed panels gives depth without a boxed vignette.
        contact = pygame.Surface((rect.width, 18), pygame.SRCALPHA)
        for step in range(contact.get_height()):
            alpha = int(40 * (1.0 - step / max(1, contact.get_height() - 1)) ** 2)
            pygame.draw.line(contact, (0, 0, 0, alpha), (0, step), (rect.width, step))
        surface.blit(contact, rect.topleft)

    def _draw_resource_chip(
        self,
        surface,
        x,
        y,
        icon_key,
        label,
        value,
        max_right,
        accent=(200, 170, 80),
        metric_key=None,
        mouse=None,
    ):
        icon = self._topbar_icons.get(icon_key)
        metric_key = metric_key or icon_key
        mouse = mouse or pygame.mouse.get_pos()
        value = str(value)
        label = str(label)
        value_surface = self.number_font.render(value, True, _C_TEXT)
        label_surface = self.small_font.render(label, True, _C_TEXT_MUTED)
        chip_width = max(112, value_surface.get_width() + 68, label_surface.get_width() + 56)
        if icon_key == "date":
            chip_width = max(148, value_surface.get_width() + 68, label_surface.get_width() + 56)
        chip_height = 56

        if x + chip_width > max_right:
            return x, False

        rect = pygame.Rect(x, y, chip_width, chip_height)
        hovered = rect.collidepoint(mouse)
        active = metric_key == self._active_topbar_metric
        glow = self._topbar_metric_glows.get(metric_key, 0.0)
        if hovered or active:
            glow = min(1.0, glow + 0.14)
        else:
            glow = max(0.0, glow - 0.08)
        self._topbar_metric_glows[metric_key] = glow

        if glow > 0.01:
            glow_surface = pygame.Surface((rect.width + 24, rect.height + 24), pygame.SRCALPHA)
            for ring in range(4):
                ring_alpha = int(glow * (38 - ring * 7))
                if ring_alpha <= 0:
                    continue
                offset = ring * 2 + 2
                pygame.draw.rect(
                    glow_surface,
                    (*accent, ring_alpha),
                    (12 - offset, 12 - offset, rect.width + offset * 2, rect.height + offset * 2),
                    width=2,
                    border_radius=8 + offset,
                )
            surface.blit(glow_surface, (rect.x - 12, rect.y - 12))

        border = accent if active else ((72, 88, 111) if hovered else (48, 62, 80))
        self._draw_glass_panel(surface, rect, radius=6, border=border)
        pygame.draw.line(surface, accent, (rect.x + 8, rect.y + 9), (rect.x + 8, rect.bottom - 9), 2)

        draw_x = rect.x + 20
        if icon is not None:
            surface.blit(icon, (draw_x, rect.y + 12))
            draw_x += icon.get_width() + 12
        surface.blit(value_surface, (draw_x, rect.y + 9))
        surface.blit(label_surface, (draw_x, rect.y + 32))
        if metric_key:
            self._topbar_metric_rects[metric_key] = rect
            self._topbar_metric_data[metric_key] = {
                "label": label,
                "value": value,
                "icon_key": icon_key,
                "accent": accent,
            }
        return rect.right + 10, True

    def _draw_country_chip(self, surface, x, y, country_text, flag_img, max_right):
        text_surface = self.title_font.render(str(country_text), True, _C_TEXT)
        label_surface = self.small_font.render("PLAYER COUNTRY", True, _C_TEXT_MUTED)
        flag_width = 32 if flag_img is not None else 0
        flag_gap = 10 if flag_img is not None else 0
        chip_width = max(200, 18 + flag_width + flag_gap + text_surface.get_width() + 36)
        chip_height = 56

        if x + chip_width > max_right:
            return x, False

        rect = pygame.Rect(x, y, chip_width, chip_height)
        self._draw_glass_panel(surface, rect, radius=6, border=(73, 67, 49), glow=True)

        draw_x = rect.x + 16
        if flag_img is not None:
            scaled_flag = pygame.transform.smoothscale(flag_img, (32, 22))
            flag_rect = scaled_flag.get_rect()
            flag_rect.topleft = (draw_x, rect.y + (chip_height - flag_rect.height) // 2)
            surface.blit(scaled_flag, flag_rect)
            draw_x += scaled_flag.get_width() + flag_gap

        surface.blit(text_surface, (draw_x, rect.y + 9))
        surface.blit(label_surface, (draw_x, rect.y + 34))
        return rect.right + 12, True

    def _topbar_metric_values(self):
        return {
            "gold": float(self.playergold or 0),
            "population": float(self.playerpopulation or 0),
            "manpower": float(self._active_manpower or 0),
            "stability": float(self.playerstability or 0),
            "political_power": float(self.playerpp or 0),
            "action_points": float(self.playerap or 0),
            "turn": float(self.currentturnnumber or 0),
        }

    def _update_topbar_metric_rates(self):
        values = self._topbar_metric_values()
        try:
            turnnumber = int(self.currentturnnumber or 0)
        except (TypeError, ValueError):
            turnnumber = 0

        if self._topbar_metric_rate_turn is None:
            self._topbar_metric_rates = {key: 0.0 for key in values}
        elif turnnumber != self._topbar_metric_rate_turn:
            previousvalues = self._topbar_metric_snapshot or {}
            self._topbar_metric_rates = {
                key: values.get(key, 0.0) - float(previousvalues.get(key, values.get(key, 0.0)) or 0.0)
                for key in values
            }

        self._topbar_metric_snapshot = values
        self._topbar_metric_rate_turn = turnnumber

    def _get_topbar_metric_info(self, metric_key):
        affected = {
            "gold": "tax income, controlled land, focus rewards, recruitment and spending",
            "population": "controlled population, recruitment, conquest, scripted events",
            "manpower": "troops in controlled provinces and active movement orders",
            "stability": "focus effects, events, war pressure and national policy",
            "political_power": "turn income, focuses, diplomacy and decision costs",
            "action_points": "turn refreshes, movement orders and command actions",
            "turn": "end-turn actions, research progress, focus progress and movement",
            "date": "turn length and campaign start date",
        }
        full_names = {
            "gold": "Treasury Gold",
            "population": "National Population",
            "manpower": "Active Manpower",
            "stability": "National Stability",
            "political_power": "Political Power",
            "action_points": "Action Points",
            "turn": "Campaign Turn",
            "date": "Campaign Date",
        }
        rate = float(self._topbar_metric_rates.get(metric_key, 0.0) or 0.0)
        if metric_key == "date":
            rate_text = f"+{int(self._daysperturn)} days / turn"
        elif metric_key == "turn":
            rate_text = "+1 / turn"
        elif metric_key == "stability":
            rate_text = "No change last turn" if abs(rate) < 0.05 else f"{rate:+.1f}% / turn"
        else:
            rate_text = (
                "No change last turn"
                if abs(rate) < 0.05
                else f"{self._format_signed_compact_number(rate)} / turn"
            )

        data = self._topbar_metric_data.get(metric_key, {})
        return {
            "full_name": full_names.get(metric_key, str(data.get("label", metric_key)).title()),
            "current": str(data.get("value", "")),
            "rate": rate_text,
            "affected": affected.get(metric_key, "current campaign state and scripted effects"),
            "icon_key": data.get("icon_key", metric_key),
            "accent": data.get("accent", _C_GOLD),
        }

    def _draw_topbar_metric_popup(self, surface, mouse):
        metric_key = self._active_topbar_metric
        anchor_rect = self._topbar_metric_rects.get(metric_key)
        if not metric_key or anchor_rect is None:
            self._topbar_metric_popup_rect = pygame.Rect(0, 0, 10, 10)
            return

        info = self._get_topbar_metric_info(metric_key)
        popup_w = min(332, max(284, surface.get_width() - 24))
        popup_h = 156
        popup_x = anchor_rect.centerx - popup_w // 2
        popup_y = anchor_rect.bottom + 8
        popup_x = max(12, min(surface.get_width() - popup_w - 12, popup_x))
        popup_y = max(self.topbar_height + 8, min(surface.get_height() - popup_h - 12, popup_y))
        popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
        self._topbar_metric_popup_rect = popup_rect

        self._draw_glass_panel(surface, popup_rect, radius=8, border=info["accent"], glow=True)
        icon = self._topbar_icons.get(info["icon_key"])
        title_x = popup_rect.x + 18
        if icon is not None:
            surface.blit(icon, (title_x, popup_rect.y + 16))
            title_x += icon.get_width() + 10
        surface.blit(self.font_bold.render(info["full_name"], True, _C_TEXT), (title_x, popup_rect.y + 12))
        current_text = self.small_font.render(f"Current: {info['current']}", True, _C_TEXT_MUTED)
        surface.blit(current_text, (title_x, popup_rect.y + 34))

        row_defs = (
            ("turn", "Rate", info["rate"]),
            ("logistics", "Affected by", info["affected"]),
            ("intel", "Shown as", self._topbar_metric_data.get(metric_key, {}).get("label", info["full_name"])),
        )
        row_y = popup_rect.y + 64
        for row_icon_key, label, value in row_defs:
            row_rect = pygame.Rect(popup_rect.x + 14, row_y, popup_rect.width - 28, 26)
            hovered = row_rect.collidepoint(mouse)
            row_top = (28, 39, 59) if hovered else (16, 24, 38)
            self._draw_vertical_gradient_rect(surface, row_rect, row_top, (9, 15, 24), radius=5)
            pygame.draw.rect(surface, (48, 62, 80), row_rect, 1, border_radius=5)
            row_icon = self._topbar_icons.get(row_icon_key)
            row_x = row_rect.x + 8
            if row_icon is not None:
                small_icon = pygame.transform.smoothscale(row_icon, (16, 16))
                surface.blit(small_icon, (row_x, row_rect.y + 5))
                row_x += 22
            label_surface = self.small_font_bold.render(str(label).upper(), True, _C_GOLD_BRIGHT)
            surface.blit(label_surface, (row_x, row_rect.y + 6))
            value_x = row_x + 82
            max_value_w = max(40, row_rect.right - value_x - 8)
            self._draw_text_fit(surface, value, _C_TEXT, value_x, row_rect.y + 5, max_value_w, self.small_font)
            row_y += 30

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
                or self.bottom_buttons.selected == "PRODUCTION"
                or self.bottom_buttons.selected == "TROOPS"
                or self.active_left_tab == "COMBAT"
                or self._selectedmapcountry
            )

        left_w = self.leftbar_width if show_left else 0
        bottom_h = self.bottombar_height if show_bottom else 0
        right_w = self.rightbar_width if show_right else 0

        self.leftbar.rect = pygame.Rect(0, self.topbar_height, left_w, max(0, window_height - self.topbar_height))

        right_x = max(0, window_width - right_w)
        self.rightbar.rect = pygame.Rect(
            right_x,
            self.topbar_height,
            right_w,
            max(0, window_height - self.topbar_height - bottom_h),
        )

        bottom_y = max(0, window_height - bottom_h)
        self.bottombar.rect = pygame.Rect(left_w, bottom_y, max(1, window_width - left_w), bottom_h)
        self.bottom_buttons.rect = self.bottombar.rect

        center_x = left_w
        center_y = self.topbar_height
        center_w = max(1, window_width - left_w - right_w)
        center_h = max(1, window_height - self.topbar_height)
        self.map_rect = pygame.Rect(center_x, center_y, center_w, center_h)

        # End turn sits above the command dock while the map renders beneath it.
        end_w = 196
        end_h = 74
        end_x = self.map_rect.right - end_w - 18
        end_limit_y = self.bottombar.rect.y if show_bottom else self.map_rect.bottom
        end_y = max(self.map_rect.y + 12, end_limit_y - end_h - 16)
        self._endturn_rect = pygame.Rect(end_x, end_y, end_w, end_h)

        # choose button near bottom-right of map in choosecountry (draw will override)

        # right panel content layout (play phase; safe even if right panel hidden)
        content_x = self.rightbar.rect.x + 12
        content_y = self.rightbar.rect.y + 12
        content_w = max(1, self.rightbar.rect.width - 24)
        self._recruit_action_rect = pygame.Rect(content_x, content_y + 40, content_w, 34)
        self._declarewar_rect = pygame.Rect(content_x, content_y + 82, content_w, 34)
        self._production_blank_rect = pygame.Rect(content_x, content_y + 40, content_w, 90)

        # troop decision buttons at the bottom of right panel
        btn_w = max(1, (content_w - 30) // 4)
        btn_h = 50
        btn_y = (self.rightbar.rect.bottom - 12 - btn_h) if self.rightbar.rect.width else (self.map_rect.bottom - 12 - btn_h)
        self._split_rect = pygame.Rect(content_x, btn_y, btn_w, btn_h)
        self._merge_rect = pygame.Rect(content_x + btn_w + 10, btn_y, btn_w, btn_h)
        self._frontline_rect = pygame.Rect(content_x + (btn_w + 10) * 2, btn_y, btn_w, btn_h)
        self._auto_advance_rect = pygame.Rect(content_x + (btn_w + 10) * 3, btn_y, btn_w, btn_h)
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
        systemstatus=None,
        notificationcount=0,
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
        if systemstatus is not None:
            self._systemstatus = dict(systemstatus)
            try:
                fps_val = float(self._systemstatus.get("fps", 0.0) or 0.0)
            except Exception:
                fps_val = 0.0
            self._fps_history.append(fps_val)
            if len(self._fps_history) > 42:
                # keep most recent 42 samples
                self._fps_history = self._fps_history[-42:]
        self._notificationcount = max(0, int(notificationcount or 0))

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
        self._update_topbar_metric_rates()

    def update(self, elapsedseconds: float):
        # retained for runtime compatibility
        return

    def _get_selected_division_entry(self):
        for entry in self._selectedtroopentries or ():
            if isinstance(entry, dict) and entry.get("divisionid"):
                return entry
        return None



    def process_event(self, event):

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.warprogressopen:
                self.warprogressopen = False
                return None
            self.pausemenuopen = not self.pausemenuopen
            return self.actionpausemenu
        
        if self.production_popup_open:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.production_popup_open = False
                return None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._production_popup_back_rect.collidepoint(event.pos):
                    self.production_popup_open = False
                    return None
                
                for i in range(4):
                    if self._production_selection_rects[i].collidepoint(event.pos):
                        self.production_selected = i + 1
                        return None
                
                self.production_popup_open = False
                return None

        if self.warprogressopen:
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self._warprogress_dragging = False
                if self._warprogress_popup_rect.collidepoint(event.pos):
                    return None
            if event.type == pygame.MOUSEMOTION and self._warprogress_dragging:
                target_x = int(event.pos[0] - self._warprogress_drag_offset[0])
                target_y = int(event.pos[1] - self._warprogress_drag_offset[1])
                popup = self._warprogress_popup_rect.copy()
                popup.topleft = (target_x, target_y)
                bounds = pygame.Rect(12, self.topbar_height + 8, self.window_size[0] - 24, self.window_size[1] - self.topbar_height - 20)
                popup.clamp_ip(bounds)
                self._warprogress_popup_pos = popup.topleft
                return None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._warprogress_close_rect.collidepoint(event.pos):
                    self.warprogressopen = False
                    self._warprogress_dragging = False
                    return None
                for tab_index, tab_rect in enumerate(self._warprogress_tab_rects):
                    if tab_rect.collidepoint(event.pos):
                        self._warprogress_active_index = tab_index
                        return None
                if self._warprogress_header_rect.collidepoint(event.pos):
                    self._warprogress_dragging = True
                    self._warprogress_drag_offset = (
                        event.pos[0] - self._warprogress_popup_rect.x,
                        event.pos[1] - self._warprogress_popup_rect.y,
                    )
                    return None
                if self._warprogress_popup_rect.collidepoint(event.pos):
                    return None

        if self.pausemenuopen:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._pausequit_rect.collidepoint(event.pos):
                    self.ui_click_sound.play()
                    return self.actionquitgame
            return None

        if self.gamephase == "play" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            clicked_metric = None
            for metric_key, metric_rect in (self._topbar_metric_rects or {}).items():
                if metric_rect.collidepoint(pos):
                    clicked_metric = metric_key
                    break
            if clicked_metric:
                self._active_topbar_metric = (
                    None if self._active_topbar_metric == clicked_metric else clicked_metric
                )
                return None
            if self._active_topbar_metric:
                if self._topbar_metric_popup_rect.collidepoint(pos):
                    return None
                self._active_topbar_metric = None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            selected_bottom_tab = self.bottom_buttons.selected
            if selected_bottom_tab:
                selected_rect = (self.bottom_buttons.item_rects or {}).get(selected_bottom_tab)
                if selected_rect is not None and selected_rect.collidepoint(pos):
                    self.bottom_buttons.set_selected(None)
                    if selected_bottom_tab == "RESEARCH":
                        self.researchview.isopen = False
                    self.applylayout()
                    return None

            selected_left_tab = self.active_left_tab
            if selected_left_tab:
                selected_rect = (self.leftbar.item_rects or {}).get(selected_left_tab)
                if selected_rect is not None and selected_rect.collidepoint(pos):
                    self.active_left_tab = None
                    if selected_left_tab == "NATIONAL POLICY":
                        self.focusview.isopen = False
                    self.applylayout()
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
                
                self.ui_click_sound.play()
                self.active_left_tab = item
                self.applylayout()
                if item == "NATIONAL POLICY":
                    self.focusview.toggleview()
                    return self.actiontogglefocuspanel
                return None

        for item, rect in (self.bottom_buttons.item_rects or {}).items():
            if rect.collidepoint(pos):
                self.ui_click_sound.play()
                self.bottom_buttons.set_selected(item)
                self.applylayout()
                if item == "RESEARCH":
                    self.researchview.toggleview()
                return None

      
        if self._endturn_rect.collidepoint(pos):
            self.ui_click_sound.play()
            return self.actionendturn

        selected_tab = self.bottom_buttons.selected

        if selected_tab == "PRODUCTION" and not self._countrymenutarget:
            if self._production_blank_rect.collidepoint(pos):
                self.production_popup_open = True
                return None

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
                self.ui_click_sound.play()
                self.warprogressopen = not self.warprogressopen
                return self.actionwarprogress
        if self._selectedmapcountry and not self._countrymenutarget:
            if self._declarewar_rect.collidepoint(pos):
                if (
                    self.playercountry
                    and self._selectedmapcountry != self.playercountry
                    and self._selectedmapcountry not in self._countriesatwarset
                ):
                    return self.actiondeclarewar
                return None
        if selected_tab == "TROOPS":
            if self._recruit_action_rect.collidepoint(pos):
                self.ui_click_sound.play()
                if self.recruitenabled:
                    return self.actionrecruit
                return None
            for provinceid, detachrect in (self._detach_regiment_rects or {}).items():
                if detachrect.collidepoint(pos):
                    return (self.actiondetachregiment, provinceid)

      
        if selected_tab == "TROOPS" and self._selectedtroopentries:
            selected = [e for e in self._selectedtroopentries if isinstance(e, dict)]
            totaltroops = sum(max(0, int(e.get("troops", 0))) for e in selected)
            if totaltroops > 0:
                if self._split_rect.collidepoint(pos) and totaltroops > 1:
                    self.ui_click_sound.play()
                    return self.actionsplit
                if self._merge_rect.collidepoint(pos) and len(selected) > 1:
                    self.ui_click_sound.play()
                    return self.actionmerge
                if self._frontline_rect.collidepoint(pos):
                    self.ui_click_sound.play()
                    return self.actionfrontline
                divisionentry = self._get_selected_division_entry()
                if self._auto_advance_rect.collidepoint(pos) and divisionentry:
                    return (self.actionautoadvance, divisionentry.get("divisionid"))

            return None
       
    def ispointeroverui(self, mouseposition):
        if self.warprogressopen and self._warprogress_popup_rect.collidepoint(mouseposition):
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
            self._draw_topbar_background(surface)
            title = self.title_font.render("EBEE COMMAND", True, _C_GOLD_BRIGHT)
            subtitle = self.small_font.render("SELECT THEATER COMMAND", True, _C_TEXT_MUTED)
            surface.blit(title, (20, 16))
            surface.blit(subtitle, (20, 45))

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
            self._draw_glass_panel(
                surface,
                self._choose_rect,
                radius=6,
                border=(_C_SUCCESS if enabled else (69, 75, 84)),
                glow=enabled,
            )
            label = self.font_bold.render("CHOOSE COUNTRY", True, (_C_TEXT if enabled else _C_TEXT_MUTED))
            surface.blit(label, label.get_rect(center=self._choose_rect.center))
            if self.pendingcountry:
                selected = self.font.render(f"Selected: {self.pendingcountry}", True, _C_TEXT)
                surface.blit(selected, (self._choose_rect.x, self._choose_rect.y - 22))

            return

                

        # full UI chrome (play)
        self._draw_map_edge_shadows(surface)
        if self.leftbar.rect.width:
            self.leftbar.draw(
                surface,
                self.font,
                mouse,
                font_bold=self.font_bold,
                icons=self._topbar_icons,
                selected=self.active_left_tab,
                statusdata=self._systemstatus,
                notification_count=self._notificationcount,
            )
        self._draw_bottombar_background(surface)
        self.bottom_buttons.draw(surface, self.font, mouse, font_bold=self.font_bold, icons=self._topbar_icons)
        self._draw_topbar_background(surface)

        # end turn button (bottom-right of map)
        hovered = self._endturn_rect.collidepoint(mouse)
        if hovered:
            self._endturn_glow = min(1.0, self._endturn_glow + 0.12)
        else:
            self._endturn_glow = max(0.0, self._endturn_glow - 0.08)
        glow = self._endturn_glow
        radius = 8
        if glow > 0.01:
            ew, eh = self._endturn_rect.size
            ex, ey = self._endturn_rect.topleft
            glow_surf = pygame.Surface((ew + 28, eh + 28), pygame.SRCALPHA)
            for ring in range(5):
                ring_alpha = int(glow * (42 - ring * 7))
                if ring_alpha <= 0:
                    continue
                offset = ring * 2 + 2
                pygame.draw.rect(glow_surf, (*_C_SUCCESS, ring_alpha),
                    (14 - offset, 14 - offset, ew + offset * 2, eh + offset * 2),
                    border_radius=radius + offset, width=2)
            surface.blit(glow_surf, (ex - 14, ey - 14))
        self._draw_vertical_gradient_rect(
            surface,
            self._endturn_rect,
            (20, 92, 56) if hovered else (17, 73, 46),
            (7, 32, 25),
            radius=radius,
        )
        pygame.draw.rect(surface, (58, 178, 116) if hovered else (45, 136, 91), self._endturn_rect, 1, border_radius=radius)
        pygame.draw.line(surface, (136, 232, 181), (self._endturn_rect.x + 14, self._endturn_rect.y + 2), (self._endturn_rect.right - 14, self._endturn_rect.y + 2), 1)
        end_font = self.font_bold
        end_label = end_font.render("END TURN", True, _C_TEXT)
        sub_label = self.small_font.render(f"Turn {int(self.currentturnnumber)}", True, (196, 226, 209))
        surface.blit(end_label, end_label.get_rect(center=(self._endturn_rect.centerx - 10, self._endturn_rect.y + 28)))
        surface.blit(sub_label, sub_label.get_rect(center=(self._endturn_rect.centerx - 10, self._endturn_rect.y + 55)))
        arrow = self.title_font.render(">", True, (200, 244, 221))
        surface.blit(arrow, arrow.get_rect(center=(self._endturn_rect.right - 26, self._endturn_rect.centery)))

        # top title + stats line (with mini flag)
        base_title = "EBEE COMMAND"
        info_x = 18
        info_y = 12
        emblem_center = (info_x + 26, info_y + 27)
        pygame.draw.circle(surface, _C_GOLD, emblem_center, 24, 1)
        pygame.draw.circle(surface, (88, 70, 34), emblem_center, 17, 1)
        pygame.draw.line(surface, _C_GOLD, (emblem_center[0], emblem_center[1] - 22), (emblem_center[0], emblem_center[1] + 22), 1)
        pygame.draw.line(surface, _C_GOLD, (emblem_center[0] - 22, emblem_center[1]), (emblem_center[0] + 22, emblem_center[1]), 1)
        title_x = info_x + 64
        title_surface = self.title_font.render(base_title, True, _C_GOLD_BRIGHT)
        subtitle_surface = self.small_font.render("STRATEGIC COMMAND & CONTROL", True, _C_TEXT_MUTED)
        surface.blit(title_surface, (title_x, info_y + 5))
        surface.blit(subtitle_surface, (title_x, info_y + 34))

        flag_img = None
        if self.playercountry:
            key = str(self.playercountry).strip().lower().replace(" ", "_").replace("-", "_")
            flag_img = self._flags.get(key) if self._flags.get(key) else None
        stats_x = max(396, title_x + title_surface.get_width() + 38)
        stats_y = 12

        country_text = str(self.playercountry or "None")
        date_text = self._format_ingame_date()
        max_right = self.topbar.rect.right - 12
        stats_x, _ = self._draw_country_chip(surface, stats_x, stats_y, country_text, flag_img, max_right)

        self._topbar_metric_rects = {}
        self._topbar_metric_data = {}
        chip_data = (
            ("gold", "Gold", self._format_number(self.playergold), (177, 145, 70)),
            ("turn", "Turn", str(int(self.currentturnnumber)), (130, 138, 146)),
            ("date", "Date", date_text, (177, 145, 70)),
            ("population", "Population", self._format_compact_number(self.playerpopulation), (130, 138, 146)),
            ("manpower", "Active MP", self._format_compact_number(self._active_manpower), (177, 145, 70)),
            ("stability", "Stability", f"{self.playerstability:.0f}%", (177, 145, 70)),
            ("political_power", "PP", str(int(self.playerpp)), (130, 138, 146)),
            ("action_points", "AP", str(int(self.playerap)), (177, 145, 70)),
        )
        for icon_key, label_text, value_text, accent in chip_data:
            stats_x, did_draw = self._draw_resource_chip(
                surface,
                stats_x,
                stats_y,
                icon_key,
                label_text,
                value_text,
                max_right,
                accent=accent,
                metric_key=icon_key,
                mouse=mouse,
            )
            if not did_draw:
                break

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

            padding = 10
            text_surfs = []
            for index, line in enumerate(tooltip_lines):
                color = _C_GOLD_BRIGHT if index == 0 else (_C_TEXT if index <= 2 else _C_TEXT_MUTED)
                font = self.font_bold if index == 0 else self.font
                text_surfs.append(font.render(line, True, color))
            box_w = max(ts.get_width() for ts in text_surfs) + padding * 2
            box_h = sum(ts.get_height() for ts in text_surfs) + padding * 2

            mx, my = self._hovermousepos
            x = int(mx + 16)
            y = int(my + 16)
            x = max(0, min(surface.get_width() - box_w, x))
            y = max(0, min(surface.get_height() - box_h, y))
            rect = pygame.Rect(x, y, box_w, box_h)

            self._draw_glass_panel(surface, rect, radius=5, border=(126, 102, 58))
            ty = rect.y + padding
            for ts in text_surfs:
                surface.blit(ts, (rect.x + padding, ty))
                ty += ts.get_height()



        if self.production_popup_open:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            surface.blit(overlay, (0, 0))
            popup_rect = pygame.Rect(0, 0, 600, 400)
            popup_rect.center = surface.get_rect().center
            self._draw_glass_panel(surface, popup_rect, radius=8, border=(72, 86, 108), glow=True)
            title = self.title_font.render("PRODUCTION", True, _C_GOLD_BRIGHT)
            surface.blit(title, title.get_rect(center=(popup_rect.centerx, popup_rect.y + 40)))

            btn_w, btn_h = 160, 50
            btn_gap_x, btn_gap_y = 20, 15
            start_x = popup_rect.centerx - btn_w - btn_gap_x // 2
            start_y = popup_rect.y + 90

            for i in range(4):
                col = i % 2
                row = i // 2
                x = start_x + col * (btn_w + btn_gap_x)
                y = start_y + row * (btn_h + btn_gap_y)
                self._production_selection_rects[i] = pygame.Rect(x, y, btn_w, btn_h)
                selected = self.production_selected == (i + 1)
                label = f"selection {i + 1}"
                self._draw_glow_btn(surface, f"prod_sel_{i}", self._production_selection_rects[i], True, label, primary=selected, mouse=mouse)

            back_w, back_h = 140, 40
            self._production_popup_back_rect = pygame.Rect(0, 0, back_w, back_h)
            self._production_popup_back_rect.centerx = popup_rect.centerx
            self._production_popup_back_rect.y = popup_rect.bottom - back_h - 20
            self._draw_glow_btn(surface, "prod_back", self._production_popup_back_rect, True, "BACK", mouse=mouse)

        if self.focusview.isopen:
            self.focusview.draw(surface, self.title_font, self.font, mouse)
            self._draw_topbar_metric_popup(surface, mouse)
            if self.pausemenuopen:
                self._draw_pausemenu(surface)
            return

        if self.researchview.isopen:
            self.researchview.draw(surface, self.title_font, self.font, mouse)
            self._draw_topbar_metric_popup(surface, mouse)
            if self.pausemenuopen:
                self._draw_pausemenu(surface)
            return

        selected_tab = self.bottom_buttons.selected
        if not self.rightbar.rect.width:
            self._draw_topbar_metric_popup(surface, mouse)
            if self.pausemenuopen:
                self._draw_pausemenu(surface)
            return
                
       

        content_rect = self.rightbar.rect.inflate(-24, -24)
        content_rect.topleft = (self.rightbar.rect.x + 12, self.rightbar.rect.y + 12)

        # base panel — premium command drawer
        self._draw_glass_panel(surface, self.rightbar.rect, radius=0, border=(44, 58, 76))
        pygame.draw.rect(surface, (10, 16, 25), content_rect, border_radius=6)

        panel_title = "COUNTRY" if (self._countrymenutarget or self._selectedmapcountry) else str(selected_tab or "")
        header = self.font_bold.render(panel_title, True, _C_GOLD_BRIGHT)
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
            surface.blit(self.font_bold.render("War Operations", True, _C_GOLD_BRIGHT), (content_rect.x, y_cursor))
            self._draw_text_fit(
                surface,
                "Monitor active theaters, victory-point control, casualties, and pressure.",
                _C_TEXT_MUTED,
                content_rect.x,
                y_cursor + 26,
                content_rect.width,
                self.font,
            )
            self._war_progress_rect.topleft = (content_rect.x, content_rect.bottom - self._war_progress_rect.height)
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
                f"Armies: {self._format_number(stats.get('population', 0))}",
                f"Manpower:   {self._format_number(stats.get('manpower', 0))}",
                f"Stability:  {self._format_decimal(stats.get('stability', 0))}%",
                f"Leader:     {stats.get('leader', 'Unknown')}",
            ]
            for line in lines:
                surface.blit(self.font.render(line, True, (212, 212, 212)), (content_rect.x, y_cursor))
                y_cursor += 20

            alreadyatwar = self._selectedmapcountry in self._countriesatwarset
            can_declare = (
                bool(self.playercountry)
                and self._selectedmapcountry != self.playercountry
                and not alreadyatwar
            )
            status = "At war" if alreadyatwar else ("Player country" if self._selectedmapcountry == self.playercountry else "Peace")
            status_surf = self.small_font.render(f"STATUS: {status.upper()}", True, _C_TEXT_MUTED)
            surface.blit(status_surf, (content_rect.x, y_cursor + 8))

            self._declarewar_rect.topleft = (content_rect.x, content_rect.bottom - self._declarewar_rect.height)
            declare_label = "DECLARE WAR" if can_declare else ("ALREADY AT WAR" if alreadyatwar else "DECLARE WAR")
            self._draw_glow_btn(
                surface,
                "declarewar_selected_country",
                self._declarewar_rect,
                can_declare,
                declare_label,
                mouse=mouse,
            )

        
        elif selected_tab == "TROOPS":
           
            self._recruit_action_rect.topleft = (content_rect.x, self._split_rect.y - 44)
            recruit_label = f"RECRUIT +{int(self.recruitamount)}"
            self._draw_glow_btn(
                surface, "recruit", self._recruit_action_rect,
                self.recruitenabled, recruit_label, primary=True, mouse=mouse,
            )
            y_cursor = max(y_cursor, content_rect.y + 24)

        elif selected_tab == "PRODUCTION" and not self._countrymenutarget:
            self._production_blank_rect.topleft = (content_rect.x, content_rect.y + 40)
            self._draw_glow_btn(
                surface, "production_blank", self._production_blank_rect,
                True, "     +      ", mouse=mouse,
            )
            y_cursor += 100

        # Troop info + decision buttons only show in TROOPS tab, and only when troops > 0
        if selected_tab == "TROOPS" and not self._countrymenutarget and self.active_left_tab != "COMBAT" and not self._selectedmapcountry:
            self._detach_regiment_rects = {}
            selected = [e for e in (self._selectedtroopentries or []) if isinstance(e, dict)]
            totaltroops = sum(max(0, int(e.get("troops", 0))) for e in selected)
            if totaltroops > 0:
                header_y = content_rect.y + 60
                divisionentry = self._get_selected_division_entry()
                divisionname = divisionentry.get("divisionname") if divisionentry else None
                divisionautoadvance = bool(divisionentry.get("divisionautoadvance", False)) if divisionentry else False

                icon = self._topbar_icons.get("manpower")
                if icon is not None:
                    surface.blit(icon, (content_rect.x, header_y - 2))
                    title_x = content_rect.x + icon.get_width() + 8
                else:
                    title_x = content_rect.x
                surface.blit(self.font_bold.render("Selected Regiments", True, _C_TEXT), (title_x, header_y))

                chip_gap = 8
                chip_w = (content_rect.width - chip_gap) // 2
                chip_y = header_y + 28
                self._draw_metric_chip(
                    surface,
                    pygame.Rect(content_rect.x, chip_y, chip_w, 48),
                    "Regiments",
                    str(len(selected)),
                    icon_key="combat",
                    accent=_C_INFO,
                )
                self._draw_metric_chip(
                    surface,
                    pygame.Rect(content_rect.x + chip_w + chip_gap, chip_y, chip_w, 48),
                    "Troops",
                    self._format_number(totaltroops),
                    icon_key="manpower",
                    accent=_C_SUCCESS,
                )

                division_y = chip_y + 58
                if divisionname:
                    division_rect = pygame.Rect(content_rect.x, division_y, content_rect.width, 44)
                    self._draw_vertical_gradient_rect(surface, division_rect, (26, 35, 52), (13, 20, 33), radius=6)
                    pygame.draw.rect(surface, (61, 75, 96), division_rect, 1, border_radius=6)
                    div_icon = self._topbar_icons.get("logistics")
                    div_x = division_rect.x + 10
                    if div_icon is not None:
                        surface.blit(div_icon, (div_x, division_rect.centery - div_icon.get_height() // 2))
                        div_x += div_icon.get_width() + 8
                    surface.blit(self.small_font.render("DIVISION", True, _C_TEXT_MUTED), (div_x, division_rect.y + 7))
                    surface.blit(self.font_bold.render(str(divisionname), True, _C_TEXT), (div_x, division_rect.y + 22))
                    status_text = "ADVANCE" if divisionautoadvance else "HOLD"
                    status_color = _C_SUCCESS if divisionautoadvance else _C_GOLD_BRIGHT
                    status_surface = self.small_font_bold.render(status_text, True, status_color)
                    surface.blit(
                        status_surface,
                        (
                            division_rect.right - status_surface.get_width() - 10,
                            division_rect.centery - status_surface.get_height() // 2,
                        ),
                    )
                    list_top = division_rect.bottom + 10
                else:
                    list_top = chip_y + 60

                list_bottom = min(self._recruit_action_rect.y, self._split_rect.y) - 10
                maxrows = max(0, (list_bottom - list_top) // 48)
                maxrows = min(7, maxrows)

                col_x = content_rect.x
                row_h = 44
                for i in range(maxrows):
                    if i >= len(selected):
                        break
                    row_rect = pygame.Rect(col_x, list_top + i * (row_h + 4), content_rect.width, row_h)
                    row_top = (23, 33, 50) if i % 2 == 0 else (18, 27, 42)
                    self._draw_vertical_gradient_rect(surface, row_rect, row_top, (10, 16, 27), radius=6)
                    pygame.draw.rect(surface, (43, 56, 73), row_rect, 1, border_radius=6)
                    pygame.draw.line(surface, _C_INFO, (row_rect.x + 5, row_rect.y + 8), (row_rect.x + 5, row_rect.bottom - 8), 2)

                    prov = selected[i].get("provinceid", "unknown")
                    troops = int(selected[i].get("troops", 0))
                    regiment_label = selected[i].get("regimentname") or f"Regiment {i + 1}"
                    label_x = row_rect.x + 16
                    label_y = row_rect.y + 6
                    regiment_surface = self.font_bold.render(str(regiment_label), True, _C_TEXT)
                    surface.blit(regiment_surface, (label_x, label_y))

                    rowdivisionid = selected[i].get("divisionid")
                    if rowdivisionid:
                        detachrect = pygame.Rect(label_x + regiment_surface.get_width() + 8, label_y - 1, 18, 18)
                        self._detach_regiment_rects[str(prov)] = detachrect
                        pygame.draw.rect(surface, _C_DANGER, detachrect, border_radius=4)
                        pygame.draw.line(surface, (255, 235, 235), (detachrect.x + 5, detachrect.y + 5), (detachrect.right - 5, detachrect.bottom - 5), 2)
                        pygame.draw.line(surface, (255, 235, 235), (detachrect.right - 5, detachrect.y + 5), (detachrect.x + 5, detachrect.bottom - 5), 2)

                    prov_str = self.small_font.render(str(prov), True, _C_TEXT_MUTED)
                    surface.blit(prov_str, (label_x, row_rect.y + 25))

                    troop_str = self.font_bold.render(f"{troops:,}", True, (200, 232, 204))
                    surface.blit(troop_str,
                        (content_rect.right - troop_str.get_width() - 8, row_rect.y + 8))
                    troop_label = self.small_font.render("troops", True, _C_TEXT_MUTED)
                    surface.blit(troop_label, (content_rect.right - troop_label.get_width() - 8, row_rect.y + 26))

                if len(selected) > maxrows and maxrows > 0:
                    overflow = len(selected) - maxrows
                    surface.blit(self.font.render(f"... +{overflow} more", True, (170, 170, 170)),
                        (col_x, list_top + (maxrows - 1) * (row_h + 4) + row_h + 2))

                split_enabled = totaltroops > 1
                merge_enabled = len(selected) > 1
                hasdivision = divisionentry is not None
                frontline_label = "Cancel" if self._frontlineplacementmode else "Line"
                advance_label = "Auto"
                self._draw_glow_btn(surface, "split", self._split_rect, split_enabled, "Split", mouse=mouse, icon_key="manpower")
                self._draw_glow_btn(surface, "merge", self._merge_rect, merge_enabled, "Merge", mouse=mouse, icon_key="logistics")
                self._draw_glow_btn(surface, "frontline", self._frontline_rect, True, frontline_label, mouse=mouse, icon_key="combat")
                self._draw_glow_btn(
                    surface,
                    "autoadvance",
                    self._auto_advance_rect,
                    hasdivision,
                    advance_label,
                    primary=divisionautoadvance,
                    mouse=mouse,
                    icon_key="turn",
                )
        else:
            self._detach_regiment_rects = {}

        self._draw_topbar_metric_popup(surface, mouse)

        if self.warprogressopen:
            self._draw_war_progress_popup(surface, mouse)

        if self.pausemenuopen:
            self._draw_pausemenu(surface)


    def _draw_metric_chip(self, surface, rect, label, value, icon_key=None, accent=_C_GOLD):
        self._draw_vertical_gradient_rect(surface, rect, (18, 27, 42), (9, 15, 24), radius=6)
        pygame.draw.rect(surface, (49, 63, 82), rect, 1, border_radius=6)
        pygame.draw.line(surface, accent, (rect.x + 8, rect.y + 9), (rect.x + 8, rect.bottom - 9), 2)
        draw_x = rect.x + 18
        icon = self._topbar_icons.get(icon_key) if icon_key else None
        if icon is not None:
            surface.blit(icon, (draw_x, rect.centery - icon.get_height() // 2))
            draw_x += icon.get_width() + 10
        value_surface = self.font_bold.render(str(value), True, _C_TEXT)
        label_surface = self.small_font.render(str(label), True, _C_TEXT_MUTED)
        text_gap = 2
        text_block_h = value_surface.get_height() + text_gap + label_surface.get_height()
        text_y = rect.y + max(7, (rect.height - text_block_h) // 2)
        surface.blit(value_surface, (draw_x, text_y))
        surface.blit(label_surface, (draw_x, text_y + value_surface.get_height() + text_gap))

    def _draw_occupation_bar(self, surface, rect, label, percent, count_text, fill_color):
        percent = max(0.0, min(100.0, float(percent or 0.0)))
        label_surface = self.font_bold.render(str(label), True, _C_TEXT)
        value_surface = self.font_bold.render(f"{percent:.1f}%", True, _C_TEXT)
        surface.blit(label_surface, (rect.x, rect.y))
        surface.blit(value_surface, (rect.right - value_surface.get_width(), rect.y))

        bar_rect = pygame.Rect(rect.x, rect.y + 28, rect.width, 24)
        pygame.draw.rect(surface, (7, 12, 20), bar_rect, border_radius=5)
        pygame.draw.rect(surface, (43, 56, 73), bar_rect, 1, border_radius=5)

        fill_width = int(bar_rect.width * (percent / 100.0))
        if fill_width > 0:
            fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, fill_width, bar_rect.height)
            self._draw_vertical_gradient_rect(surface, fill_rect, fill_color, (max(0, fill_color[0] - 32), max(0, fill_color[1] - 32), max(0, fill_color[2] - 32)), radius=5)

        risk_x = bar_rect.x + int(bar_rect.width * 0.8)
        pygame.draw.line(surface, _C_DANGER, (risk_x, bar_rect.y - 4), (risk_x, bar_rect.bottom + 4), 2)
        risk_label = self.small_font.render("80% capitulation risk", True, _C_DANGER)
        surface.blit(risk_label, (bar_rect.right - risk_label.get_width(), bar_rect.bottom + 6))

        count_surface = self.small_font.render(str(count_text), True, _C_TEXT_MUTED)
        surface.blit(count_surface, (rect.x, bar_rect.bottom + 6))

    def _draw_war_progress_popup(self, surface, mouse):
        popup_w = min(900, max(640, self.map_rect.width - 72))
        max_popup_h = max(520, surface.get_height() - self.topbar_height - 36)
        popup_h = min(740, max_popup_h, max(620, self.map_rect.height - 64))
        popup_rect = pygame.Rect(0, 0, popup_w, popup_h)
        if self._warprogress_popup_pos is None:
            popup_rect.center = self.map_rect.center
        else:
            popup_rect.topleft = self._warprogress_popup_pos
        popup_rect.clamp_ip(surface.get_rect().inflate(-32, -32))
        self._warprogress_popup_pos = popup_rect.topleft
        self._warprogress_popup_rect = popup_rect

        shadow = pygame.Surface((popup_rect.width + 28, popup_rect.height + 28), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 150), shadow.get_rect(), border_radius=12)
        surface.blit(shadow, (popup_rect.x - 14, popup_rect.y - 10))
        self._draw_glass_panel(surface, popup_rect, radius=8, border=(72, 86, 108), glow=True)

        header_h = 64
        self._warprogress_header_rect = pygame.Rect(popup_rect.x, popup_rect.y, popup_rect.width, header_h)
        pygame.draw.line(surface, (76, 64, 38), (popup_rect.x + 16, popup_rect.y + header_h), (popup_rect.right - 16, popup_rect.y + header_h), 1)
        icon = self._topbar_icons.get("war_progress")
        title_x = popup_rect.x + 24
        if icon is not None:
            surface.blit(icon, (title_x, popup_rect.y + 21))
            title_x += icon.get_width() + 12
        title = self.title_font.render("WAR PROGRESS", True, _C_GOLD_BRIGHT)
        subtitle = self.small_font.render("OCCUPATION AND CAPITULATION RISK", True, _C_TEXT_MUTED)
        surface.blit(title, (title_x, popup_rect.y + 14))
        surface.blit(subtitle, (title_x, popup_rect.y + 40))

        close_size = 34
        self._warprogress_close_rect = pygame.Rect(popup_rect.right - close_size - 16, popup_rect.y + 15, close_size, close_size)
        close_hovered = self._warprogress_close_rect.collidepoint(mouse)
        close_top = (45, 55, 68) if close_hovered else (23, 32, 48)
        self._draw_vertical_gradient_rect(surface, self._warprogress_close_rect, close_top, (10, 16, 25), radius=6)
        pygame.draw.rect(surface, (_C_DANGER if close_hovered else (62, 76, 95)), self._warprogress_close_rect, 1, border_radius=6)
        close_icon = self._topbar_icons.get("close")
        if close_icon is not None:
            surface.blit(close_icon, close_icon.get_rect(center=self._warprogress_close_rect.center))
        else:
            close_label = self.font_bold.render("X", True, _C_TEXT)
            surface.blit(close_label, close_label.get_rect(center=self._warprogress_close_rect.center))

        data = self._warprogressdata or {}
        wars = [war for war in data.get("wars", []) if isinstance(war, dict)]
        if not wars and data.get("aggressor") and data.get("defender"):
            wars = [data]
        if wars:
            self._warprogress_active_index = max(0, min(self._warprogress_active_index, len(wars) - 1))
            data = wars[self._warprogress_active_index]
        else:
            self._warprogress_active_index = 0
        aggressor = data.get("aggressor")
        defender = data.get("defender")
        content_x = popup_rect.x + 28
        content_y = popup_rect.y + header_h + 18
        content_w = popup_rect.width - 56

        tab_label = self.small_font.render("ACTIVE WARS", True, _C_TEXT_MUTED)
        surface.blit(tab_label, (content_x, content_y))
        self._warprogress_tab_rects = []
        tab_y = content_y + 18
        if wars:
            gap = 8
            tab_w = max(118, min(178, (content_w - gap * max(0, len(wars) - 1)) // max(1, len(wars))))
            for index, war in enumerate(wars):
                tab_rect = pygame.Rect(content_x + index * (tab_w + gap), tab_y, tab_w, 38)
                if tab_rect.right > content_x + content_w:
                    break
                self._warprogress_tab_rects.append(tab_rect)
                selected = index == self._warprogress_active_index
                hovered = tab_rect.collidepoint(mouse)
                top = (43, 36, 24) if selected else ((28, 39, 59) if hovered else (14, 22, 33))
                bottom = (25, 22, 18) if selected else (9, 15, 24)
                self._draw_vertical_gradient_rect(surface, tab_rect, top, bottom, radius=6)
                pygame.draw.rect(surface, (_C_GOLD if selected else (46, 59, 78)), tab_rect, 1, border_radius=6)
                label = f"{war.get('aggressor', '?')} - {war.get('defender', '?')}"
                self._draw_text_fit(surface, label, (_C_GOLD_BRIGHT if selected else _C_TEXT), tab_rect.x + 10, tab_rect.y + 10, tab_rect.width - 20, self.font_bold if selected else self.font)

        content_y = tab_y + 52
        if not aggressor or not defender:
            empty = self.font_bold.render("No active war", True, _C_TEXT)
            surface.blit(empty, empty.get_rect(center=(popup_rect.centerx, content_y + 120)))
            return

        matchup = self.font_bold.render(f"{aggressor} vs {defender}", True, _C_TEXT)
        surface.blit(matchup, (content_x, content_y))
        since = data.get("start_turn")
        meta = f"Active wars: {self._format_number(data.get('active_war_count', 1))}"
        if since:
            meta += f"  |  Since turn {self._format_number(since)}"
        self._draw_text_fit(surface, meta, _C_TEXT_MUTED, content_x, content_y + 24, content_w)

        bar_y = content_y + 56
        defender_percent = data.get("defender_occupied_percent", data.get("progress", 0.0))
        aggressor_percent = data.get("aggressor_occupied_percent", data.get("defender_progress", 0.0))
        defender_count = (
            f"{self._format_number(data.get('defender_foreign_occupied_provinces', data.get('aggressor_occupied_enemy_provinces', 0)))}"
            f" / {self._format_number(data.get('defender_total_provinces', 0))} provinces under foreign control"
        )
        aggressor_count = (
            f"{self._format_number(data.get('aggressor_foreign_occupied_provinces', data.get('defender_occupied_enemy_provinces', 0)))}"
            f" / {self._format_number(data.get('aggressor_total_provinces', 0))} provinces under foreign control"
        )
        self._draw_occupation_bar(
            surface,
            pygame.Rect(content_x, bar_y, content_w, 72),
            f"{defender} occupied by {aggressor}",
            defender_percent,
            defender_count,
            (180, 78, 78),
        )
        self._draw_occupation_bar(
            surface,
            pygame.Rect(content_x, bar_y + 92, content_w, 72),
            f"{aggressor} occupied by {defender}",
            aggressor_percent,
            aggressor_count,
            (74, 143, 231),
        )

        def draw_breakdown(panel_rect, title, breakdown):
            self._draw_vertical_gradient_rect(surface, panel_rect, (15, 23, 36), (8, 13, 22), radius=6)
            pygame.draw.rect(surface, (43, 56, 73), panel_rect, 1, border_radius=6)
            self._draw_text_fit(surface, title, _C_GOLD_BRIGHT, panel_rect.x + 12, panel_rect.y + 10, panel_rect.width - 24, self.font_bold)
            line_y = panel_rect.y + 36
            if not breakdown:
                self._draw_text_fit(surface, "No foreign occupation tracked.", _C_TEXT_MUTED, panel_rect.x + 12, line_y, panel_rect.width - 24)
                return
            for item in breakdown[:3]:
                line = (
                    f"{item.get('controller', 'Unknown')}: "
                    f"{self._format_number(item.get('provinces', 0))} provinces "
                    f"({float(item.get('province_percent', 0.0)):.1f}%)"
                )
                self._draw_text_fit(surface, line, _C_TEXT, panel_rect.x + 12, line_y, panel_rect.width - 24)
                line_y += 21

        breakdown_y = bar_y + 184
        col_gap = 12
        col_w = (content_w - col_gap) // 2
        draw_breakdown(
            pygame.Rect(content_x, breakdown_y, col_w, 112),
            f"{defender} territory controllers",
            data.get("defender_occupation_breakdown", []),
        )
        draw_breakdown(
            pygame.Rect(content_x + col_w + col_gap, breakdown_y, col_w, 112),
            f"{aggressor} territory controllers",
            data.get("aggressor_occupation_breakdown", []),
        )

        chip_gap = 10
        chip_w = (content_w - chip_gap * 2) // 3
        chip_y = popup_rect.bottom - 76
        transfer_y = breakdown_y + 126
        transfer_h = max(56, min(82, chip_y - transfer_y - 12))
        transfer_rect = pygame.Rect(content_x, transfer_y, content_w, transfer_h)
        self._draw_vertical_gradient_rect(surface, transfer_rect, (13, 21, 34), (7, 12, 20), radius=6)
        pygame.draw.rect(surface, (43, 56, 73), transfer_rect, 1, border_radius=6)
        self._draw_text_fit(surface, "Occupation Transfers", _C_GOLD_BRIGHT, transfer_rect.x + 12, transfer_rect.y + 9, transfer_rect.width - 24, self.font_bold)
        transfer_lines = data.get("occupation_transfers", [])
        line_y = transfer_rect.y + 34
        if not transfer_lines:
            self._draw_text_fit(surface, "No third-party occupation handoffs tracked yet.", _C_TEXT_MUTED, transfer_rect.x + 12, line_y, transfer_rect.width - 24)
        else:
            for transfer in transfer_lines[:2]:
                if transfer.get("from_occupation"):
                    line = (
                        f"{transfer.get('controller', 'Unknown')} seized {transfer.get('owner', 'Unknown')} "
                        f"{transfer.get('provinceid', 'province')} from {transfer.get('previous_controller', 'Unknown')}'s occupation"
                    )
                else:
                    line = (
                        f"{transfer.get('controller', 'Unknown')} occupied {transfer.get('owner', 'Unknown')} "
                        f"{transfer.get('provinceid', 'province')}"
                    )
                self._draw_text_fit(surface, line, _C_TEXT, transfer_rect.x + 12, line_y, transfer_rect.width - 24)
                line_y += 20

        self._draw_metric_chip(
            surface,
            pygame.Rect(content_x, chip_y, chip_w, 50),
            f"{aggressor} losses",
            self._format_number(data.get("aggressor_casualties", 0)),
            icon_key="manpower",
            accent=_C_DANGER,
        )
        self._draw_metric_chip(
            surface,
            pygame.Rect(content_x + chip_w + chip_gap, chip_y, chip_w, 50),
            f"{defender} losses",
            self._format_number(data.get("defender_casualties", 0)),
            icon_key="manpower",
            accent=_C_DANGER,
        )
        total_casualties = int(data.get("total_casualties", 0) or 0)
        self._draw_metric_chip(
            surface,
            pygame.Rect(content_x + (chip_w + chip_gap) * 2, chip_y, chip_w, 50),
            "Total casualties",
            self._format_number(total_casualties),
            icon_key="COMBAT",
            accent=_C_DANGER,
        )

    def _draw_glow_btn(self, surface, key, rect, enabled, label, primary=False, mouse=None, icon_key=None):
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
            top = (26, 93, 60) if hovered else ((20, 74, 50) if enabled else (48, 53, 60))
            bottom = (9, 38, 29) if enabled else (35, 38, 43)
            border = (72, 183, 123) if enabled else (69, 75, 84)
        else:
            top = (31, 48, 74) if hovered else ((22, 34, 53) if enabled else (48, 53, 60))
            bottom = (11, 17, 27) if enabled else (35, 38, 43)
            border = _C_GOLD if hovered and enabled else ((69, 84, 104) if enabled else (69, 75, 84))

        self._draw_vertical_gradient_rect(surface, rect, top, bottom, radius=radius)
        pygame.draw.rect(surface, border, rect, 1, border_radius=radius)

        if glow > 0.01 and enabled:
            w, h = rect.size
            glow_surf = pygame.Surface((w + 24, h + 24), pygame.SRCALPHA)
            for ring in range(5):
                ring_alpha = int(glow * (28 - ring * 5))
                if ring_alpha <= 0:
                    continue
                offset = ring * 2 + 2
                gw = w + offset * 2
                gh = h + offset * 2
                glow_color = _C_SUCCESS if primary else _C_GOLD
                pygame.draw.rect(glow_surf, (*glow_color, ring_alpha),
                    (12 - offset, 12 - offset, gw, gh),
                    border_radius=radius + offset, width=2)
            surface.blit(glow_surf, (rect.x - 12, rect.y - 12))

        if hovered:
            text_color = _C_TEXT
            fnt = self.font_bold
        elif primary and enabled:
            text_color = _C_TEXT
            fnt = self.font
        else:
            text_color = _C_TEXT if enabled else _C_TEXT_MUTED
            fnt = self.font
        txt = fnt.render(label, True, text_color)
        icon = self._topbar_icons.get(icon_key) if icon_key else None
        if icon is not None and rect.width >= 80:
            gap = 6
            total_width = icon.get_width() + gap + txt.get_width()
            start_x = rect.centerx - total_width // 2
            surface.blit(icon, (start_x, rect.centery - icon.get_height() // 2))
            surface.blit(txt, (start_x + icon.get_width() + gap, rect.centery - txt.get_height() // 2))
        else:
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
