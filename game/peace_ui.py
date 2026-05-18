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
        pygame.display.set_caption("PEACE TREATY")
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.SysFont("bahnschrift", 22, bold=True)  
        self.small_font = pygame.font.SysFont("arial narrow", 20)
        self.running = True
        
        self.exit_btn_rect = pygame.Rect(20, HEIGHT - BOTTOMBAR_HEIGHT + 15, 180, 40)
        self.clear_btn_rect = pygame.Rect(WIDTH - 140, STATUS_BAR_HEIGHT + 10, 120, 32)
        self.chat_btn_rect = pygame.Rect((WIDTH // 2) - 210, HEIGHT - BOTTOMBAR_HEIGHT + 15, 200, 40)
        self.history_btn_rect = pygame.Rect((WIDTH // 2) + 10, HEIGHT - BOTTOMBAR_HEIGHT + 15, 200, 40)
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

    def draw_status_bar(self):
        status_rect = pygame.Rect(0, 0, WIDTH, STATUS_BAR_HEIGHT)
   
        pygame.draw.rect(self.screen, (12, 18, 29), status_rect)
        pygame.draw.line(self.screen, (76, 64, 38), 
                         (0, STATUS_BAR_HEIGHT - 2), 
                         (WIDTH, STATUS_BAR_HEIGHT - 2), 1)
        pygame.draw.line(self.screen, (240, 198, 116), 
                         (0, STATUS_BAR_HEIGHT - 1), 
                         (WIDTH, STATUS_BAR_HEIGHT - 1), 1)
    

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

        if self.ceasefire_btn_rect.collidepoint(mouse_pos):
            ceasefire_btn_color = (40, 52, 72)
            ceasefire_text_color = (255, 220, 150)
        else:
            ceasefire_btn_color = (24, 33, 46)
            ceasefire_text_color = (240, 198, 116)

        pygame.draw.rect(self.screen, ceasefire_btn_color, self.ceasefire_btn_rect)
        pygame.draw.rect(self.screen, ceasefire_text_color, self.ceasefire_btn_rect, 1)
        ceasefire_text = self.small_font.render("CEASEFIRE                          >", True, ceasefire_text_color)
        ceasefire_rect = ceasefire_text.get_rect(center=self.ceasefire_btn_rect.center)
        self.screen.blit(ceasefire_text, ceasefire_rect)
        if self.state_transfer_btn_rect.collidepoint(mouse_pos):
            st_btn_color = (40, 52, 72)
            st_text_color = (255, 220, 150)
        else:
            st_btn_color = (24, 33, 46)
            st_text_color = (240, 198, 116)
        pygame.draw.rect(self.screen, st_btn_color, self.state_transfer_btn_rect)
        pygame.draw.rect(self.screen, st_text_color, self.state_transfer_btn_rect, 1)
        st_text = self.small_font.render("STATE TRANSFER               >", True, st_text_color)
        st_rect = st_text.get_rect(center=self.state_transfer_btn_rect.center)
        self.screen.blit(st_text, st_rect)

        if self.puppet_state_btn_rect.collidepoint(mouse_pos):
            ps_btn_color = (40, 52, 72)
            ps_text_color = (255, 220, 150)
        else:
            ps_btn_color = (24, 33, 46)
            ps_text_color = (240, 198, 116)
        pygame.draw.rect(self.screen, ps_btn_color, self.puppet_state_btn_rect)
        pygame.draw.rect(self.screen, ps_text_color, self.puppet_state_btn_rect, 1)
        ps_text = self.small_font.render("PUPPET STATE                     >", True, ps_text_color)
        ps_rect = ps_text.get_rect(center=self.puppet_state_btn_rect.center)
        self.screen.blit(ps_text, ps_rect)

        if self.military_access_btn_rect.collidepoint(mouse_pos):
            ma_btn_color = (40, 52, 72)
            ma_text_color = (255, 220, 150)
        else:
            ma_btn_color = (24, 33, 46)
            ma_text_color = (240, 198, 116)
        pygame.draw.rect(self.screen, ma_btn_color, self.military_access_btn_rect)
        pygame.draw.rect(self.screen, ma_text_color, self.military_access_btn_rect, 1)
        ma_text = self.small_font.render("MILITARY ACCESS               >", True, ma_text_color)
        ma_rect = ma_text.get_rect(center=self.military_access_btn_rect.center)
        self.screen.blit(ma_text, ma_rect)

        if self.regime_change_btn_rect.collidepoint(mouse_pos):
            rc_btn_color = (40, 52, 72)
            rc_text_color = (255, 220, 150)
        else:
            rc_btn_color = (24, 33, 46)
            rc_text_color = (240, 198, 116)
        pygame.draw.rect(self.screen, rc_btn_color, self.regime_change_btn_rect)
        pygame.draw.rect(self.screen, rc_text_color, self.regime_change_btn_rect, 1)
        rc_text = self.small_font.render("REGIME CHANGE                 >", True, rc_text_color)
        rc_rect = rc_text.get_rect(center=self.regime_change_btn_rect.center)
        self.screen.blit(rc_text, rc_rect)

        ebee_surf = self.title_font.render("EBEE COMMAND", True, (240, 198, 116))
        ebee_rect = ebee_surf.get_rect(midleft=(16, STATUS_BAR_HEIGHT // 2))
        self.screen.blit(ebee_surf, ebee_rect)
        
        title_surf = self.title_font.render("PEACE TREATY", True, (240, 198, 116))
        title_rect = title_surf.get_rect(center=(WIDTH // 2, STATUS_BAR_HEIGHT // 2))
        self.screen.blit(title_surf, title_rect)



    def draw_bottom_bar(self):
        bottombar_rect = pygame.Rect(0, HEIGHT - BOTTOMBAR_HEIGHT, WIDTH, BOTTOMBAR_HEIGHT)
        pygame.draw.rect(self.screen, (5, 10, 17), bottombar_rect)
        pygame.draw.line(self.screen, (240, 198, 116), bottombar_rect.topleft, bottombar_rect.topright, 1)
        

        mouse_pos = pygame.mouse.get_pos()
        if self.exit_btn_rect.collidepoint(mouse_pos):
            button_color = (40, 52, 72)
            text_color = (255, 220, 150)
        else:
            button_color = (24, 33, 46)
            text_color = (240, 198, 116)

        pygame.draw.rect(self.screen, button_color, self.exit_btn_rect)
        pygame.draw.rect(self.screen, text_color, self.exit_btn_rect, 1)
        btn_text = self.small_font.render("EXIT CONFERENCE", True, text_color)
        btn_text_rect = btn_text.get_rect(center=self.exit_btn_rect.center)
        self.screen.blit(btn_text, btn_text_rect)
        if self.chat_btn_rect.collidepoint(mouse_pos):
            chat_btn_color = (40, 52, 72)
           
        else:
            chat_btn_color = (24, 33, 46)
            

        pygame.draw.rect(self.screen, chat_btn_color, self.chat_btn_rect)
        pygame.draw.rect(self.screen, (255,255,255), self.chat_btn_rect, 1)
        chat_text = self.small_font.render("CHAT", True, (255,255,255))
        chat_text_rect = chat_text.get_rect(center=self.chat_btn_rect.center)
        self.screen.blit(chat_text, chat_text_rect)

        if self.history_btn_rect.collidepoint(mouse_pos):
            history_btn_color = (40, 52, 72)
            
        else:
            history_btn_color = (24, 33, 46)
           

        pygame.draw.rect(self.screen, history_btn_color, self.history_btn_rect)
        pygame.draw.rect(self.screen, (255, 255,255), self.history_btn_rect, 1)
        history_text = self.small_font.render("PROPOSAL HISTORY", True, (255, 255,255))
        history_text_rect = history_text.get_rect(center=self.history_btn_rect.center)
        self.screen.blit(history_text, history_text_rect)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if self.exit_btn_rect.collidepoint(event.pos):
                        self.running = False
                    if self.clear_btn_rect.collidepoint(event.pos):
                        pass

                    if self.chat_btn_rect.collidepoint(event.pos):
                        pass
                    if self.history_btn_rect.collidepoint(event.pos):
                        pass


                    if self.ceasefire_btn_rect.collidepoint(event.pos):
                        pass
                    
                    if self.state_transfer_btn_rect.collidepoint(event.pos):
                        pass
                    if self.puppet_state_btn_rect.collidepoint(event.pos):
                        pass
                    if self.military_access_btn_rect.collidepoint(event.pos):
                        pass
                    if self.regime_change_btn_rect.collidepoint(event.pos):
                        pass

                    for i, rect in enumerate(self.country_rects):
                            if rect.collidepoint(event.pos):
                                pass
    def draw(self):
        self.screen.fill((11, 18, 32))
        self.draw_status_bar()
        self.draw_left_bar()
        self.draw_right_bar()
        self.draw_bottom_bar()
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