"""
Estatística usada na aba de Qualidade do BI (funções puras, sem acesso ao banco).

Indicador central: NFF (No Fault Found), a peça que o técnico de campo trocou por defeituosa e que a bancada
constatou FUNCIONAL (Triagem.status == 1).

- Intervalo de confiança de Wilson (95%): evita punir quem tem poucas triagens.
- Carta de controle p / funnel plot: os limites de 2 e 3 sigma dependem do volume (n) de cada técnico.
- Comparação do diagnóstico do técnico de campo com o defeito constatado na bancada.
"""
import math
import re
import unicodedata

NFF = 1                         # status 1: peça funcional (No Fault Found)
REFERENCIA_NFF = (20.0, 50.0)   # faixa de NFF reportada na literatura de eletrônicos (%)
MIN_AMOSTRA = 5                 # abaixo disso o técnico não é classificado
Z95 = 1.96


def pct(k, n) -> float:
    return round(100.0 * k / n, 1) if n else 0.0


def intervalo_wilson(k: int, n: int, z: float = Z95):
    """Intervalo de confiança de Wilson para uma proporção. Devolve (inferior, superior) como fração de 0 a 1."""
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margem = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centro - margem), min(1.0, centro + margem)


def classificar(p: float, p_medio: float, n: int):
    """
    Carta de controle p. Devolve (status, z):
    critico (z >= 3), atencao (z >= 2), destaque (z <= -2), normal ou insuficiente (n < MIN_AMOSTRA).
    """
    if n < MIN_AMOSTRA:
        return 'insuficiente', None
    if p_medio <= 0 or p_medio >= 1:
        return 'normal', 0.0
    z = (p - p_medio) / math.sqrt(p_medio * (1 - p_medio) / n)
    if z >= 3:
        return 'critico', round(z, 2)
    if z >= 2:
        return 'atencao', round(z, 2)
    if z <= -2:
        return 'destaque', round(z, 2)
    return 'normal', round(z, 2)


def limites_controle(p_medio: float, n: int) -> dict:
    """Limites de 2 e 3 sigma (em %) para um grupo com n triagens."""
    sigma = math.sqrt(p_medio * (1 - p_medio) / n) if n > 0 else 0.0
    def lim(z, sinal):
        return round(100 * min(1.0, max(0.0, p_medio + sinal * z * sigma)), 1)
    return {'n': n, 'sup2': lim(2, 1), 'inf2': lim(2, -1), 'sup3': lim(3, 1), 'inf3': lim(3, -1)}


def normalizar_texto(valor) -> str:
    """Minúsculas, sem acentos nem pontuação: base da comparação diagnóstico x constatação."""
    if not valor:
        return ''
    sem_acento = ''.join(c for c in unicodedata.normalize('NFD', str(valor)) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', sem_acento.lower()).strip()


def limpar(valor, limite: int = 60) -> str:
    texto = ' '.join((valor or '').split())
    return texto if len(texto) <= limite else texto[:limite - 1] + '…'


def comparar_diagnostico(diag, const):
    """Devolve (comparavel, diverge). Só compara quando os dois textos existem."""
    a, b = normalizar_texto(diag), normalizar_texto(const)
    if not a or not b:
        return False, False
    return True, a != b
