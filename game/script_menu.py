import pygame

from engine import EbeeEngine
from game.animation.motion import (
    AmbientParticleField,
    clamp,
    draw_light_sweep,
    draw_scanlines,
    draw_soft_glow,
    ease_out_back,
    exp_lerp,
    mix_color,
    scale_rect,
)


class ScriptMenuController:
    def __init__(self, scriptfolder="scripts"):
        self.engine = EbeeEngine()
        self.manager = self.engine.initscripts(scriptfolder, autoload=False)
        self.backrect = pygame.Rect(0, 0, 1, 1)
        self.togglerects = {}
        self.scroll = 0
        self._opened_at = pygame.time.get_ticks() / 1000.0
        self._button_motion = {}
        self._row_motion = {}
        self._particles = AmbientParticleField(44, seed=91)

    def handle_event(self, event, mouseposition, screensize):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None

        if self.backrect.collidepoint(mouseposition):
            return "back"

        for scriptname, rect in self.togglerects.items():
            if rect.collidepoint(mouseposition):
                self.toggle_script(scriptname)
                return "handled"

        return None

    def draw(self, screen):
        width, height = screen.get_size()
        now = pygame.time.get_ticks() / 1000.0
        open_progress = clamp((now - self._opened_at) / 0.5)
        eased_open = ease_out_back(open_progress)
        titlefont = pygame.font.SysFont("Arial", 34, bold=True)
        font = pygame.font.SysFont("Arial", 18)
        smallfont = pygame.font.SysFont("Arial", 14)

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(174 + eased_open * 54)))
        screen.blit(overlay, (0, 0))
        self._particles.draw(screen, screen.get_rect(), now, color=(124, 196, 255))
        draw_scanlines(screen, screen.get_rect(), now, alpha=10, spacing=34)

        panel = pygame.Rect(width // 2 - 360, 70, 720, max(420, height - 140))
        panel = panel.move(0, int((1.0 - eased_open) * 42))
        draw_soft_glow(screen, panel, (212, 169, 77), 0.38, radius=10, rings=6)
        self.draw_panel(screen, panel, now)

        title = titlefont.render("SCRIPTS", True, (245, 245, 245))
        screen.blit(title, (panel.x + 24, panel.y + 22))

        self.backrect = pygame.Rect(panel.right - 118, panel.y + 22, 92, 36)
        self.draw_button(screen, self.backrect, "Back", font)

        scripts = self.manager.get_loaded_scripts()
        listtop = panel.y + 82
        rowheight = 52
        self.togglerects = {}

        if not scripts:
            empty = font.render("NO SCRIPTS!! found in /scripts.", True, (220, 220, 220))
            screen.blit(empty, (panel.x + 24, listtop + 24))
            return

        header = smallfont.render("LOADED from /scripts", True, (180, 188, 198))
        screen.blit(header, (panel.x + 24, listtop - 22))

        maxrows = max(1, (panel.bottom - listtop - 24) // rowheight)
        for index, script in enumerate(scripts[:maxrows]):
            y = listtop + index * rowheight
            rowrect = pygame.Rect(panel.x + 18, y, panel.width - 36, rowheight - 8)
            staged = clamp((open_progress - index * 0.035) / 0.7)
            rowrect = rowrect.move(int((1.0 - ease_out_back(staged)) * 44), 0)

            enabled = bool(script.get("enabled"))
            name = str(script.get("name", "unknown"))
            status = "enabled" if enabled else "disabled"
            statuscolor = (120, 220, 140) if enabled else (230, 130, 120)
            hover = rowrect.collidepoint(pygame.mouse.get_pos())
            rowkey = f"row:{name}"
            value = self._row_motion.get(rowkey, 0.0)
            value = exp_lerp(value, 1.0 if hover else 0.0, 9.0, 1.0 / 60.0)
            self._row_motion[rowkey] = value
            drawrect = scale_rect(rowrect, 1.0 + value * 0.015)
            draw_soft_glow(screen, drawrect, statuscolor, value * 0.45, radius=6, rings=3)
            top = mix_color((28, 35, 46), (38, 52, 72), value)
            bottom = mix_color((15, 22, 34), (20, 31, 48), value)
            self.draw_gradient_rect(screen, drawrect, top, bottom, radius=5)
            pygame.draw.rect(screen, mix_color((54, 65, 80), statuscolor, value * 0.55), drawrect, 1, border_radius=5)
            pygame.draw.line(screen, statuscolor, (drawrect.x + 6, drawrect.y + 8), (drawrect.x + 6, drawrect.bottom - 8), 2)

            namesurface = font.render(name, True, (240, 240, 240))
            statussurface = smallfont.render(status, True, statuscolor)
            screen.blit(namesurface, (drawrect.x + 18, drawrect.y + 8))
            screen.blit(statussurface, (drawrect.x + 18, drawrect.y + 30))

            buttonlabel = "Disable" if enabled else "Enable"
            togglerect = pygame.Rect(drawrect.right - 126, drawrect.y + 8, 104, 28)
            self.togglerects[name] = togglerect
            self.draw_button(screen, togglerect, buttonlabel, smallfont)

    def toggle_script(self, scriptname):
        if self.manager.is_enabled(scriptname):
            self.manager.disable_script(scriptname)
        else:
            self.manager.enable_script(scriptname)

    def draw_button(self, screen, rect, label, font):
        mouse = pygame.mouse.get_pos()
        hover = rect.collidepoint(mouse)
        key = f"button:{label}:{rect.x}:{rect.y}"
        value = self._button_motion.get(key, 0.0)
        value = exp_lerp(value, 1.0 if hover else 0.0, 10.0, 1.0 / 60.0)
        self._button_motion[key] = value
        drawrect = scale_rect(rect, 1.0 + value * 0.04)
        fill = mix_color((35, 47, 64), (64, 82, 104), value)
        border = mix_color((140, 78, 38), (220, 122, 48), value)
        draw_soft_glow(screen, drawrect, border, value * 0.72, radius=5, rings=3)
        self.draw_gradient_rect(screen, drawrect, fill, (14, 20, 32), radius=4)
        pygame.draw.rect(screen, border, drawrect, 1, border_radius=4)
        draw_light_sweep(screen, drawrect, pygame.time.get_ticks() / 1000.0, border, alpha=int(10 + value * 25))
        text = font.render(label, True, (245, 245, 245))
        screen.blit(text, text.get_rect(center=drawrect.center))

    def draw_panel(self, screen, panel, now):
        self.draw_gradient_rect(screen, panel, (18, 24, 34), (7, 11, 19), radius=8)
        pygame.draw.rect(screen, (120, 78, 36), panel, 2, border_radius=8)
        pygame.draw.line(screen, (232, 190, 86), (panel.x + 18, panel.y + 1), (panel.right - 18, panel.y + 1), 1)
        draw_light_sweep(screen, panel, now, (232, 190, 86), alpha=18)

    @staticmethod
    def draw_gradient_rect(screen, rect, top, bottom, radius=0):
        if rect.width <= 0 or rect.height <= 0:
            return
        gradient = pygame.Surface(rect.size, pygame.SRCALPHA)
        for y in range(rect.height):
            color = mix_color(top, bottom, y / max(1, rect.height - 1))
            pygame.draw.line(gradient, (*color, 255), (0, y), (rect.width, y))
        if radius:
            mask = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
            gradient.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(gradient, rect.topleft)
