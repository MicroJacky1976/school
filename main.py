"""互动地图游戏 - 使用 pgzero 实现

功能：
  1. 地图背景展示
  2. 鼠标悬停在兴趣点（POI）上直接弹出简介面板（紧贴 POI 旁边）
  3. 鼠标离开 POI 和面板 → 面板自动消失
"""

import os
import sys

# PyInstaller 打包运行时，切换工作目录到解包目录（sys._MEIPASS），
# 使 images/ 等相对路径在单文件 exe 中也能找到
if hasattr(sys, "_MEIPASS"):
    os.chdir(sys._MEIPASS)

os.environ['SDL_VIDEO_CENTERED'] = '1'

# ── 应用图标 ──────────────────────────────────────────────
_ICON_PATH = "images/logo.png"

import pgzrun
import pygame
from map_data import POIS

# ── 窗口设置 ──────────────────────────────────────────────
WIDTH = 1096
HEIGHT = 800
TITLE = "文一街小学"
ICON = "images/logo.png"  # pgzero 读取此属性，在窗口创建前设置窗口图标

# ── 字体 ───────────────────────────────────────────────────
FONT_NAME = "stheiti.ttc"

# 字体候选文件，按顺序尝试（跨平台：macOS 项目符号链接 → Windows 系统字体 → macOS 系统字体）
_FONT_CANDIDATES = [
    os.path.join("fonts", FONT_NAME),                 # macOS：项目内符号链接
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyh.ttc"),    # Windows：微软雅黑
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simhei.ttf"),  # Windows：黑体
    "/System/Library/Fonts/STHeiti Light.ttc",        # macOS：系统字体
]

# ── 现代简约 UI 颜色 ──────────────────────────────────────
COLOR_POI        = (70, 130, 220)     # 现代蓝 POI 标记
COLOR_POI_GLOW   = (100, 160, 240)    # POI 发光色
COLOR_PANEL_BG   = (255, 255, 255, 245)  # 半透明白色卡片背景
COLOR_PANEL_BORDER = (220, 225, 230)  # 浅灰细边框
COLOR_TEXT       = (50, 55, 65)       # 深色正文
COLOR_TITLE      = (30, 35, 45)       # 深色标题
COLOR_MUTED      = (130, 138, 150)    # 次要文字色

# 面板尺寸（PANEL_W 固定，PANEL_H 根据内容动态计算）
PANEL_W = 560

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
    """在地图上绘制现代化兴趣点标记"""
    for poi in POIS:
        x, y = poi["x"], poi["y"]
        is_hovered = (poi is hovered_poi) or (poi is panel_poi)

        # 悬停时柔和的脉冲光环
        if is_hovered:
            for r, alpha in [(24, 30), (18, 50), (13, 80)]:
                glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*COLOR_POI_GLOW, alpha), (r, r), r)
                screen.surface.blit(glow, (x - r, y - r))

        # POI 标记：外层白色、内层现代蓝
        pygame.draw.circle(screen.surface, (255, 255, 255), (x, y), 10)
        pygame.draw.circle(screen.surface, COLOR_POI, (x, y), 7)

        # POI 名称（标记下方，现代简约标签）
        font = _get_font(13)
        text = poi["name"]
        tw, th = font.size(text)
        tx = x - tw // 2
        ty = y + 14
        # 白色半透明背景标签
        bg_rect = Rect(tx - 8, ty - 1, tw + 16, th + 5)
        bg_surf = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, (255, 255, 255, 220), (0, 0, bg_rect.w, bg_rect.h), border_radius=4)
        screen.surface.blit(bg_surf, (bg_rect.x, bg_rect.y))
        _render_text_line(font, text, tx, ty, COLOR_TITLE)

# ── 面板位置计算 ──────────────────────────────────────────
def _panel_rect_for(poi):
    """根据 POI 坐标计算面板矩形（贴在旁边，智能选方向）"""
    pw, ph = _compute_panel_size(poi)
    gap = 20
    px, py = 0, 0

    # 先尝试右边
    right_x = poi["x"] + gap
    if right_x + pw <= WIDTH - 10:
        px = right_x
    # 再尝试左边
    elif poi["x"] - gap - pw >= 10:
        px = poi["x"] - gap - pw
    # 左右都放不下 → 居中
    else:
        px = (WIDTH - pw) // 2

    # 垂直方向：优先对齐 POI 顶部，根据上方空间决定放 POI 上方还是下方
    # 先尝试放下方
    py = poi["y"] + gap
    if py + ph > HEIGHT - 10:
        # 下方不够 → 放上方
        py = poi["y"] - gap - ph
    if py < 10:
        # 上方也不够 → 贴底
        py = max(10, HEIGHT - 10 - ph)

    return Rect(px, py, pw, ph)

# ── 简介面板（现代简约卡片风格） ────────────────────────
def draw_content_panel():
    """绘制现代卡片风格的简介面板"""
    global panel_close_rect
    if not panel_poi:
        return

    info = _panel_info(panel_poi)
    pw, ph = info["pw"], info["ph"]
    panel_rect = _panel_rect_for(panel_poi)
    px, py = panel_rect.x, panel_rect.y

    # 多层阴影，营造柔和的悬浮感
    for offset, alpha in [(8, 30), (4, 50), (2, 80)]:
        shadow = pygame.Surface((pw + offset, ph + offset), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 0))
        r = pygame.Rect(offset, offset, pw, ph)
        pygame.draw.rect(shadow, (0, 0, 0, alpha), r, border_radius=16)
        screen.surface.blit(shadow, (px, py))

    # 面板主体：白色圆角卡片
    card_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
    card_surf.fill((0, 0, 0, 0))
    pygame.draw.rect(card_surf, COLOR_PANEL_BG, (0, 0, pw, ph), border_radius=16)
    # 细边框
    pygame.draw.rect(card_surf, COLOR_PANEL_BORDER, (0, 0, pw, ph), 1, border_radius=16)
    screen.surface.blit(card_surf, (px, py))

    # 顶部标题栏
    title_font = _get_font(22)
    title_color = COLOR_TITLE
    title_text = panel_poi["name"]
    # 如果 POI 有图片，标题在图片区域下方；没有图片则顶部标题栏
    has_img = bool(info["poi_img"] and info["img_dh"] > 0)

    if not has_img:
        # 无图片：顶部标题 + 一条分隔线
        _render_text_line(_get_font(22), title_text, px + 24, py + 20, title_color)
        # 底部一条细分隔线
        line_rect = Rect(px + 24, py + 60, pw - 48, 1)
        pygame.draw.rect(screen.surface, COLOR_PANEL_BORDER, line_rect)

    # 关闭按钮（鼠标离开自动关闭，无需手动按钮）
    # panel_close_rect 保留给点击逻辑兼容性
    panel_close_rect = None

    _draw_intro_content(px, py, pw, ph, info, has_img)

def _get_font(size):
    for font_path in _FONT_CANDIDATES:
        try:
            return pygame.font.Font(font_path, size)
        except (FileNotFoundError, OSError, pygame.error):
            continue
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

def _measure_wrapped_text(text, font, max_width):
    """测量文字换行后的行数和总高度"""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        line = ""
        for ch in paragraph:
            test_line = line + ch
            if font.size(test_line)[0] > max_width:
                lines.append(line)
                line = ch
            else:
                line = test_line
        if line:
            lines.append(line)
    line_height = 24
    return lines, len(lines) * line_height, line_height


def _panel_info(poi):
    """根据 POI 内容完整计算面板信息（尺寸 + 图片缩放 + 文字行），返回 dict"""
    pw = PANEL_W
    padding = 24
    content_max_w = pw - padding * 2  # 内容区最大宽度（包括图片和文字）
    text_font = _get_font(16)
    text_max_w = content_max_w
    lines, text_h, line_height = _measure_wrapped_text(poi["intro"], text_font, text_max_w)

    poi_img = _load_poi_image(poi)
    has_img = bool(poi_img)

    # 根据是否有图片计算布局常量
    title_h = 30        # 标题 + 间距
    gap_title_text = 4  # 标题与文字的额外间距

    # 先算图片高度
    img_dw, img_dh = 0, 0
    if has_img:
        img_w, img_nh = poi_img.get_size()
        # 按面板内容宽度满配
        scale_full = min(content_max_w / img_w, 1.0)
        img_dw = int(img_w * scale_full)
        img_dh = int(img_nh * scale_full)

    # 现代布局总高度公式：
    # 有图片: padding + img_dh + 16(图→标题) + title_h + gap_title_text + text_h + padding
    # 无图片: 24 + 60(标题栏) + gap_title_text + text_h + padding
    if has_img:
        total_h = padding + img_dh + 16 + title_h + gap_title_text + text_h + padding
    else:
        total_h = padding + 60 + gap_title_text + text_h + padding

    # 屏幕限制
    total_h = min(total_h, HEIGHT - 10)
    # 最小高度
    total_h = max(total_h, 240)

    return {
        "pw": pw, "ph": total_h,
        "img_dw": img_dw, "img_dh": img_dh,
        "text_lines": lines, "font": text_font,
        "poi_img": poi_img,
    }


# 保留 _compute_panel_size 供 _panel_rect_for 使用
def _compute_panel_size(poi):
    info = _panel_info(poi)
    return info["pw"], info["ph"]


def _draw_intro_content(px, py, pw, ph, info, has_img):
    """绘制现代简约内容区：图片+标题+文字，干净无装饰"""
    padding = 24

    font = info["font"]
    text_color = COLOR_TEXT

    cur_y = py + padding

    # ── 有图片时：图片铺满顶部圆角，标题在图片下方 ──
    if has_img:
        poi_img = info["poi_img"]
        img_dw = info["img_dw"]
        img_dh = info["img_dh"]

        # 图片区域（从面板顶部延伸，宽度撑满面板）
        max_w = pw - padding * 2
        # 重新按面板宽度适配图片
        nat_w, nat_h = poi_img.get_size()
        scale = min(max_w / nat_w, 1.0)
        final_dw = int(nat_w * scale)
        final_dh = int(nat_h * scale)

        scaled = pygame.transform.smoothscale(poi_img, (final_dw, final_dh))
        img_x = px + (pw - final_dw) // 2
        # 图片顶部贴紧面板顶，有圆角溢出做遮罩
        screen.surface.blit(scaled, (img_x, cur_y))
        cur_y += final_dh + 16  # 图片与标题间距 16px

        # 标题（深色，无装饰）
        _render_text_line(_get_font(22), panel_poi["name"], px + padding, cur_y, COLOR_TITLE)
        cur_y += 30  # 标题高度约 26px + 间距 4px
    else:
        # 无图片：cur_y 在标题下方（已预留 60px 空间）
        cur_y = py + padding + 60 - 22  # 从标题栏下方开始写文字

    cur_y += 4  # 一点额外间距

    # ── 绘制文字 ──
    line_height = 24
    text_x = px + padding
    for line in info["text_lines"]:
        _render_text_line(font, line, text_x, cur_y, text_color)
        cur_y += line_height

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
        # macOS Dock 图标需在窗口创建后通过 AppKit 设置（Windows 图标已在启动前设置）
        if sys.platform == "darwin":
            _set_dock_icon_via_ctypes()
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
