import pygame
import sys
import os

from engine.runtime import main
from game.scripts import ScriptMenuController

pygame.init()
pygame.mixer.init()

button_click_sound = pygame.mixer.Sound("assets/sounds/click.wav")
button_click_sound.set_volume(0.4)




import shutil

def remove_cache():
    targets = [
        os.path.join(_ROOT, '.ebee_super_optimization'),
        os.path.join(_ROOT, 'map', '.ebee_super_optimization')
    ]
    for path in targets:
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
                print(f'Deleted {path}')
        except Exception as e:
            print(f'Error deleting {path}: {e}')

    

def lerp(start, end, t):
    return start + (end - start) * t

WIDTH,HEIGHT = 1280,720

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_FONTS = os.path.join(_ROOT, 'fonts')
_IMAGES = os.path.join(_ROOT, 'images')

screen = pygame.display.set_mode((WIDTH, HEIGHT))

pygame.display.set_caption('Ebee Conquest - Main Menu') 

text= (255, 255, 255)

ease = 1
ease2= 1
ease3= 1
ease4 = 1
ease_scripts = 1
ease_backbutton = 1
ease_removecache = 1



is_fullscreen = False
ease_fullscreen = 1 

volume_drag = False


main_font = pygame.font.Font(os.path.join(_FONTS, "Inter_18pt-Medium.ttf"), 18)
settings_font = pygame.font.Font(os.path.join(_FONTS, "Inter_18pt-Medium.ttf"), 36)



def scale_button():
    global button_m, button_width, button_height, button_y_positions, main_font
    w, h = screen.get_size()

    
    BASE_W, BASE_H = 297, 53
    BASE_FONT = 18

    if is_fullscreen:
        scale = 1.3 
        gap = 35
    else:
        scale = 0.85 
        gap = 25
    
    button_width = int(BASE_W * scale)
    button_height = int(BASE_H * scale)
    main_font = pygame.font.Font(os.path.join(_FONTS, "Inter_18pt-Medium.ttf"), int(BASE_FONT * scale))
    
    total_height = button_height * 5 + gap * 4
    start_y = (h - total_height) // 2
    button_y_positions = {
        'new_game': start_y,
        'load_game': start_y + button_height + gap,
        'scripts': start_y + (button_height + gap) * 2,
        'settings': start_y + (button_height + gap) * 3,
        'quit': start_y + (button_height + gap) * 4
    }

    button_m = (w // 2) - (button_width // 2)



menu = 'main' 
run = True
volume = 50



bg_image = pygame.image.load(os.path.join(_IMAGES, "Game Menu UI Design (1).png")).convert()
bg_image = pygame.transform.smoothscale(bg_image,(WIDTH, HEIGHT))

def glow(screen,x,y,w,h):
    for i in range(1,4):
        lighting = pygame.Surface((w + i*4, h + i*4), pygame.SRCALPHA)
        glow_color =(255,195,0,17)
        pygame.draw.rect(lighting, glow_color, (0, 0, w + i*4, h + i*4))
        
        screen.blit(lighting, (x - i*2, y - i*2))


def button(screen,x,y,w,h):
    button_surf = pygame.Surface((w, h),pygame.SRCALPHA)
    button_color = (15,23,43,180)  
    pygame.draw.rect(button_surf, button_color, (0,0,w,h))
    pygame.draw.rect(button_surf,(187,77,0,255),(0,0,w,h),width=2)
    screen.blit(button_surf, (x, y))


clock = pygame.time.Clock()
script_menu = ScriptMenuController()


scale_button()
while run:
    mouse = pygame.mouse.get_pos()
    screen.blit(bg_image, (0, 0))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False




        if event.type == pygame.MOUSEBUTTONDOWN:
            if menu == 'scripts':
                action = script_menu.handle_event(event, mouse, screen.get_size())
                if action == "back":
                    menu = 'main'
                continue

            if menu == 'settings':
                vol_bar_rect = pygame.Rect(button_m, 280, button_width, 30)
                if vol_bar_rect.collidepoint(mouse):
                    volume_drag = True
                    volume = int((mouse[0] - button_m) / button_width * 100)
                    volume = max(0, min(100, volume))
                    pygame.mixer.music.set_volume(volume / 100)

                if button_m < mouse[0] < button_m + button_width and 530 < mouse[1] < 583:
                    button_click_sound.play()
                    remove_cache() 



                if button_m < mouse[0] < button_m + button_width and 310 < mouse[1] < 363:
                    is_fullscreen = not is_fullscreen
                    if is_fullscreen:
                        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((WIDTH, HEIGHT))

                    scale_button()
                    w, h = screen.get_size()
                    bg_image = pygame.transform.smoothscale(
                        pygame.image.load(os.path.join(_IMAGES, "Game Menu UI Design (1).png")).convert(),
                        (w, h),
                    )



                if button_m < mouse[0] < button_m + button_width and 420 < mouse[1] < 473:
                            menu = 'main'

            elif menu == 'main':
                if button_m < mouse[0] < button_m + button_width and button_y_positions['new_game'] < mouse[1] < button_y_positions['new_game'] + button_height:
                    main(is_fullscreen=is_fullscreen)
                    pygame.quit()
                    sys.exit()
                    
                elif button_m < mouse[0] < button_m+button_width and button_y_positions['settings'] < mouse[1] < button_y_positions['settings'] + button_height:
                    menu = 'settings'

                elif button_m < mouse[0] < button_m + button_width and button_y_positions['scripts'] < mouse[1] < button_y_positions['scripts'] + button_height:
                    menu = 'scripts'

                elif button_m < mouse[0] < button_m + button_width and button_y_positions['quit'] < mouse[1] < button_y_positions['quit'] + button_height:
                    run = False

                elif button_m < mouse[0] < button_m + button_width and button_y_positions['load_game'] < mouse[1] < button_y_positions['load_game'] + button_height:
                    print('loading game....')


        if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    volume_drag = False

        if event.type == pygame.MOUSEMOTION:
            if volume_drag and menu == 'settings':
                volume = int((mouse[0] - button_m) / button_width * 100)
                volume = max(0, min(100, volume))
                pygame.mixer.music.set_volume(volume / 100)






                    
    if menu == 'main':
        
        
        y_pos = button_y_positions['new_game']
        hover = button_m < mouse[0] < button_m + button_width and y_pos < mouse[1] < y_pos + button_height

        
        new_w = int(button_width * ease)
        new_x = button_m - (new_w - button_width) // 2
        
        new_h = int(button_height * ease)

       
        new_y = y_pos - (new_h - button_height) // 2

        
        if hover:
            expand = 1.15
        else:
            expand = 1 

        ease = lerp(ease, expand, 0.15)

      

        if ease > 1.01:
            glow(screen, new_x, new_y, new_w, new_h)
        button(screen, new_x, new_y, new_w, new_h)

        txt1 = main_font.render('NEW GAME',True,text)
        txt1_rect = txt1.get_rect(center=(new_x + new_w // 2, new_y + new_h // 2))
        screen.blit(txt1, txt1_rect)

            
        
        y_pos = button_y_positions['settings']
        hover = button_m < mouse[0] < button_m + button_width and y_pos < mouse[1] < y_pos + button_height

        new_w = int(button_width * ease2)
        new_x = button_m - (new_w - button_width) // 2
        
        new_h = int(button_height * ease2)

        
        new_y = y_pos - (new_h - button_height) // 2



        if hover:
            expand = 1.15
        else:
            expand = 1

        ease2 = lerp(ease2, expand, 0.15)

      

        if ease2 > 1.01:
            glow(screen, new_x, new_y, new_w, new_h)
        button(screen, new_x, new_y, new_w, new_h)

        txt2 = main_font.render('SETTINGS',True,text)
        txt2_rect = txt2.get_rect(center=(new_x + new_w // 2, new_y + new_h // 2))
        screen.blit(txt2, txt2_rect)



        y_pos = button_y_positions['quit']
        hover = button_m < mouse[0] < button_m + button_width and y_pos < mouse[1] < y_pos + button_height
        new_w = int(button_width * ease3)
        new_x = button_m - (new_w - button_width) // 2
        
        new_h = int(button_height * ease3)

       
        new_y = y_pos - (new_h - button_height) // 2


      
        if hover:
            expand = 1.15
        else:
            expand = 1

        ease3 = lerp(ease3, expand, 0.15)

      

        if ease3 > 1.01:
            glow(screen, new_x, new_y, new_w, new_h)
        button(screen, new_x, new_y, new_w, new_h)


        txt3 = main_font.render('QUIT', True, text)
        txt3_rect = txt3.get_rect(center=(new_x + new_w // 2, new_y + new_h // 2))
        screen.blit(txt3, txt3_rect)




        y_pos = button_y_positions['load_game']
        hover = button_m < mouse[0] < button_m + button_width and y_pos < mouse[1] < y_pos + button_height
        new_w = int(button_width * ease4)
        new_x = button_m - (new_w - button_width) // 2
        
        new_h = int(button_height * ease4)


        new_y = y_pos - (new_h - button_height) // 2
       

        if hover:
            expand = 1.15
        else:
            expand = 1

        ease4 = lerp(ease4, expand, 0.15)

      

        if ease4 > 1.01:
            glow(screen, new_x, new_y, new_w, new_h)
        button(screen, new_x, new_y, new_w, new_h)

        txt5 = main_font.render('LOAD GAME', True, text)
        txt5_rect = txt5.get_rect(center=(new_x + new_w // 2, new_y + new_h // 2))
        screen.blit(txt5, txt5_rect)


        y_pos = button_y_positions['scripts']
        hover = button_m < mouse[0] < button_m + button_width and y_pos < mouse[1] < y_pos + button_height
        new_w = int(button_width * ease_scripts)
        new_x = button_m - (new_w - button_width) // 2

        new_h = int(button_height * ease_scripts)

        new_y = y_pos - (new_h - button_height) // 2

        if hover:
            expand = 1.15
        else:
            expand = 1

        ease_scripts = lerp(ease_scripts, expand, 0.15)

        if ease_scripts > 1.01:
            glow(screen, new_x, new_y, new_w, new_h)
        button(screen, new_x, new_y, new_w, new_h)

        scripts_text = main_font.render('SCRIPTS', True, text)
        scripts_rect = scripts_text.get_rect(center=(new_x + new_w // 2, new_y + new_h // 2))
        screen.blit(scripts_text, scripts_rect)







    if menu == 'settings':
        overlay = pygame.Surface(screen.get_size())
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        title = settings_font.render('       SETTINGS', True, text)
        screen.blit(title, (button_m, 30))

        vol_text = main_font.render('Volume: ' + str(volume) + '%', True, text)
        screen.blit(vol_text, (button_m, 250))

        pygame.draw.rect(screen, (60, 60, 60), (button_m, 290, button_width, 8))
        bar_fill = int(button_width * volume / 100)
        pygame.draw.rect(screen, (0, 255, 0), (button_m, 290, bar_fill, 8))

        knob = button_m + bar_fill
        pygame.draw.circle(screen, (255, 255, 255), (knob, 295), 8)

        
        hover_fullscreen = button_m < mouse[0] < button_m + button_width and 310 < mouse[1] < 363

        new_w = int(button_width * ease_fullscreen)
        new_x = button_m - (new_w - button_width) // 2
        new_h = int(button_height * ease_fullscreen)
        new_y = 310 - (new_h - button_height) // 2

        if hover_fullscreen:
            expand = 1.15
        else:
            expand = 1
        ease_fullscreen = lerp(ease_fullscreen, expand, 0.15)

        if ease_fullscreen > 1.01:
            glow(screen, new_x, new_y, new_w, new_h)
        button(screen, new_x, new_y, new_w, new_h)

        fs_text = 'TOGGLE FULLSCREEN: ON' if is_fullscreen else 'TOGGLE FULLSCREEN: OFF'
        fullscreen_text = main_font.render(fs_text, True, text)
        fs_box = fullscreen_text.get_rect(center=(new_x + new_w // 2, new_y + new_h // 2))
        screen.blit(fullscreen_text, fs_box)

    
        hover_back = button_m < mouse[0] < button_m + button_width and 420 < mouse[1] < 473
        new_w = int(button_width * ease_backbutton)
        new_x = button_m - (new_w - button_width) // 2
        new_h = int(button_height * ease_backbutton)
        new_y = 420 - (new_h - button_height) // 2

        if hover_back:
            expand = 1.15
        else:
            expand = 1
        ease_backbutton = lerp(ease_backbutton, expand, 0.15)

        if ease_backbutton > 1.01:
            glow(screen, new_x, new_y, new_w, new_h)
        button(screen, new_x, new_y, new_w, new_h)

        back_text = main_font.render('BACK', True, text)
        back_rect = back_text.get_rect(center=(new_x + new_w // 2, new_y + new_h // 2))
        screen.blit(back_text, back_rect)

        hover_cache = button_m < mouse[0] < button_m + button_width and 530 < mouse[1] < 583
        new_w = int(button_width * ease_removecache)
        new_x = button_m - (new_w - button_width) // 2
        new_h = int(button_height * ease_removecache)
        new_y = 530 - (new_h - button_height) // 2

        if hover_cache:
            expand = 1.15
        else:
            expand = 1
        ease_removecache = lerp(ease_removecache, expand, 0.15)

        if ease_removecache > 1.01:
            glow(screen, new_x, new_y, new_w, new_h)
        button(screen, new_x, new_y, new_w, new_h)

        cache_text = main_font.render('REMOVE CACHE', True, text)
        cache_rect = cache_text.get_rect(center=(new_x + new_w // 2, new_y + new_h // 2))
        screen.blit(cache_text, cache_rect)

        warning_text = main_font.render('WARNING: GAME WILL RUN SLOWER THE NEXT TIME IF YOU PRESS REMOVE CACHE !!', True, (255, 100,100)) 
        warning_rect = warning_text.get_rect(center=(button_m + button_width // 2, new_y + new_h + 20))
        screen.blit(warning_text, warning_rect)

    if menu == 'scripts':
        script_menu.draw(screen)

    pygame.display.flip()

    clock.tick(240)


 
pygame.quit()           
sys.exit()
