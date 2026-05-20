import math
import random

import pygame


def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def lerp(start, end, t):
    return start + (end - start) * t


def smoothstep(t):
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def ease_out_cubic(t):
    t = clamp(t)
    return 1.0 - pow(1.0 - t, 3)


def ease_out_back(t, overshoot=1.42):
    t = clamp(t) - 1.0
    return 1.0 + t * t * ((overshoot + 1.0) * t + overshoot)


def ease_in_out_sine(t):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(t))


def exp_lerp(current, target, speed, dt):
    try:
        dt = max(0.0, min(0.25, float(dt or 0.0)))
    except (TypeError, ValueError):
        dt = 0.0
    if dt <= 0.0:
        return current
    return lerp(current, target, 1.0 - pow(0.001, dt * max(0.01, speed)))


def pulse(time_value, speed=1.0, phase=0.0):
    return 0.5 + 0.5 * math.sin(time_value * speed + phase)


def mix_color(first, second, t):
    t = clamp(t)
    return tuple(int(first[i] + (second[i] - first[i]) * t) for i in range(3))


def scale_rect(rect, scale, offset=(0, 0)):
    scaled = rect.copy()
    scaled.width = max(1, int(rect.width * scale))
    scaled.height = max(1, int(rect.height * scale))
    scaled.center = (int(rect.centerx + offset[0]), int(rect.centery + offset[1]))
    return scaled


def draw_soft_glow(surface, rect, color, strength=1.0, radius=8, rings=5):
    strength = clamp(strength)
    if strength <= 0.01 or rect.width <= 0 or rect.height <= 0:
        return
    glow_surface = pygame.Surface(
        (rect.width + rings * radius * 2, rect.height + rings * radius * 2),
        pygame.SRCALPHA,
    )
    origin = rings * radius
    for ring in range(rings):
        alpha = int(strength * max(0, 42 - ring * 7))
        if alpha <= 0:
            continue
        offset = ring * radius // 2 + 2
        ring_rect = pygame.Rect(
            origin - offset,
            origin - offset,
            rect.width + offset * 2,
            rect.height + offset * 2,
        )
        pygame.draw.rect(
            glow_surface,
            (*color[:3], alpha),
            ring_rect,
            width=2,
            border_radius=max(1, int(radius + offset)),
        )
    surface.blit(glow_surface, (rect.x - origin, rect.y - origin))


def draw_scanlines(surface, rect, time_value, color=(74, 143, 231), alpha=16, spacing=28):
    if rect.width <= 0 or rect.height <= 0:
        return
    overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
    offset = int((time_value * 42.0) % max(1, spacing))
    for y in range(-spacing, rect.height + spacing, spacing):
        line_y = y + offset
        pygame.draw.line(overlay, (*color, alpha), (0, line_y), (rect.width, line_y), 1)
    surface.blit(overlay, rect.topleft)


def draw_light_sweep(surface, rect, time_value, color=(255, 230, 150), alpha=38):
    if rect.width <= 0 or rect.height <= 0:
        return
    travel = rect.width + rect.height + 120
    sweep_x = int((time_value * 180.0) % travel) - rect.height - 60
    sweep = pygame.Surface(rect.size, pygame.SRCALPHA)
    points = [
        (sweep_x, 0),
        (sweep_x + 36, 0),
        (sweep_x + rect.height + 36, rect.height),
        (sweep_x + rect.height, rect.height),
    ]
    pygame.draw.polygon(sweep, (*color[:3], alpha), points)
    surface.blit(sweep, rect.topleft)


def draw_animated_icon(
    surface,
    icon,
    center,
    time_value,
    hover=0.0,
    accent=(212, 169, 77),
    phase=0.0,
):
    if icon is None:
        return pygame.Rect(center[0], center[1], 0, 0)
    hover = clamp(hover)
    bob = math.sin(time_value * 2.8 + phase) * hover * 3.0
    scale = 1.0 + hover * (0.14 + math.sin(time_value * 3.6 + phase) * 0.018)
    angle = math.sin(time_value * 3.2 + phase) * hover * 4.0
    rendered = pygame.transform.rotozoom(icon, angle, scale)
    rect = rendered.get_rect(center=(int(center[0]), int(center[1] + bob)))
    if hover > 0.02:
        glow_rect = rect.inflate(10, 10)
        glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*accent[:3], int(42 * hover)), glow.get_rect())
        surface.blit(glow, glow_rect.topleft)
    surface.blit(rendered, rect)
    return rect


class MotionValue:
    def __init__(self, value=0.0):
        self.value = float(value)

    def update(self, target, dt, speed=8.0):
        self.value = exp_lerp(self.value, float(target), speed, dt)
        return self.value


class PulseLayer:
    def __init__(self):
        self.pulses = []

    def emit(self, position, color=(212, 169, 77), radius=96, duration=0.75, width=2):
        if position is None:
            return
        self.pulses.append(
            {
                "x": float(position[0]),
                "y": float(position[1]),
                "color": tuple(color[:3]),
                "radius": float(radius),
                "duration": max(0.05, float(duration)),
                "age": 0.0,
                "width": max(1, int(width)),
            }
        )
        if len(self.pulses) > 42:
            self.pulses = self.pulses[-42:]

    def update(self, dt):
        alive = []
        for entry in self.pulses:
            entry["age"] += max(0.0, float(dt or 0.0))
            if entry["age"] < entry["duration"]:
                alive.append(entry)
        self.pulses = alive

    def draw(self, surface, offset=(0, 0)):
        for entry in self.pulses:
            progress = clamp(entry["age"] / entry["duration"])
            eased = ease_out_cubic(progress)
            radius = max(2, int(entry["radius"] * eased))
            alpha = int(150 * (1.0 - progress) ** 1.7)
            if alpha <= 0:
                continue
            size = radius * 2 + 8
            pulse_surface = pygame.Surface((size, size), pygame.SRCALPHA)
            center = (size // 2, size // 2)
            pygame.draw.circle(
                pulse_surface,
                (*entry["color"], alpha),
                center,
                radius,
                max(1, entry["width"]),
            )
            inner_alpha = int(alpha * 0.26)
            if inner_alpha > 0:
                pygame.draw.circle(pulse_surface, (*entry["color"], inner_alpha), center, max(1, radius // 3))
            surface.blit(
                pulse_surface,
                (
                    int(entry["x"] + offset[0] - size // 2),
                    int(entry["y"] + offset[1] - size // 2),
                ),
            )


class AmbientParticleField:
    def __init__(self, count=80, seed=11):
        self.count = count
        self.seed = seed
        self._size = None
        self._particles = []

    def _reset(self, size):
        rng = random.Random(self.seed)
        width, height = max(1, size[0]), max(1, size[1])
        self._particles = []
        for index in range(self.count):
            self._particles.append(
                {
                    "x": rng.random() * width,
                    "y": rng.random() * height,
                    "speed": rng.uniform(8.0, 32.0),
                    "drift": rng.uniform(-18.0, 18.0),
                    "size": rng.uniform(1.0, 2.7),
                    "phase": rng.uniform(0.0, math.tau),
                    "alpha": rng.randint(16, 58),
                    "index": index,
                }
            )
        self._size = (width, height)

    def draw(self, surface, rect, time_value, color=(124, 196, 255), parallax=(0.0, 0.0)):
        if rect.width <= 0 or rect.height <= 0:
            return
        if self._size != rect.size:
            self._reset(rect.size)
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        width, height = rect.size
        for particle in self._particles:
            x = (particle["x"] + math.sin(time_value * 0.5 + particle["phase"]) * particle["drift"] + parallax[0]) % width
            y = (particle["y"] + time_value * particle["speed"] + parallax[1]) % height
            glow = pulse(time_value, 1.4, particle["phase"])
            alpha = int(particle["alpha"] * (0.55 + glow * 0.45))
            radius = max(1, int(particle["size"] + glow * 1.4))
            pygame.draw.circle(overlay, (*color[:3], alpha), (int(x), int(y)), radius)
            if particle["index"] % 7 == 0:
                pygame.draw.line(
                    overlay,
                    (*color[:3], max(8, alpha // 2)),
                    (int(x), int(y)),
                    (int(x - 8), int(y - 18)),
                    1,
                )
        surface.blit(overlay, rect.topleft)
