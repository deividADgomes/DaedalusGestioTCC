"""Relatório mensal e alerta de técnicos por e-mail (rodados por comandos agendados)."""
import calendar
import logging
from datetime import date

from django.conf import settings
from django.core.mail import send_mail

from ..models import ChamadoRFB, Funcionario
from .bi import BIService, Filtros
from .estatistica import MIN_AMOSTRA
from .orcamento import OrcamentoService

logger = logging.getLogger(__name__)

NOMES_MES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
SITUACAO = {'critico': 'fora do limite (3 sigma)', 'atencao': 'atenção (2 sigma)'}


def _moeda(valor) -> str:
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def _pct(valor) -> str:
    return '—' if valor is None else f"{valor:.1f}%".replace('.', ',')


class RelatorioService:
    @staticmethod
    def destinatarios() -> list:
        """Administradores e Gestores com e-mail cadastrado, mais os extras de ADMIN_EMAIL."""
        emails = list(Funcionario.objects.filter(cargo__in=['Administrador', 'Gestor']).exclude(email='').values_list('email', flat=True))
        emails += [e.strip() for e in (getattr(settings, 'DAEDALUS_EMAIL_ADMIN', '') or '').split(',') if e.strip()]
        vistos, unicos = set(), []
        for e in emails:
            if e.lower() not in vistos:
                vistos.add(e.lower())
                unicos.append(e)
        return unicos

    @staticmethod
    def _filtros(inicio: date, fim: date) -> Filtros:
        return Filtros({'inicio': inicio.isoformat(), 'fim': fim.isoformat(), 'comparar': 'anterior', 'historico': '1'})

    @staticmethod
    def tecnicos_fora_do_padrao(inicio: date, fim: date) -> list:
        q = BIService.qualidade(RelatorioService._filtros(inicio, fim))
        return [t for t in q['controle_tecnicos'] if t['status'] in SITUACAO]

    @staticmethod
    def resumo_mensal(ano: int, mes: int) -> dict:
        inicio, fim = date(ano, mes, 1), date(ano, mes, calendar.monthrange(ano, mes)[1])
        q = BIService.qualidade(RelatorioService._filtros(inicio, fim))
        orc = OrcamentoService.estatisticas(inicio.isoformat(), fim.isoformat())
        return {
            'titulo': f"{NOMES_MES[mes - 1].capitalize()} de {ano}", 'inicio': inicio, 'fim': fim,
            'triagens': q['total'], 'defeitos': q['defeitos'], 'taxa_defeito': q['taxa_defeito']['atual'],
            'taxa_nff': q['nff']['taxa']['atual'], 'tecnicos': [t for t in q['controle_tecnicos'] if t['status'] in SITUACAO],
            'orcamentos': orc['total'], 'por_status': orc['por_status'], 'valor_emitido': orc['valor_emitido'],
            'valor_aprovado': orc['valor_aprovado'], 'taxa_aprovacao': orc['taxa_aprovacao'], 'motivos_recusa': orc['motivos_recusa'],
            'rfb_abertos': ChamadoRFB.objects.filter(data_abertura__date__range=(inicio, fim)).count(),
            'rfb_concluidos': ChamadoRFB.objects.filter(data_conclusao__date__range=(inicio, fim)).count(),
        }

    @staticmethod
    def texto_mensal(r: dict) -> str:
        linhas = [
            f"Relatório mensal do Daedalus Gestio: {r['titulo']}", '',
            'TRIAGEM',
            f"  Triagens: {r['triagens']}  |  defeito confirmado: {_pct(r['taxa_defeito'])}  |  peça funcional (NFF): {_pct(r['taxa_nff'])}",
            '', 'ORÇAMENTOS',
            f"  Laudos criados no período: {r['orcamentos']}  |  aprovados: {r['por_status'].get('aprovado', 0)}  |  recusados: {r['por_status'].get('recusado', 0)}",
            f"  Valor emitido: {_moeda(r['valor_emitido'])}  |  valor aprovado: {_moeda(r['valor_aprovado'])}  |  taxa de aprovação: {_pct(r['taxa_aprovacao'])}",
        ]
        if r['motivos_recusa']:
            linhas.append('  Motivos de recusa: ' + '; '.join(f"{m['nome']} ({m['quantidade']})" for m in r['motivos_recusa']))
        linhas += ['', 'CHAMADOS RFB', f"  Abertos: {r['rfb_abertos']}  |  concluídos: {r['rfb_concluidos']}", '', 'TÉCNICOS FORA DO PADRÃO (taxa de NFF)']
        if r['tecnicos']:
            linhas += [f"  {t['nome']}: {t['nff']} de {t['total']} triagens ({_pct(t['taxa_nff'])}), {SITUACAO[t['status']]}" for t in r['tecnicos']]
            linhas.append(f"  (Só entram técnicos com {MIN_AMOSTRA}+ triagens no mês. É um sinal para conversar, não uma conclusão.)")
        else:
            linhas.append('  Nenhum técnico fora do padrão no período.')
        return '\n'.join(linhas)

    @staticmethod
    def enviar_mensal(ano: int, mes: int) -> dict:
        destinatarios = RelatorioService.destinatarios()
        if not destinatarios:
            return {'enviado': False, 'motivo': 'Nenhum Administrador ou Gestor com e-mail cadastrado (e ADMIN_EMAIL vazio).'}
        r = RelatorioService.resumo_mensal(ano, mes)
        send_mail(f"[Daedalus] Relatório mensal: {r['titulo']}", RelatorioService.texto_mensal(r), None, destinatarios)
        return {'enviado': True, 'destinatarios': len(destinatarios), 'titulo': r['titulo']}

    @staticmethod
    def alertar_tecnicos(inicio: date, fim: date) -> dict:
        tecnicos = RelatorioService.tecnicos_fora_do_padrao(inicio, fim)
        if not tecnicos:
            return {'enviado': False, 'motivo': 'Nenhum técnico fora do padrão no período.', 'tecnicos': 0}
        destinatarios = RelatorioService.destinatarios()
        if not destinatarios:
            return {'enviado': False, 'motivo': 'Nenhum Administrador ou Gestor com e-mail cadastrado (e ADMIN_EMAIL vazio).', 'tecnicos': len(tecnicos)}
        corpo = (f"Técnicos com taxa de peça funcional (NFF) fora do padrão entre {inicio:%d/%m/%Y} e {fim:%d/%m/%Y}:\n\n"
                 + '\n'.join(f"- {t['nome']} ({t['prestadora'] or 'sem prestadora'}): {t['nff']} de {t['total']} triagens "
                             f"({_pct(t['taxa_nff'])}), {SITUACAO[t['status']]}" for t in tecnicos)
                 + "\n\nÉ um indício estatístico para conversar com o técnico, não uma conclusão. "
                   "Veja o gráfico de controle em Dashboard > Qualidade.")
        send_mail(f"[Daedalus] {len(tecnicos)} técnico(s) fora do padrão de NFF", corpo, None, destinatarios)
        return {'enviado': True, 'tecnicos': len(tecnicos), 'destinatarios': len(destinatarios)}
