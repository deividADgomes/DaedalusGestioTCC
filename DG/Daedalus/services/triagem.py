import re
from django.utils import timezone as django_timezone
from typing import List, Optional
import os
from io import BytesIO
from datetime import date
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from docx import Document
from ..models import Empresa, Equipamento, Funcionario, Peca, Tecnico, Triagem, TriagemHistorico
from ..dtos import TriagemDTO, StatusPeca


# ==========================================
# SERVIÇO DE TRIAGEM
# ==========================================
class TriagemService:
    @staticmethod
    def validar(dto: TriagemDTO):
        if not dto.n_ticket: 
            raise ValueError("O número do Ticket é obrigatório.")
        if not dto.sn or not str(dto.sn).strip(): 
            raise ValueError("O Serial Number (SN) é obrigatório.")
        if not dto.id_tecnico or not dto.id_cliente or not dto.id_analista_chamado or not dto.id_analista_triagem or not dto.id_equipamento:
            raise ValueError("Todos os vínculos são obrigatórios.")

    # Motivos para uma troca ser indevida. Para acrescentar um motivo novo, basta incluí-lo nesta lista.
    MOTIVO_OUTRO = 'Outro'
    MOTIVOS_TROCA_INDEVIDA = ['Avaria constatada (orçamento)', 'Não era a peça com defeito', 'Resolvido com software', MOTIVO_OUTRO]

    @staticmethod
    def _validar_motivo_indevida(dto: TriagemDTO):
        """Troca indevida exige o motivo (e a explicação quando o motivo é "Outro"). Nos demais casos nada é guardado."""
        if dto.troca_indevida is not True:
            return '', ''
        motivo = ' '.join(str(dto.motivo_troca_indevida or '').split())
        if motivo not in TriagemService.MOTIVOS_TROCA_INDEVIDA:
            raise ValueError("Informe o motivo da troca indevida.")
        justificativa = ' '.join(str(dto.justificativa_troca_indevida or '').split())[:300]
        if motivo == TriagemService.MOTIVO_OUTRO and len(justificativa) < 3:
            raise ValueError("Descreva o motivo da troca indevida (motivo \"Outro\").")
        return motivo, justificativa

    @staticmethod
    def _eh_system(peca, texto: str) -> bool:
        """System board: o PN da peça termina em -601 (também vale um PN terminado em -601 digitado em "Outra peça")."""
        pn = (peca.part_number if peca else '') or ''
        return pn.strip().upper().endswith('-601') or bool(re.search(r'-601\b', texto or ''))

    @staticmethod
    def _validar_ct(dto: TriagemDTO, peca, troca) -> str:
        """CT é o número de série da System board: obrigatório quando a peça é uma System, e só é guardado nesse caso."""
        if not TriagemService._eh_system(peca, troca):
            return ''
        ct = ''.join(str(dto.ct or '').split()).upper()
        if not ct:
            raise ValueError("Informe o CT (número de série da placa) quando a peça trocada for uma System board (PN terminado em -601).")
        return ct[:60]

    @staticmethod
    def _resolver_troca(dto: TriagemDTO, equipamento: Equipamento):
        """
        Devolve (peça, texto) da troca. Se uma peça do modelo foi escolhida, o texto vira "PN - descrição"
        dela; sem peça, vale o texto livre digitado (compatível com as triagens antigas).
        """
        if dto.id_peca_trocada:
            peca = Peca.objects.filter(pk=dto.id_peca_trocada).first()
            if peca is None or not equipamento.pecas.filter(pk=peca.pk).exists():
                raise ValueError("A peça trocada precisa ser uma das peças cadastradas para este modelo.")
            descricao = ' '.join((peca.descricao or '').split())
            texto = f"{peca.part_number} - {descricao}" if descricao else peca.part_number
            return peca, texto[:255]
        texto = (dto.troca or '').strip()
        return None, (texto[:255] or None)

    # Campos que entram no histórico, na ordem em que aparecem na tela.
    ROTULOS_HISTORICO = [
        ('n_ticket', 'Ticket'), ('nf', 'NF'), ('cliente', 'Cliente'), ('tecnico', 'Técnico'),
        ('analista_chamado', 'Analista do chamado'), ('cidade', 'Cidade'), ('estado', 'UF'),
        ('equipamento', 'Equipamento'), ('sn', 'Nº de série'), ('status', 'Status da peça'),
        ('troca', 'Peça/equipamento trocado'), ('troca_indevida', 'Troca indevida'), ('motivo_troca_indevida', 'Motivo da troca indevida'), ('justificativa_troca_indevida', 'Justificativa da troca indevida'), ('ct', 'CT'), ('defeito_usuario', 'Defeito alegado'),
        ('defeito_tecnico', 'Constatação do técnico'), ('defeito_constatado', 'Defeito constatado'),
        ('testes', 'Testes realizados'), ('analise', 'Análise técnica'), ('conclusao', 'Conclusão'),
    ]

    @staticmethod
    def _valores_para_historico(t: Triagem) -> dict:
        def texto(v):
            v = '' if v is None else str(v).strip()
            return v if len(v) <= 500 else v[:499] + '…'
        return {
            'n_ticket': texto(t.n_ticket), 'nf': texto(t.nf), 'cliente': texto(t.cliente.razao_social),
            'tecnico': texto(t.tecnico.nome), 'analista_chamado': texto(t.analista_chamado.nome),
            'cidade': texto(t.cidade), 'estado': texto(t.estado), 'equipamento': texto(t.equipamento.modelo),
            'sn': texto(t.sn), 'status': 'Funcional' if t.status == StatusPeca.FUNCIONAL else 'Defeito',
            'troca': texto(t.troca), 'troca_indevida': {True: 'Sim', False: 'Não'}.get(t.troca_indevida, ''),
            'motivo_troca_indevida': texto(t.motivo_troca_indevida), 'justificativa_troca_indevida': texto(t.justificativa_troca_indevida),
            'ct': texto(t.ct), 'defeito_usuario': texto(t.defeito_usuario),
            'defeito_tecnico': texto(t.defeito_tecnico), 'defeito_constatado': texto(t.defeito_constatado),
            'testes': texto(t.testes), 'analise': texto(t.analise), 'conclusao': texto(t.conclusao),
        }

    @staticmethod
    def _diferencas(antes: dict, depois: dict) -> list:
        return [{'campo': rotulo, 'de': antes[chave] or '—', 'para': depois[chave] or '—'}
                for chave, rotulo in TriagemService.ROTULOS_HISTORICO if antes[chave] != depois[chave]]

    @staticmethod
    def historico(id_triagem: int) -> list:
        triagem = Triagem.objects.get(pk=id_triagem)
        return [
            {'id': h.id_historico, 'quando': django_timezone.localtime(h.criado_em).isoformat(),
             'usuario': h.funcionario_nome or '—', 'alteracoes': h.alteracoes}
            for h in triagem.historico.all()
        ]

    @staticmethod
    def pode_editar(id_triagem: int, id_funcionario: int, cargo: str) -> bool:
        """Edita quem fez a triagem ou a gestão (Administrador/Gestor)."""
        if cargo in ('Administrador', 'Gestor'):
            return True
        return Triagem.objects.filter(pk=id_triagem, analista_triagem_id=id_funcionario).exists()

    @staticmethod
    def salvar(dto: TriagemDTO) -> TriagemDTO:
        TriagemService.validar(dto)
        tecnico = Tecnico.objects.get(pk=dto.id_tecnico)
        cliente = Empresa.objects.get(pk=dto.id_cliente)
        equipamento = Equipamento.objects.get(pk=dto.id_equipamento)
        analista_chamado = Funcionario.objects.get(pk=dto.id_analista_chamado)
        analista_triagem = Funcionario.objects.get(pk=dto.id_analista_triagem)

        status_enum = dto.status_peca.value if hasattr(dto.status_peca, 'value') else dto.status_peca
        peca_trocada, troca = TriagemService._resolver_troca(dto, equipamento)
        ct = TriagemService._validar_ct(dto, peca_trocada, troca)
        motivo_indevida, justificativa_indevida = TriagemService._validar_motivo_indevida(dto)

        if dto.id_triagem:
            triagem = Triagem.objects.select_related('cliente', 'equipamento', 'tecnico', 'analista_chamado').get(pk=dto.id_triagem)
            antes = TriagemService._valores_para_historico(triagem)
            triagem.n_ticket = dto.n_ticket
            triagem.nf = dto.nf
            triagem.cidade = dto.cidade
            triagem.estado = dto.estado
            triagem.sn = dto.sn
            triagem.status = status_enum
            triagem.troca = troca
            triagem.peca_trocada = peca_trocada
            triagem.troca_indevida = dto.troca_indevida
            triagem.motivo_troca_indevida, triagem.justificativa_troca_indevida = motivo_indevida, justificativa_indevida
            triagem.ct = ct
            triagem.defeito_usuario = dto.defeito_usuario
            triagem.defeito_tecnico = dto.defeito_tecnico
            triagem.defeito_constatado = dto.defeito_constatado
            triagem.testes = dto.testes
            triagem.analise = dto.analise
            triagem.conclusao = dto.conclusao
            triagem.tecnico = tecnico
            triagem.cliente = cliente
            triagem.equipamento = equipamento
            triagem.analista_chamado = analista_chamado
            # analista_triagem NÃO muda: continua sendo quem fez a triagem. Quem corrigiu fica só no histórico.
            triagem.atualizado_em = django_timezone.now()
            triagem.save()
            difs = TriagemService._diferencas(antes, TriagemService._valores_para_historico(triagem))
            if difs:
                TriagemHistorico.objects.create(
                    triagem=triagem, funcionario=analista_triagem,
                    funcionario_nome=analista_triagem.nome, alteracoes=difs)
        else:
            triagem = Triagem.objects.create(
                n_ticket=dto.n_ticket, 
                nf=dto.nf, 
                cidade=dto.cidade, 
                estado=dto.estado,
                sn=dto.sn, 
                status=status_enum,
                troca=troca,
                peca_trocada=peca_trocada,
                troca_indevida=dto.troca_indevida,
                motivo_troca_indevida=motivo_indevida,
                justificativa_troca_indevida=justificativa_indevida,
                ct=ct,
                defeito_usuario=dto.defeito_usuario, 
                defeito_tecnico=dto.defeito_tecnico,
                defeito_constatado=dto.defeito_constatado, 
                testes=dto.testes, 
                analise=dto.analise, 
                conclusao=dto.conclusao,
                tecnico=tecnico, 
                cliente=cliente, 
                equipamento=equipamento, 
                analista_chamado=analista_chamado, 
                analista_triagem=analista_triagem,
                criado_em=django_timezone.now(),
                atualizado_em=django_timezone.now(),
            )
            
        dto.id_triagem = triagem.id_triagem
        return dto

    @staticmethod
    def listar() -> List[TriagemDTO]:
        triagens = Triagem.objects.select_related('cliente', 'equipamento', 'tecnico', 'analista_chamado', 'analista_triagem').all()
        return [TriagemService._mapear_para_dto(t) for t in triagens]

    @staticmethod
    def buscar_por_id(id_triagem: int) -> Optional[TriagemDTO]:
        triagem = Triagem.objects.select_related('cliente', 'equipamento', 'tecnico', 'analista_chamado', 'analista_triagem').filter(pk=id_triagem).first()
        if triagem: 
            return TriagemService._mapear_para_dto(triagem)
        return None

    @staticmethod
    def buscar_por_ticket(ticket: int) -> Optional[TriagemDTO]:
        if not ticket: 
            raise ValueError("Ticket obrigatório para a busca.")
        triagem = Triagem.objects.select_related('cliente', 'equipamento', 'tecnico', 'analista_chamado', 'analista_triagem').filter(n_ticket=ticket).first()
        if triagem: 
            return TriagemService._mapear_para_dto(triagem)
        return None

    @staticmethod
    def buscar_por_filtro(campo: str, valor: str) -> List[TriagemDTO]:
        if not valor or not campo: 
            raise ValueError("Campo e valor de busca são obrigatórios.")
        filtro = {f"{campo}__icontains": valor}
        triagens = Triagem.objects.select_related('cliente', 'equipamento', 'tecnico', 'analista_chamado', 'analista_triagem').filter(**filtro)
        return [TriagemService._mapear_para_dto(t) for t in triagens]

    @staticmethod
    def deletar(ticket: int):
        if not ticket: 
            raise ValueError("Ticket obrigatório para exclusão.")
        registros_apagados, _ = Triagem.objects.filter(n_ticket=ticket).delete()
        if registros_apagados == 0: 
            raise ObjectDoesNotExist("Nenhuma triagem encontrada.")

    @staticmethod
    def total_triagens() -> int: 
        return Triagem.objects.count()
        
    @staticmethod
    def total_peca_funcional() -> int: 
        return Triagem.objects.filter(status=StatusPeca.FUNCIONAL).count()
        
    @staticmethod
    def total_peca_nao_funcional() -> int: 
        return Triagem.objects.filter(status=StatusPeca.NAO_FUNCIONAL).count()

    @staticmethod
    def _mapear_para_dto(triagem: Triagem) -> TriagemDTO:
        return TriagemDTO(
            id_triagem=triagem.id_triagem, 
            n_ticket=triagem.n_ticket, 
            nf=triagem.nf, 
            cidade=triagem.cidade, 
            estado=triagem.estado,
            id_tecnico=triagem.tecnico_id, 
            id_cliente=triagem.cliente_id, 
            id_equipamento=triagem.equipamento_id,
            id_analista_chamado=triagem.analista_chamado_id, 
            id_analista_triagem=triagem.analista_triagem_id,
            sn=triagem.sn, 
            status_peca=StatusPeca(triagem.status), 
            troca=triagem.troca,
            id_peca_trocada=triagem.peca_trocada_id,
            troca_indevida=triagem.troca_indevida,
            motivo_troca_indevida=triagem.motivo_troca_indevida,
            justificativa_troca_indevida=triagem.justificativa_troca_indevida,
            ct=triagem.ct,
            defeito_usuario=triagem.defeito_usuario, 
            defeito_tecnico=triagem.defeito_tecnico, 
            defeito_constatado=triagem.defeito_constatado,
            testes=triagem.testes, 
            analise=triagem.analise, 
            conclusao=triagem.conclusao,
            nome_cliente=triagem.cliente.razao_social, 
            nome_equipamento=triagem.equipamento.modelo,
            nome_tecnico=triagem.tecnico.nome, 
            nome_analista_chamado=triagem.analista_chamado.nome, 
            nome_analista_triagem=triagem.analista_triagem.nome,
            criado_em=triagem.criado_em
        )

    @staticmethod
    def gerar_docx(id_triagem: int) -> tuple[BytesIO, str]:
        tri = TriagemService.buscar_por_id(id_triagem)
        if not tri: 
            raise ValueError("Triagem não encontrada")

        template_path = os.path.join(settings.BASE_DIR, 'templates', 'Daedalus', 'TRIAGEM.docx')
        if not os.path.exists(template_path): 
            raise FileNotFoundError("Modelo TRIAGEM.docx não encontrado.")
            
        doc = Document(template_path)
        data_hoje = date.today().strftime("%d/%m/%Y")

        t2 = doc.tables[2]
        t2.cell(0, 0).text = f"Data: {data_hoje}"
        t2.cell(0, 1).text = f"NF: {tri.nf or ''}"
        t2.cell(0, 2).text = f"Ticket: {tri.n_ticket or ''}"
        t2.cell(1, 1).text = f"Técnico: {tri.nome_tecnico or ''}"
        t2.cell(1, 2).text = f"Analista Chamado: {tri.nome_analista_chamado or ''} | Triagem: {tri.nome_analista_triagem or ''}"
        t2.cell(2, 1).text = f"Região: {tri.cidade or ''} - {tri.estado or ''}"
        t2.cell(2, 2).text = f"Equipamento: {tri.nome_equipamento or ''}"
        t2.cell(3, 1).text = f"N° de Série: {tri.sn or ''}"
        indevida = {True: 'Sim', False: 'Não'}.get(tri.troca_indevida, 'não informado')
        if tri.troca_indevida and tri.motivo_troca_indevida:
            indevida += f" ({tri.motivo_troca_indevida}{': ' + tri.justificativa_troca_indevida if tri.justificativa_troca_indevida else ''})"
        t2.cell(4, 1).text = f"Peça/Equipamento Trocado: {tri.troca or ''}  |  Troca indevida: {indevida}" + (f"  |  CT: {tri.ct}" if tri.ct else "")
        t2.cell(5, 1).text = f"Defeito alegado: {tri.defeito_usuario or ''}"
        t2.cell(6, 1).text = f"Constatação do Técnico: {tri.defeito_tecnico or ''}"

        t4 = doc.tables[4]
        t4.cell(0, 0).text = f"Defeito constatado: {tri.defeito_constatado or ''}"
        t4.cell(1, 0).text = f"Testes Realizados: {tri.testes or ''}"
        t4.cell(2, 0).text = f"Análise: {tri.analise or ''}"
        t4.cell(3, 0).text = f"Conclusão: {tri.conclusao or ''}"

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        modelo_str = str(tri.nome_equipamento or 'SemModelo').replace(" ", "")
        cliente_str = str(tri.nome_cliente or 'SemCliente').replace(" ", "")
        ticket_str = str(tri.n_ticket)
        nome_arquivo = f"Triagem_{ticket_str}_{modelo_str}_{cliente_str}.docx"
        
        return buffer, nome_arquivo
