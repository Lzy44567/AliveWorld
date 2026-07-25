"""Generate AliveWorld's multi-resolution Windows icon for packaging."""

from pathlib import Path

from PIL import Image, ImageDraw


PROJECT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT / "assets" / "aliveworld.ico"


def build_icon() -> Path:
    canvas_size = 1024
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (48, 48, 976, 976),
        radius=220,
        fill=(8, 18, 38, 255),
        outline=(45, 212, 191, 255),
        width=44,
    )
    draw.ellipse(
        (245, 245, 779, 779),
        fill=(12, 74, 110, 255),
        outline=(34, 211, 238, 255),
        width=46,
    )
    draw.ellipse((345, 265, 680, 750), outline=(52, 211, 153, 255), width=30)
    draw.ellipse((270, 360, 755, 650), outline=(94, 234, 212, 255), width=30)
    draw.arc((238, 315, 790, 705), 194, 350, fill=(125, 240, 214, 255), width=26)
    draw.ellipse((700, 208, 814, 322), fill=(250, 204, 21, 255))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        OUTPUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Created Windows icon: {OUTPUT}")
    return OUTPUT


if __name__ == "__main__":
    build_icon()
