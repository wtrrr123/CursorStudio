"""Image processing, portable cursor packs and the Windows CUR format."""
import base64
import io
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

# Stable pack keys, display labels, and Win32 OCR identifiers.
ROLES = {
    "arrow": ("普通箭头", 32512),
    "text": ("文字输入", 32513),
    "busy": ("忙碌", 32514),
    "cross": ("十字准星", 32515),
    "hand": ("链接手形", 32649),
    "working": ("后台工作", 32650),
    "resize_h": ("横向缩放", 32644),
    "resize_v": ("纵向缩放", 32645),
    "blocked": ("禁止操作", 32648),
}
SIZES = (32, 48, 64, 96, 128, 192, 256)
MAX_IMAGE_BYTES = 40 * 1024 * 1024
MAX_PACK_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 50_000_000
MAX_SOURCE_SIDE = 2048


@dataclass
class Slot:
    image: Image.Image
    size: int = 32
    hotspot: tuple[int, int] = (0, 0)
    crop: bool = False
    anchor: tuple[float, float] | None = None

    def at_size(self, size):
        anchor = self.anchor or tuple((point + 0.5) / self.size for point in self.hotspot)
        hotspot = tuple(min(size - 1, int(point * size)) for point in anchor)
        return Slot(self.image, size, hotspot, self.crop, self.anchor)

    def render(self):
        bounds = (self.size, self.size)
        if self.crop:
            return ImageOps.fit(self.image, bounds, Image.Resampling.LANCZOS)
        width, height = self.image.size
        factor = self.size / max(width, height)
        scaled = self.image.resize((max(1, round(width * factor)),
                                    max(1, round(height * factor))), Image.Resampling.LANCZOS)
        result = Image.new("RGBA", bounds)
        result.paste(scaled, ((self.size - scaled.width) // 2,
                              (self.size - scaled.height) // 2))
        return result


def read_image(path):
    with open(path, "rb") as stream:
        data = stream.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("图片大小上限为 40 MB。")
    with Image.open(io.BytesIO(data), formats=("PNG", "JPEG", "WEBP", "GIF")) as image:
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ValueError("图片总像素上限为 5000 万。")
        result = ImageOps.exif_transpose(image).convert("RGBA")
        result.thumbnail((MAX_SOURCE_SIDE, MAX_SOURCE_SIDE), Image.Resampling.LANCZOS)
        return result


def save_pack(path, slots):
    entries = {}
    for key, slot in slots.items():
        data = io.BytesIO()
        slot.image.save(data, format="PNG")
        entries[key] = {
            "png": base64.b64encode(data.getvalue()).decode("ascii"),
            "size": slot.size,
            "hotspot": list(slot.hotspot),
            "crop": slot.crop,
            "anchor": slot.anchor,
        }
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps({"version": 1, "slots": entries}, indent=2), encoding="utf-8")
    temp.replace(path)


def load_pack(path):
    with open(path, "rb") as stream:
        data = stream.read(MAX_PACK_BYTES + 1)
    if len(data) > MAX_PACK_BYTES:
        raise ValueError("套装大小上限为 64 MB。")
    pack = json.loads(data)
    if not isinstance(pack, dict) or pack.get("version") != 1:
        raise ValueError("无法读取这个版本的光标套装。")
    entries = pack.get("slots")
    if not isinstance(entries, dict) or entries.keys() - ROLES.keys():
        raise ValueError("套装包含无效的光标状态。")
    slots = {}
    for key, entry in entries.items():
        size = entry["size"]
        hotspot = entry["hotspot"]
        crop = entry["crop"]
        anchor = entry.get("anchor")
        if anchor is not None and (not isinstance(anchor, list) or len(anchor) != 2
                or any(type(point) not in (float, int) or not 0 <= point < 1 for point in anchor)):
            raise ValueError("套装点击点无效。")
        if (type(size) is not int or size not in SIZES
                or not isinstance(hotspot, list) or len(hotspot) != 2
                or any(type(point) is not int or not 0 <= point < size for point in hotspot)
                or type(crop) is not bool):
            raise ValueError(f"{ROLES[key][0]}的尺寸或点击点无效。")
        raw = base64.b64decode(entry["png"], validate=True)
        with Image.open(io.BytesIO(raw), formats=("PNG",)) as image:
            if max(image.size) > MAX_SOURCE_SIDE:
                raise ValueError("套装图片尺寸过大。")
            slots[key] = Slot(image.convert("RGBA"), size, tuple(hotspot), crop,
                              tuple(anchor) if anchor is not None else None)
    return slots


def cursor_bytes(slot):
    image = slot.render()
    width, height = image.size
    x, y = slot.hotspot
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError("点击点必须位于光标内。")
    # CUR stores a bottom-up 32-bit DIB and a DWORD-aligned 1-bit AND mask.
    flipped = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    color = bytearray(flipped.tobytes("raw", "BGRA"))
    alpha = flipped.getchannel("A").tobytes()
    mask_stride = ((width + 31) // 32) * 4
    mask = bytearray(mask_stride * height)
    for row in range(height):
        for col in range(width):
            pixel = row * width + col
            if alpha[pixel] == 0:
                # A zero XOR pixel leaves the desktop intact in mask-based drawing.
                color[pixel * 4:pixel * 4 + 3] = b"\0\0\0"
                mask[row * mask_stride + col // 8] |= 0x80 >> (col % 8)
    dib = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32,
                      0, len(color), 0, 0, 0, 0) + color + mask
    return (struct.pack("<HHH", 0, 2, 1)
            + struct.pack("<BBBBHHII", width % 256, height % 256, 0, 0, x, y, len(dib), 22)
            + dib)


def demo_pack():
    """Build a coordinated purple set with nine recognizably different shapes."""
    ink = "#302053"
    fill = "#CBB5FF"
    slots = {}
    for key in ROLES:
        image = Image.new("RGBA", (32, 32))
        draw = ImageDraw.Draw(image)
        hotspot = (16, 16)
        if key == "arrow":
            draw.polygon([(3, 2), (25, 19), (16, 20), (21, 28), (16, 30),
                          (11, 22), (4, 28)], fill=fill, outline=ink, width=2)
            hotspot = (3, 2)
        elif key == "hand":
            draw.rounded_rectangle((9, 11, 26, 29), 4, fill=fill, outline=ink, width=2)
            draw.rounded_rectangle((9, 2, 16, 20), 3, fill=fill, outline=ink, width=2)
            hotspot = (12, 2)
        elif key == "text":
            for points in [((16, 5), (16, 27)), ((10, 5), (22, 5)), ((10, 27), (22, 27))]:
                draw.line(points, fill=ink, width=5)
                draw.line(points, fill=fill, width=2)
        elif key in ("cross", "resize_h", "resize_v"):
            if key == "cross":
                draw.line((16, 4, 16, 28), fill=ink, width=5)
                draw.line((4, 16, 28, 16), fill=ink, width=5)
                draw.line((16, 4, 16, 28), fill=fill, width=2)
                draw.line((4, 16, 28, 16), fill=fill, width=2)
            else:
                draw.polygon([(2, 16), (10, 8), (10, 13), (22, 13), (22, 8),
                              (30, 16), (22, 24), (22, 19), (10, 19), (10, 24)],
                             fill=fill, outline=ink, width=2)
                if key == "resize_v":
                    image = image.transpose(Image.Transpose.ROTATE_90)
                    hotspot = (16, 15)
        elif key in ("busy", "blocked"):
            draw.ellipse((5, 5, 27, 27), fill=fill, outline=ink, width=3)
            if key == "busy":
                draw.line((16, 9, 16, 16, 21, 19), fill=ink, width=3)
            else:
                draw.line((9, 23, 23, 9), fill=ink, width=3)
        else:
            draw.polygon([(2, 2), (18, 13), (10, 14), (4, 22)],
                         fill=fill, outline=ink, width=2)
            draw.ellipse((15, 15, 29, 29), fill=fill, outline=ink, width=2)
            draw.line((22, 18, 22, 22, 25, 24), fill=ink, width=2)
            hotspot = (2, 2)
        slots[key] = Slot(image, hotspot=hotspot)
    return slots
