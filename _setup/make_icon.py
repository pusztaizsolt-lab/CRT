"""
CRT ikon generátor — crt.ico létrehozása Pillow-val
Futtatás: py -3.11 _setup/make_icon.py
"""
from pathlib import Path
import struct, zlib

OUT = Path(__file__).parent.parent / "crt.ico"


def _make_icon_pillow():
    from PIL import Image, ImageDraw, ImageFont
    import io

    sizes = [16, 32, 48, 256]
    images = []

    for sz in sizes:
        img  = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Lekerekített téglalap háttér — sötét lila
        pad = max(1, sz // 12)
        draw.rounded_rectangle(
            [pad, pad, sz - pad - 1, sz - pad - 1],
            radius=max(2, sz // 6),
            fill=(28, 20, 60, 255),
        )

        # Villám jel (⚡) — fehér
        bolt_color = (200, 185, 252, 255)   # világos lila-fehér
        accent     = (124, 106, 247, 255)   # CRT accent lila

        if sz >= 32:
            # Villám polygon — egyszerű háromszög + lépés
            cx = sz // 2
            pts = [
                (cx,          sz * 18 // 100),   # csúcs
                (cx - sz//6,  sz * 55 // 100),   # bal közép
                (cx,          sz * 50 // 100),   # középső bev.
                (cx - sz//8,  sz * 82 // 100),   # bal alap
                (cx,          sz * 42 // 100),   # jobb közép
                (cx + sz//6,  sz * 42 // 100),   # jobb szár
            ]
            draw.polygon(pts, fill=bolt_color)

            # "CRT" felirat kis méretben (32+)
            if sz >= 48:
                fs = max(6, sz // 7)
                try:
                    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", fs)
                except Exception:
                    font = ImageFont.load_default()
                draw.text((sz // 2, sz - pad - fs - 2), "CRT",
                          fill=accent, font=font, anchor="mt")
        else:
            # 16px — csak villám, kis méretben
            pts16 = [
                (sz // 2,      sz * 2 // 10),
                (sz * 3 // 10, sz * 6 // 10),
                (sz // 2,      sz * 5 // 10),
                (sz * 3 // 10, sz * 9 // 10),
                (sz // 2,      sz * 4 // 10),
                (sz * 7 // 10, sz * 4 // 10),
            ]
            draw.polygon(pts16, fill=bolt_color)

        images.append(img)

    # Mentés ICO formátumba
    buf = io.BytesIO()
    images[0].save(
        buf, format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    return buf.getvalue()


def _make_icon_fallback() -> bytes:
    """
    Minimális 16×16 ICO Pillow nélkül — egyszínű lila négyzet.
    Ez csak akkor fut ha Pillow nincs telepítve.
    """
    # 16×16 RGBA bitmap — sötét lila háttér
    W, H = 16, 16
    px   = bytes([28, 20, 60, 255] * W * H)   # BGRA sorrend az ICO-ban

    # BMP fejléc (BITMAPINFOHEADER, 40 bájt)
    bih = struct.pack("<IiiHHIIiiII",
        40,         # biSize
        W, H * 2,   # biWidth, biHeight (× 2 az ICO konvenció)
        1,          # biPlanes
        32,         # biBitCount
        0,          # biCompression (BI_RGB)
        len(px),    # biSizeImage
        0, 0, 0, 0  # egyéb
    )
    # AND maszk (minden pixel látható)
    and_mask = bytes(((W + 7) // 8) * H)
    bmp_data = bih + px + and_mask

    # ICO fejléc
    ico_hdr = struct.pack("<HHH",
        0,    # rezervált
        1,    # típus: ikon
        1,    # képek száma
    )
    # ICONDIRENTRY
    offset = 6 + 16
    entry = struct.pack("<BBBBHHII",
        W, H,       # szélesség, magasság
        0,          # szín szám (0=256+)
        0,          # rezervált
        1, 32,      # síkok, bpp
        len(bmp_data), offset,
    )
    return ico_hdr + entry + bmp_data


def main():
    print("CRT ikon generálás…")
    try:
        data = _make_icon_pillow()
        motor = "Pillow"
    except ImportError:
        print("  Pillow nincs — egyszerű fallback ikon (pip install pillow a szebb verzióhoz)")
        data = _make_icon_fallback()
        motor = "fallback"

    OUT.write_bytes(data)
    print(f"  [{motor}] Mentve: {OUT}  ({len(data)} bájt)")


if __name__ == "__main__":
    main()
