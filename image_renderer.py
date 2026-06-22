from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from price_algorithm import format_price


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
LOGO_PATH = ASSETS / "diamantsk.png"
FONT_REGULAR_PATH = ASSETS / "NotoSans-Regular.ttf"
FONT_BOLD_PATH = ASSETS / "NotoSans-Bold.ttf"
EVOLVENTA_REGULAR_PATH = ASSETS / "Evolventa-Regular.ttf"
EVOLVENTA_BOLD_PATH = ASSETS / "Evolventa-Bold.ttf"
TILLACHI_CORNER_PATH = ASSETS / "tillachi_corner_source.png"
GOLDEXPERT_LOGO_PATH = ASSETS / "goldexpert_logo.webp"
SKUPKA_LOGO_PATH = ASSETS / "skupka_logo.webp"

CANVAS_WIDTH = 904
CANVAS_HEIGHT = 1280
TITLE_TEXT = "\u0426\u0415\u041D\u0410 \u0417\u0410 1 \u0413\u0420\u0410\u041C\u041C \u0417\u041E\u041B\u041E\u0422\u0410"

PRICE_TABLE = {
    "left_x": 86,
    "right_edge": 818,
    "start_y": 430,
    "row_h": 76,
    "sample_size": 42,
    "price_size": 42,
    "price_min_size": 30,
    "price_max_width": 458,
}

ORG_TEMPLATES = {
    "diamant": {
        "style": "diamant",
        "title": TITLE_TEXT,
        "logo": LOGO_PATH,
        "accent": "#d52b24",
        "background": "#ffffff",
        "text": "#050505",
        "phone": "+998 55 055 00 02",
    },
    "org2": {
        "style": "diamant",
        "title": TITLE_TEXT,
        "logo": LOGO_PATH,
        "accent": "#d52b24",
        "background": "#ffffff",
        "text": "#050505",
        "phone": "+998 55 055 00 02",
    },
    "org3": {
        "style": "diamant",
        "title": TITLE_TEXT,
        "logo": LOGO_PATH,
        "accent": "#d52b24",
        "background": "#ffffff",
        "text": "#050505",
        "phone": "+998 55 055 00 02",
    },
    "org4": {
        "style": "diamant",
        "title": TITLE_TEXT,
        "logo": LOGO_PATH,
        "accent": "#d52b24",
        "background": "#ffffff",
        "text": "#050505",
        "phone": "+998 55 055 00 02",
    },
    "tillachi": {
        "style": "tillachi",
        "brand": "Tillachi bolla",
        "title": TITLE_TEXT,
        "accent": "#ffcc00",
        "background": "#000000",
        "text": "#ffcc00",
        "phone": "+998 50 590 14 50",
    },
    "goldexpert": {
        "style": "goldexpert",
        "brand": "GOLDEXPERT.UZ",
        "title": TITLE_TEXT,
        "accent": "#ffa30a",
        "background": "#000014",
        "text": "#ffa30a",
        "logo": GOLDEXPERT_LOGO_PATH,
        "phone": "+998 55 055 20 00",
    },
    "skupka": {
        "style": "skupka",
        "brand": "SKUPKA-ZOLOTA.UZ",
        "title": TITLE_TEXT,
        "accent": "#f7ca39",
        "background": "#000000",
        "text": "#ffffff",
        "logo": SKUPKA_LOGO_PATH,
        "phone": "+998 90 714 90 90",
    },
}


def load_font(size, bold=False, family=None):
    if family == "evolventa":
        path = EVOLVENTA_BOLD_PATH if bold else EVOLVENTA_REGULAR_PATH
        if path.exists():
            return ImageFont.truetype(str(path), size=int(round(size)))
    path = FONT_BOLD_PATH if bold else FONT_REGULAR_PATH
    if path.exists():
        return ImageFont.truetype(str(path), size=int(round(size)))
    return ImageFont.load_default()


def fit_font(draw, text, max_width, start_size, min_size=20, bold=False, family=None):
    for size in range(start_size, min_size - 1, -1):
        font = load_font(size, bold=bold, family=family)
        if draw.textlength(str(text), font=font) <= max_width:
            return font
    return load_font(min_size, bold=bold, family=family)


def draw_centered(draw, y, text, font, fill, width=CANVAS_WIDTH):
    text_w = draw.textlength(text, font=font)
    draw.text(((width - text_w) / 2, y), text, font=font, fill=fill)


def draw_price_table(draw, price_ranges, fill):
    sample_font = load_font(PRICE_TABLE["sample_size"], bold=True, family="evolventa")
    price_texts = {
        probe: f"{format_price(min_price)}-{format_price(max_price)} \u0421\u0423\u041C"
        for probe, (min_price, max_price) in price_ranges.items()
    }
    longest_price = max(price_texts.values(), key=len) if price_texts else ""
    price_font = fit_font(
        draw,
        longest_price,
        PRICE_TABLE["price_max_width"],
        start_size=PRICE_TABLE["price_size"],
        min_size=PRICE_TABLE["price_min_size"],
        bold=True,
        family="evolventa",
    )
    y = PRICE_TABLE["start_y"]
    for probe in price_ranges:
        sample_text = f"{probe} \u041F\u0420\u041E\u0411\u0410"
        price_text = price_texts[probe]
        price_w = draw.textlength(price_text, font=price_font)
        draw.text((PRICE_TABLE["left_x"], y), sample_text, font=sample_font, fill=fill)
        draw.text((PRICE_TABLE["right_edge"] - price_w, y), price_text, font=price_font, fill=fill)
        y += PRICE_TABLE["row_h"]


def save_png(image):
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output.getvalue()


def transparent_black_to_alpha(image, threshold=20):
    image = image.convert("RGBA")
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a == 0 or (r < threshold and g < threshold and b < threshold):
                pixels[x, y] = (0, 0, 0, 0)
    return image


def recolored_logo(path, size, color):
    logo = Image.open(path).convert("RGBA")
    logo.thumbnail((size, size), Image.Resampling.LANCZOS)
    recolored = Image.new("RGBA", logo.size, (0, 0, 0, 0))
    src = logo.load()
    dst = recolored.load()
    r_new, g_new, b_new = Image.new("RGB", (1, 1), color).getpixel((0, 0))
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b, a = src[x, y]
            if a == 0 or (r > 238 and g > 238 and b > 238):
                dst[x, y] = (0, 0, 0, 0)
            else:
                strength = max(100, min(255, int(a * (255 - min(r, g, b)) / 255)))
                dst[x, y] = (r_new, g_new, b_new, strength)
    return recolored


def build_price_image(price_ranges, org="diamant", phone=None, date=None):
    template = ORG_TEMPLATES.get(org, ORG_TEMPLATES["diamant"])
    style = template.get("style")
    if style == "diamant":
        return build_diamant_image(price_ranges, template, phone=phone, date=date)
    if style == "tillachi":
        return build_tillachi_image(price_ranges, template, phone=phone, date=date)
    if style == "goldexpert":
        return build_goldexpert_image(price_ranges, template, phone=phone, date=date)
    if style == "skupka":
        return build_skupka_image(price_ranges, template, phone=phone, date=date)
    return build_diamant_image(price_ranges, ORG_TEMPLATES["diamant"], phone=phone, date=date)


def build_diamant_image(price_ranges, template, phone=None, date=None):
    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), template["background"])
    draw = ImageDraw.Draw(image)
    accent = template["accent"]
    text = template["text"]

    frame_x = 70
    top_line = 70
    bottom_line = CANVAS_HEIGHT - 72
    draw.line((frame_x, 0, frame_x, CANVAS_HEIGHT), fill=accent, width=5)
    draw.line((CANVAS_WIDTH - frame_x, 0, CANVAS_WIDTH - frame_x, CANVAS_HEIGHT), fill=accent, width=5)
    draw.line((0, top_line, CANVAS_WIDTH, top_line), fill=accent, width=5)
    draw.line((0, bottom_line, CANVAS_WIDTH, bottom_line), fill=accent, width=5)

    logo_path = template["logo"]
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo_w = 640
        logo_h = int(logo.height * (logo_w / logo.width))
        logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
        image.paste(logo, ((CANVAS_WIDTH - logo_w) // 2, 108), logo)

    date_font = load_font(34, bold=True, family="evolventa")
    title_font = fit_font(draw, template["title"], CANVAS_WIDTH - 170, 42, 32, bold=True, family="evolventa")
    phone_font = fit_font(draw, phone or template["phone"], CANVAS_WIDTH - 220, 57, 42, bold=True, family="evolventa")

    draw_centered(draw, 260, date or datetime.now().strftime("%d.%m.%Y"), date_font, text)
    draw_centered(draw, 312, template["title"], title_font, text)
    draw_price_table(draw, price_ranges, text)
    draw_centered(draw, CANVAS_HEIGHT - 150, phone or template["phone"], phone_font, text)
    return save_png(image)


def build_tillachi_image(price_ranges, template, phone=None, date=None):
    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), template["background"])
    draw = ImageDraw.Draw(image)
    accent = template["accent"]

    if TILLACHI_CORNER_PATH.exists():
        corner = transparent_black_to_alpha(Image.open(TILLACHI_CORNER_PATH).resize((105, 105), Image.Resampling.LANCZOS))
        image.paste(corner, (0, 0), corner)
        image.paste(corner.rotate(90), (CANVAS_WIDTH - 105, 0), corner.rotate(90))
        image.paste(corner.rotate(270), (0, CANVAS_HEIGHT - 105), corner.rotate(270))
        image.paste(corner.rotate(180), (CANVAS_WIDTH - 105, CANVAS_HEIGHT - 105), corner.rotate(180))

    brand_font = load_font(64, bold=True, family="evolventa")
    date_font = load_font(42, bold=True, family="evolventa")
    title_font = fit_font(draw, template["title"], CANVAS_WIDTH - 170, 43, 34, bold=True, family="evolventa")
    phone_font = fit_font(draw, phone or template["phone"], CANVAS_WIDTH - 220, 57, 42, bold=True, family="evolventa")

    draw_centered(draw, 165, template["brand"], brand_font, accent)
    draw_centered(draw, 282, date or datetime.now().strftime("%d.%m.%Y"), date_font, accent)
    draw_centered(draw, 340, template["title"], title_font, accent)
    draw_price_table(draw, price_ranges, template["text"])
    draw_centered(draw, CANVAS_HEIGHT - 150, phone or template["phone"], phone_font, accent)
    return save_png(image)


def build_goldexpert_image(price_ranges, template, phone=None, date=None):
    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), template["background"])
    draw = ImageDraw.Draw(image)
    accent = template["accent"]

    radius = 88
    for cx, cy in ((0, 0), (CANVAS_WIDTH, 0), (0, CANVAS_HEIGHT), (CANVAS_WIDTH, CANVAS_HEIGHT)):
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=accent)

    draw.line((90, 70, CANVAS_WIDTH - 90, 70), fill=accent, width=4)
    draw.line((90, CANVAS_HEIGHT - 70, CANVAS_WIDTH - 90, CANVAS_HEIGHT - 70), fill=accent, width=4)
    draw.line((70, 92, 70, CANVAS_HEIGHT - 92), fill=accent, width=4)
    draw.line((CANVAS_WIDTH - 70, 92, CANVAS_WIDTH - 70, CANVAS_HEIGHT - 92), fill=accent, width=4)

    logo = recolored_logo(template["logo"], 150, accent)
    logo_x = 100
    logo_y = 108
    image.paste(logo, (logo_x, logo_y), logo)

    brand_font = fit_font(draw, template["brand"], CANVAS_WIDTH - 290, 63, 48, bold=True, family="evolventa")
    brand_bbox = draw.textbbox((0, 0), template["brand"], font=brand_font)
    brand_y = logo_y + (logo.height - (brand_bbox[3] - brand_bbox[1])) / 2 - brand_bbox[1]
    draw.text((270, brand_y), template["brand"], font=brand_font, fill=accent)

    date_font = load_font(42, bold=True, family="evolventa")
    title_font = fit_font(draw, template["title"], CANVAS_WIDTH - 170, 43, 34, bold=True, family="evolventa")
    phone_font = fit_font(draw, phone or template["phone"], CANVAS_WIDTH - 220, 57, 42, bold=True, family="evolventa")

    draw_centered(draw, 282, date or datetime.now().strftime("%d.%m.%Y"), date_font, accent)
    draw_centered(draw, 340, template["title"], title_font, accent)
    draw_price_table(draw, price_ranges, template["text"])
    draw_centered(draw, CANVAS_HEIGHT - 150, phone or template["phone"], phone_font, accent)
    return save_png(image)


def lion_logo(path, size):
    logo = Image.open(path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    return transparent_black_to_alpha(logo)


def build_skupka_image(price_ranges, template, phone=None, date=None):
    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), template["background"])
    draw = ImageDraw.Draw(image)
    accent = template["accent"]
    text = template["text"]

    draw.line((138, 60, CANVAS_WIDTH - 138, 60), fill=accent, width=5)
    draw.line((138, CANVAS_HEIGHT - 60, CANVAS_WIDTH - 138, CANVAS_HEIGHT - 60), fill=accent, width=5)
    draw.line((70, 122, 70, CANVAS_HEIGHT - 122), fill=accent, width=5)
    draw.line((CANVAS_WIDTH - 70, 122, CANVAS_WIDTH - 70, CANVAS_HEIGHT - 122), fill=accent, width=5)

    lion_size = 140
    lion = lion_logo(template["logo"], lion_size)
    image.paste(lion, (0, 0), lion)
    image.paste(lion.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (CANVAS_WIDTH - lion_size, 0), lion.transpose(Image.Transpose.FLIP_LEFT_RIGHT))
    image.paste(lion, (0, CANVAS_HEIGHT - lion_size), lion)
    image.paste(
        lion.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
        (CANVAS_WIDTH - lion_size, CANVAS_HEIGHT - lion_size),
        lion.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
    )

    brand_font = fit_font(draw, template["brand"], CANVAS_WIDTH - 160, 67, 48, bold=False, family="evolventa")
    title_font = fit_font(draw, template["title"], CANVAS_WIDTH - 220, 43, 34, bold=True, family="evolventa")
    date_font = load_font(39, bold=True, family="evolventa")
    phone_font = fit_font(draw, phone or template["phone"], CANVAS_WIDTH - 260, 58, 42, bold=True, family="evolventa")

    draw_centered(draw, 150, template["brand"], brand_font, text)
    draw_centered(draw, 275, template["title"], title_font, text)
    draw_centered(draw, 330, date or datetime.now().strftime("%d.%m.%Y"), date_font, text)
    draw_price_table(draw, price_ranges, text)
    draw_centered(draw, CANVAS_HEIGHT - 150, phone or template["phone"], phone_font, text)
    return save_png(image)
