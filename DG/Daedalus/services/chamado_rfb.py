from django.utils import timezone as django_timezone
from datetime import timedelta
from collections import Counter
from django.db import transaction
from django.db.models import Q, F, Case, When, Value, FloatField, ExpressionWrapper, Count
from ..models import ChamadoRFB, Equipamento, Peca
from .utils import consultar_ibge_metropolitana, get_feriados_nacionais


# ==========================================
# SERVIÇO DE CHAMADOS RFB (SAD)
# ==========================================
class ChamadoRFBService:
    @staticmethod
    def _equipamento_permitido(id_equipamento, atual_id=None) -> Equipamento:
        """Modelo escolhido na tela: precisa existir e estar habilitado para o RFB (ou já ser o do chamado)."""
        try:
            equipamento = Equipamento.objects.get(pk=int(id_equipamento))
        except (TypeError, ValueError, Equipamento.DoesNotExist):
            raise ValueError("Modelo de equipamento inválido.")
        if not equipamento.rfb and equipamento.pk != atual_id:
            raise ValueError(f"O modelo {equipamento.modelo} não está habilitado para o RFB.")
        return equipamento

    @staticmethod
    def _equipamento_por_nome(nome):
        """Compatibilidade: quem ainda envia só o texto do modelo."""
        alvo = ' '.join(str(nome or '').lower().split())
        if not alvo:
            return None
        for equipamento in Equipamento.objects.filter(rfb=True):
            if ' '.join(equipamento.modelo.lower().split()) == alvo:
                return equipamento
        return None

    @staticmethod
    def _pecas_do_encerramento(chamado, dados: dict):
        """
        As peças do encerramento são padronizadas: só valem as peças cadastradas para o modelo do chamado.
        Devolve (lista de peças, texto para exibição). Levanta ValueError se algo estiver incorreto.
        """
        if chamado.equipamento is None:
            raise ValueError("Informe o modelo cadastrado do chamado antes de encerrar.")
        sem_peca = bool(dados.get('sem_peca'))
        ids_brutos = dados.get('pecas_utilizadas_ids')
        if ids_brutos is None and not sem_peca:
            raise ValueError("Selecione as peças utilizadas ou marque \"Nenhuma peça utilizada\".")
        try:
            ids = [int(i) for i in (ids_brutos or [])]
        except (TypeError, ValueError):
            raise ValueError("Lista de peças inválida.")
        if sem_peca and ids:
            raise ValueError("Marque \"Nenhuma peça utilizada\" ou escolha as peças, não as duas coisas.")
        if not sem_peca and not ids:
            raise ValueError("Selecione as peças utilizadas ou marque \"Nenhuma peça utilizada\".")
        validas = {p.id_peca: p for p in chamado.equipamento.pecas.all()}
        if any(i not in validas for i in ids):
            raise ValueError("Há peças que não pertencem ao modelo deste chamado.")
        pecas = [validas[i] for i in dict.fromkeys(ids)]
        rotulo = ' + '.join(f"{p.part_number} ({p.descricao})" if p.descricao else p.part_number for p in pecas)[:500]
        return pecas, rotulo or 'Nenhuma peça utilizada'

    @staticmethod
    def salvar(dados: dict):
        chamado_id = dados.get('id')

        if chamado_id:
            chamado = ChamadoRFB.objects.get(pk=chamado_id)
            status_anterior = chamado.status

            ticket = dados.get('ticket', chamado.ticket)
            sn = dados.get('sn', chamado.sn)
            cidade = dados.get('cidade', chamado.cidade)
            estado = dados.get('estado', chamado.estado)

            if not ticket or not sn:
                raise ValueError("Ticket e Serial Number são obrigatórios.")

            chamado.ticket = ticket

            if dados.get('data_abertura'):
                chamado.data_abertura = dados.get('data_abertura')

            chamado.estado = estado
            chamado.cidade = cidade
            chamado.is_metropolitana = consultar_ibge_metropolitana(cidade, estado)

            if dados.get('descricao_defeito'):
                chamado.descricao_defeito = dados.get('descricao_defeito')
            if dados.get('equipamento_id'):
                equipamento = ChamadoRFBService._equipamento_permitido(dados['equipamento_id'], chamado.equipamento_id)
                chamado.equipamento = equipamento
                chamado.modelo_equipamento = equipamento.modelo
            elif dados.get('modelo_equipamento'):
                chamado.modelo_equipamento = dados.get('modelo_equipamento')
                equipamento = ChamadoRFBService._equipamento_por_nome(dados.get('modelo_equipamento'))
                if equipamento:
                    chamado.equipamento = equipamento

            chamado.sn = sn

            if 'status' in dados:
                chamado.status = dados.get('status')
            if 'observacao' in dados:
                chamado.observacao = dados.get('observacao')

            chamado.resolucao_caso = dados.get('resolucao_caso', chamado.resolucao_caso)

            # "Sem intervenção técnica": resolvido sem ir a campo. Não tem técnico nem peças, e só vale em chamado concluído
            # (se o chamado for reaberto, a marcação some).
            sem_intervencao = bool(dados['sem_intervencao_tecnica']) if 'sem_intervencao_tecnica' in dados else chamado.sem_intervencao_tecnica
            sem_intervencao = sem_intervencao and chamado.status == 'concluido'
            concluindo = dados.get('status') == 'concluido' and status_anterior != 'concluido'
            if sem_intervencao and not (chamado.resolucao_caso or '').strip():
                raise ValueError("Descreva como o chamado foi resolvido sem intervenção técnica.")

            pecas = None
            if sem_intervencao:
                pecas = ([], 'Nenhuma peça utilizada')
                chamado.peca_utilizada = pecas[1]
            elif concluindo:
                pecas = ChamadoRFBService._pecas_do_encerramento(chamado, dados)
                chamado.peca_utilizada = pecas[1]
            else:
                chamado.peca_utilizada = dados.get('peca_utilizada', chamado.peca_utilizada)
            chamado.sem_intervencao_tecnica = sem_intervencao

            if 'analista_responsavel_id' in dados:
                chamado.analista_responsavel_id = dados.get('analista_responsavel_id')
            if 'tecnico_atendimento_id' in dados:
                chamado.tecnico_atendimento_id = dados.get('tecnico_atendimento_id')
            if sem_intervencao:
                chamado.tecnico_atendimento_id = None
            if 'tipo_chamado' in dados:
                chamado.tipo_chamado = dados.get('tipo_chamado')

            if chamado.status == 'concluido' and dados.get('data_conclusao'):
                chamado.data_conclusao = dados.get('data_conclusao')

            with transaction.atomic():
                chamado.save()
                if pecas is not None:
                    chamado.pecas_utilizadas.set(pecas[0])
            return chamado

        else:
            ticket = dados.get('ticket')
            sn = dados.get('sn')
            cidade = dados.get('cidade')
            estado = dados.get('estado')

            if not ticket or not sn:
                raise ValueError("Ticket e Serial Number são obrigatórios.")

            if dados.get('equipamento_id'):
                equipamento = ChamadoRFBService._equipamento_permitido(dados['equipamento_id'])
            else:
                equipamento = ChamadoRFBService._equipamento_por_nome(dados.get('modelo_equipamento'))
            if equipamento is None:
                raise ValueError("Selecione o modelo do equipamento (cadastrado em Modelos e peças e habilitado para o RFB).")

            is_metro = consultar_ibge_metropolitana(cidade, estado) if cidade and estado else False

            return ChamadoRFB.objects.create(
                ticket=ticket,
                data_abertura=dados.get('data_abertura'),
                estado=estado,
                cidade=cidade,
                is_metropolitana=is_metro,
                descricao_defeito=dados.get('descricao_defeito'),
                equipamento=equipamento,
                modelo_equipamento=equipamento.modelo,
                sn=sn,
                status='aberto',
                resolucao_caso=dados.get('resolucao_caso', ''),
                peca_utilizada=dados.get('peca_utilizada', 'Nenhuma peça utilizada'),
                observacao=dados.get('observacao', ''),
                analista_responsavel_id=dados.get('analista_responsavel_id'),
                tecnico_atendimento_id=dados.get('tecnico_atendimento_id'),
                tipo_chamado=dados.get('tipo_chamado', 'Não informado')
            )

    @staticmethod
    def _top_pecas(qs, excluir) -> list:
        """Peças mais usadas: as padronizadas (por PN) e, em chamados antigos, o texto livre que já existia."""
        contagem = Counter()
        for peca in Peca.objects.filter(chamados_rfb__in=qs).annotate(total=Count('chamados_rfb')):
            contagem[peca.part_number] += peca.total
        antigos = (qs.filter(pecas_utilizadas__isnull=True).exclude(peca_utilizada__in=excluir)
                   .values('peca_utilizada').annotate(total=Count('pk')))
        for linha in antigos:
            if linha['peca_utilizada']:
                contagem[linha['peca_utilizada']] += linha['total']
        return [{'peca_utilizada': nome, 'total': n} for nome, n in contagem.most_common(5)]

    @staticmethod
    def obter_dashboard() -> dict:
        # 1. Atualiza o consumo de SLA apenas para os chamados ativos
        chamados_ativos = ChamadoRFB.objects.prefetch_related('agendamentos').exclude(status='concluido')
        
        for chamado in chamados_ativos:
            consumo = ChamadoRFBService.calcular_consumo_sla(chamado)
            if getattr(chamado, 'horas_consumidas', 0) != consumo:
                chamado.horas_consumidas = consumo
                chamado.save(update_fields=['horas_consumidas'])

        # 2. Query global com o cálculo de SLA anotado
        query = ChamadoRFB.objects.annotate(
            limite_calc=Case(
                When(is_metropolitana=True, then=Value(72.0)), 
                default=Value(120.0), 
                output_field=FloatField()
            )
        ).annotate(
            pct_sla=ExpressionWrapper(
                (F('horas_consumidas') / F('limite_calc')) * 100.0, 
                output_field=FloatField()
            )
        )
        
        # 3. Extração dos totais globais (baseados estritamente na base inteira, ignorando buscas)
        ativos_total = query.exclude(status='concluido').count()
        concluidos_total = query.filter(status='concluido').count()
        
        # Exemplo das métricas de SLA exibidas nos cards superiores:
        no_prazo = query.exclude(status='concluido').filter(pct_sla__lte=80.0).count()
        em_risco = query.exclude(status='concluido').filter(pct_sla__gt=80.0, pct_sla__lte=100.0).count()
        estourado = query.exclude(status='concluido').filter(pct_sla__gt=100.0).count()

        # 4. Retorno obrigatório do dicionário de contexto para a view
        return {
            'abertos_andamento': ativos_total,
            'concluidos': concluidos_total,
            'no_prazo': no_prazo,
            'em_risco': em_risco,
            'estourado': estourado,
            # Adicione aqui outras chaves dos gráficos se necessário
        }
        total = query.count()
        estourados = query.filter(pct_sla__gte=100).exclude(status='concluido').count()
        em_risco = query.filter(pct_sla__gte=80, pct_sla__lt=100).exclude(status='concluido').count()
        no_prazo = query.filter(pct_sla__lt=80).exclude(status='concluido').count()
        
        total_ativos = em_risco + estourados + no_prazo
        porcentagem = (no_prazo / total_ativos * 100) if total_ativos > 0 else 0

        return {
            'dash_total': total,
            'dash_abertos': query.filter(Q(status='aberto') | Q(status='andamento')).count(),
            'dash_concluidos': query.filter(status='concluido').count(),
            'dash_risco': em_risco,
            'dash_estourado': estourados,
            'dash_no_prazo': no_prazo,
            'porcentagem_no_prazo': round(porcentagem, 1)
        }

    @staticmethod
    def listar_para_api(status_filter='todos', busca='', pagina=1, limite=50, tipo_filter='todos', estado_filter='todos', analista_filter='todos') -> dict:
        from django.db.models import Count, Q, Case, When, Value, FloatField, ExpressionWrapper, F
        from django.utils import timezone as django_timezone
        
        chamados_ativos = ChamadoRFB.objects.prefetch_related('agendamentos').exclude(status__iexact='concluido')
        
        hoje_str = django_timezone.localtime(django_timezone.now()).strftime('%Y-%m-%d')
        agendados_hoje_lista = []
        abertos_sem_acao_lista = []
        
        em_risco = 0
        estourados = 0
        no_prazo = 0
        geo_estouros = {}

        # 1. CLASSIFICAÇÃO DE ATIVOS E PREVISÃO
        for c in chamados_ativos:
            consumo_atualizado = ChamadoRFBService.calcular_consumo_sla(c)
            if float(getattr(c, 'horas_consumidas', 0) or 0) != consumo_atualizado:
                c.horas_consumidas = consumo_atualizado
                c.save(update_fields=['horas_consumidas'])
                
            status_clean = str(getattr(c, 'status', '')).strip().lower()
            if status_clean == 'aberto':
                abertos_sem_acao_lista.append(c)
                
            agendamentos_pendentes = [a for a in c.agendamentos.all() if str(getattr(a, 'status', '')).strip().lower() == 'pendente']
            is_hoje = False
            for a in agendamentos_pendentes:
                if getattr(a, 'tipo_pausa', '') == 'agendamento' and getattr(a, 'data_agendamento', None):
                    dt_agend = getattr(a, 'data_agendamento')
                    dt_str = django_timezone.localtime(dt_agend).strftime('%Y-%m-%d') if hasattr(dt_agend, 'astimezone') else dt_agend.strftime('%Y-%m-%d')
                    if dt_str == hoje_str:
                        is_hoje = True
                        break
            if is_hoje:
                agendados_hoje_lista.append(c)
                
            limite_sla = 72 if getattr(c, 'is_metropolitana', False) else 120
            hr_cons = float(getattr(c, 'horas_consumidas', 0) or 0)
            pct = (hr_cons / limite_sla) * 100.0 if limite_sla > 0 else 0
            
            if pct >= 100:
                estourados += 1
                est = getattr(c, 'estado', 'N/A')
                geo_estouros[est] = geo_estouros.get(est, 0) + 1
            elif pct >= 80:
                em_risco += 1
            else:
                no_prazo += 1

        # 2. EFICIÊNCIA DE CONCLUÍDOS E INDICADORES (DASHBOARD GLOBAL ISOLADO)
        qs_global = ChamadoRFB.objects.select_related('analista_responsavel', 'tecnico_atendimento').prefetch_related('agendamentos')
        concluidos_qs = qs_global.filter(status__iexact='concluido')
        
        total_concluidos = len(concluidos_qs)
        concluidos_sem_intervencao = sum(1 for c in concluidos_qs if c.sem_intervencao_tecnica)
        concluidos_estourados = 0
        
        for c in concluidos_qs:
            hr_cons_c = ChamadoRFBService.calcular_consumo_sla(c)
            limite_c = 72.0 if getattr(c, 'is_metropolitana', False) else 120.0
            if hr_cons_c > limite_c:
                concluidos_estourados += 1
                
        pct_concluidos_no_prazo = 0.0
        if total_concluidos > 0:
            pct_concluidos_no_prazo = round(((total_concluidos - concluidos_estourados) / float(total_concluidos)) * 100.0, 1)

        total_abertos = len(chamados_ativos)
        pct_no_prazo = 0.0
        if total_abertos > 0:
            pct_no_prazo = round(((total_abertos - estourados) / float(total_abertos)) * 100.0, 1)

        abertos_sem_acao_lista = sorted(abertos_sem_acao_lista, key=lambda x: getattr(x, 'data_abertura', None) or django_timezone.now())[:15]
        agendados_hoje_lista = agendados_hoje_lista[:15]

        def serializar_card(c):
            agend_pendentes = [a for a in c.agendamentos.all() if str(getattr(a, 'status', '')).strip().lower() == 'pendente']
            ultimo_agendamento_pendente = "Aberto / Sem Ação"
            if agend_pendentes:
                ultimo = sorted(agend_pendentes, key=lambda x: getattr(x, 'id_agendamento', getattr(x, 'id', 0)))[-1]
                if getattr(ultimo, 'tipo_pausa', '') == 'sem_resposta':
                    dt_val = getattr(ultimo, 'data_inicio_tentativas', None)
                    dt_str = django_timezone.localtime(dt_val).strftime('%d/%m às %H:%M') if dt_val else '--'
                    ultimo_agendamento_pendente = f"Falta Resposta ({dt_str})"
                else:
                    dt_val = getattr(ultimo, 'data_agendamento', None)
                    dt_str = django_timezone.localtime(dt_val).strftime('%d/%m às %H:%M') if dt_val else '--'
                    ultimo_agendamento_pendente = f"Visita: {dt_str}"
            
            return {
                'id': getattr(c, 'id_chamado', getattr(c, 'id', None)),
                'ticket': getattr(c, 'ticket', '--'),
                'cidade': getattr(c, 'cidade', '--'),
                'estado': getattr(c, 'estado', '--'),
                'modelo_equipamento': getattr(c, 'modelo_equipamento', '--'),
                'sn': getattr(c, 'sn', '--'),
                'horas_consumidas': float(getattr(c, 'horas_consumidas', 0) or 0.0),
                'limite_sla': 72 if getattr(c, 'is_metropolitana', False) else 120,
                'ultimo_agendamento_pendente': ultimo_agendamento_pendente,
            }

        top_equips = list(qs_global.values('modelo_equipamento').annotate(total=Count('pk')).order_by('-total')[:5])
        excluir_pecas = ['', 'Nenhuma peça utilizada', 'Nenhuma', 'N/A', None]
        top_pecas = ChamadoRFBService._top_pecas(qs_global, excluir_pecas)
        top_geo_sorted = sorted(geo_estouros.items(), key=lambda x: x[1], reverse=True)[:5]
        
        dash_global = {
            'abertos': total_abertos,
            'concluidos': total_concluidos,
            'concluidos_sem_intervencao': concluidos_sem_intervencao,
            'risco': em_risco,
            'estourados': estourados,
            'no_prazo': no_prazo,
            'pct_no_prazo': pct_no_prazo,
            'pct_concluidos_no_prazo': pct_concluidos_no_prazo,
            'graficos': {
                'equips_labels': [e['modelo_equipamento'] for e in top_equips if e['modelo_equipamento']],
                'equips_data': [e['total'] for e in top_equips],
                'pecas_labels': [p['peca_utilizada'] for p in top_pecas if p['peca_utilizada']],
                'pecas_data': [p['total'] for p in top_pecas],
                'geo_labels': [g[0] for g in top_geo_sorted],
                'geo_data': [g[1] for g in top_geo_sorted],
            },
            'visitas_hoje': [serializar_card(c) for c in agendados_hoje_lista],
            'abertos_sem_acao': [serializar_card(c) for c in abertos_sem_acao_lista]
        }

        # 3. FILTROS DA TABELA DINÂMICA (Os filtros aplicados aqui NÃO afetam o dash_global acima)
        qs_tabela = qs_global.annotate(
            limite_calc=Case(
                When(is_metropolitana=True, then=Value(72.0)), 
                default=Value(120.0), 
                output_field=FloatField()
            )
        ).annotate(
            pct_sla=ExpressionWrapper(
                (F('horas_consumidas') / F('limite_calc')) * 100.0, 
                output_field=FloatField()
            )
        ).order_by('-data_abertura')
        
        if status_filter and status_filter != 'todos':
            if status_filter == 'no_prazo': qs_tabela = qs_tabela.filter(pct_sla__lt=80).exclude(status__iexact='concluido')
            elif status_filter == 'em_risco': qs_tabela = qs_tabela.filter(pct_sla__gte=80, pct_sla__lt=100).exclude(status__iexact='concluido')
            elif status_filter == 'estourado': qs_tabela = qs_tabela.filter(pct_sla__gte=100).exclude(status__iexact='concluido')
            elif status_filter == 'agendado': qs_tabela = qs_tabela.filter(agendamentos__status__iexact='pendente', agendamentos__tipo_pausa='agendamento').distinct()
            else: qs_tabela = qs_tabela.filter(status__iexact=status_filter)

        if tipo_filter and tipo_filter != 'todos':
            qs_tabela = qs_tabela.filter(tipo_chamado__iexact=tipo_filter)

        if estado_filter and estado_filter != 'todos':
            qs_tabela = qs_tabela.filter(estado__iexact=estado_filter)

        if analista_filter and analista_filter != 'todos':
            qs_tabela = qs_tabela.filter(analista_responsavel_id=analista_filter)

        if busca:
            qs_tabela = qs_tabela.filter(
                Q(ticket__icontains=busca) | Q(sn__icontains=busca) | Q(cidade__icontains=busca) | Q(modelo_equipamento__icontains=busca)
            )

        total_registros = qs_tabela.count()
        pagina_int = int(pagina) if str(pagina).isdigit() else 1
        inicio = (pagina_int - 1) * limite
        fim = inicio + limite
        
        resultado = []
        for c in qs_tabela[inicio:fim]:
            horas_consumidas_reais = ChamadoRFBService.calcular_consumo_sla(c)
            
            if float(getattr(c, 'horas_consumidas', 0) or 0) != horas_consumidas_reais:
                c.horas_consumidas = horas_consumidas_reais
                c.save(update_fields=['horas_consumidas'])

            limite_sla = 72 if getattr(c, 'is_metropolitana', False) else 120
            agendamentos = c.agendamentos.all()
            fim_ref = getattr(c, 'data_conclusao', None) if str(getattr(c, 'status', '')).lower() == 'concluido' and getattr(c, 'data_conclusao', None) else django_timezone.now()
            
            horas_pausadas = ChamadoRFBService.calcular_horas_pausadas(c, fim_ref)
            limite_efetivo_com_pausa = limite_sla + int(horas_pausadas)
            expiracao = ChamadoRFBService.calcular_data_expiracao(getattr(c, 'data_abertura', django_timezone.now()), limite_efetivo_com_pausa)
            
            ultimo_agendamento_pendente = ""
            data_agendamento_iso = None
            agendamentos_pendentes = [a for a in agendamentos if str(getattr(a, 'status', '')).strip().lower() == 'pendente']
            
            if agendamentos_pendentes:
                ultimo = sorted(agendamentos_pendentes, key=lambda x: getattr(x, 'id_agendamento', getattr(x, 'id', 0)))[-1]
                if getattr(ultimo, 'tipo_pausa', '') == 'sem_resposta':
                    dt_val = getattr(ultimo, 'data_inicio_tentativas', None)
                    dt_str = django_timezone.localtime(dt_val).strftime('%d/%m às %H:%M') if dt_val else '--'
                    ultimo_agendamento_pendente = f"Falta Resposta ({dt_str})"
                    data_agendamento_iso = dt_val.isoformat() if hasattr(dt_val, 'isoformat') else None
                else:
                    dt_val = getattr(ultimo, 'data_agendamento', None)
                    dt_str = django_timezone.localtime(dt_val).strftime('%d/%m às %H:%M') if dt_val else '--'
                    ultimo_agendamento_pendente = f"Visita: {dt_str}"
                    data_agendamento_iso = dt_val.isoformat() if hasattr(dt_val, 'isoformat') else None
            
            resultado.append({
                'id': getattr(c, 'id_chamado', getattr(c, 'id', None)),
                'ticket': getattr(c, 'ticket', '--'),
                'data_abertura': c.data_abertura.isoformat() if hasattr(c.data_abertura, 'isoformat') else None,
                'estado': getattr(c, 'estado', '--'),
                'cidade': getattr(c, 'cidade', '--'),
                'modelo_equipamento': getattr(c, 'modelo_equipamento', '--'),
                'sn': getattr(c, 'sn', '--'),
                'descricao_defeito': getattr(c, 'descricao_defeito', '--'),
                'status': getattr(c, 'status', '--'),
                'limite_sla': limite_sla,
                'horas_consumidas': float(horas_consumidas_reais),
                'data_expiracao': expiracao.isoformat() if hasattr(expiracao, 'isoformat') else None,
                'is_metropolitana': getattr(c, 'is_metropolitana', False),
                'resolucao_caso': getattr(c, 'resolucao_caso', ''),
                'sem_intervencao_tecnica': bool(getattr(c, 'sem_intervencao_tecnica', False)),
                'peca_utilizada': getattr(c, 'peca_utilizada', 'Nenhuma'),
                'tipo_chamado': getattr(c, 'tipo_chamado', 'Não informado'),
                'data_conclusao': c.data_conclusao.isoformat() if hasattr(c, 'data_conclusao') and c.data_conclusao else None,
                'observacao': getattr(c, 'observacao', ''),
                'ultimo_agendamento_pendente': ultimo_agendamento_pendente,
                'data_agendamento_pendente': data_agendamento_iso,
                'analista_responsavel_id': getattr(c, 'analista_responsavel_id', None),
                'analista_responsavel_nome': c.analista_responsavel.nome if getattr(c, 'analista_responsavel', None) else None,
                'tecnico_atendimento_id': getattr(c, 'tecnico_atendimento_id', None),
                'equipamento_id': getattr(c, 'equipamento_id', None),
                'tecnico_atendimento_nome': c.tecnico_atendimento.nome if getattr(c, 'tecnico_atendimento', None) else None,
            })
            
        return {
            'dados': resultado,
            'dashboard': dash_global,
            'total': total_registros,
            'pagina_atual': pagina_int,
            'total_paginas': (total_registros // limite) + (1 if total_registros % limite > 0 else 0)
        }

        def serializar_card(c):
            agend_pendentes = [a for a in c.agendamentos.all() if str(getattr(a, 'status', '')).strip().lower() == 'pendente']
            ultimo_agendamento_pendente = "Aberto / Sem Ação"
            if agend_pendentes:
                ultimo = sorted(agend_pendentes, key=lambda x: getattr(x, 'id_agendamento', getattr(x, 'id', 0)))[-1]
                if getattr(ultimo, 'tipo_pausa', '') == 'sem_resposta':
                    dt_val = getattr(ultimo, 'data_inicio_tentativas', None)
                    dt_str = django_timezone.localtime(dt_val).strftime('%d/%m às %H:%M') if dt_val else '--'
                    ultimo_agendamento_pendente = f"Falta Resposta ({dt_str})"
                else:
                    dt_val = getattr(ultimo, 'data_agendamento', None)
                    dt_str = django_timezone.localtime(dt_val).strftime('%d/%m às %H:%M') if dt_val else '--'
                    ultimo_agendamento_pendente = f"Visita: {dt_str}"
            
            return {
                'id': getattr(c, 'id_chamado', getattr(c, 'id', None)),
                'ticket': getattr(c, 'ticket', '--'),
                'cidade': getattr(c, 'cidade', '--'),
                'estado': getattr(c, 'estado', '--'),
                'modelo_equipamento': getattr(c, 'modelo_equipamento', '--'),
                'sn': getattr(c, 'sn', '--'),
                'horas_consumidas': float(getattr(c, 'horas_consumidas', 0) or 0.0),
                'limite_sla': 72 if getattr(c, 'is_metropolitana', False) else 120,
                'ultimo_agendamento_pendente': ultimo_agendamento_pendente,
            }

        top_equips = list(qs_global.values('modelo_equipamento').annotate(total=Count('pk')).order_by('-total')[:5])
        excluir_pecas = ['', 'Nenhuma peça utilizada', 'Nenhuma', 'N/A', None]
        top_pecas = ChamadoRFBService._top_pecas(qs_global, excluir_pecas)
        top_geo_sorted = sorted(geo_estouros.items(), key=lambda x: x[1], reverse=True)[:5]
        
        dash_global = {
            'abertos': total_abertos,
            'concluidos': total_concluidos,
            'concluidos_sem_intervencao': concluidos_sem_intervencao,
            'risco': em_risco,
            'estourados': estourados,
            'no_prazo': no_prazo,
            'pct_no_prazo': pct_no_prazo,
            'pct_concluidos_no_prazo': pct_concluidos_no_prazo,
            'graficos': {
                'equips_labels': [e['modelo_equipamento'] for e in top_equips if e['modelo_equipamento']],
                'equips_data': [e['total'] for e in top_equips],
                'pecas_labels': [p['peca_utilizada'] for p in top_pecas if p['peca_utilizada']],
                'pecas_data': [p['total'] for p in top_pecas],
                'geo_labels': [g[0] for g in top_geo_sorted],
                'geo_data': [g[1] for g in top_geo_sorted],
            },
            'visitas_hoje': [serializar_card(c) for c in agendados_hoje_lista],
            'abertos_sem_acao': [serializar_card(c) for c in abertos_sem_acao_lista]
        }

        # 3. FILTROS DA TABELA DINÂMICA
        qs_tabela = qs_global.annotate(
            limite_calc=Case(
                When(is_metropolitana=True, then=Value(72.0)), 
                default=Value(120.0), 
                output_field=FloatField()
            )
        ).annotate(
            pct_sla=ExpressionWrapper(
                (F('horas_consumidas') / F('limite_calc')) * 100.0, 
                output_field=FloatField()
            )
        ).order_by('-data_abertura')
        
        if status_filter and status_filter != 'todos':
            if status_filter == 'no_prazo': qs_tabela = qs_tabela.filter(pct_sla__lt=80).exclude(status__iexact='concluido')
            elif status_filter == 'em_risco': qs_tabela = qs_tabela.filter(pct_sla__gte=80, pct_sla__lt=100).exclude(status__iexact='concluido')
            elif status_filter == 'estourado': qs_tabela = qs_tabela.filter(pct_sla__gte=100).exclude(status__iexact='concluido')
            elif status_filter == 'agendado': qs_tabela = qs_tabela.filter(agendamentos__status__iexact='pendente', agendamentos__tipo_pausa='agendamento').distinct()
            else: qs_tabela = qs_tabela.filter(status__iexact=status_filter)

        if tipo_filter and tipo_filter != 'todos':
            qs_tabela = qs_tabela.filter(tipo_chamado__iexact=tipo_filter)

        if busca:
            qs_tabela = qs_tabela.filter(
                Q(ticket__icontains=busca) | Q(sn__icontains=busca) | Q(cidade__icontains=busca) | Q(modelo_equipamento__icontains=busca)
            )

        total_registros = qs_tabela.count()
        pagina_int = int(pagina) if str(pagina).isdigit() else 1
        inicio = (pagina_int - 1) * limite
        fim = inicio + limite
        
        resultado = []
        for c in qs_tabela[inicio:fim]:
            
            # ---> CORREÇÃO AQUI: Recalcula dinamicamente para exibição, mesmo que já esteja finalizado <---
            horas_consumidas_reais = ChamadoRFBService.calcular_consumo_sla(c)
            
            # Se for um registro antigo salvo como 0, ele conserta no banco silenciosamente
            if float(getattr(c, 'horas_consumidas', 0) or 0) != horas_consumidas_reais:
                c.horas_consumidas = horas_consumidas_reais
                c.save(update_fields=['horas_consumidas'])

            limite_sla = 72 if getattr(c, 'is_metropolitana', False) else 120
            agendamentos = c.agendamentos.all()
            fim_ref = getattr(c, 'data_conclusao', None) if str(getattr(c, 'status', '')).lower() == 'concluido' and getattr(c, 'data_conclusao', None) else django_timezone.now()
            
            horas_pausadas = ChamadoRFBService.calcular_horas_pausadas(c, fim_ref)
            limite_efetivo_com_pausa = limite_sla + int(horas_pausadas)
            expiracao = ChamadoRFBService.calcular_data_expiracao(getattr(c, 'data_abertura', django_timezone.now()), limite_efetivo_com_pausa)
            
            ultimo_agendamento_pendente = ""
            data_agendamento_iso = None
            agendamentos_pendentes = [a for a in agendamentos if str(getattr(a, 'status', '')).strip().lower() == 'pendente']
            
            if agendamentos_pendentes:
                ultimo = sorted(agendamentos_pendentes, key=lambda x: getattr(x, 'id_agendamento', getattr(x, 'id', 0)))[-1]
                if getattr(ultimo, 'tipo_pausa', '') == 'sem_resposta':
                    dt_val = getattr(ultimo, 'data_inicio_tentativas', None)
                    dt_str = django_timezone.localtime(dt_val).strftime('%d/%m às %H:%M') if dt_val else '--'
                    ultimo_agendamento_pendente = f"Falta Resposta ({dt_str})"
                    data_agendamento_iso = dt_val.isoformat() if hasattr(dt_val, 'isoformat') else None
                else:
                    dt_val = getattr(ultimo, 'data_agendamento', None)
                    dt_str = django_timezone.localtime(dt_val).strftime('%d/%m às %H:%M') if dt_val else '--'
                    ultimo_agendamento_pendente = f"Visita: {dt_str}"
                    data_agendamento_iso = dt_val.isoformat() if hasattr(dt_val, 'isoformat') else None
            
            resultado.append({
                'id': getattr(c, 'id_chamado', getattr(c, 'id', None)),
                'ticket': getattr(c, 'ticket', '--'),
                'data_abertura': c.data_abertura.isoformat() if hasattr(c.data_abertura, 'isoformat') else None,
                'estado': getattr(c, 'estado', '--'),
                'cidade': getattr(c, 'cidade', '--'),
                'modelo_equipamento': getattr(c, 'modelo_equipamento', '--'),
                'sn': getattr(c, 'sn', '--'),
                'descricao_defeito': getattr(c, 'descricao_defeito', '--'),
                'status': getattr(c, 'status', '--'),
                'limite_sla': limite_sla,
                'horas_consumidas': float(horas_consumidas_reais),
                'data_expiracao': expiracao.isoformat() if hasattr(expiracao, 'isoformat') else None,
                'is_metropolitana': getattr(c, 'is_metropolitana', False),
                'resolucao_caso': getattr(c, 'resolucao_caso', ''),
                'sem_intervencao_tecnica': bool(getattr(c, 'sem_intervencao_tecnica', False)),
                'peca_utilizada': getattr(c, 'peca_utilizada', 'Nenhuma'),
                'tipo_chamado': getattr(c, 'tipo_chamado', 'Não informado'),
                'data_conclusao': c.data_conclusao.isoformat() if hasattr(c, 'data_conclusao') and c.data_conclusao else None,
                'observacao': getattr(c, 'observacao', ''),
                'ultimo_agendamento_pendente': ultimo_agendamento_pendente,
                'data_agendamento_pendente': data_agendamento_iso,
                # ---> ADICIONE ESTAS LINHAS <---
                'analista_responsavel_id': getattr(c, 'analista_responsavel_id', None),
                'analista_responsavel_nome': c.analista_responsavel.nome if getattr(c, 'analista_responsavel', None) else None,
                'tecnico_atendimento_id': getattr(c, 'tecnico_atendimento_id', None),
                'equipamento_id': getattr(c, 'equipamento_id', None),
                'tecnico_atendimento_nome': c.tecnico_atendimento.nome if getattr(c, 'tecnico_atendimento', None) else None,
            })
            
        return {
            'dados': resultado,
            'dashboard': dash_global,
            'total': total_registros,
            'pagina_atual': pagina_int,
            'total_paginas': (total_registros // limite) + (1 if total_registros % limite > 0 else 0)
        }
    @staticmethod
    def calcular_data_expiracao(inicio, limite_horas):
        if not inicio:
            return None
            
        data_calc = inicio
        horas_restantes = limite_horas
        
        while horas_restantes > 0:
            data_calc += timedelta(hours=1)
            dia_str = data_calc.strftime('%Y-%m-%d')
            datas_excluidas = get_feriados_nacionais(data_calc.year)
            
            if data_calc.weekday() < 5 and dia_str not in datas_excluidas: 
                horas_restantes -= 1
                
        return data_calc

    @staticmethod
    def calcular_horas_uteis(inicio, fim):
        if inicio >= fim:
            return 0.0
            
        total_horas = 0.0
        dia_atual = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
        fim_dia = fim.replace(hour=0, minute=0, second=0, microsecond=0)
        
        anos_envolvidos = range(inicio.year, fim.year + 1)
        datas_excluidas = []
        for ano in anos_envolvidos: 
            datas_excluidas.extend(get_feriados_nacionais(ano))
            
        while dia_atual <= fim_dia:
            dia_str = dia_atual.strftime('%Y-%m-%d')
            if dia_atual.weekday() < 5 and dia_str not in datas_excluidas:
                if dia_atual == inicio.replace(hour=0, minute=0, second=0, microsecond=0) and dia_atual == fim_dia:
                    total_horas += (fim - inicio).total_seconds() / 3600.0
                elif dia_atual == inicio.replace(hour=0, minute=0, second=0, microsecond=0):
                    total_horas += (dia_atual + timedelta(days=1) - inicio).total_seconds() / 3600.0
                elif dia_atual == fim_dia:
                    total_horas += (fim - fim_dia).total_seconds() / 3600.0
                else: 
                    total_horas += 24.0
            dia_atual += timedelta(days=1)
            
        return total_horas

    @staticmethod
    def calcular_horas_pausadas(chamado: ChamadoRFB, fim_referencia) -> float:
        agendamentos_validos = [a for a in chamado.agendamentos.all() if str(a.status).strip().lower() != 'frustrado']
        intervalos = []
        
        for p in agendamentos_validos:
            if not p.data_registro_pausa: 
                continue
                
            inicio_pausa = p.data_registro_pausa
            
            if str(p.status).strip().lower() in ['realizado', 'concluido']: 
                fim_pausa = p.data_resposta_cliente or p.data_agendamento or fim_referencia
            else: 
                fim_pausa = fim_referencia
                
            if fim_pausa and fim_pausa > fim_referencia: 
                fim_pausa = fim_referencia
                
            if fim_pausa and fim_pausa > inicio_pausa: 
                intervalos.append((inicio_pausa, fim_pausa))
                
        intervalos_merged = []
        if intervalos:
            intervalos.sort(key=lambda x: x[0])
            inicio_atual, fim_atual = intervalos[0]
            for prox_inicio, prox_fim in intervalos[1:]:
                if prox_inicio <= fim_atual: 
                    fim_atual = max(fim_atual, prox_fim)
                else: 
                    intervalos_merged.append((inicio_atual, fim_atual))
                    inicio_atual, fim_atual = prox_inicio, prox_fim
            intervalos_merged.append((inicio_atual, fim_atual))
            
        horas_pausadas = 0.0
        for inicio, fim in intervalos_merged: 
            horas_pausadas += ChamadoRFBService.calcular_horas_uteis(inicio, fim)
            
        return horas_pausadas

    @staticmethod
    def calcular_consumo_sla(chamado: ChamadoRFB) -> float:
        fim_referencia = chamado.data_conclusao if chamado.status == 'concluido' and chamado.data_conclusao else django_timezone.now()
        consumo_real = ChamadoRFBService.calcular_horas_uteis(chamado.data_abertura, fim_referencia) - ChamadoRFBService.calcular_horas_pausadas(chamado, fim_referencia)
        return consumo_real if consumo_real > 0 else 0.0
