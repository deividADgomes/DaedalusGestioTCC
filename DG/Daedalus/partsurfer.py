import logging
from typing import Dict, List
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://partsurfer.hpcloud.hp.com/bff"
ORIGEM = "https://partsurfer.hp.com"
PARTSURFER_URL = f"{ORIGEM}/"
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
    pass


def _cabecalhos_da_api(**extras: str) -> Dict[str, str]:
    return {**HEADERS_BASE, "Referer": PARTSURFER_URL, "Origin": ORIGEM, **extras}


def _iniciar_sessao(session: requests.Session) -> None:
    headers = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": HEADERS_BASE["Accept-Language"],
        "User-Agent": USER_AGENT,
    }
    resposta = session.get(PARTSURFER_URL, headers=headers, timeout=TIMEOUT)
    resposta.raise_for_status()


def _obter_hpiuid(session: requests.Session) -> str:
    url = f"{BASE_URL}/proxy/get?input=/LogIn/VerifyLogin"
    resposta = session.get(url, headers=_cabecalhos_da_api(), timeout=TIMEOUT)

    if resposta.status_code != 200:
        logger.warning("PartSurfer VerifyLogin retornou HTTP %s", resposta.status_code)
        raise PartSurferError(f"O PartSurfer recusou a autenticação (HTTP {resposta.status_code}).")

    dados = resposta.text.strip()
    if not dados or ":" not in dados:
        raise PartSurferError("Formato inesperado retornado pelo VerifyLogin.")

    hpiuid = dados.split(":", 1)[1].strip()
    if not hpiuid:
        raise PartSurferError("O VerifyLogin não retornou um HPIUID válido.")

    return hpiuid


def _consultar_produto(session: requests.Session, hpiuid: str, product_number: str) -> List[Dict[str, str]]:
    url = (
        f"{BASE_URL}/proxy/get?input=/Product/GetProduct/"
        f"{quote(product_number, safe='')}"
        f"/country/{COUNTRY}/usertype/{USERTYPE}"
    )
    resposta = session.get(url, headers=_cabecalhos_da_api(Cookie=hpiuid), timeout=TIMEOUT)

    if resposta.status_code != 200:
        logger.warning("PartSurfer GetProduct retornou HTTP %s", resposta.status_code)
        raise PartSurferError(f"O PartSurfer retornou HTTP {resposta.status_code} para o PN {product_number}.")

    try:
        dados = resposta.json()
    except ValueError as erro:
        raise PartSurferError("A HP não retornou uma resposta JSON válida.") from erro

    body = dados.get("Body") if isinstance(dados, dict) else None
    if body is None:
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
    vistos = set()
    resultado = []
    for peca in pecas:
        if peca["part_number"] in vistos:
            continue
        vistos.add(peca["part_number"])
        resultado.append(peca)
    return resultado


def buscar_pecas_por_pn(product_number: str) -> List[Dict[str, str]]:
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
