"""互动地图游戏 - 使用 pgzero 实现

功能：
  1. 地图背景展示
  2. 鼠标悬停在兴趣点（POI）上直接弹出简介面板（紧贴 POI 旁边）
  3. 鼠标离开 POI 和面板 → 面板自动消失
"""

import os
os.environ['SDL_VIDEO_CENTERED'] = '1'

# ── 应用图标 ──────────────────────────────────────────────
_ICON_PATH = "images/logo.png"

import pgzrun
import pygame
from map_data import POIS

# ── 窗口设置 ──────────────────────────────────────────────
WIDTH = 1096
HEIGHT = 800
TITLE = "互动地图"

# ── 字体 ───────────────────────────────────────────────────
FONT_NAME = "stheiti.ttc"

# ── 游戏 UI 颜色 ──────────────────────────────────────────
COLOR_POI        = (220, 180, 60)     # 金铜色 POI 标记
COLOR_POI_GLOW   = (255, 200, 80)     # POI 发光色
COLOR_PANEL_BG   = (25, 22, 40, 240)  # 深色面板背景
COLOR_PANEL_BORDER = (160, 130, 50)   # 面板金色边框
COLOR_TEXT       = (220, 215, 200)    # 米白文字
COLOR_TITLE      = (255, 200, 80)     # 金色标题
COLOR_CLOSE_BTN  = (180, 60, 50)      # 关闭按钮

# 面板尺寸（和之前一致，但位置会紧贴 POI）
PANEL_W = 630
PANEL_H = 510

# ── 状态 ──────────────────────────────────────────────────
mouse_pos = (0, 0)
hovered_poi = None          # 当前悬停的 POI 对象
panel_poi = None            # 当前显示面板的 POI
panel_close_rect = None

# ── 地图背景 ──────────────────────────────────────────────
_bg_cache = None

def draw_map():
    """绘制地图背景（左右裁剪为窗口比例，再拉伸填满）"""
    global _bg_cache
    if _bg_cache is None:
        img = pygame.image.load(os.path.join("images", "school-bg.png")).convert()
        iw, ih = img.get_size()
        target_ratio = WIDTH / HEIGHT
        crop_w = int(ih * target_ratio)
        crop_x = (iw - crop_w) // 2
        img = img.subsurface(pygame.Rect(crop_x, 0, crop_w, ih))
        _bg_cache = pygame.transform.smoothscale(img, (WIDTH, HEIGHT))
    screen.surface.blit(_bg_cache, (0, 0))

# ── 工具函数 ──────────────────────────────────────────────
def draw_rounded_rect(surf, rect, color, radius=8, border_color=None, border_width=2):
    """绘制圆角矩形"""
    r = pygame.Rect(rect)
    s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    pygame.draw.rect(s, color, (2, 2, r.w - 4, r.h - 4), border_radius=radius)
    if border_color:
        pygame.draw.rect(s, border_color, (2, 2, r.w - 4, r.h - 4), border_width, border_radius=radius)
    surf.blit(s, (r.x, r.y))

# ── POI 标记绘制 ──────────────────────────────────────────
def draw_poi_markers():
    """在地图上绘制兴趣点标记（黑色实心小圆）"""
    for poi in POIS:
        x, y = poi["x"], poi["y"]
        is_hovered = (poi is hovered_poi) or (poi is panel_poi)
        # 悬停时发光外圈
        if is_hovered:
            for r in range(6, 0, -1):
                alpha = 20 + r * 6
                pygame.draw.circle(
                    screen.surface, (*COLOR_POI_GLOW[:3], alpha),
                    (x, y), 30 + r * 5, 3
                )
        # POI 标记：白色描边 + 金铜色实心圆
        pygame.draw.circle(screen.surface, (255, 255, 255), (x, y), 12)  # 白色描边
        pygame.draw.circle(screen.surface, COLOR_POI, (x, y), 8)       # 金铜色实心

        # POI 名称（标记下方，白色描边+深色填充防地图背景干扰）
        font = _get_font(14)
        text = poi["name"]
        tw, th = font.size(text)
        tx = x - tw // 2
        ty = y + 16
        # 深色半透明背景条（让文字在任何底色上可读）
        bg_rect = Rect(tx - 6, ty - 1, tw + 12, th + 4)
        bg_surf = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
        bg_surf.fill((20, 18, 30, 180))
        screen.surface.blit(bg_surf, (bg_rect.x, bg_rect.y))
        # 白色边框
        pygame.draw.rect(screen.surface, (255, 255, 255), bg_rect, 1, border_radius=3)
        # 文字
        _render_text_line(font, text, tx, ty, COLOR_TITLE)

# ── 面板位置计算 ──────────────────────────────────────────
def _panel_rect_for(poi):
    """根据 POI 坐标计算面板矩形（贴在 POI 旁边，自动靠边）"""
    pw, ph = PANEL_W, PANEL_H
    px, py = poi["x"] + 28, poi["y"] - 20
    # 水平方向：优先放 POI 右边，不够就放左边
    if px + pw > WIDTH - 10:
        px = poi["x"] - pw - 28
    # 垂直方向：确保不超出窗口
    if py + ph > HEIGHT - 10:
        py = HEIGHT - 10 - ph
    if py < 10:
        py = 10
    return Rect(px, py, pw, ph)

# ── 简介面板 ──────────────────────────────────────────────
def draw_content_panel():
    """绘制 RPG 风格的简介面板"""
    global panel_close_rect
    if not panel_poi:
        return

    pw, ph = PANEL_W, PANEL_H
    panel_rect = _panel_rect_for(panel_poi)
    px, py = panel_rect.x, panel_rect.y

    # 面板阴影
    shadow = pygame.Surface((pw, ph), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 80))
    screen.surface.blit(shadow, (px + 4, py + 4))

    # 面板主体
    draw_rounded_rect(screen.surface, panel_rect, COLOR_PANEL_BG,
                      radius=10, border_color=COLOR_PANEL_BORDER, border_width=2)

    # 装饰顶框
    top_bar = Rect(px + 2, py + 2, pw - 4, 4)
    pygame.draw.rect(screen.surface, COLOR_PANEL_BORDER, top_bar, border_radius=2)

    # 标题装饰：小菱形
    pygame.draw.polygon(screen.surface, COLOR_TITLE,
                        [(px + 18, py + 22), (px + 24, py + 16),
                         (px + 30, py + 22), (px + 24, py + 28)])

    # 标题
    screen.draw.text(panel_poi["name"],
                     topleft=(px + 38, py + 14),
                     fontname=FONT_NAME,
                     fontsize=20, color=COLOR_TITLE)

    # 关闭按钮
    close_rect = Rect(px + pw - 40, py + 8, 30, 30)
    panel_close_rect = close_rect
    pad = 9
    pygame.draw.line(screen.surface, COLOR_CLOSE_BTN,
                     (close_rect.left + pad, close_rect.top + pad),
                     (close_rect.right - pad, close_rect.bottom - pad), 2)
    pygame.draw.line(screen.surface, COLOR_CLOSE_BTN,
                     (close_rect.right - pad, close_rect.top + pad),
                     (close_rect.left + pad, close_rect.bottom - pad), 2)

    _draw_intro_content(px, py, pw, ph)

def _get_font(size):
    font_path = os.path.join("fonts", FONT_NAME)
    try:
        return pygame.font.Font(font_path, size)
    except (FileNotFoundError, pygame.error):
        try:
            return pygame.font.SysFont(FONT_NAME.replace(".ttc", ""), size)
        except pygame.error:
            return pygame.font.Font(None, size)

def _render_text_line(font, text, x, y, color):
    surf = font.render(text, True, color)
    screen.surface.blit(surf, (x, y))

def _load_poi_image(poi):
    if not hasattr(_load_poi_image, "cache"):
        _load_poi_image.cache = {}
    img_name = poi.get("image")
    if not img_name:
        return None
    if img_name in _load_poi_image.cache:
        return _load_poi_image.cache[img_name]
    img_path = os.path.join("images", img_name)
    try:
        img = pygame.image.load(img_path).convert()
        _load_poi_image.cache[img_name] = img
        return img
    except (FileNotFoundError, pygame.error):
        _load_poi_image.cache[img_name] = None
        return None

def _draw_intro_content(px, py, pw, ph):
    """绘制古卷轴风格的简介内容"""
    content_rect = Rect(px + 16, py + 50, pw - 32, ph - 70)
    scroll_surf = pygame.Surface((content_rect.w, content_rect.h), pygame.SRCALPHA)
    pygame.draw.rect(scroll_surf, (60, 52, 40, 230), (0, 0, content_rect.w, content_rect.h),
                     border_radius=4)
    for yy in (4, content_rect.h - 5):
        pygame.draw.rect(scroll_surf, (120, 100, 60, 100),
                         (10, yy, content_rect.w - 20, 2))
    for xx in (6, content_rect.w - 7):
        pygame.draw.line(scroll_surf, (120, 100, 60, 60),
                         (xx, 6), (xx, content_rect.h - 6))
    screen.surface.blit(scroll_surf, (content_rect.x, content_rect.y))

    screen.draw.text("◇ 介 绍 ◇",
                     center=(px + pw // 2, py + 56),
                     fontname=FONT_NAME,
                     fontsize=13, color=(180, 160, 100))

    max_width = pw - 60
    line_height = 22
    text_x = px + 30
    text_y = py + 78

    font = _get_font(16)
    text_color = (230, 215, 180)

    for paragraph in panel_poi["intro"].split("\n"):
        if not paragraph:
            text_y += line_height
            continue
        line = ""
        for ch in paragraph:
            test_line = line + ch
            if font.size(test_line)[0] > max_width:
                _render_text_line(font, line, text_x, text_y, text_color)
                text_y += line_height
                line = ch
            else:
                line = test_line
        if line:
            _render_text_line(font, line, text_x, text_y, text_color)
            text_y += line_height

    poi_img = _load_poi_image(panel_poi)
    if poi_img:
        img_w, img_h = poi_img.get_size()
        max_img_w = pw - 60
        content_bottom = py + 50 + (ph - 70) - 8
        avail_h = content_bottom - text_y - 6
        if avail_h > 20:
            scale = min(max_img_w / img_w, avail_h / img_h, 1.0)
            d_w = int(img_w * scale)
            d_h = int(img_h * scale)
            scaled = pygame.transform.smoothscale(poi_img, (d_w, d_h))
            img_x = px + (pw - d_w) // 2
            img_y = text_y + 6
            screen.surface.blit(scaled, (img_x, img_y))

# ── 逻辑更新 ──────────────────────────────────────────────
def update():
    pass

# ── 绘制 ──────────────────────────────────────────────────
_window_icon_set = False

def _set_dock_icon_via_ctypes():
    import ctypes
    try:
        objc = ctypes.cdll.LoadLibrary('/usr/lib/libobjc.A.dylib')
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        ctypes.cdll.LoadLibrary('/System/Library/Frameworks/AppKit.framework')
        NSImage = objc.objc_getClass(b'NSImage')
        alloc_sel = objc.sel_registerName(b'alloc')
        init_sel = objc.sel_registerName(b'initWithContentsOfFile:')
        path = _ICON_PATH.encode('utf-8')
        img = objc.objc_msgSend(NSImage, alloc_sel)
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        img = objc.objc_msgSend(img, init_sel, ctypes.c_char_p(path))
        NSApp = objc.objc_getClass(b'NSApplication')
        shared_sel = objc.sel_registerName(b'sharedApplication')
        app = objc.objc_msgSend(NSApp, shared_sel)
        set_icon_sel = objc.sel_registerName(b'setApplicationIconImage:')
        objc.objc_msgSend(app, set_icon_sel, img)
    except Exception:
        pass

def draw():
    global _window_icon_set
    if not _window_icon_set:
        try:
            icon_img = pygame.image.load(_ICON_PATH)
            pygame.display.set_icon(icon_img)
            _set_dock_icon_via_ctypes()
        except Exception:
            pass
        _window_icon_set = True
    screen.clear()
    draw_map()
    draw_poi_markers()
    draw_content_panel()

# ── 鼠标事件 ──────────────────────────────────────────────
def _hit_poi(pos):
    """检测鼠标位置是否命中某个 POI，返回 POI 或 None"""
    for poi in POIS:
        dx = pos[0] - poi["x"]
        dy = pos[1] - poi["y"]
        if dx * dx + dy * dy <= poi["radius"] * poi["radius"]:
            return poi
    return None

def _in_panel(pos):
    """检测鼠标是否在当前面板内"""
    if not panel_poi:
        return False
    return _panel_rect_for(panel_poi).collidepoint(pos)

def on_mouse_move(pos):
    global mouse_pos, hovered_poi, panel_poi
    mouse_pos = pos

    hit = _hit_poi(pos)

    if panel_poi is None:
        # 面板没开 → 悬停 POI 就打开
        hovered_poi = hit
        if hit:
            panel_poi = hit
    else:
        # 面板已开
        in_panel = _in_panel(pos)

        if hit is panel_poi or in_panel:
            # 在当前 POI 上 或 在面板内 → 什么都不做（保持原样）
            hovered_poi = hit
        elif hit and hit is not panel_poi:
            # 移到另一个 POI → 切换面板
            hovered_poi = hit
            panel_poi = hit
        else:
            # 离开 POI 和面板 → 关闭
            hovered_poi = None
            panel_poi = None

def on_mouse_down(pos, button):
    global panel_poi, hovered_poi

    # 点击关闭按钮 → 关闭面板
    if panel_poi and panel_close_rect and panel_close_rect.collidepoint(pos):
        panel_poi = None
        return

    # 点击面板外
    if panel_poi and not _in_panel(pos):
        hit = _hit_poi(pos)
        if hit:
            panel_poi = hit
        else:
            panel_poi = None
        hovered_poi = hit

# ── 启动 ──────────────────────────────────────────────────
pgzrun.go()
