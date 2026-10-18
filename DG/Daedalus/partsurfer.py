"""
Cliente do HP PartSurfer.

Adaptado do script teste_API-HP.py. Em vez de imprimir no console, as funções
retornam dados e levantam PartSurferError, que as views traduzem para JSON.

ATENÇÃO: o endpoint /bff/proxy/get não é uma API pública documentada da HP.
O formato pode mudar ou o acesso pode ser bloqueado a qualquer momento.
Por isso o PartSurfer só é consultado quando o usuário pede (ver
EquipamentoService.consultar_partsurfer) e o usuário escolhe quais peças salvar.
"""
import logging
from typing import Dict, List
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://partsurfer.hpcloud.hp.com/bff"
PARTSURFER_URL = "https://partsurfer.hp.com/"
COUNTRY = "US"
USERTYPE = "EXT"
TIMEOUT = 15

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/154.0.0.0 Safari/537.36"
)

HEADERS_BASE = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": USER_AGENT,
}


class PartSurferError(Exception):
    """Falha ao consultar o PartSurfer (rede, resposta inesperada, bloqueio...)."""


def _iniciar_sessao(session: requests.Session) -> None:
    """Acessa a home do PartSurfer para estabelecer a sessão e os cookies."""
    headers = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": HEADERS_BASE["Accept-Language"],
        "User-Agent": USER_AGENT,
    }
    resp = session.get(PARTSURFER_URL, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()


def _obter_hpiuid(session: requests.Session) -> str:
    """
    Chama o VerifyLogin e extrai o HPIUID.
    Formato esperado da resposta:  valor_base64:HPIUID=...
    """
    url = f"{BASE_URL}/proxy/get?input=/LogIn/VerifyLogin"
    headers = {
        **HEADERS_BASE,
        "Referer": PARTSURFER_URL,
        "Origin": "https://partsurfer.hp.com",
    }
    resp = session.get(url, headers=headers, timeout=TIMEOUT)

    if resp.status_code != 200:
        logger.warning("PartSurfer VerifyLogin retornou HTTP %s", resp.status_code)
        raise PartSurferError(
            f"O PartSurfer recusou a autenticação (HTTP {resp.status_code})."
        )

    dados = resp.text.strip()
    if not dados or ":" not in dados:
        raise PartSurferError("Formato inesperado retornado pelo VerifyLogin.")

    hpiuid = dados.split(":", 1)[1].strip()
    if not hpiuid:
        raise PartSurferError("O VerifyLogin não retornou um HPIUID válido.")

    return hpiuid


def _consultar_produto(
    session: requests.Session, hpiuid: str, product_number: str
) -> List[Dict[str, str]]:
    url = (
        f"{BASE_URL}/proxy/get?input=/Product/GetProduct/"
        f"{quote(product_number, safe='')}"
        f"/country/{COUNTRY}/usertype/{USERTYPE}"
    )
    headers = {
        **HEADERS_BASE,
        "Referer": PARTSURFER_URL,
        "Origin": "https://partsurfer.hp.com",
        # O VerifyLogin devolve o contexto neste formato (HPIUID=...).
        "Cookie": hpiuid,
    }
    resp = session.get(url, headers=headers, timeout=TIMEOUT)

    if resp.status_code != 200:
        logger.warning("PartSurfer GetProduct retornou HTTP %s", resp.status_code)
        raise PartSurferError(
            f"O PartSurfer retornou HTTP {resp.status_code} para o PN {product_number}."
        )

    try:
        dados = resp.json()
    except ValueError as erro:
        raise PartSurferError("A HP não retornou uma resposta JSON válida.") from erro

    body = dados.get("Body") if isinstance(dados, dict) else None
    if body is None:
        # Produto inexistente costuma vir sem Body; tratamos como "sem peças".
        return []
    if not isinstance(body, list):
        raise PartSurferError("O campo 'Body' da resposta não tem o formato esperado.")

    pecas = []
    for item in body:
        if not isinstance(item, dict):
            continue
        part_number = item.get("PartNumber")
        if not part_number:
            continue
        descricao = item.get("EnhancedDescription")
        pecas.append({
            "part_number": str(part_number).strip(),
            "descricao": str(descricao).strip() if descricao else "",
        })
    return pecas


def _remover_duplicidades(pecas: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Remove part numbers repetidos, mantendo a primeira ocorrência e a ordem."""
    vistos = set()
    resultado = []
    for peca in pecas:
        if peca["part_number"] in vistos:
            continue
        vistos.add(peca["part_number"])
        resultado.append(peca)
    return resultado


def buscar_pecas_por_pn(product_number: str) -> List[Dict[str, str]]:
    """
    Retorna as peças do produto como [{'part_number': ..., 'descricao': ...}],
    sem duplicidades. Lista vazia = o PartSurfer não conhece peças para o PN.
    Levanta PartSurferError em qualquer falha de comunicação.
    """
    product_number = (product_number or "").strip().upper()
    if not product_number:
        raise PartSurferError("Product Number não informado.")

    try:
        with requests.Session() as session:
            _iniciar_sessao(session)
            hpiuid = _obter_hpiuid(session)
            pecas = _consultar_produto(session, hpiuid, product_number)
    except requests.exceptions.Timeout as erro:
        raise PartSurferError("Tempo limite excedido ao consultar o PartSurfer.") from erro
    except requests.exceptions.ConnectionError as erro:
        raise PartSurferError("Não foi possível conectar ao PartSurfer.") from erro
    except requests.exceptions.HTTPError as erro:
        raise PartSurferError(f"Erro HTTP ao consultar o PartSurfer: {erro}") from erro
    except requests.exceptions.RequestException as erro:
        raise PartSurferError(f"Erro ao consultar o PartSurfer: {erro}") from erro

    return _remover_duplicidades(pecas)
