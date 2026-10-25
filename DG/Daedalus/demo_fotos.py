"""Gera fotos de demonstração (ilustrações desenhadas com Pillow) para as triagens do banco demo."""
import random
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

LARGURA, ALTURA = 1280, 960


def _fonte(tamanho):
    for caminho in ('DejaVuSans.ttf', 'arial.ttf', 'Arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:
        return ImageFont.load_default()


def _fundo(rng):
    """Bancada de testes: degradê cinza com fios de luz."""
    img = Image.new('RGB', (LARGURA, ALTURA))
    d = ImageDraw.Draw(img)
    for y in range(ALTURA):
        c = int(52 - 22 * y / ALTURA)
        d.line([(0, y), (LARGURA, y)], fill=(c, c + 2, c + 6))
    for _ in range(40):
        y = rng.randint(0, ALTURA)
        d.line([(0, y), (LARGURA, y + rng.randint(-8, 8))], fill=(68, 72, 80), width=1)
    return img, d


def _placa(d, rng, x0, y0, x1, y1, cor=(24, 110, 62), chips=6):
    d.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=cor, outline=(10, 60, 34), width=4)
    traco = tuple(min(255, c + 45) for c in cor)
    for _ in range(46):
        x, y = rng.randint(x0 + 20, x1 - 20), rng.randint(y0 + 20, y1 - 20)
        d.line([(x, y), (x + rng.randint(-120, 120), y)], fill=traco, width=3)
        d.line([(x, y), (x, y + rng.randint(-90, 90))], fill=traco, width=3)
    for _ in range(chips):
        w, h = rng.randint(70, 150), rng.randint(60, 120)
        cx, cy = rng.randint(x0 + 30, x1 - w - 30), rng.randint(y0 + 30, y1 - h - 30)
        d.rectangle((cx, cy, cx + w, cy + h), fill=(20, 20, 24), outline=(90, 90, 96), width=2)
        for k in range(0, w, 14):
            d.line([(cx + k, cy - 6), (cx + k, cy)], fill=(200, 200, 200), width=3)
            d.line([(cx + k, cy + h), (cx + k, cy + h + 6)], fill=(200, 200, 200), width=3)
    for _ in range(14):
        x, y = rng.randint(x0 + 25, x1 - 25), rng.randint(y0 + 25, y1 - 25)
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(200, 170, 60), outline=(90, 70, 20))
    for x, y in ((x0 + 22, y0 + 22), (x1 - 22, y0 + 22), (x0 + 22, y1 - 22), (x1 - 22, y1 - 22)):
        d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=(180, 180, 185), outline=(60, 60, 64), width=3)


def _desenhar(tipo, d, rng):
    cx, cy = LARGURA // 2, ALTURA // 2 - 40
    if tipo == 'bateria':
        d.rounded_rectangle((220, 250, 1060, 640), radius=26, fill=(36, 38, 44), outline=(110, 114, 124), width=5)
        for i in range(6):
            d.rounded_rectangle((250 + i * 135, 285, 360 + i * 135, 605), radius=16, fill=(58, 62, 72), outline=(88, 92, 104), width=3)
        d.rectangle((1060, 360, 1110, 530), fill=(190, 160, 70), outline=(110, 90, 30), width=3)
        d.rectangle((300, 300, 700, 360), fill=(230, 230, 235))
        d.text((320, 308), 'HP  LI-ION  11.4V', font=_fonte(34), fill=(30, 30, 36))
    elif tipo == 'tela':
        d.rounded_rectangle((170, 170, 1110, 700), radius=24, fill=(14, 14, 18), outline=(120, 124, 134), width=8)
        d.rectangle((215, 215, 1065, 655), fill=(28, 52, 92))
        for i in range(8):
            x = 260 + i * 100
            d.line([(x, 215), (x, 655)], fill=(60, 110, 190), width=3)
        if rng.random() < 0.5:
            x, y = rng.randint(400, 800), rng.randint(300, 500)
            for _ in range(7):
                nx, ny = x + rng.randint(-190, 190), y + rng.randint(-150, 150)
                d.line([(x, y), (nx, ny)], fill=(235, 235, 240), width=3)
    elif tipo in ('placa', 'ssd', 'memoria', 'wifi'):
        if tipo == 'placa':
            _placa(d, rng, 150, 170, 1130, 720, chips=9)
        elif tipo == 'ssd':
            _placa(d, rng, 260, 330, 1020, 560, cor=(34, 38, 50), chips=3)
            d.rectangle((1020, 380, 1062, 510), fill=(200, 170, 60))
        elif tipo == 'memoria':
            _placa(d, rng, 140, 360, 1140, 560, cor=(22, 96, 54), chips=8)
            for x in range(170, 1110, 22):
                d.rectangle((x, 560, x + 12, 590), fill=(200, 170, 60))
        else:
            _placa(d, rng, 400, 330, 880, 570, cor=(30, 120, 140), chips=2)
            d.line([(400, 400), (200, 250)], fill=(230, 230, 230), width=6)
            d.line([(880, 400), (1080, 250)], fill=(30, 30, 30), width=6)
    elif tipo == 'teclado':
        d.rounded_rectangle((100, 230, 1180, 720), radius=24, fill=(26, 28, 32), outline=(90, 94, 104), width=5)
        for r in range(5):
            for c in range(14 if r < 4 else 7):
                if rng.random() < 0.04:
                    continue
                x = 130 + c * 74 + (0 if r < 4 else 0)
                w = 64 if r < 4 else (64 if c != 3 else 380)
                if r == 4 and c > 3:
                    x = 130 + (c + 5) * 74
                d.rounded_rectangle((x, 255 + r * 88, x + w, 255 + r * 88 + 70), radius=8, fill=(54, 58, 66), outline=(98, 102, 112), width=2)
    elif tipo == 'fonte':
        d.rounded_rectangle((330, 290, 880, 600), radius=34, fill=(20, 20, 24), outline=(90, 90, 98), width=5)
        d.text((380, 420), '65 W   19.5 V', font=_fonte(52), fill=(190, 190, 198))
        d.line([(880, 445), (1130, 445), (1130, 640)], fill=(30, 30, 34), width=14)
        d.rectangle((1100, 640, 1160, 720), fill=(70, 70, 76))
    elif tipo == 'cooler':
        d.rounded_rectangle((260, 150, 1020, 760), radius=30, fill=(40, 42, 48), outline=(100, 104, 114), width=6)
        d.ellipse((330, 220, 950, 690), fill=(24, 26, 30), outline=(120, 124, 134), width=6)
        for a in range(7):
            ang = a * 51.4
            from math import cos, sin, radians
            x, y = 640 + 200 * cos(radians(ang)), 455 + 200 * sin(radians(ang))
            d.polygon([(640, 455), (x - 40, y - 60), (x + 60, y + 30)], fill=(70, 74, 84))
        d.ellipse((600, 415, 680, 495), fill=(110, 114, 124))
    elif tipo == 'dobradica':
        d.polygon([(260, 280), (900, 250), (960, 520), (300, 600)], fill=(150, 154, 162), outline=(70, 72, 78))
        for x, y in ((340, 360), (460, 345), (780, 320), (880, 330)):
            d.ellipse((x - 24, y - 24, x + 24, y + 24), fill=(90, 92, 98), outline=(40, 40, 44), width=4)
        d.line([(560, 300), (610, 520)], fill=(30, 30, 34), width=6)
    elif tipo in ('fusor', 'rolo'):
        d.rounded_rectangle((150, 300, 1130, 600), radius=40, fill=(70, 74, 82), outline=(120, 124, 132), width=6)
        d.rounded_rectangle((190, 340, 1090, 560), radius=60, fill=(28, 28, 32))
        for x in range(230, 1060, 60):
            d.line([(x, 345), (x, 555)], fill=(50, 50, 56), width=3)
    else:  # formatadora e demais
        _placa(d, rng, 200, 220, 1080, 680, cor=(24, 90, 70), chips=6)


def _etiqueta(img, d, rng, ticket, legenda):
    if 'Etiqueta' in legenda:
        d.rectangle((760, 120, 1180, 260), fill=(245, 245, 245), outline=(20, 20, 20), width=3)
        for k in range(46):
            x = 780 + k * 8
            d.line([(x, 140), (x, 195)], fill=(15, 15, 15), width=rng.choice([2, 3, 5]))
        d.text((780, 205), 'S/N  DEMO' + str(ticket), font=_fonte(26), fill=(20, 20, 20))
    faixa = Image.new('RGBA', (LARGURA, 74), (0, 0, 0, 160))
    img.paste(faixa, (0, ALTURA - 74), faixa)
    d.text((28, ALTURA - 62), f'DEMONSTRATIVO  |  Ticket {ticket}  |  {legenda}', font=_fonte(30), fill=(235, 235, 240))


def gerar_foto(tipo, legenda, ticket, semente):
    """Devolve os bytes de um JPEG (1280x960) com uma ilustração da peça."""
    rng = random.Random(semente)
    img, d = _fundo(rng)
    _desenhar(tipo, d, rng)
    d = ImageDraw.Draw(img)
    _etiqueta(img, d, rng, ticket, legenda)
    saida = BytesIO()
    img.save(saida, format='JPEG', quality=82, optimize=True)
    return saida.getvalue()
