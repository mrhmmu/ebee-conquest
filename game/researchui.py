from __future__ import annotations
import json
import os
import pygame
from game.animation.motion import (
    AmbientParticleField,
    draw_light_sweep,
    draw_scanlines,
    draw_soft_glow,
    mix_color,
    pulse,
    scale_rect,
)


_NODE_W      = 164
_NODE_H      = 64
_H_GAP       = 36
_V_GAP       = 28
_TAB_H       = 44
_TOP_H       = 50
_PAD         = 20
_NODE_SPACE_X = _NODE_W + _H_GAP
_NODE_SPACE_Y = _NODE_H + _V_GAP

_C_BG             = (18, 20, 26)
_C_BORDER         = (45, 48, 60)
_C_TITLE          = (200, 170, 80)
_C_HINT           = (140, 140, 150)

_C_TAB_IDLE       = (30, 33, 42)
_C_TAB_HOVER      = (50, 55, 70)
_C_TAB_ACTIVE     = (55, 70, 100)
_C_TAB_BORDER     = (60, 65, 80)

_C_NODE_AVAIL     = (36, 56, 90)
_C_NODE_AVAIL_BD  = (80, 120, 190)
_C_NODE_AVAIL_LB  = (180, 210, 255)

_C_NODE_DONE      = (28, 88, 52)
_C_NODE_DONE_BD   = (60, 170, 100)
_C_NODE_DONE_LB   = (140, 230, 170)

_C_NODE_LOCKED    = (35, 35, 40)
_C_NODE_LOCKED_BD = (55, 55, 65)
_C_NODE_LOCKED_LB = (110, 110, 120)

_C_NODE_HOVER     = (55, 82, 128)
_C_NODE_SEL_BD    = (220, 200, 100)

_C_NODE_RESEARCHING    = (50, 60, 100)
_C_NODE_RESEARCHING_BD = (80, 130, 220)
_C_NODE_RESEARCHING_LB = (150, 200, 255)

_C_LINE_IDLE      = (60, 75, 100)
_C_LINE_DONE      = (55, 140, 90)
_C_LINE_LOCKED    = (50, 50, 58)

_C_CLOSE_BG       = (45, 30, 30)
_C_CLOSE_HOVER    = (80, 30, 30)
_C_CLOSE_BD       = (160, 60, 60)

RESEARCH_RP_PER_TURN = 50

_RESEARCH_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "data", "research")
)


def load_research_data() -> dict[str, dict]:
    categories: dict[str, dict] = {}
    if not os.path.isdir(_RESEARCH_DATA_DIR):
        return categories
    for filename in sorted(os.listdir(_RESEARCH_DATA_DIR)):
        if not filename.lower().endswith(".json"):
            continue
        filepath = os.path.join(_RESEARCH_DATA_DIR, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "id" in data and "nodes" in data:
                categories[data["id"]] = data
        except (json.JSONDecodeError, OSError):
            continue
    return categories


def _wrap_text(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if font.size(candidate)[0] <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


class ResearchTreeView:
    ACTION_RESEARCH = "research_node"

    def __init__(self) -> None:
        self.isopen: bool = False
        self._researched: set[str] = set()
        self._researching_id: str | None = None
        self._researching_turns_remaining: int = 0
        self._selected_id: str | None = None

        self._categories: dict[str, dict] = {}
        self._active_category_id: str | None = None
        self._category_nodes: dict[str, dict[str, dict]] = {}

        self._close_rect: pygame.Rect = pygame.Rect(0, 0, 10, 10)
        self._tab_rects: dict[str, pygame.Rect] = {}

        self._world_rects: dict[str, pygame.Rect] = {}
        self._node_rects: dict[str, pygame.Rect] = {}
        self._viewsize: tuple[int, int] = (0, 0)
        self._layout_ready: bool = False
        self._world_bounds: pygame.Rect = pygame.Rect(0, 0, 1, 1)

        self.zoom = 1.0
        self.minzoom = 0.3
        self.maxzoom = 2.0
        self.panx = 0.0
        self.pany = 0.0
        self.dragging = False
        self.dragbutton = None
        self.dragstart = (0, 0)
        self.panstart = (0.0, 0.0)
        self._particles = AmbientParticleField(68, seed=707)

    def reload_data(self) -> None:
        self._categories = load_research_data()
        self._category_nodes = {}
        for cat_id, cat_data in self._categories.items():
            self._category_nodes[cat_id] = {n["id"]: n for n in cat_data.get("nodes", [])}
        if self._active_category_id is None and self._categories:
            self._active_category_id = "weapons" if "weapons" in self._categories else next(iter(self._categories))
        self._layout_ready = False

    def toggleview(self) -> None:
        self.isopen = not self.isopen
        self._selected_id = None
        if self.isopen:
            self.reload_data()

    def setdata(self, data, researching_id=None, researching_turns_remaining=0) -> None:
        if isinstance(data, (set, frozenset)):
            self._researched = set(data)
        self._researching_id = researching_id
        self._researching_turns_remaining = researching_turns_remaining

    def viewdata(self) -> frozenset:
        return frozenset(self._researched)

    def pointerover(self, pos) -> bool:
        if not self.isopen:
            return False
        return pygame.Rect(0, 0, self._viewsize[0], self._viewsize[1]).collidepoint(pos)

    def handleevent(self, event: pygame.event.Event):
        if not self.isopen:
            return None

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.isopen = False
            return None

        if event.type == pygame.MOUSEWHEEL:
            self._zoomat(pygame.mouse.get_pos(), event.y)
            return None

        if event.type == pygame.MOUSEMOTION and self.dragging:
            pos = event.pos
            self.panx = self.panstart[0] + pos[0] - self.dragstart[0]
            self.pany = self.panstart[1] + pos[1] - self.dragstart[1]
            return None

        if event.type == pygame.MOUSEBUTTONUP and self.dragging:
            if event.button == self.dragbutton:
                self.dragging = False
                self.dragbutton = None
            return None

        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos
            if event.button in (2, 3):
                self._begindrag(pos, event.button)
                return None

            if event.button != 1:
                return None

            if self._close_rect.collidepoint(pos):
                self.isopen = False
                return None

            for tab_id, tab_rect in self._tab_rects.items():
                if tab_rect.collidepoint(pos):
                    if self._active_category_id != tab_id:
                        self._active_category_id = tab_id
                        self._selected_id = None
                        self._layout_ready = False
                    return None

            for node_id, rect in self._node_rects.items():
                if not rect.collidepoint(pos):
                    continue
                status = self._node_status(node_id)
                if status == "researched":
                    self._selected_id = node_id
                    return None
                if status == "available":
                    self._selected_id = node_id
                    return (self.ACTION_RESEARCH, node_id)
                self._selected_id = node_id
                return None

            self._begindrag(pos, event.button)
            return None

        return None

    def _begindrag(self, position, button):
        self.dragging = True
        self.dragbutton = button
        self.dragstart = position
        self.panstart = (self.panx, self.pany)

    def _zoomat(self, position, amount):
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

    def _centerlayout(self, viewrect):
        tree_top = _TOP_H + 28
        tree_bottom = viewrect.height - _TAB_H - 4
        focusarea = pygame.Rect(0, tree_top, viewrect.width, max(1, tree_bottom - tree_top))
        bounds = self._world_bounds
        self.panx = focusarea.centerx - bounds.centerx * self.zoom
        self.pany = focusarea.centery - bounds.centery * self.zoom

    def _screentorect(self, rect):
        return pygame.Rect(
            int(rect.x * self.zoom + self.panx),
            int(rect.y * self.zoom + self.pany),
            max(1, int(rect.width * self.zoom)),
            max(1, int(rect.height * self.zoom)),
        )

    def _screenpoint(self, point):
        return (
            int(point[0] * self.zoom + self.panx),
            int(point[1] * self.zoom + self.pany),
        )

    def draw(
        self,
        surface: pygame.Surface,
        title_font: pygame.font.Font,
        font: pygame.font.Font,
        mouse: tuple[int, int],
    ) -> None:
        if not self.isopen:
            return

        sw, sh = surface.get_size()
        self._viewsize = (sw, sh)

        if not self._categories:
            self.reload_data()

        viewrect = surface.get_rect()

        now = pygame.time.get_ticks() / 1000.0
        pygame.draw.rect(surface, (0, 0, 0), viewrect)
        self._particles.draw(surface, viewrect, now, color=(104, 154, 226))
        draw_scanlines(surface, viewrect, now, color=(80, 130, 220), alpha=7, spacing=32)

        title_surf = title_font.render("RESEARCH", True, _C_TITLE)
        surface.blit(title_surf, (_PAD, (_TOP_H - title_surf.get_height()) // 2))

        self._close_rect = pygame.Rect(sw - 130, 8, 118, 34)
        close_hover = self._close_rect.collidepoint(mouse)
        close_draw_rect = scale_rect(self._close_rect, 1.0 + (0.035 if close_hover else 0.0))
        draw_soft_glow(surface, close_draw_rect, _C_CLOSE_BD, 0.55 if close_hover else 0.0, radius=5, rings=3)
        pygame.draw.rect(surface, _C_CLOSE_HOVER if close_hover else _C_CLOSE_BG, close_draw_rect, border_radius=4)
        pygame.draw.rect(surface, _C_CLOSE_BD, close_draw_rect, 1, border_radius=4)
        draw_light_sweep(surface, close_draw_rect, now, _C_CLOSE_BD, alpha=18 if close_hover else 7)
        cx_surf = font.render("Close", True, (230, 100, 100))
        surface.blit(cx_surf, cx_surf.get_rect(center=close_draw_rect.center))

        hint_surf = font.render(
            f"click a node to research  •  scroll to zoom  •  drag to pan  •  {RESEARCH_RP_PER_TURN} RP per turn",
            True, _C_HINT,
        )
        surface.blit(hint_surf, (_PAD, _TOP_H + 4))

        if self._researching_id and self._researching_turns_remaining > 0:
            researching_node = self._get_node(self._researching_id)
            rlabel = researching_node["label"] if researching_node else self._researching_id
            prog_text = font.render(
                f"Researching: {rlabel} ({self._researching_turns_remaining} turn{'s' if self._researching_turns_remaining > 1 else ''} left)",
                True, _C_NODE_RESEARCHING_LB,
            )
            surface.blit(prog_text, (_PAD + hint_surf.get_width() + 20, _TOP_H + 4))

        tree_top = _TOP_H + 28
        tree_bottom = sh - _TAB_H - 4
        tree_clip = pygame.Rect(0, tree_top, sw, tree_bottom - tree_top)
        old_clip = surface.get_clip()
        surface.set_clip(tree_clip)

        active_nodes = self._get_active_nodes()
        self._build_world_layout(active_nodes)

        if not self._layout_ready and active_nodes:
            self._centerlayout(viewrect)
            self._layout_ready = True

        self._node_rects = {}
        for node in active_nodes:
            nid = node["id"]
            wrect = self._world_rects.get(nid)
            if wrect:
                self._node_rects[nid] = self._screentorect(wrect)

        self._draw_connectors(surface, active_nodes, tree_clip)

        hovered_id: str | None = None
        for node in active_nodes:
            nid = node["id"]
            rect = self._node_rects.get(nid)
            if rect is None:
                continue
            if not tree_clip.colliderect(rect):
                continue

            status = self._node_status(nid)
            hovered = rect.collidepoint(mouse)
            if hovered:
                hovered_id = nid

            selected = (self._selected_id == nid)

            if status == "researched":
                bg, border_c, label_c = _C_NODE_DONE, _C_NODE_DONE_BD, _C_NODE_DONE_LB
            elif status == "researching":
                bg, border_c, label_c = _C_NODE_RESEARCHING, _C_NODE_RESEARCHING_BD, _C_NODE_RESEARCHING_LB
            elif status == "available":
                bg = _C_NODE_HOVER if hovered else _C_NODE_AVAIL
                border_c = _C_NODE_AVAIL_BD
                label_c = _C_NODE_AVAIL_LB
            else:
                bg, border_c, label_c = _C_NODE_LOCKED, _C_NODE_LOCKED_BD, _C_NODE_LOCKED_LB

            node_draw_rect = scale_rect(
                rect,
                1.0 + (0.035 if hovered else 0.0) + (0.014 * pulse(now, 2.4) if status == "researching" else 0.0),
            )
            bd_color = _C_NODE_SEL_BD if selected else border_c
            bd_w = 2 if selected else 1
            draw_soft_glow(
                surface,
                node_draw_rect,
                bd_color,
                (0.64 if hovered else 0.0) + (0.42 * pulse(now, 3.4) if status == "researching" else 0.0),
                radius=7,
                rings=4,
            )
            pygame.draw.rect(surface, bg, node_draw_rect, border_radius=5)
            pygame.draw.rect(surface, bd_color, node_draw_rect, bd_w, border_radius=5)
            draw_light_sweep(surface, node_draw_rect, now + len(nid) * 0.05, bd_color, alpha=18 if hovered or selected else 8)

            node_old_clip = surface.get_clip()
            surface.set_clip(node_draw_rect)

            if self.zoom >= 0.6:
                label_lines = node["label"].split("\n")
                line_h = font.get_height()
                total_h = line_h * len(label_lines)
                text_y = node_draw_rect.centery - total_h // 2
                max_label_w = max(1, node_draw_rect.width - 8)
                for line in label_lines:
                    fitted = line
                    while font.size(fitted)[0] > max_label_w and fitted:
                        fitted = fitted[:-1]
                    if fitted != line:
                        fitted = fitted[:-3] + "..." if len(fitted) > 3 else fitted
                    ls = font.render(fitted, True, label_c)
                    surface.blit(ls, ls.get_rect(centerx=node_draw_rect.centerx, top=text_y))
                    text_y += line_h

            if status not in ("researched", "researching") and node_draw_rect.width >= 40:
                cost_txt = font.render(f"⚙ {node['cost']}", True, _C_NODE_AVAIL_LB)
                if cost_txt.get_width() < node_draw_rect.width:
                    surface.blit(cost_txt, (node_draw_rect.right - cost_txt.get_width() - 4, node_draw_rect.bottom - cost_txt.get_height() - 2))

            if status == "researched" and node_draw_rect.width >= 40:
                tick = font.render("✓", True, _C_NODE_DONE_LB)
                if tick.get_width() < node_draw_rect.width:
                    surface.blit(tick, (node_draw_rect.right - tick.get_width() - 4, node_draw_rect.bottom - tick.get_height() - 2))

            surface.set_clip(node_old_clip)

            if nid == self._researching_id and self._researching_turns_remaining > 0:
                node_data = self._get_node(nid)
                total = max(1, node_data["cost"] // RESEARCH_RP_PER_TURN) if node_data else 1
                progress = total - self._researching_turns_remaining
                bar_w = node_draw_rect.width - 8
                bar_h = max(2, int(4 * self.zoom))
                bar_x = node_draw_rect.x + 4
                bar_y = node_draw_rect.bottom - bar_h - 4
                fill_w = int(bar_w * progress / total)
                pygame.draw.rect(surface, (40, 40, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
                if fill_w > 0:
                    pygame.draw.rect(surface, (80, 180, 255), (bar_x, bar_y, fill_w, bar_h), border_radius=2)

        surface.set_clip(old_clip)

        self._draw_tabs(surface, font, mouse, sw, sh)

        tip_id = hovered_id or self._selected_id
        if tip_id:
            node_data = self._get_node(tip_id)
            if node_data:
                self._draw_tooltip(surface, font, title_font, node_data, mouse)

    def _draw_tabs(self, surface, font, mouse, sw, sh):
        tab_ids = list(self._categories.keys())
        if not tab_ids:
            return
        now = pygame.time.get_ticks() / 1000.0

        tab_area_y = sh - _TAB_H
        tab_w = min(150, (sw - _PAD * 2) // len(tab_ids))
        gap = 6
        total_row_w = len(tab_ids) * tab_w + (len(tab_ids) - 1) * gap
        start_x = (sw - total_row_w) // 2

        self._tab_rects = {}
        for i, tab_id in enumerate(tab_ids):
            tx = start_x + i * (tab_w + gap)
            tab_rect = pygame.Rect(tx, tab_area_y + 4, tab_w, _TAB_H - 8)
            self._tab_rects[tab_id] = tab_rect

            is_active = tab_id == self._active_category_id
            is_hover = tab_rect.collidepoint(mouse)

            if is_active:
                bg = _C_TAB_ACTIVE
            elif is_hover:
                bg = _C_TAB_HOVER
            else:
                bg = _C_TAB_IDLE
            draw_rect = scale_rect(tab_rect, 1.0 + (0.035 if is_hover or is_active else 0.0))
            draw_soft_glow(surface, draw_rect, _C_TITLE, 0.34 if is_hover or is_active else 0.0, radius=5, rings=3)

            pygame.draw.rect(surface, bg, draw_rect, border_radius=5)
            pygame.draw.rect(surface, _C_TAB_BORDER, draw_rect, 1, border_radius=5)
            draw_light_sweep(surface, draw_rect, now + i * 0.17, _C_TITLE, alpha=16 if is_hover or is_active else 7)

            cat_data = self._categories.get(tab_id, {})
            label = cat_data.get("label", tab_id)
            tab_surf = font.render(label, True, (200, 200, 210) if not is_active else (240, 240, 255))
            surface.blit(tab_surf, tab_surf.get_rect(center=draw_rect.center))

    def _get_active_nodes(self) -> list[dict]:
        if not self._active_category_id:
            return []
        cat_data = self._categories.get(self._active_category_id, {})
        return cat_data.get("nodes", [])

    def _get_node(self, node_id: str) -> dict | None:
        for cat_nodes in self._category_nodes.values():
            if node_id in cat_nodes:
                return cat_nodes[node_id]
        return None

    def _node_status(self, node_id: str) -> str:
        if node_id in self._researched:
            return "researched"
        if node_id == self._researching_id:
            return "researching"
        node = self._get_node(node_id)
        if node is None:
            return "locked"
        if all(p in self._researched for p in node.get("prereqs", [])):
            return "available"
        return "locked"

    def _build_world_layout(self, nodes: list[dict]) -> None:
        self._world_rects = {}
        if not nodes:
            return

        min_col = min(n["col"] for n in nodes)
        min_row = min(n["row"] for n in nodes)

        for node in nodes:
            nx = (node["col"] - min_col) * _NODE_SPACE_X
            ny = (node["row"] - min_row) * _NODE_SPACE_Y
            self._world_rects[node["id"]] = pygame.Rect(nx, ny, _NODE_W, _NODE_H)

        bounds = None
        for rect in self._world_rects.values():
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        self._world_bounds = bounds or pygame.Rect(0, 0, 1, 1)

    def _draw_connectors(self, surface, nodes, tree_clip):
        for node in nodes:
            nid = node["id"]
            target = self._world_rects.get(nid)
            if target is None:
                continue
            for prereq_id in node.get("prereqs", []):
                source = self._world_rects.get(prereq_id)
                if source is None:
                    continue
                both_done = (nid in self._researched and prereq_id in self._researched)
                either_locked = (
                    self._node_status(nid) == "locked"
                    or self._node_status(prereq_id) == "locked"
                )
                line_color = (
                    _C_LINE_DONE if both_done
                    else _C_LINE_LOCKED if either_locked
                    else _C_LINE_IDLE
                )

                start = self._screenpoint(source.midbottom)
                end = self._screenpoint(target.midtop)
                mid_y = (start[1] + end[1]) // 2
                bend = (start[0], mid_y)
                bendtwo = (end[0], mid_y)

                linew = max(1, int(3 * self.zoom))
                now = pygame.time.get_ticks() / 1000.0
                live_line_color = mix_color(line_color, _C_TITLE, 0.22 * pulse(now, 2.0, end[0] * 0.01))
                pygame.draw.lines(surface, (40, 50, 65), False, (start, bend, bendtwo, end), linew + 1)
                pygame.draw.lines(surface, live_line_color, False, (start, bend, bendtwo, end), max(1, linew - 1))

    def _draw_tooltip(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        title_font: pygame.font.Font,
        node: dict,
        mouse: tuple[int, int],
    ) -> None:
        status = self._node_status(node["id"])
        tip_w = 260
        pad = 10
        line_h = font.get_height()
        content_w = tip_w - pad * 2

        label = node.get("label", node["id"])
        status_str = {
            "researched": "Status: Completed",
            "researching": f"Status: In Progress ({self._researching_turns_remaining}/{max(1, node['cost'] // RESEARCH_RP_PER_TURN)} turns)",
            "available": f"Status: Available ({max(1, node['cost'] // RESEARCH_RP_PER_TURN)} turns)",
            "locked": "Status: Locked",
        }.get(status, "Status: Unknown")
        cost_str = f"Cost: {node['cost']} RP ({max(1, node['cost'] // RESEARCH_RP_PER_TURN)} turns)"

        prereqs = node.get("prereqs", [])
        if prereqs:
            prereq_labels = []
            for pid in prereqs:
                pnode = self._get_node(pid)
                prereq_labels.append(pnode["label"] if pnode else pid)
            prereq_line = "Requires: " + ", ".join(prereq_labels)
        else:
            prereq_line = "No prerequisites"

        wrap_lines: list[tuple[str, tuple[int, int, int]]] = []
        wrap_lines.append((label, (230, 230, 230)))
        wrap_lines.append(("", (170, 170, 180)))
        for wrapped in _wrap_text(font, prereq_line, content_w):
            wrap_lines.append((wrapped, (170, 170, 180)))
        wrap_lines.append((status_str, (170, 170, 180)))
        wrap_lines.append((cost_str, (170, 170, 180)))

        tip_h = len(wrap_lines) * line_h + pad * 2
        mx, my = mouse
        tx = min(mx + 16, surface.get_width() - tip_w - 10)
        ty = min(my + 16, surface.get_height() - tip_h - 10)

        tip_rect = pygame.Rect(tx, ty, tip_w, tip_h)
        pygame.draw.rect(surface, (20, 20, 24), tip_rect, border_radius=4)
        pygame.draw.rect(surface, (200, 170, 80), tip_rect, 1, border_radius=4)

        for i, (text, color) in enumerate(wrap_lines):
            if not text:
                continue
            ls = font.render(text, True, color)
            surface.blit(ls, (tx + pad, ty + pad + i * line_h))
