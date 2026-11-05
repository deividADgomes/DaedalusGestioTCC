"""
Auditoria geral: registra quem gravou ou excluiu cadastros.

Roda como middleware, depois da autenticação, e só olha respostas de sucesso das rotas listadas em ROTAS_AUDITADAS.
Guarda apenas campos escolhidos de cada rota (nunca o corpo inteiro), então senhas e e-mails não vão para o log.
Uma falha aqui nunca derruba a requisição.
"""
import json
import logging
import re

from .models import AuditoriaLog

logger = logging.getLogger(__name__)

# (prefixo da rota, nome da entidade, campos do corpo que descrevem o registro)
ROTAS_AUDITADAS = [
    ('/api/funcionario/', 'Funcionário', ('nome', 'login', 'cargo')),
    ('/api/empresa/', 'Empresa', ('razao_social', 'cnpj', 'tipo')),
    ('/api/tecnico/', 'Técnico', ('nome',)),
    ('/api/modelo-equipamento/', 'Modelo / peças do modelo', ('modelo', 'pn')),
    ('/api/pecas/', 'Peça / cotação', ('part_number', 'valor')),
    ('/api/cotacoes/', 'Cotação', ()),
    ('/api/saidas/', 'Saída de peças', ('numero_nf',)),
    ('/api/estoque/config/', 'Estoque (mínimo e local)', ('id_peca', 'minimo', 'local')),   # os movimentos têm histórico próprio
]
METODOS = {'POST', 'PUT', 'DELETE'}


def _corpo(request) -> dict:
    try:
        dados = json.loads(request.body or b'{}')
        return dados if isinstance(dados, dict) else {}
    except Exception:
        return {}


def _descricao(corpo: dict, campos) -> str:
    partes = [f"{c}={str(corpo[c]).strip()}" for c in campos if corpo.get(c) not in (None, '')]
    if isinstance(corpo.get('pecas'), list):
        partes.append(f"{len(corpo['pecas'])} peça(s) na lista")
    if isinstance(corpo.get('itens'), list):
        partes.append(f"{len(corpo['itens'])} linha(s)")
    if isinstance(corpo.get('linhas'), list):
        partes.append(f"{len(corpo['linhas'])} linha(s) com NF/rastreio")
    if corpo.get('senha'):
        partes.append('senha redefinida')
    return ', '.join(partes)[:300]


class AuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if request.method in METODOS and response.status_code < 300 and request.session.get('funcionario_id'):
                self._registrar(request)
        except Exception:
            logger.exception("Falha ao registrar a auditoria (a requisição não foi afetada)")
        return response

    @staticmethod
    def _registrar(request):
        caminho = request.path
        if '/partsurfer/' in caminho:        # só consulta a HP, não grava nada
            return
        for prefixo, entidade, campos in ROTAS_AUDITADAS:
            if caminho.startswith(prefixo):
                break
        else:
            return
        if '/cotacoes/' in caminho and prefixo == '/api/pecas/':
            entidade = 'Cotação'
        corpo = _corpo(request) if request.method != 'DELETE' else {}
        if 'importar-pecas' in caminho:
            acao, descricao = 'importou', 'planilha de peças'
        else:
            acao = 'excluiu' if request.method == 'DELETE' else 'gravou'
            descricao = _descricao(corpo, campos)
        numeros = re.findall(r'/(\d+)/', caminho)
        entidade_id = int(numeros[0]) if numeros else (corpo.get('id') if isinstance(corpo.get('id'), int) else None)
        AuditoriaLog.objects.create(
            funcionario_id=request.session.get('funcionario_id'), funcionario_nome=getattr(request, 'funcionario_nome', '') or '',
            acao=acao, entidade=entidade, entidade_id=entidade_id, descricao=descricao)
