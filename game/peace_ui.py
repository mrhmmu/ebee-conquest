import pygame
import sys
import ctypes

WIDTH, HEIGHT = 1280, 720
STATUS_BAR_HEIGHT = 60  
FPS = 60

LEFTBAR_WIDTH = 230
RIGHTBAR_WIDTH = 250
BOTTOMBAR_HEIGHT = 70

ctypes.windll.user32.SetProcessDPIAware()


class PeaceTreatyScreen:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.SysFont("bahnschrift", 22, bold=True)  
        self.small_font = pygame.font.SysFont("arial narrow", 20)
        self.running = True
        
        self.exit_btn_rect = pygame.Rect(20, HEIGHT - BOTTOMBAR_HEIGHT + 15, 180, 40)
        self.clear_btn_rect = pygame.Rect(WIDTH - 140, STATUS_BAR_HEIGHT + 10, 120, 32)
        self.chat_btn_rect = pygame.Rect((WIDTH // 2) - 210, HEIGHT - BOTTOMBAR_HEIGHT + 15, 200, 40)
        self.history_btn_rect = pygame.Rect((WIDTH // 2) + 10, HEIGHT - BOTTOMBAR_HEIGHT + 15, 200, 40)
        self.submit_btn_rect = pygame.Rect(WIDTH - 200, HEIGHT - BOTTOMBAR_HEIGHT + 15, 180, 40)

        self.ceasefire_btn_rect = pygame.Rect(WIDTH - RIGHTBAR_WIDTH + 20, STATUS_BAR_HEIGHT + 60, RIGHTBAR_WIDTH - 40, 40)
        self.state_transfer_btn_rect = pygame.Rect(WIDTH - RIGHTBAR_WIDTH + 20, STATUS_BAR_HEIGHT + 110, RIGHTBAR_WIDTH - 40, 40)
        self.puppet_state_btn_rect = pygame.Rect(WIDTH - RIGHTBAR_WIDTH + 20, STATUS_BAR_HEIGHT + 160, RIGHTBAR_WIDTH - 40, 40)
        self.military_access_btn_rect = pygame.Rect(WIDTH - RIGHTBAR_WIDTH + 20, STATUS_BAR_HEIGHT + 210, RIGHTBAR_WIDTH - 40, 40)
        self.regime_change_btn_rect = pygame.Rect(WIDTH - RIGHTBAR_WIDTH + 20, STATUS_BAR_HEIGHT + 260, RIGHTBAR_WIDTH - 40, 40)
        
        self.countries = ["Malaysia", "Thailand", "Vietnam", "Indonesia", "Philippines", "Laos"]
        self.country_rects = []
        start_y = STATUS_BAR_HEIGHT + 60
        for i in range(len(self.countries)):
            rect = pygame.Rect(15, start_y + (i * 50), LEFTBAR_WIDTH - 30, 40)
            self.country_rects.append(rect)

        self.chat_open = False
        self.chat_input_text = ""
        self.chat_history = [
            ("LEADER", "Welcome to the Peace Conference."),
        ]
        
        self.chat_panel_rect = pygame.Rect(LEFTBAR_WIDTH + 40, STATUS_BAR_HEIGHT + 40, 
                                           WIDTH - LEFTBAR_WIDTH - RIGHTBAR_WIDTH - 80, 
                                           HEIGHT - STATUS_BAR_HEIGHT - BOTTOMBAR_HEIGHT - 80)
        self.chat_input_rect = pygame.Rect(self.chat_panel_rect.x + 20, self.chat_panel_rect.bottom - 60, 
                                           self.chat_panel_rect.width - 40, 40)

    def draw_status_bar(self):
        status_rect = pygame.Rect(0, 0, WIDTH, STATUS_BAR_HEIGHT)
        pygame.draw.rect(self.screen, (12, 18, 29), status_rect)
        pygame.draw.line(self.screen, (76, 64, 38), (0, STATUS_BAR_HEIGHT - 2), (WIDTH, STATUS_BAR_HEIGHT - 2), 1)
        pygame.draw.line(self.screen, (240, 198, 116), (0, STATUS_BAR_HEIGHT - 1), (WIDTH, STATUS_BAR_HEIGHT - 1), 1)
        
        ebee_surf = self.title_font.render("EBEE COMMAND", True, (240, 198, 116))
        ebee_rect = ebee_surf.get_rect(midleft=(16, STATUS_BAR_HEIGHT // 2))
        self.screen.blit(ebee_surf, ebee_rect)
        
        title_surf = self.title_font.render("PEACE CONFERENCE", True, (240, 198, 116))
        title_rect = title_surf.get_rect(center=(WIDTH // 2, STATUS_BAR_HEIGHT // 2))
        self.screen.blit(title_surf, title_rect)

    def draw_left_bar(self):
        leftbar_rect = pygame.Rect(0, STATUS_BAR_HEIGHT, LEFTBAR_WIDTH, HEIGHT - STATUS_BAR_HEIGHT - BOTTOMBAR_HEIGHT)
        pygame.draw.rect(self.screen, (12, 18, 29), leftbar_rect)
        pygame.draw.rect(self.screen, (28, 38, 52), leftbar_rect, 1)
        pygame.draw.line(self.screen, (76, 64, 38), leftbar_rect.topright, leftbar_rect.bottomright, 1)
        
        left_title = self.small_font.render("PARTICIPANTS", True, (240, 198, 116))
        left_rect = left_title.get_rect(centerx=leftbar_rect.centerx, y=leftbar_rect.y + 16)
        self.screen.blit(left_title, left_rect)

        mouse_pos = pygame.mouse.get_pos()
        for i, rect in enumerate(self.country_rects):
            if rect.collidepoint(mouse_pos):
                btn_color = (40, 52, 72)
                text_color = (255, 220, 150)
            else:
                btn_color = (24, 33, 46)
                text_color = (240, 198, 116)
                
            pygame.draw.rect(self.screen, btn_color, rect)
            pygame.draw.rect(self.screen, text_color, rect, 1)
            
            country_text = self.small_font.render(self.countries[i].upper(), True, (255,255,255))
            country_rect = country_text.get_rect(center=rect.center)
            self.screen.blit(country_text, country_rect)

    def draw_right_bar(self):
        rightbar_rect = pygame.Rect(WIDTH - RIGHTBAR_WIDTH, STATUS_BAR_HEIGHT, RIGHTBAR_WIDTH, HEIGHT - STATUS_BAR_HEIGHT - BOTTOMBAR_HEIGHT)
        pygame.draw.rect(self.screen, (12, 18, 29), rightbar_rect)
        pygame.draw.rect(self.screen, (28, 38, 52), rightbar_rect, 1)
        pygame.draw.line(self.screen, (76, 64, 38), rightbar_rect.topleft, rightbar_rect.bottomleft, 1)
        right_title = self.small_font.render("DEMANDS", True, (240, 198, 116))
        right_rect = right_title.get_rect(left=rightbar_rect.left + 20, y=rightbar_rect.y + 16)
        self.screen.blit(right_title, right_rect)

        mouse_pos = pygame.mouse.get_pos()
        if self.clear_btn_rect.collidepoint(mouse_pos):
            clear_btn_color = (40, 52, 72)
            clear_text_color = (255, 220, 150)
        else:
            clear_btn_color = (24, 33, 46)
            clear_text_color = (240, 198, 116)

        pygame.draw.rect(self.screen, clear_btn_color, self.clear_btn_rect)
        pygame.draw.rect(self.screen, clear_text_color, self.clear_btn_rect, 1)
        
        clear_font = pygame.font.SysFont("arial narrow", 18, bold=True)
        clear_surf = clear_font.render("CLEAR ALL", True, clear_text_color)
        clear_rect = clear_surf.get_rect(center=self.clear_btn_rect.center)
        self.screen.blit(clear_surf, clear_rect)

        buttons = [
            (self.ceasefire_btn_rect, "CEASEFIRE                      >"),
            (self.state_transfer_btn_rect, "STATE TRANSFER               >"),
            (self.puppet_state_btn_rect, "PUPPET STATE                  >"),
            (self.military_access_btn_rect, "MILITARY ACCESS               >"),
            (self.regime_change_btn_rect, "REGIME CHANGE                 >")
        ]

        for rect, label in buttons:
            if rect.collidepoint(mouse_pos):
                b_color, t_color = (40, 52, 72), (255, 220, 150)
            else:
                b_color, t_color = (24, 33, 46), (240, 198, 116)
            pygame.draw.rect(self.screen, b_color, rect)
            pygame.draw.rect(self.screen, t_color, rect, 1)
            txt_surf = self.small_font.render(label, True, t_color)
            txt_rect = txt_surf.get_rect(center=rect.center)
            self.screen.blit(txt_surf, txt_rect)

    def draw_bottom_bar(self):
        bottombar_rect = pygame.Rect(0, HEIGHT - BOTTOMBAR_HEIGHT, WIDTH, BOTTOMBAR_HEIGHT)
        pygame.draw.rect(self.screen, (5, 10, 17), bottombar_rect)
        pygame.draw.line(self.screen, (240, 198, 116), bottombar_rect.topleft, bottombar_rect.topright, 1)
        
        mouse_pos = pygame.mouse.get_pos()
        
        if self.exit_btn_rect.collidepoint(mouse_pos):
            button_color, text_color = (40, 52, 72), (255, 220, 150)
        else:
            button_color, text_color = (24, 33, 46), (240, 198, 116)
        pygame.draw.rect(self.screen, button_color, self.exit_btn_rect)
        pygame.draw.rect(self.screen, text_color, self.exit_btn_rect, 1)
        btn_text = self.small_font.render("EXIT CONFERENCE", True, text_color)
        self.screen.blit(btn_text, btn_text.get_rect(center=self.exit_btn_rect.center))

        if self.chat_btn_rect.collidepoint(mouse_pos) or self.chat_open:
            chat_btn_color = (40, 65, 100) if self.chat_open else (40, 52, 72)
            chat_text_color = (255, 255, 255)
        else:
            chat_btn_color = (24, 33, 46)
            chat_text_color = (180, 180, 180)

        pygame.draw.rect(self.screen, chat_btn_color, self.chat_btn_rect)
        pygame.draw.rect(self.screen, chat_text_color, self.chat_btn_rect, 1)
        chat_text = self.small_font.render("CHAT WITH LEADERS", True, chat_text_color)
        self.screen.blit(chat_text, chat_text.get_rect(center=self.chat_btn_rect.center))

        if self.history_btn_rect.collidepoint(mouse_pos):
            history_btn_color = (40, 52, 72)
        else:
            history_btn_color = (24, 33, 46)
        pygame.draw.rect(self.screen, history_btn_color, self.history_btn_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), self.history_btn_rect, 1)
        history_text = self.small_font.render("PROPOSAL HISTORY", True, (255, 255, 255))
        self.screen.blit(history_text, history_text.get_rect(center=self.history_btn_rect.center))

        if self.submit_btn_rect.collidepoint(mouse_pos):
            submit_btn_color, submit_text_color = (40, 120, 40), (255, 255, 255) 
        else:
            submit_btn_color, submit_text_color = (30, 90, 30), (255, 255, 255)   
        pygame.draw.rect(self.screen, submit_btn_color, self.submit_btn_rect)
        pygame.draw.rect(self.screen, submit_text_color, self.submit_btn_rect, 1) 
        submit_text = self.small_font.render("SUBMIT DEMANDS", True, submit_text_color)
        self.screen.blit(submit_text, submit_text.get_rect(center=self.submit_btn_rect.center))

    def draw_chat_window(self):
        if not self.chat_open:
            return
            
        pygame.draw.rect(self.screen, (16, 24, 38), self.chat_panel_rect)
        pygame.draw.rect(self.screen, (240, 198, 116), self.chat_panel_rect, 2)
        
        header_surf = self.title_font.render("NEGOTIATE PLACE", True, (240, 198, 116))
        self.screen.blit(header_surf, (self.chat_panel_rect.x + 20, self.chat_panel_rect.y + 15))
        pygame.draw.line(self.screen, (40, 52, 72), 
                         (self.chat_panel_rect.x, self.chat_panel_rect.y + 50), 
                         (self.chat_panel_rect.right, self.chat_panel_rect.y + 50), 2)
        
        start_y = self.chat_panel_rect.y + 70
        for sender, msg in self.chat_history[-8:]:
            color = (150, 200, 255) if sender == "You" else (240, 198, 116)
            display_line = f"{sender}: {msg}"
            msg_surf = self.small_font.render(display_line, True, color)
            self.screen.blit(msg_surf, (self.chat_panel_rect.x + 20, start_y))
            start_y += 30

        pygame.draw.rect(self.screen, (24, 33, 46), self.chat_input_rect)
        pygame.draw.rect(self.screen, (76, 64, 38), self.chat_input_rect, 1)
        
        text_to_render = self.chat_input_text + ("|" if pygame.time.get_ticks() % 1000 < 500 else "")
        input_surf = self.small_font.render(text_to_render, True, (255, 255, 255))
        self.screen.blit(input_surf, (self.chat_input_rect.x + 10, self.chat_input_rect.y + 10))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                
                if self.chat_open:
                    if event.key == pygame.K_RETURN:
                        if self.chat_input_text.strip():
                            user_msg = self.chat_input_text
                            self.chat_history.append(("You", user_msg))
                            
                            reply = f"to be answered...... '{user_msg}'."
                            self.chat_history.append(("LEADER", reply))
                            
                            self.chat_input_text = ""
                    elif event.key == pygame.K_BACKSPACE:
                        self.chat_input_text = self.chat_input_text[:-1]
                    else:
                        if event.unicode.isprintable():
                            self.chat_input_text += event.unicode

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if self.chat_btn_rect.collidepoint(event.pos):
                        self.chat_open = not self.chat_open
                        
                    if self.exit_btn_rect.collidepoint(event.pos):
                        self.running = False
                    if self.submit_btn_rect.collidepoint(event.pos):
                        print("Demands Submitted!") 
                    if self.clear_btn_rect.collidepoint(event.pos):
                        pass

    def draw(self):
        self.screen.fill((11, 18, 32))
        self.draw_status_bar()
        self.draw_left_bar()
        self.draw_right_bar()
        self.draw_bottom_bar()
        
        self.draw_chat_window()
        
        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    app = PeaceTreatyScreen()
    app.run()