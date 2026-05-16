"""
game/researchui.py

Drop-in research tree panel that mirrors the FocusTreeView interface:

    view = ResearchTreeView()
    view.setdata(researched_set)       # sync which nodes are done
    view.toggleview()                  # open / close
    view.isopen                        # bool
    view.handleevent(event)            # returns action string or None
    view.draw(surface, title_font, font, mouse)
    view.pointerover(mouseposition)    # bool – used by ispointeroverui()
    view.viewdata()                    # returns frozenset of researched node ids
"""

from __future__ import annotations
import pygame


_NODE_W      = 164
_NODE_H      = 64
_H_GAP       = 36      
_V_GAP       = 28         
_PANEL_PAD   = 28          

_C_PANEL_BG      = (18, 20, 26)
_C_PANEL_BORDER  = (45, 48, 60)
_C_TITLE         = (200, 170, 80)
_C_HINT          = (140, 140, 150)

_C_NODE_AVAIL    = (36, 56, 90)
_C_NODE_AVAIL_BD = (80, 120, 190)
_C_NODE_AVAIL_LB = (180, 210, 255)

_C_NODE_DONE     = (28, 88, 52)
_C_NODE_DONE_BD  = (60, 170, 100)
_C_NODE_DONE_LB  = (140, 230, 170)

_C_NODE_LOCKED   = (35, 35, 40)
_C_NODE_LOCKED_BD= (55, 55, 65)
_C_NODE_LOCKED_LB= (110, 110, 120)

_C_NODE_HOVER    = (55, 82, 128)
_C_NODE_SEL_BD   = (220, 200, 100)

_C_LINE_IDLE     = (60, 75, 100)
_C_LINE_DONE     = (55, 140, 90)
_C_LINE_LOCKED   = (50, 50, 58)

_C_TOOLTIP_BG    = (20, 20, 24)
_C_TOOLTIP_BD    = (200, 170, 80)
_C_TOOLTIP_TEXT  = (230, 230, 230)
_C_TOOLTIP_SUB   = (170, 170, 180)
_C_TOOLTIP_COST  = (140, 200, 255)


_WEAPON_TREE: list[dict] = [
    {
        "id":          "Weapon_1",
        "label":       "Basic small arms ",
        
        "cost":        50,
        "col": 1, "row": 0,
        "prereqs":     [],
    },
    {
        "id":          "heavy_weapons",
        "label":       "weapon 1",
       
        "cost":        80,
        "col": 0, "row": 1,
        "prereqs":     ["Weapon_1"],
    },
    {
        "id":          "field_artillery",
        "label":       "weapon 2",
        
        "cost":        90,
        "col": 2, "row": 1,
        "prereqs":     ["Weapon_1"],
    },
    {
        "id":          "armored_cars",
        "label":       "weapon 3",
       
        "cost":        100,
        "col": 0, "row": 2,
        "prereqs":     ["heavy_weapons"],
    },
    {
        "id":          "battle_tanks",
        "label":       "weapon 4",
        
        "cost":        140,
        "col": 1, "row": 2,
        "prereqs":     ["heavy_weapons", "field_artillery"],
    },
    {
        "id":          "rocket_artillery",
        "label":       "weapon 5",
        "cost":        130,
        "col": 2, "row": 2,
        "prereqs":     ["field_artillery"],
    },
    {
        "id":          "advanced_tanks",
        "label":       "weapon 6",
        "cost":        200,
        "col": 1, "row": 3,
        "prereqs":     ["battle_tanks"],
    },
]


def _wrap_text(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    """Word-wrap a string into lines that fit within max_w pixels."""
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
    """
    Overlay panel that renders the weapon research tree.
    Interface deliberately mirrors FocusTreeView so InGameUI can call
    the same methods for both panels.
    """

   
    ACTION_RESEARCH = "research_node"

    def __init__(self) -> None:
        self.isopen: bool = False
        self._researched: set[str] = set()
        self._selected_id: str | None = None

       
        self._node_rects:  dict[str, pygame.Rect] = {}
        self._panel_rect:  pygame.Rect = pygame.Rect(0, 0, 10, 10)
        self._close_rect:  pygame.Rect = pygame.Rect(0, 0, 10, 10)
        self._scroll_y:    int = 0

    
        self._nodes: dict[str, dict] = {n["id"]: n for n in _WEAPON_TREE}


    def toggleview(self) -> None:
        self.isopen = not self.isopen
        self._selected_id = None
        self._scroll_y = 0

    def setdata(self, data) -> None:
        """Accept a set / frozenset of researched node ids."""
        if isinstance(data, (set, frozenset)):
            self._researched = set(data)

    def viewdata(self) -> frozenset:
        """Return current researched ids (read by sync / save)."""
        return frozenset(self._researched)

    def pointerover(self, pos) -> bool:
        if not self.isopen:
            return False
        return self._panel_rect.collidepoint(pos)

    def handleevent(self, event: pygame.event.Event):
        """
        Process one pygame event.  Returns:
          (ACTION_RESEARCH, node_id)  when the player clicks a researchable node
          None                        otherwise
        Returning a non-None value also closes the panel when appropriate.
        """
        if not self.isopen:
            return None

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.isopen = False
            return None

        if event.type == pygame.MOUSEWHEEL:
            self._scroll_y = max(0, self._scroll_y - event.y * 24)
            return None

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None

        pos = event.pos

       
        if self._close_rect.collidepoint(pos):
            self.isopen = False
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
                self._researched.add(node_id)
                return (self.ACTION_RESEARCH, node_id)
        
            self._selected_id = node_id
            return None

        return None



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
        self._build_layout(sw, sh)


        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        pr = self._panel_rect

       
        pygame.draw.rect(surface, _C_PANEL_BG, pr, border_radius=6)
        pygame.draw.rect(surface, _C_PANEL_BORDER, pr, 1, border_radius=6)


        title_surf = title_font.render("WEAPONS RESEARCH", True, _C_TITLE)
        surface.blit(title_surf, title_surf.get_rect(
            centerx=pr.centerx,
            top=pr.top + 14,
        ))

    
        cr = self._close_rect
        close_hover = cr.collidepoint(mouse)
        pygame.draw.rect(surface, (80, 30, 30) if close_hover else (45, 30, 30), cr, border_radius=3)
        pygame.draw.rect(surface, (160, 60, 60), cr, 1, border_radius=3)
        cx_surf = font.render("×", True, (230, 100, 100))
        surface.blit(cx_surf, cx_surf.get_rect(center=cr.center))

   
        hint = font.render("click a node to research  •  scroll to pan", True, _C_HINT)
        surface.blit(hint, hint.get_rect(centerx=pr.centerx, bottom=pr.bottom - 10))

    
        tree_clip = pygame.Rect(pr.x + _PANEL_PAD, pr.y + 52,
                                pr.width - _PANEL_PAD * 2,
                                pr.height - 52 - 28)
        old_clip = surface.get_clip()
        surface.set_clip(tree_clip)

    
        for node in _WEAPON_TREE:
            nid   = node["id"]
            nrect = self._node_rects.get(nid)
            if nrect is None:
                continue
            for prereq_id in node["prereqs"]:
                prect = self._node_rects.get(prereq_id)
                if prect is None:
                    continue
                both_done = (nid in self._researched and prereq_id in self._researched)
                either_locked = (self._node_status(nid) == "locked"
                                 or self._node_status(prereq_id) == "locked")
                line_color = (_C_LINE_DONE if both_done
                              else _C_LINE_LOCKED if either_locked
                              else _C_LINE_IDLE)

                start = (nrect.centerx,   nrect.top)
                end   = (prect.centerx,   prect.bottom)
                mid_y = (start[1] + end[1]) // 2

                pygame.draw.line(surface, line_color, start,         (start[0], mid_y), 2)
                pygame.draw.line(surface, line_color, (start[0], mid_y), (end[0], mid_y), 2)
                pygame.draw.line(surface, line_color, (end[0], mid_y), end,           2)

 
        hovered_id: str | None = None
        for node in _WEAPON_TREE:
            nid    = node["id"]
            rect   = self._node_rects.get(nid)
            if rect is None:
                continue
            if not tree_clip.colliderect(rect):
                continue

            status  = self._node_status(nid)
            hovered = rect.collidepoint(mouse)
            if hovered:
                hovered_id = nid

            selected = (self._selected_id == nid)

   
            if status == "researched":
                bg, border_c, label_c = _C_NODE_DONE, _C_NODE_DONE_BD, _C_NODE_DONE_LB
            elif status == "available":
                bg = _C_NODE_HOVER if hovered else _C_NODE_AVAIL
                border_c = _C_NODE_AVAIL_BD
                label_c  = _C_NODE_AVAIL_LB
            else:
                bg, border_c, label_c = _C_NODE_LOCKED, _C_NODE_LOCKED_BD, _C_NODE_LOCKED_LB

            pygame.draw.rect(surface, bg, rect, border_radius=4)
            bd_color = _C_NODE_SEL_BD if selected else border_c
            bd_w     = 2 if selected else 1
            pygame.draw.rect(surface, bd_color, rect, bd_w, border_radius=4)

           
            label_lines = node["label"].split("\n")
            line_h      = font.get_height()
            total_h     = line_h * len(label_lines)
            text_y      = rect.centery - total_h // 2
            for line in label_lines:
                ls = font.render(line, True, label_c)
                surface.blit(ls, ls.get_rect(centerx=rect.centerx, top=text_y))
                text_y += line_h

            if status != "researched":
                cost_txt = font.render(f"⚙ {node['cost']}", True, _C_TOOLTIP_COST)
                surface.blit(cost_txt, (rect.right - cost_txt.get_width() - 4,
                                        rect.bottom - cost_txt.get_height() - 2))

            
            if status == "researched":
                tick = font.render("✓", True, _C_NODE_DONE_LB)
                surface.blit(tick, (rect.right - tick.get_width() - 4,
                                    rect.bottom - tick.get_height() - 2))

        surface.set_clip(old_clip)


        tip_id = hovered_id or self._selected_id
        if tip_id and tip_id in self._nodes:
            self._draw_tooltip(surface, font, title_font, self._nodes[tip_id], mouse, pr)

    def _node_status(self, node_id: str) -> str:
        """Return 'researched', 'available', or 'locked'."""
        if node_id in self._researched:
            return "researched"
        node = self._nodes.get(node_id)
        if node is None:
            return "locked"
        if all(p in self._researched for p in node["prereqs"]):
            return "available"
        return "locked"

    def _build_layout(self, sw: int, sh: int) -> None:
        """Recompute panel and node rects from screen size + scroll offset."""
  
        cols = max(n["col"] for n in _WEAPON_TREE) + 1
        rows = max(n["row"] for n in _WEAPON_TREE) + 1

        tree_w = cols * _NODE_W + (cols - 1) * _H_GAP
        tree_h = rows * _NODE_H + (rows - 1) * _V_GAP

        panel_w = tree_w  + _PANEL_PAD * 2
        panel_h = tree_h  + _PANEL_PAD * 2 + 52 + 28  
        panel_w = max(panel_w, 420)
        panel_h = min(panel_h, sh - 40)

        px = (sw - panel_w) // 2
        py = (sh - panel_h) // 2
        self._panel_rect = pygame.Rect(px, py, panel_w, panel_h)

        
        self._close_rect = pygame.Rect(
            self._panel_rect.right - 34,
            self._panel_rect.top   + 10,
            24, 24,
        )

        origin_x = px + _PANEL_PAD
        origin_y = py + 52 - self._scroll_y          

        self._node_rects = {}
        for node in _WEAPON_TREE:
            nx = origin_x + node["col"] * (_NODE_W + _H_GAP)
            ny = origin_y + node["row"] * (_NODE_H + _V_GAP)
            self._node_rects[node["id"]] = pygame.Rect(nx, ny, _NODE_W, _NODE_H)

    def _draw_tooltip(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        title_font: pygame.font.Font,
        node: dict,
        mouse: tuple[int, int],
        panel_rect: pygame.Rect,
    ) -> None:
        status    = self._node_status(node["id"])
        tip_w     = 240
        pad       = 10
        line_h    = font.get_height()

   
        
        
        status_line  = {
            "researched": "✓ Already researched",
            "available":  f"Click to research  (cost: {node['cost']})",
            "locked":     "✗ Prerequisites not met",
        }[status]
        prereq_names = [self._nodes[p]["label"].replace("\n", " ")
                        for p in node["prereqs"] if p in self._nodes]

       

    
  



     
        