import random
from io import BytesIO
from math import cos, radians, sin

from PIL import Image, ImageDraw, ImageFont

LARGURA, ALTURA = 1280, 960
ALTURA_DA_FAIXA = 74
QUALIDADE_JPEG = 82
FONTES_CANDIDATAS = ('DejaVuSans.ttf', 'arial.ttf', 'Arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
COR_DOURADA = (200, 170, 60)


def _fonte(tamanho):
    for caminho in FONTES_CANDIDATAS:
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:
        return ImageFont.load_default()


def _fundo(rng):
    imagem = Image.new('RGB', (LARGURA, ALTURA))
    pincel = ImageDraw.Draw(imagem)
    for y in range(ALTURA):
        tom = int(52 - 22 * y / ALTURA)
        pincel.line([(0, y), (LARGURA, y)], fill=(tom, tom + 2, tom + 6))
    for _ in range(40):
        y = rng.randint(0, ALTURA)
        pincel.line([(0, y), (LARGURA, y + rng.randint(-8, 8))], fill=(68, 72, 80), width=1)
    return imagem, pincel


def _placa(pincel, rng, x0, y0, x1, y1, cor=(24, 110, 62), chips=6):
    pincel.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=cor, outline=(10, 60, 34), width=4)
    traco = tuple(min(255, canal + 45) for canal in cor)
    for _ in range(46):
        x, y = rng.randint(x0 + 20, x1 - 20), rng.randint(y0 + 20, y1 - 20)
        pincel.line([(x, y), (x + rng.randint(-120, 120), y)], fill=traco, width=3)
        pincel.line([(x, y), (x, y + rng.randint(-90, 90))], fill=traco, width=3)
    for _ in range(chips):
        largura, altura = rng.randint(70, 150), rng.randint(60, 120)
        cx, cy = rng.randint(x0 + 30, x1 - largura - 30), rng.randint(y0 + 30, y1 - altura - 30)
        pincel.rectangle((cx, cy, cx + largura, cy + altura), fill=(20, 20, 24), outline=(90, 90, 96), width=2)
        for passo in range(0, largura, 14):
            pincel.line([(cx + passo, cy - 6), (cx + passo, cy)], fill=(200, 200, 200), width=3)
            pincel.line([(cx + passo, cy + altura), (cx + passo, cy + altura + 6)], fill=(200, 200, 200), width=3)
    for _ in range(14):
        x, y = rng.randint(x0 + 25, x1 - 25), rng.randint(y0 + 25, y1 - 25)
        pincel.ellipse((x - 9, y - 9, x + 9, y + 9), fill=COR_DOURADA, outline=(90, 70, 20))
    for x, y in ((x0 + 22, y0 + 22), (x1 - 22, y0 + 22), (x0 + 22, y1 - 22), (x1 - 22, y1 - 22)):
        pincel.ellipse((x - 10, y - 10, x + 10, y + 10), fill=(180, 180, 185), outline=(60, 60, 64), width=3)


def _bateria(pincel, rng):
    pincel.rounded_rectangle((220, 250, 1060, 640), radius=26, fill=(36, 38, 44), outline=(110, 114, 124), width=5)
    for i in range(6):
        pincel.rounded_rectangle(
            (250 + i * 135, 285, 360 + i * 135, 605), radius=16, fill=(58, 62, 72), outline=(88, 92, 104), width=3
        )
    pincel.rectangle((1060, 360, 1110, 530), fill=(190, 160, 70), outline=(110, 90, 30), width=3)
    pincel.rectangle((300, 300, 700, 360), fill=(230, 230, 235))
    pincel.text((320, 308), 'HP  LI-ION  11.4V', font=_fonte(34), fill=(30, 30, 36))


def _tela(pincel, rng):
    pincel.rounded_rectangle((170, 170, 1110, 700), radius=24, fill=(14, 14, 18), outline=(120, 124, 134), width=8)
    pincel.rectangle((215, 215, 1065, 655), fill=(28, 52, 92))
    for i in range(8):
        x = 260 + i * 100
        pincel.line([(x, 215), (x, 655)], fill=(60, 110, 190), width=3)
    if rng.random() < 0.5:
        x, y = rng.randint(400, 800), rng.randint(300, 500)
        for _ in range(7):
            destino = (x + rng.randint(-190, 190), y + rng.randint(-150, 150))
            pincel.line([(x, y), destino], fill=(235, 235, 240), width=3)


def _placa_principal(pincel, rng):
    _placa(pincel, rng, 150, 170, 1130, 720, chips=9)


def _ssd(pincel, rng):
    _placa(pincel, rng, 260, 330, 1020, 560, cor=(34, 38, 50), chips=3)
    pincel.rectangle((1020, 380, 1062, 510), fill=COR_DOURADA)


def _memoria(pincel, rng):
    _placa(pincel, rng, 140, 360, 1140, 560, cor=(22, 96, 54), chips=8)
    for x in range(170, 1110, 22):
        pincel.rectangle((x, 560, x + 12, 590), fill=COR_DOURADA)


def _wifi(pincel, rng):
    _placa(pincel, rng, 400, 330, 880, 570, cor=(30, 120, 140), chips=2)
    pincel.line([(400, 400), (200, 250)], fill=(230, 230, 230), width=6)
    pincel.line([(880, 400), (1080, 250)], fill=(30, 30, 30), width=6)


def _teclado(pincel, rng):
    pincel.rounded_rectangle((100, 230, 1180, 720), radius=24, fill=(26, 28, 32), outline=(90, 94, 104), width=5)
    for linha in range(5):
        for coluna in range(14 if linha < 4 else 7):
            if rng.random() < 0.04:
                continue
            x = 130 + coluna * 74
            largura = 64 if linha < 4 else (64 if coluna != 3 else 380)
            if linha == 4 and coluna > 3:
                x = 130 + (coluna + 5) * 74
            topo = 255 + linha * 88
            pincel.rounded_rectangle(
                (x, topo, x + largura, topo + 70), radius=8, fill=(54, 58, 66), outline=(98, 102, 112), width=2
            )


def _fonte_de_alimentacao(pincel, rng):
    pincel.rounded_rectangle((330, 290, 880, 600), radius=34, fill=(20, 20, 24), outline=(90, 90, 98), width=5)
    pincel.text((380, 420), '65 W   19.5 V', font=_fonte(52), fill=(190, 190, 198))
    pincel.line([(880, 445), (1130, 445), (1130, 640)], fill=(30, 30, 34), width=14)
    pincel.rectangle((1100, 640, 1160, 720), fill=(70, 70, 76))


def _cooler(pincel, rng):
    pincel.rounded_rectangle((260, 150, 1020, 760), radius=30, fill=(40, 42, 48), outline=(100, 104, 114), width=6)
    pincel.ellipse((330, 220, 950, 690), fill=(24, 26, 30), outline=(120, 124, 134), width=6)
    for pa in range(7):
        angulo = radians(pa * 51.4)
        x, y = 640 + 200 * cos(angulo), 455 + 200 * sin(angulo)
        pincel.polygon([(640, 455), (x - 40, y - 60), (x + 60, y + 30)], fill=(70, 74, 84))
    pincel.ellipse((600, 415, 680, 495), fill=(110, 114, 124))


def _dobradica(pincel, rng):
    pincel.polygon([(260, 280), (900, 250), (960, 520), (300, 600)], fill=(150, 154, 162), outline=(70, 72, 78))
    for x, y in ((340, 360), (460, 345), (780, 320), (880, 330)):
        pincel.ellipse((x - 24, y - 24, x + 24, y + 24), fill=(90, 92, 98), outline=(40, 40, 44), width=4)
    pincel.line([(560, 300), (610, 520)], fill=(30, 30, 34), width=6)


def _rolo(pincel, rng):
    pincel.rounded_rectangle((150, 300, 1130, 600), radius=40, fill=(70, 74, 82), outline=(120, 124, 132), width=6)
    pincel.rounded_rectangle((190, 340, 1090, 560), radius=60, fill=(28, 28, 32))
    for x in range(230, 1060, 60):
        pincel.line([(x, 345), (x, 555)], fill=(50, 50, 56), width=3)


def _placa_generica(pincel, rng):
    _placa(pincel, rng, 200, 220, 1080, 680, cor=(24, 90, 70), chips=6)


DESENHISTAS = {
    'bateria': _bateria,
    'tela': _tela,
    'placa': _placa_principal,
    'ssd': _ssd,
    'memoria': _memoria,
    'wifi': _wifi,
    'teclado': _teclado,
    'fonte': _fonte_de_alimentacao,
    'cooler': _cooler,
    'dobradica': _dobradica,
    'fusor': _rolo,
    'rolo': _rolo,
}


def _etiquetar(imagem, pincel, rng, ticket, legenda):
    if 'Etiqueta' in legenda:
        pincel.rectangle((760, 120, 1180, 260), fill=(245, 245, 245), outline=(20, 20, 20), width=3)
        for barra in range(46):
            x = 780 + barra * 8
            pincel.line([(x, 140), (x, 195)], fill=(15, 15, 15), width=rng.choice([2, 3, 5]))
        pincel.text((780, 205), 'S/N  DEMO' + str(ticket), font=_fonte(26), fill=(20, 20, 20))

    faixa = Image.new('RGBA', (LARGURA, ALTURA_DA_FAIXA), (0, 0, 0, 160))
    imagem.paste(faixa, (0, ALTURA - ALTURA_DA_FAIXA), faixa)
    pincel.text(
        (28, ALTURA - 62),
        f'DEMONSTRATIVO  |  Ticket {ticket}  |  {legenda}',
        font=_fonte(30),
        fill=(235, 235, 240),
    )


def gerar_foto(tipo, legenda, ticket, semente):
    rng = random.Random(semente)
    imagem, pincel = _fundo(rng)
    DESENHISTAS.get(tipo, _placa_generica)(pincel, rng)
    pincel = ImageDraw.Draw(imagem)
    _etiquetar(imagem, pincel, rng, ticket, legenda)

    saida = BytesIO()
    imagem.save(saida, format='JPEG', quality=QUALIDADE_JPEG, optimize=True)
    return saida.getvalue()
