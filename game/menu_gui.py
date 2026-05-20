import math
import os
import shutil
import sys

import pygame

from engine.runtime import main as run_game
from game.animation.motion import (
    AmbientParticleField,
    PulseLayer,
    clamp,
    draw_light_sweep,
    draw_scanlines,
    draw_soft_glow,
    ease_out_back,
    exp_lerp,
    mix_color,
    pulse,
    scale_rect,
)
from game.script_menu import ScriptMenuController


WIDTH, HEIGHT = 1280, 720

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_FONTS = os.path.join(_ROOT, "fonts")
_IMAGES = os.path.join(_ROOT, "images")
_MENU_BACKGROUND = os.path.join(_IMAGES, "Game Menu UI Design (1).png")

_C_TEXT = (248, 250, 252)
_C_MUTED = (156, 163, 175)
_C_GOLD = (212, 169, 77)
_C_GOLD_BRIGHT = (242, 204, 119)
_C_BLUE = (74, 143, 231)
_C_DANGER = (224, 93, 93)


def remove_cache():
    targets = [
        os.path.join(_ROOT, ".ebee_super_optimization"),
        os.path.join(_ROOT, "map", ".ebee_super_optimization"),
    ]
    for path in targets:
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
                print(f"Deleted {path}")
        except Exception as exc:
            print(f"Error deleting {path}: {exc}")


def _load_font(name, size, fallback="bahnschrift", bold=False):
    filepath = os.path.join(_FONTS, name)
    if os.path.isfile(filepath):
        return pygame.font.Font(filepath, size)
    return pygame.font.SysFont(fallback, size, bold=bold)


def _safe_sound(path, volume=0.4):
    try:
        sound = pygame.mixer.Sound(path)
        sound.set_volume(volume)
        return sound
    except pygame.error:
        return None


def _draw_vertical_gradient(surface, rect, top_color, bottom_color, radius=0):
    if rect.width <= 0 or rect.height <= 0:
        return
    gradient = pygame.Surface(rect.size, pygame.SRCALPHA)
    for y in range(rect.height):
        t = y / max(1, rect.height - 1)
        color = mix_color(top_color, bottom_color, t)
        pygame.draw.line(gradient, (*color, 255), (0, y), (rect.width, y))
    if radius:
        mask = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255), mask.get_rect(), border_radius=radius)
        gradient.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(gradient, rect.topleft)


class AnimatedMainMenu:
    def __init__(self, is_fullscreen=False):
        self.is_fullscreen = bool(is_fullscreen)
        flags = pygame.FULLSCREEN if self.is_fullscreen else 0
        size = (0, 0) if self.is_fullscreen else (WIDTH, HEIGHT)
        self.screen = pygame.display.set_mode(size, flags)
        pygame.display.set_caption("Ebee Conquest - Main Menu")
        self.clock = pygame.time.Clock()
        self.running = True
        self.menu = "main"
        self.menu_transition = 1.0
        self.volume = 50
        self.volume_dragging = False
        self.mouse = (0, 0)
        self.notice = None
        self.notice_time = 0.0

        self.title_font = _load_font("Inter_18pt-Medium.ttf", 42, bold=True)
        self.heading_font = _load_font("Inter_18pt-Medium.ttf", 28, bold=True)
        self.main_font = _load_font("Inter_18pt-Medium.ttf", 18)
        self.small_font = _load_font("Inter_18pt-Medium.ttf", 13)

        self.click_sound = _safe_sound("game/sounds/click.wav")
        self.script_menu = ScriptMenuController()
        self.particles = AmbientParticleField(96, seed=37)
        self.pulses = PulseLayer()
        self.button_motion = {}
        self._bg_surface = None
        self._bg_size = None
        self._refresh_background()

    def _refresh_background(self):
        size = self.screen.get_size()
        if size == self._bg_size:
            return
        self._bg_size = size
        try:
            image = pygame.image.load(_MENU_BACKGROUND).convert()
            self._bg_surface = pygame.transform.smoothscale(image, size)
        except pygame.error:
            self._bg_surface = pygame.Surface(size)
            self._bg_surface.fill((8, 12, 20))

    def _play_click(self):
        if self.click_sound is not None:
            self.click_sound.play()

    def _set_menu(self, name):
        if name == self.menu:
            return
        self.menu = name
        self.menu_transition = 0.0
        if name == "scripts":
            self.script_menu._opened_at = pygame.time.get_ticks() / 1000.0
        self.pulses.emit(self.screen.get_rect().center, _C_GOLD, radius=220, duration=0.8, width=3)

    def _toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        flags = pygame.FULLSCREEN if self.is_fullscreen else 0
        size = (0, 0) if self.is_fullscreen else (WIDTH, HEIGHT)
        self.screen = pygame.display.set_mode(size, flags)
        self._bg_size = None
        self._refresh_background()
        self.pulses.emit(self.screen.get_rect().center, _C_BLUE, radius=260, duration=0.9, width=2)

    def _main_button_rects(self):
        w, h = self.screen.get_size()
        scale = 1.22 if self.is_fullscreen else max(0.9, min(1.08, w / WIDTH))
        button_w = int(312 * scale)
        button_h = int(56 * scale)
        gap = int(15 * scale)
        labels = [
            ("new_game", "NEW GAME"),
            ("load_game", "LOAD GAME"),
            ("scripts", "SCRIPTS"),
            ("settings", "SETTINGS"),
            ("quit", "QUIT"),
        ]
        total_h = len(labels) * button_h + (len(labels) - 1) * gap
        start_y = int(h * 0.5 - total_h * 0.42)
        start_x = int(w * 0.5 - button_w * 0.5)
        return [
            (key, label, pygame.Rect(start_x, start_y + i * (button_h + gap), button_w, button_h))
            for i, (key, label) in enumerate(labels)
        ]

    def _button_hover_value(self, key, hovered, dt, speed=10.0):
        motion = self.button_motion.setdefault(key, {"hover": 0.0, "press": 0.0})
        motion["hover"] = exp_lerp(motion["hover"], 1.0 if hovered else 0.0, speed, dt)
        motion["press"] = exp_lerp(motion["press"], 0.0, 13.0, dt)
        return motion

    def _button_click(self, key, rect):
        motion = self.button_motion.setdefault(key, {"hover": 0.0, "press": 0.0})
        motion["press"] = 1.0
        self.pulses.emit(rect.center, _C_GOLD_BRIGHT, radius=90, duration=0.45, width=2)
        self._play_click()

    def _draw_button(self, rect, key, label, dt, primary=False, danger=False):
        hovered = rect.collidepoint(self.mouse)
        motion = self._button_hover_value(key, hovered, dt)
        hover = motion["hover"]
        press = motion["press"]
        t = pygame.time.get_ticks() / 1000.0
        scale = 1.0 + hover * 0.055 - press * 0.035
        offset_x = math.sin(t * 2.2 + len(key)) * hover * 3.0
        draw_rect = scale_rect(rect, scale, (offset_x, 0))
        radius = 8

        accent = _C_DANGER if danger else (_C_BLUE if not primary else _C_GOLD)
        draw_soft_glow(self.screen, draw_rect, accent, hover * 0.95 + press * 0.9, radius=radius, rings=5)
        top = mix_color((16, 25, 42), (34, 54, 86), hover)
        bottom = mix_color((6, 10, 18), (13, 24, 42), hover)
        if primary:
            top = mix_color((31, 56, 64), (98, 76, 30), hover * 0.85)
            bottom = mix_color((7, 24, 29), (42, 27, 10), hover * 0.7)
        if danger:
            top = mix_color((38, 30, 35), (90, 38, 45), hover)
            bottom = mix_color((18, 12, 17), (42, 14, 20), hover)

        _draw_vertical_gradient(self.screen, draw_rect, top, bottom, radius=radius)
        pygame.draw.rect(self.screen, mix_color((69, 84, 104), accent, hover), draw_rect, 1, border_radius=radius)
        pygame.draw.line(
            self.screen,
            (*mix_color((105, 121, 142), accent, 0.65 + hover * 0.35),),
            (draw_rect.x + 14, draw_rect.y + 2),
            (draw_rect.right - 14, draw_rect.y + 2),
            1,
        )
        draw_light_sweep(self.screen, draw_rect, t + len(key) * 0.33, accent, alpha=int(18 + hover * 34))

        glyph_x = draw_rect.x + 24
        glyph_y = draw_rect.centery
        glyph_color = mix_color((92, 116, 144), accent, 0.4 + hover * 0.6)
        glyph_radius = int(8 + hover * 4)
        pygame.draw.circle(self.screen, glyph_color, (glyph_x, glyph_y), glyph_radius, 1)
        pygame.draw.line(self.screen, glyph_color, (glyph_x - 12, glyph_y), (glyph_x + 12, glyph_y), 1)
        pygame.draw.line(self.screen, glyph_color, (glyph_x, glyph_y - 12), (glyph_x, glyph_y + 12), 1)

        text_color = mix_color(_C_TEXT, _C_GOLD_BRIGHT if primary else (226, 236, 248), hover)
        font = self.heading_font if draw_rect.height >= 60 else self.main_font
        text_surface = font.render(label, True, text_color)
        text_rect = text_surface.get_rect(center=(draw_rect.centerx + int(hover * 4), draw_rect.centery))
        self.screen.blit(text_surface, text_rect)
        return hovered

    def _draw_background(self, dt):
        self._refresh_background()
        w, h = self.screen.get_size()
        t = pygame.time.get_ticks() / 1000.0
        if self._bg_surface:
            self.screen.blit(self._bg_surface, (0, 0))

        wash = pygame.Surface((w, h), pygame.SRCALPHA)
        wash.fill((2, 6, 14, 132))
        pygame.draw.rect(wash, (0, 0, 0, 98), pygame.Rect(0, 0, int(w * 0.34), h))
        pygame.draw.rect(wash, (0, 0, 0, 74), pygame.Rect(int(w * 0.66), 0, int(w * 0.34), h))
        self.screen.blit(wash, (0, 0))

        self.particles.draw(self.screen, self.screen.get_rect(), t, color=(124, 196, 255), parallax=(0.0, 0.0))
        draw_scanlines(self.screen, self.screen.get_rect(), t, color=(74, 143, 231), alpha=14, spacing=32)
        self.pulses.update(dt)
        self.pulses.draw(self.screen)

    def _handle_main_click(self):
        for key, _label, rect in self._main_button_rects():
            if not rect.collidepoint(self.mouse):
                continue
            self._button_click(key, rect)
            if key == "new_game":
                self._launch_transition(rect)
                run_game(is_fullscreen=self.is_fullscreen)
                pygame.quit()
                sys.exit()
            if key == "settings":
                self._set_menu("settings")
            elif key == "scripts":
                self._set_menu("scripts")
            elif key == "quit":
                self.running = False
            elif key == "load_game":
                self.notice = "Save loading is not implemented yet."
                self.notice_time = 2.4
            return

    def _launch_transition(self, origin_rect):
        start_time = pygame.time.get_ticks() / 1000.0
        duration = 0.78
        while True:
            dt = self.clock.tick(144) / 1000.0
            self.mouse = pygame.mouse.get_pos()
            elapsed = pygame.time.get_ticks() / 1000.0 - start_time
            progress = clamp(elapsed / duration)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return

            self._draw_background(dt)
            self._draw_main(dt)

            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(185 * progress)))
            self.screen.blit(overlay, (0, 0))

            cx, cy = origin_rect.center
            radius = int(40 + progress * max(self.screen.get_size()) * 0.82)
            pulse_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            pygame.draw.circle(pulse_surface, (*_C_GOLD_BRIGHT, int(120 * (1.0 - progress))), (cx, cy), radius, 3)
            pygame.draw.circle(pulse_surface, (*_C_BLUE, int(70 * (1.0 - progress))), (cx, cy), max(1, radius // 2), 1)
            self.screen.blit(pulse_surface, (0, 0))

            pygame.display.flip()
            if progress >= 1.0:
                return

    def _draw_main(self, dt):
        for index, (key, label, rect) in enumerate(self._main_button_rects()):
            staged = clamp((self.menu_transition - index * 0.045) / 0.82)
            enter = ease_out_back(staged)
            draw_rect = rect.move(int((1.0 - enter) * 84), int((1.0 - enter) * 22))
            self._draw_button(draw_rect, key, label, dt, primary=key == "new_game", danger=key == "quit")

        if self.notice_time > 0.0 and self.notice:
            self.notice_time = max(0.0, self.notice_time - dt)
            alpha = int(230 * clamp(min(self.notice_time, 0.35) / 0.35))
            surf = self.main_font.render(self.notice, True, _C_TEXT)
            pad = 18
            rect = surf.get_rect()
            rect.inflate_ip(pad * 2, 18)
            rect.center = (self.screen.get_width() // 2, int(self.screen.get_height() * 0.84))
            toast = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(toast, (7, 13, 22, alpha), toast.get_rect(), border_radius=8)
            pygame.draw.rect(toast, (*_C_GOLD, alpha), toast.get_rect(), 1, border_radius=8)
            toast.blit(surf, surf.get_rect(center=toast.get_rect().center))
            self.screen.blit(toast, rect.topleft)

    def _settings_controls(self):
        w, h = self.screen.get_size()
        panel_w = min(720, max(440, int(w * 0.54)))
        panel_h = 430
        panel = pygame.Rect(0, 0, panel_w, panel_h)
        panel.center = (w // 2, h // 2)
        slider = pygame.Rect(panel.x + 54, panel.y + 128, panel.width - 108, 12)
        fullscreen = pygame.Rect(panel.x + 54, panel.y + 182, panel.width - 108, 52)
        back = pygame.Rect(panel.x + 54, panel.y + 254, (panel.width - 124) // 2, 50)
        cache = pygame.Rect(back.right + 16, back.y, back.width, 50)
        return panel, slider, fullscreen, back, cache

    def _draw_settings(self, dt):
        panel, slider, fullscreen, back, cache = self._settings_controls()
        t = pygame.time.get_ticks() / 1000.0
        enter = ease_out_back(self.menu_transition)
        panel = panel.move(0, int((1.0 - enter) * 42))
        draw_soft_glow(self.screen, panel, _C_GOLD, 0.32 + pulse(t, 1.5) * 0.12, radius=12, rings=7)
        _draw_vertical_gradient(self.screen, panel, (18, 27, 42), (6, 10, 18), radius=10)
        pygame.draw.rect(self.screen, (86, 78, 52), panel, 1, border_radius=10)
        draw_light_sweep(self.screen, panel, t, _C_GOLD_BRIGHT, alpha=22)

        title = self.heading_font.render("SETTINGS", True, _C_GOLD_BRIGHT)
        self.screen.blit(title, (panel.x + 34, panel.y + 30))
        volume_label = self.main_font.render(f"Volume: {self.volume}%", True, _C_TEXT)
        self.screen.blit(volume_label, (slider.x, slider.y - 34))

        pygame.draw.rect(self.screen, (36, 45, 60), slider, border_radius=6)
        fill = slider.copy()
        fill.width = int(slider.width * self.volume / 100)
        _draw_vertical_gradient(self.screen, fill, (83, 199, 132), (39, 130, 82), radius=6)
        knob_x = slider.x + fill.width
        knob_hover = abs(self.mouse[0] - knob_x) < 18 and abs(self.mouse[1] - slider.centery) < 18
        knob_radius = 10 + int((knob_hover or self.volume_dragging) * 3)
        pygame.draw.circle(self.screen, _C_TEXT, (knob_x, slider.centery), knob_radius)
        pygame.draw.circle(self.screen, _C_GOLD, (knob_x, slider.centery), knob_radius + 4, 1)

        fs_label = "FULLSCREEN: ON" if self.is_fullscreen else "FULLSCREEN: OFF"
        self._draw_button(fullscreen, "settings_fullscreen", fs_label, dt, primary=self.is_fullscreen)
        self._draw_button(back, "settings_back", "BACK", dt)
        self._draw_button(cache, "settings_cache", "REMOVE CACHE", dt, danger=True)

        warning = self.small_font.render("Removing cache rebuilds map geometry next launch.", True, (236, 166, 166))
        self.screen.blit(warning, (panel.x + 54, panel.bottom - 50))

    def _handle_settings_click(self):
        panel, slider, fullscreen, back, cache = self._settings_controls()
        if slider.inflate(6, 24).collidepoint(self.mouse):
            self.volume_dragging = True
            self._update_volume_from_mouse(slider)
            self.pulses.emit((self.mouse[0], slider.centery), (83, 199, 132), radius=60, duration=0.45)
            return
        if fullscreen.collidepoint(self.mouse):
            self._button_click("settings_fullscreen", fullscreen)
            self._toggle_fullscreen()
            return
        if back.collidepoint(self.mouse):
            self._button_click("settings_back", back)
            self._set_menu("main")
            return
        if cache.collidepoint(self.mouse):
            self._button_click("settings_cache", cache)
            remove_cache()
            self.notice = "Cache removed."
            self.notice_time = 2.2

    def _update_volume_from_mouse(self, slider=None):
        if slider is None:
            _panel, slider, _fullscreen, _back, _cache = self._settings_controls()
        self.volume = int(clamp((self.mouse[0] - slider.x) / max(1, slider.width)) * 100)
        try:
            pygame.mixer.music.set_volume(self.volume / 100.0)
        except pygame.error:
            pass

    def _draw_scripts(self):
        self.script_menu.draw(self.screen)

    def _handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.menu == "main":
                self.running = False
            else:
                self._set_menu("main")
            return

        if self.menu == "scripts":
            action = self.script_menu.handle_event(event, self.mouse, self.screen.get_size())
            if action == "back":
                self._play_click()
                self._set_menu("main")
            elif action == "handled":
                self._play_click()
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.pulses.emit(self.mouse, _C_BLUE, radius=72, duration=0.45)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.menu == "main":
                self._handle_main_click()
            elif self.menu == "settings":
                self._handle_settings_click()

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.volume_dragging = False

        elif event.type == pygame.MOUSEMOTION and self.volume_dragging and self.menu == "settings":
            self._update_volume_from_mouse()

    def run(self):
        while self.running:
            dt = self.clock.tick(144) / 1000.0
            dt = max(0.0, min(0.05, dt))
            self.mouse = pygame.mouse.get_pos()
            self.menu_transition = min(1.0, self.menu_transition + dt * 2.9)

            for event in pygame.event.get():
                self._handle_event(event)

            self._draw_background(dt)
            if self.menu == "settings":
                self._draw_settings(dt)
            elif self.menu == "scripts":
                self._draw_scripts()
            else:
                self._draw_main(dt)
            pygame.display.flip()


def main():
    pygame.mixer.pre_init(44100, -16, 2, 1024)
    pygame.init()
    AnimatedMainMenu().run()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
