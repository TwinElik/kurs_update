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

ORG_TEMPLATES = {
    "diamant": {
        "style": "diamant",
        "title": "ЦЕНА ЗА 1 ГРАММ ЗОЛОТА",
        "logo": LOGO_PATH,
        "red": "#d52b24",
        "phone": "+998 55 055 00 02",
    },
    "org2": {
        "style": "diamant",
        "title": "ЦЕНА ЗА 1 ГРАММ ЗОЛОТА",
        "logo": LOGO_PATH,
        "red": "#d52b24",
        "phone": "+998 55 055 00 02",
    },
    "org3": {
        "style": "diamant",
        "title": "ЦЕНА ЗА 1 ГРАММ ЗОЛОТА",
        "logo": LOGO_PATH,
        "red": "#d52b24",
        "phone": "+998 55 055 00 02",
    },
    "org4": {
        "style": "diamant",
        "title": "ЦЕНА ЗА 1 ГРАММ ЗОЛОТА",
        "logo": LOGO_PATH,
        "red": "#d52b24",
        "phone": "+998 55 055 00 02",
    },
    "tillachi": {
        "style": "black_gold",
        "brand": "Tillachi bolla",
        "title": "ЦЕНА ЗА 1 ГРАММ ЗОЛОТА",
        "yellow": "#ffcc00",
        "phone": "+998 50 590 14 50",
    },
    "goldexpert": {
        "style": "goldexpert",
        "brand": "GOLDEXPERT.UZ",
        "title": "\u0426\u0415\u041d\u0410 \u0417\u0410 1 \u0413\u0420\u0410\u041c\u041c \u0417\u041e\u041B\u041E\u0422\u0410",
        "orange": "#ffa30a",
        "background": "#000014",
        "logo": GOLDEXPERT_LOGO_PATH,
        "phone": "+998 55 055 20 00",
    },
    "skupka": {
        "style": "skupka",
        "brand": "SKUPKA-ZOLOTA.UZ",
        "title": "\u0426\u0415\u041d\u0410 \u0417\u0410 1 \u0413\u0420\u0410\u041c\u041c \u0417\u041e\u041B\u041E\u0422\u0410",
        "gold": "#f7ca39",
        "background": "#000000",
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


def build_price_image(price_ranges, org="diamant", phone=None, date=None):
    template = ORG_TEMPLATES.get(org, ORG_TEMPLATES["diamant"])
    if template.get("style") == "black_gold":
        return build_black_gold_image(price_ranges, template, phone=phone, date=date)
    if template.get("style") == "goldexpert":
        return build_goldexpert_image(price_ranges, template, phone=phone, date=date)
    if template.get("style") == "skupka":
        return build_skupka_image(price_ranges, template, phone=phone, date=date)

    width = 904
    height = 1280
    red = template["red"]
    dark = "#050505"
    white = "#ffffff"

    image = Image.new("RGB", (width, height), white)
    draw = ImageDraw.Draw(image)

    frame_x = 70
    top_line = 70
    bottom_line = height - 72
    draw.line((frame_x, 0, frame_x, height), fill=red, width=5)
    draw.line((width - frame_x, 0, width - frame_x, height), fill=red, width=5)
    draw.line((0, top_line, width, top_line), fill=red, width=5)
    draw.line((0, bottom_line, width, bottom_line), fill=red, width=5)

    logo_path = template["logo"]
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo_w = 640
        logo_h = int(logo.height * (logo_w / logo.width))
        logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
        image.paste(logo, ((width - logo_w) // 2, 108), logo)

    date_font = load_font(34, bold=True)
    title_font = load_font(36, bold=True)
    sample_font = load_font(36, bold=True)
    phone_font = load_font(46, bold=True)

    date_text = date or datetime.now().strftime("%d.%m.%Y")
    date_w = draw.textlength(date_text, font=date_font)
    draw.text(((width - date_w) / 2, 260), date_text, font=date_font, fill=dark)

    title = template["title"]
    title_w = draw.textlength(title, font=title_font)
    draw.text(((width - title_w) / 2, 312), title, font=title_font, fill=dark)

    left_x = 94
    right_x = 424
    y = 415
    row_h = 72
    for probe, (min_price, max_price) in price_ranges.items():
        sample_text = f"{probe} ПРОБА"
        price_text = f"{format_price(min_price)}-{format_price(max_price)} СУМ"
        price_font = fit_font(draw, price_text, width - right_x - 85, start_size=32, min_size=24, bold=True)
        draw.text((left_x, y), sample_text, font=sample_font, fill=dark)
        draw.text((right_x, y + 3), price_text, font=price_font, fill=dark)
        y += row_h

    phone_text = phone or template["phone"]
    phone_w = draw.textlength(phone_text, font=phone_font)
    draw.text(((width - phone_w) / 2, height - 150), phone_text, font=phone_font, fill=dark)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output.getvalue()


def transparent_corner_image(size):
    corner = Image.open(TILLACHI_CORNER_PATH).convert("RGBA")
    corner = corner.resize((size, size), Image.Resampling.LANCZOS)
    pixels = corner.load()
    for y in range(corner.height):
        for x in range(corner.width):
            r, g, b, a = pixels[x, y]
            if r < 18 and g < 18 and b < 18:
                pixels[x, y] = (0, 0, 0, 0)
            else:
                pixels[x, y] = (r, g, b, a)
    return corner


def paste_corner(base, corner, position, rotation=0):
    image = corner.rotate(rotation, expand=False)
    base.paste(image, position, image)


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


def draw_centered(draw, y, text, font, fill, width):
    text_w = draw.textlength(text, font=font)
    draw.text(((width - text_w) / 2, y), text, font=font, fill=fill)


def build_goldexpert_image(price_ranges, template, phone=None, date=None):
    width = 904
    height = 1280
    orange = template["orange"]
    background = template["background"]

    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    radius = 88
    for cx, cy in ((0, 0), (width, 0), (0, height), (width, height)):
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=orange)

    line_w = 4
    draw.line((90, 70, width - 90, 70), fill=orange, width=line_w)
    draw.line((90, height - 70, width - 90, height - 70), fill=orange, width=line_w)
    draw.line((70, 92, 70, height - 92), fill=orange, width=line_w)
    draw.line((width - 70, 92, width - 70, height - 92), fill=orange, width=line_w)

    logo_size = 150
    logo = recolored_logo(template["logo"], logo_size, orange)
    logo_x = 100
    logo_y = 108
    image.paste(logo, (logo_x, logo_y), logo)

    brand_font = fit_font(
        draw,
        template["brand"],
        width - 290,
        start_size=63,
        min_size=48,
        bold=True,
        family="evolventa",
    )
    brand_bbox = draw.textbbox((0, 0), template["brand"], font=brand_font)
    brand_h = brand_bbox[3] - brand_bbox[1]
    brand_y = logo_y + (logo.height - brand_h) / 2 - brand_bbox[1]
    draw.text((270, brand_y), template["brand"], font=brand_font, fill=orange)

    date_font = load_font(42, bold=True, family="evolventa")
    title_font = fit_font(
        draw,
        template["title"],
        width - 170,
        start_size=43,
        min_size=34,
        bold=True,
        family="evolventa",
    )
    sample_font = load_font(42, bold=True, family="evolventa")
    phone_text = phone or template["phone"]
    phone_font = fit_font(
        draw,
        phone_text,
        width - 220,
        start_size=57,
        min_size=42,
        bold=True,
        family="evolventa",
    )

    date_text = date or datetime.now().strftime("%d.%m.%Y")
    draw_centered(draw, 282, date_text, date_font, orange, width)
    draw_centered(draw, 340, template["title"], title_font, orange, width)

    left_x = 86
    right_edge = width - 86
    y = 430
    row_h = 76
    price_texts = {
        probe: f"{format_price(min_price)}-{format_price(max_price)}  \u0421\u0423\u041c"
        for probe, (min_price, max_price) in price_ranges.items()
    }
    longest_price = max(price_texts.values(), key=len) if price_texts else ""
    price_font = fit_font(
        draw,
        longest_price,
        right_edge - 360,
        start_size=42,
        min_size=30,
        bold=True,
        family="evolventa",
    )
    for probe in price_ranges:
        sample_text = f"{probe} \u041f\u0420\u041e\u0411\u0410"
        price_text = price_texts[probe]
        price_w = draw.textlength(price_text, font=price_font)
        draw.text((left_x, y), sample_text, font=sample_font, fill=orange)
        draw.text((right_edge - price_w, y), price_text, font=price_font, fill=orange)
        y += row_h

    draw_centered(draw, height - 150, phone_text, phone_font, orange, width)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output.getvalue()


def lion_logo(path, size):
    logo = Image.open(path).convert("RGBA")
    logo = logo.resize((size, size), Image.Resampling.LANCZOS)
    pixels = logo.load()
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b, a = pixels[x, y]
            if a == 0 or (r < 20 and g < 20 and b < 20):
                pixels[x, y] = (0, 0, 0, 0)
            else:
                pixels[x, y] = (r, g, b, a)
    return logo


def paste_lion_corner(base, logo, position, mirror=False):
    image = logo.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if mirror else logo
    base.paste(image, position, image)


def build_skupka_image(price_ranges, template, phone=None, date=None):
    width = 904
    height = 1280
    gold = template["gold"]
    white = "#ffffff"
    black = template["background"]

    image = Image.new("RGB", (width, height), black)
    draw = ImageDraw.Draw(image)

    line_w = 5
    left_x = 70
    right_x = width - 70
    top_line_y = 60
    inner_top_y = 122
    bottom_line_y = height - 60
    inner_bottom_y = height - 122
    draw.line((138, top_line_y, width - 138, top_line_y), fill=gold, width=line_w)
    draw.line((138, bottom_line_y, width - 138, bottom_line_y), fill=gold, width=line_w)
    draw.line((left_x, inner_top_y, left_x, inner_bottom_y), fill=gold, width=line_w)
    draw.line((right_x, inner_top_y, right_x, inner_bottom_y), fill=gold, width=line_w)

    lion_size = 140
    lion = lion_logo(template["logo"], lion_size)
    paste_lion_corner(image, lion, (0, 0), mirror=False)
    paste_lion_corner(image, lion, (width - lion_size, 0), mirror=True)
    paste_lion_corner(image, lion, (0, height - lion_size), mirror=False)
    paste_lion_corner(image, lion, (width - lion_size, height - lion_size), mirror=True)

    brand_font = fit_font(
        draw,
        template["brand"],
        width - 160,
        start_size=67,
        min_size=48,
        bold=False,
        family="evolventa",
    )
    title_font = fit_font(
        draw,
        template["title"],
        width - 220,
        start_size=43,
        min_size=34,
        bold=True,
        family="evolventa",
    )
    date_font = load_font(39, bold=True, family="evolventa")
    sample_font = load_font(43, bold=True, family="evolventa")
    phone_text = phone or template["phone"]
    phone_font = fit_font(
        draw,
        phone_text,
        width - 260,
        start_size=58,
        min_size=42,
        bold=True,
        family="evolventa",
    )

    draw_centered(draw, 150, template["brand"], brand_font, white, width)
    draw_centered(draw, 275, template["title"], title_font, white, width)
    date_text = date or datetime.now().strftime("%d.%m.%Y")
    draw_centered(draw, 330, date_text, date_font, white, width)

    sample_x = 92
    right_edge = width - 85
    y = 410
    row_h = 74
    price_texts = {
        probe: f"{format_price(min_price)}-{format_price(max_price)}\u0421\u0423\u041c"
        for probe, (min_price, max_price) in price_ranges.items()
    }
    longest_price = max(price_texts.values(), key=len) if price_texts else ""
    price_font = fit_font(
        draw,
        longest_price,
        right_edge - 380,
        start_size=43,
        min_size=29,
        bold=True,
        family="evolventa",
    )
    for probe in price_ranges:
        sample_text = f"{probe} \u041f\u0420\u041e\u0411\u0410"
        price_text = price_texts[probe]
        price_w = draw.textlength(price_text, font=price_font)
        draw.text((sample_x, y), sample_text, font=sample_font, fill=white)
        draw.text((right_edge - price_w, y), price_text, font=price_font, fill=white)
        y += row_h

    draw_centered(draw, height - 150, phone_text, phone_font, white, width)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output.getvalue()


def build_black_gold_image(price_ranges, template, phone=None, date=None):
    width = 904
    height = 1280
    yellow = template["yellow"]
    black = "#000000"

    image = Image.new("RGB", (width, height), black)
    draw = ImageDraw.Draw(image)

    corner_size = 105
    corner = transparent_corner_image(corner_size)
    paste_corner(image, corner, (0, 0), 0)
    paste_corner(image, corner, (width - corner_size, 0), 90)
    paste_corner(image, corner, (0, height - corner_size), 270)
    paste_corner(image, corner, (width - corner_size, height - corner_size), 180)

    brand_font = load_font(64, bold=True, family="evolventa")
    date_font = load_font(45, bold=True, family="evolventa")
    title_font = load_font(45, bold=True, family="evolventa")
    sample_font = load_font(45, bold=True, family="evolventa")
    phone_font = load_font(57, bold=True, family="evolventa")

    brand = template["brand"]
    brand_w = draw.textlength(brand, font=brand_font)
    draw.text(((width - brand_w) / 2, 165), brand, font=brand_font, fill=yellow)

    date_text = date or datetime.now().strftime("%d.%m.%Y")
    date_w = draw.textlength(date_text, font=date_font)
    draw.text(((width - date_w) / 2, 282), date_text, font=date_font, fill=yellow)

    title = template["title"]
    title_w = draw.textlength(title, font=title_font)
    draw.text(((width - title_w) / 2, 340), title, font=title_font, fill=yellow)

    left_x = 86
    right_edge = width - 86
    y = 430
    row_h = 76
    price_texts = {
        probe: f"{format_price(min_price)}-{format_price(max_price)}  СУМ"
        for probe, (min_price, max_price) in price_ranges.items()
    }
    longest_price = max(price_texts.values(), key=len) if price_texts else ""
    price_font = fit_font(
        draw,
        longest_price,
        right_edge - 360,
        start_size=45,
        min_size=27,
        bold=True,
        family="evolventa",
    )
    for probe, (min_price, max_price) in price_ranges.items():
        sample_text = f"{probe} ПРОБА"
        price_text = price_texts[probe]
        price_w = draw.textlength(price_text, font=price_font)
        draw.text((left_x, y), sample_text, font=sample_font, fill=yellow)
        draw.text((right_edge - price_w, y), price_text, font=price_font, fill=yellow)
        y += row_h

    phone_text = phone or template["phone"]
    phone_w = draw.textlength(phone_text, font=phone_font)
    draw.text(((width - phone_w) / 2, height - 150), phone_text, font=phone_font, fill=yellow)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output.getvalue()
