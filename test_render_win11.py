import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WINDIR = os.environ.get('WINDIR', 'C:\\Windows')
FONT_REGULAR = os.path.join(WINDIR, 'Fonts', 'segoeui.ttf')
FONT_BOLD = os.path.join(WINDIR, 'Fonts', 'segoeuib.ttf')
FONT_SEMIBOLD = os.path.join(WINDIR, 'Fonts', 'seguisb.ttf')
if not os.path.exists(FONT_SEMIBOLD):
    FONT_SEMIBOLD = FONT_BOLD

def draw_fluent_mic(d, cx, cy, sz, color, stroke_w=None):
    """Rysuje precyzyjną ikonę mikrofonu Windows 11 Fluent."""
    cap_w = sz * 0.36
    cap_h = sz * 0.60
    cap_r = cap_w / 2.0
    
    # 1. Kapsułka mikrofonu
    d.rounded_rectangle(
        [cx - cap_w/2, cy - cap_h/2 - sz*0.08, cx + cap_w/2, cy + cap_h/2 - sz*0.08],
        radius=cap_r,
        fill=color
    )
    
    # 2. Koszyczek (cradle) wokół dolnej połowy
    cradle_r = sz * 0.32
    cradle_top_y = cy - sz * 0.12
    cradle_bot_y = cy + cradle_r - sz * 0.08
    line_w = stroke_w if stroke_w else max(2, int(sz * 0.09))
    
    d.arc(
        [cx - cradle_r, cy - cradle_r - sz*0.08, cx + cradle_r, cy + cradle_r - sz*0.08],
        start=0, end=180,
        fill=color, width=line_w
    )
    d.line([(cx - cradle_r, cy - sz*0.08), (cx - cradle_r, cradle_top_y)], fill=color, width=line_w)
    d.line([(cx + cradle_r, cy - sz*0.08), (cx + cradle_r, cradle_top_y)], fill=color, width=line_w)
    
    # 3. Nóżka pionowa
    stem_top = cradle_bot_y
    stem_bot = stem_top + sz * 0.18
    d.line([(cx, stem_top), (cx, stem_bot)], fill=color, width=line_w)
    
    # 4. Podstawka pozioma
    base_w = sz * 0.44
    d.line([(cx - base_w/2, stem_bot), (cx + base_w/2, stem_bot)], fill=color, width=line_w)

def draw_fluent_gear(d, cx, cy, r, color, fill_bg):
    """Rysuje koło zębate."""
    scale = r / 8.5
    for i in range(8):
        ang = i * (math.pi / 4)
        gx1 = cx + (r - 2.5*scale) * math.cos(ang)
        gy1 = cy + (r - 2.5*scale) * math.sin(ang)
        gx2 = cx + (r + 2.2*scale) * math.cos(ang)
        gy2 = cy + (r + 2.2*scale) * math.sin(ang)
        d.line([(gx1, gy1), (gx2, gy2)], fill=color, width=int(2.4 * scale))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    d.ellipse([cx - r*0.42, cy - r*0.42, cx + r*0.42, cy + r*0.42], fill=fill_bg)

def render_state(mode="idle", show_balloon="error", theme="light", vol=0.0):
    scale = 3
    W_BASE, H_BASE = 286, 226
    W, H = W_BASE * scale, H_BASE * scale
    
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    ww_base, wh_base = 172, 98
    wx_base = (W_BASE - ww_base) // 2
    wy_base = H_BASE - wh_base - 8
    
    wx, wy = wx_base * scale, wy_base * scale
    ww, wh = ww_base * scale, wh_base * scale
    card_r = 12 * scale
    
    is_dark = (theme == "dark")
    
    # Paleta barw
    if is_dark:
        card_fill = (38, 38, 38, 250)
        card_border = (65, 65, 65, 220)
        hdr_sep = (52, 52, 52, 200)
        handle_col = (130, 130, 130, 200)
        icon_col = (205, 205, 205, 240)
        mic_bg = (52, 52, 52, 255)
        mic_border = (75, 75, 75, 240)
        mic_icon_col = (245, 245, 245, 255)
        ball_bg = (44, 44, 44, 255)
        ball_border = (70, 70, 70, 255)
        ball_text = (240, 240, 240, 255)
        btn_bg = (56, 56, 56, 255)
        btn_border = (80, 80, 80, 255)
        btn_text = (240, 240, 240, 255)
    else:
        card_fill = (243, 243, 243, 250)
        card_border = (222, 222, 222, 220)
        hdr_sep = (230, 230, 230, 180)
        handle_col = (155, 155, 155, 200)
        icon_col = (85, 85, 85, 240)
        mic_bg = (255, 255, 255, 255)
        mic_border = (226, 226, 226, 240)
        mic_icon_col = (50, 50, 50, 255)
        ball_bg = (255, 255, 255, 255)
        ball_border = (228, 228, 228, 255)
        ball_text = (32, 32, 32, 255)
        btn_bg = (255, 255, 255, 255)
        btn_border = (208, 208, 208, 255)
        btn_text = (32, 32, 32, 255)
    
    # Cień widżetu
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([wx, wy + 4 * scale, wx + ww, wy + wh + 6 * scale], radius=card_r, fill=(0, 0, 0, 45 if not is_dark else 80))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=5 * scale))
    img.alpha_composite(shadow)
    d = ImageDraw.Draw(img)
    
    # Korpus widżetu
    d.rounded_rectangle([wx, wy, wx + ww, wy + wh], radius=card_r, fill=card_fill, outline=card_border, width=max(1, int(1.2 * scale)))
    
    # Pasek nagłówka
    hdr_h = 28 * scale
    d.line([(wx + 8 * scale, wy + hdr_h), (wx + ww - 8 * scale, wy + hdr_h)], fill=hdr_sep, width=max(1, int(1 * scale)))
    
    # Uchwyt do przeciągania
    handle_w = 34 * scale
    handle_h = 3.5 * scale
    handle_x = wx + (ww - handle_w) / 2
    handle_y = wy + 10 * scale
    d.rounded_rectangle([handle_x, handle_y, handle_x + handle_w, handle_y + handle_h], radius=int(handle_h/2), fill=handle_col)
    
    # Przycisk zamykania '✕'
    close_cx = wx + ww - 18 * scale
    close_cy = wy + 12 * scale
    x_sz = 3.5 * scale
    d.line([(close_cx - x_sz, close_cy - x_sz), (close_cx + x_sz, close_cy + x_sz)], fill=icon_col, width=max(1, int(1.4 * scale)))
    d.line([(close_cx - x_sz, close_cy + x_sz), (close_cx + x_sz, close_cy - x_sz)], fill=icon_col, width=max(1, int(1.4 * scale)))
    
    controls_cy = wy + hdr_h + (wh - hdr_h) / 2
    
    # Przycisk Ustawienia ⚙
    gear_cx = wx + 30 * scale
    gear_cy = controls_cy
    gear_r = 8.5 * scale
    draw_fluent_gear(d, gear_cx, gear_cy, gear_r, icon_col, card_fill)
    
    # Przycisk Pomoc ?
    help_cx = wx + ww - 30 * scale
    help_cy = controls_cy
    help_r = 8.5 * scale
    d.ellipse([help_cx - help_r, help_cy - help_r, help_cx + help_r, help_cy + help_r], outline=icon_col, width=int(1.3 * scale))
    fnt_q = ImageFont.truetype(FONT_BOLD, int(11 * scale))
    d.text((help_cx, help_cy - 0.5 * scale), "?", fill=icon_col, font=fnt_q, anchor="mm")
    
    # Centralny Przycisk Mikrofonu
    mic_cx = wx + ww / 2
    mic_cy = controls_cy
    mic_rad = 24 * scale
    
    if mode == "recording":
        # W trybie nagrywania: dynamiczny, pulsujący pierścień audio i fale głośności
        accent_blue = (0, 103, 192) if not is_dark else (76, 194, 255)
        # Efekt fali głosu wokół przycisku
        wave_pulse = max(0.1, vol)
        outer_rad = int(mic_rad + 4 * scale + wave_pulse * 9 * scale)
        
        # Błękitna poświata reaktywna
        glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([mic_cx - outer_rad, mic_cy - outer_rad, mic_cx + outer_rad, mic_cy + outer_rad], fill=accent_blue + (int(120 * wave_pulse + 50),))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=4 * scale))
        img.alpha_composite(glow)
        d = ImageDraw.Draw(img)
        
        # Tło przycisku - błękitny Windows 11 accent
        d.ellipse([mic_cx - mic_rad, mic_cy - mic_rad, mic_cx + mic_rad, mic_cy + mic_rad], fill=accent_blue + (255,), outline=(255, 255, 255, 240), width=int(1.5 * scale))
        draw_fluent_mic(d, mic_cx, mic_cy, 21 * scale, (255, 255, 255, 255))
        
    elif mode == "processing":
        # Przetwarzanie Whisper
        proc_col = (255, 140, 0)
        d.ellipse([mic_cx - mic_rad, mic_cy - mic_rad, mic_cx + mic_rad, mic_cy + mic_rad], fill=mic_bg, outline=proc_col + (230,), width=int(2.2 * scale))
        draw_fluent_mic(d, mic_cx, mic_cy, 21 * scale, proc_col + (255,))
        
    else: # idle
        # Cień mikrofonu
        mic_shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        msd = ImageDraw.Draw(mic_shadow)
        msd.ellipse([mic_cx - mic_rad, mic_cy - mic_rad + 2*scale, mic_cx + mic_rad, mic_cy + mic_rad + 3*scale], fill=(0, 0, 0, 30))
        mic_shadow = mic_shadow.filter(ImageFilter.GaussianBlur(radius=2.5 * scale))
        img.alpha_composite(mic_shadow)
        d = ImageDraw.Draw(img)
        
        d.ellipse([mic_cx - mic_rad, mic_cy - mic_rad, mic_cx + mic_rad, mic_cy + mic_rad], fill=mic_bg, outline=mic_border, width=int(1.1 * scale))
        draw_fluent_mic(d, mic_cx, mic_cy, 21 * scale, mic_icon_col)
    
    # DYMEK POWIADOMIENIA
    if show_balloon:
        bw_base, bh_base = 262, 102
        bx_base = (W_BASE - bw_base) // 2
        by_base = wy_base - bh_base - 10
        bx, by = bx_base * scale, by_base * scale
        bw, bh = bw_base * scale, bh_base * scale
        ball_r = 10 * scale
        
        # Cień dymka
        b_shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        bsd = ImageDraw.Draw(b_shadow)
        bsd.rounded_rectangle([bx, by + 3*scale, bx + bw, by + bh + 5*scale], radius=ball_r, fill=(0, 0, 0, 40 if not is_dark else 75))
        tri_cx = W / 2
        tri_top = by + bh + 3*scale
        tri_bot = tri_top + 8 * scale
        tri_hw = 8 * scale
        bsd.polygon([(tri_cx - tri_hw, tri_top), (tri_cx + tri_hw, tri_top), (tri_cx, tri_bot)], fill=(0, 0, 0, 40 if not is_dark else 75))
        b_shadow = b_shadow.filter(ImageFilter.GaussianBlur(radius=4 * scale))
        img.alpha_composite(b_shadow)
        d = ImageDraw.Draw(img)
        
        # Korpus dymka
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=ball_r, fill=ball_bg, outline=ball_border, width=max(1, int(1.1 * scale)))
        tri_top = by + bh - 1 * scale
        tri_bot = tri_top + 8 * scale
        d.polygon([(tri_cx - tri_hw, tri_top), (tri_cx + tri_hw, tri_top), (tri_cx, tri_bot)], fill=ball_bg)
        d.line([(tri_cx - tri_hw, tri_top), (tri_cx, tri_bot)], fill=ball_border, width=max(1, int(1.1 * scale)))
        d.line([(tri_cx + tri_hw, tri_top), (tri_cx, tri_bot)], fill=ball_border, width=max(1, int(1.1 * scale)))
        
        fnt_text = ImageFont.truetype(FONT_REGULAR, int(11.5 * scale))
        
        if show_balloon == "error":
            # Czerwone kółko błędu ❌
            err_cx = bx + 22 * scale
            err_cy = by + 26 * scale
            err_r = 8.5 * scale
            d.ellipse([err_cx - err_r, err_cy - err_r, err_cx + err_r, err_cy + err_r], fill=(209, 52, 56, 255))
            ex_sz = 3.2 * scale
            d.line([(err_cx - ex_sz, err_cy - ex_sz), (err_cx + ex_sz, err_cy + ex_sz)], fill=(255, 255, 255, 255), width=max(1, int(1.6 * scale)))
            d.line([(err_cx - ex_sz, err_cy + ex_sz), (err_cx + ex_sz, err_cy - ex_sz)], fill=(255, 255, 255, 255), width=max(1, int(1.6 * scale)))
            
            msg_lines = [
                "Aby używać wpisywania głosowego,",
                "zaznacz pole tekstowe i spróbuj",
                "ponownie."
            ]
        elif show_balloon == "help":
            # Niebieska ikonka info ℹ
            info_cx = bx + 22 * scale
            info_cy = by + 26 * scale
            info_r = 8.5 * scale
            d.ellipse([info_cx - info_r, info_cy - info_r, info_cx + info_r, info_cy + info_r], fill=(0, 103, 192, 255) if not is_dark else (76, 194, 255, 255))
            fnt_i = ImageFont.truetype(FONT_BOLD, int(11 * scale))
            d.text((info_cx, info_cy - 0.5 * scale), "i", fill=(255, 255, 255, 255), font=fnt_i, anchor="mm")
            
            msg_lines = [
                "Wskazówki wpisywania głosowego:",
                "Kliknij pole tekstowe, mów po polsku.",
                "Skrót: Ctrl+Alt+D lub mysz MX Master."
            ]
        else: # general info
            err_cx = bx + 22 * scale
            err_cy = by + 26 * scale
            err_r = 8.5 * scale
            d.ellipse([err_cx - err_r, err_cy - err_r, err_cx + err_r, err_cy + err_r], fill=(0, 120, 215, 255))
            msg_lines = [show_balloon, "", ""]
            
        ty = by + 13 * scale
        tx = bx + 37 * scale
        for line in msg_lines:
            d.text((tx, ty), line, fill=ball_text, font=fnt_text)
            ty += 16 * scale
            
        # Przycisk "Rozumiem"
        btn_w = bw - 32 * scale
        btn_h = 28 * scale
        btn_x = bx + 16 * scale
        btn_y = by + bh - btn_h - 12 * scale
        btn_r = 5 * scale
        d.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=btn_r, fill=btn_bg, outline=btn_border, width=max(1, int(1 * scale)))
        d.text((btn_x + btn_w/2, btn_y + btn_h/2), "Rozumiem", fill=btn_text, font=fnt_text, anchor="mm")
        
    return img.resize((W_BASE, H_BASE), Image.Resampling.LANCZOS)

def create_full_showcase():
    im_err_light = render_state(mode="idle", show_balloon="error", theme="light")
    im_rec_light = render_state(mode="recording", show_balloon=None, theme="light", vol=0.7)
    im_idle_light = render_state(mode="idle", show_balloon=None, theme="light")
    im_err_dark = render_state(mode="idle", show_balloon="error", theme="dark")
    
    # Połącz 4 warianty na jednej planszy demonstracyjnej
    spacing = 15
    tot_w = im_err_light.width * 2 + spacing * 3
    tot_h = im_err_light.height * 2 + spacing * 3 + 40
    
    board = Image.new('RGBA', (tot_w, tot_h), (25, 28, 35, 255))
    bd = ImageDraw.Draw(board)
    fnt_title = ImageFont.truetype(FONT_BOLD, 16)
    bd.text((tot_w // 2, 22), "🎙️ Nowy Widżet Dyktowania Windows 11 (Odwzorowanie 1:1)", fill=(240, 245, 255, 255), font=fnt_title, anchor="mm")
    
    fnt_sub = ImageFont.truetype(FONT_REGULAR, 12)
    # 1. Błąd - brak pola tekstowego (Dokładnie ze zrzutu ekranu!)
    x1, y1 = spacing, 45
    board.alpha_composite(im_err_light, (x1, y1))
    bd.text((x1 + im_err_light.width//2, y1 + im_err_light.height + 2), "1. Komunikat braku pola (Zrzut 1:1)", fill=(200, 210, 225, 255), font=fnt_sub, anchor="mt")
    
    # 2. Nagrywanie na żywo (Reakcja na głos)
    x2, y2 = x1 + im_err_light.width + spacing, 45
    board.alpha_composite(im_rec_light, (x2, y2))
    bd.text((x2 + im_rec_light.width//2, y2 + im_rec_light.height + 2), "2. Aktywne nagrywanie (Fala głosu / Win 11)", fill=(200, 210, 225, 255), font=fnt_sub, anchor="mt")
    
    # 3. Stan spoczynku (Czuwanie)
    x3, y3 = spacing, y1 + im_err_light.height + spacing + 20
    board.alpha_composite(im_idle_light, (x3, y3))
    bd.text((x3 + im_idle_light.width//2, y3 + im_idle_light.height + 2), "3. Stan gotowości (Jasny motyw)", fill=(200, 210, 225, 255), font=fnt_sub, anchor="mt")
    
    # 4. Motyw Ciemny
    x4, y4 = x2, y3
    board.alpha_composite(im_err_dark, (x4, y4))
    bd.text((x4 + im_err_dark.width//2, y4 + im_err_dark.height + 2), "4. Komunikat w motywie ciemnym (Dark)", fill=(200, 210, 225, 255), font=fnt_sub, anchor="mt")
    
    board.save('win11_showcase.png')
    print("Wygenerowano planszę: win11_showcase.png")

if __name__ == '__main__':
    create_full_showcase()
