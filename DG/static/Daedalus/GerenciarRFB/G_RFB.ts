/// <reference path="../BaseUI.ts" />


(() => {
    class G_RFBUI extends BaseUI {
        private btnSalvar: HTMLButtonElement;
        private btnLimpar: HTMLButtonElement;
        private btnExportar: HTMLButtonElement;
        private form: HTMLFormElement;
        private selectEstado: HTMLSelectElement;
        private selectCidade: HTMLSelectElement;
        
        private containerChamados: HTMLElement;
        private inputPesquisa: HTMLInputElement;
        private selectFiltroStatus: HTMLSelectElement;
        private selectFiltroTipo: HTMLSelectElement; 
        private selectFiltroEstado: HTMLSelectElement;   
        private selectFiltroAnalista: HTMLSelectElement; 
        
        private btnViewTable: HTMLButtonElement;
        private btnViewKanban: HTMLButtonElement;
        private tableView: HTMLElement;
        private kanbanView: HTMLElement;
        private currentView: 'table' | 'kanban' = 'table';
        
        private paginaAtual: number = 1;
        private totalPaginas: number = 1;
        private btnPrevPage: HTMLButtonElement;
        private btnNextPage: HTMLButtonElement;
        private infoPaginacao: HTMLElement;
        private searchTimeout: number | null = null;
        private chamadosBaixadosCache: any[] = []; 

        private modalAgendamento: HTMLElement;
        private formNovoAgendamento: HTMLFormElement;
        private listaAgendamentos: HTMLElement;
        private formFinalizar: HTMLFormElement;

        private chamadoAgendamentoAberto: number | null = null;
        private idAtual: number | null = null;
        private modelosRFB: any[] = [];
        private chamadoFinalizando: any = null;

        private instanciaGraficoSLA: any = null;
        private instanciaGraficoEquip: any = null;
        private instanciaGraficoGeo: any = null;
        private instanciaGraficoPecas: any = null; 

        private btnNotificacoes: HTMLElement;
        private dropdownNotificacoes: HTMLElement;
        private listaNotificacoes: HTMLElement;

        constructor() {
            super(); 
            
            this.btnSalvar = document.getElementById('btn-salvar-chamado') as HTMLButtonElement;
            this.btnLimpar = document.getElementById('btn-limpar') as HTMLButtonElement;
            this.btnExportar = document.getElementById('btn-exportar') as HTMLButtonElement;
            
            this.form = document.getElementById('form-cadastro-chamado') as HTMLFormElement;
            this.formFinalizar = document.getElementById('form-finalizar-chamado') as HTMLFormElement;
            
            this.selectEstado = document.getElementById('estado') as HTMLSelectElement;
            this.selectCidade = document.getElementById('cidade') as HTMLSelectElement;

            this.containerChamados = document.getElementById('tabela-chamados-rfb') as HTMLElement;
            this.inputPesquisa = document.getElementById('pesquisa-chamado') as HTMLInputElement;
            this.selectFiltroStatus = document.getElementById('filtro-status') as HTMLSelectElement;
            this.selectFiltroTipo = document.getElementById('filtro-tipo') as HTMLSelectElement; 
            
            this.selectFiltroEstado = document.getElementById('filtro-estado') as HTMLSelectElement;
            this.selectFiltroAnalista = document.getElementById('filtro-analista') as HTMLSelectElement;
            
            this.btnPrevPage = document.getElementById('btn-pagina-anterior') as HTMLButtonElement;
            this.btnNextPage = document.getElementById('btn-pagina-proxima') as HTMLButtonElement;
            this.infoPaginacao = document.getElementById('info-paginacao') as HTMLElement;

            this.modalAgendamento = document.getElementById('modal-agendamento') as HTMLElement;
            this.formNovoAgendamento = document.getElementById('form-novo-agendamento') as HTMLFormElement;
            this.listaAgendamentos = document.getElementById('lista-agendamentos') as HTMLSelectElement;

            this.btnViewTable = document.getElementById('btn-view-table') as HTMLButtonElement;
            this.btnViewKanban = document.getElementById('btn-view-kanban') as HTMLButtonElement;
            this.tableView = document.getElementById('table-view') as HTMLElement;
            this.kanbanView = document.getElementById('kanban-view') as HTMLElement;

            this.btnNotificacoes = document.getElementById('btn-notificacoes') as HTMLElement;
            this.dropdownNotificacoes = document.getElementById('dropdown-notificacoes') as HTMLElement;
            this.listaNotificacoes = document.getElementById('lista-notificacoes') as HTMLElement;

            this.aplicarRegrasDeAcesso();
            this.carregarFuncionarios(); 
            this.iniciarEventos();
            this.carregarTecnicos();
            this.carregarModelosRFB();
            this.carregarChamados();
        }

        private async carregarFuncionarios(): Promise<void> {
            try {
                const req = await fetch('/api/funcionario/'); 
                if (req.ok) {
                    const res = await req.json();
                    const lista = res.dados || res; 
                    
                    const selectAnalista = document.getElementById('analista_responsavel') as HTMLSelectElement;
                    let htmlOptions = '<option value="" disabled selected>Selecione...</option>';
                    let htmlFiltroAnalista = '<option value="todos">Todos os Analistas</option>';

                    lista.forEach((func: any) => {
                        const funcId = func.id_funcionario || func.id;
                        htmlOptions += `<option value="${funcId}">${escapeHtml(func.nome)}</option>`;
                        htmlFiltroAnalista += `<option value="${funcId}">${escapeHtml(func.nome)}</option>`;
                    });

                    if (selectAnalista) selectAnalista.innerHTML = htmlOptions;
                    if (this.selectFiltroAnalista) this.selectFiltroAnalista.innerHTML = htmlFiltroAnalista;
                }
            } catch (error) {
                console.warn('Endpoint de funcionários inacessível', error);
            }
        }

        private async carregarTecnicos(): Promise<void> {
            try {
                const req = await fetch('/api/tecnico/'); 
                if (req.ok) {
                    const res = await req.json();
                    const lista = res.dados || res; 
                    
                    const selectTecnico = document.getElementById('finalizacao_tecnico') as HTMLSelectElement;
                    let htmlOptions = '<option value="" disabled selected>Selecione...</option>';
                    
                    lista.forEach((tec: any) => {
                        const tecId = tec.id_tecnico || tec.id;
                        htmlOptions += `<option value="${tecId}">${escapeHtml(tec.nome)}</option>`;
                    });

                    if (selectTecnico) selectTecnico.innerHTML = htmlOptions;
                }
            } catch (error) {
                console.warn('Endpoint de técnicos inacessível', error);
            }
        }

        private aplicarRegrasDeAcesso(): void {
            const cargo = (window as any).CARGO_USUARIO_SESSAO || '';
            const ehGestao = cargo === 'ADMINISTRADOR' || cargo === 'GESTOR' || cargo === 'COORDENADOR' || cargo === 'GERENTE';

            if (!ehGestao) {
                const bloqueio = document.getElementById('bloqueio-acesso');
                if (bloqueio) {
                    bloqueio.classList.remove('hidden');
                }

                this.form.querySelectorAll('input, select').forEach(el => {
                    (el as HTMLInputElement).disabled = true;
                });
                
                this.btnSalvar.disabled = true;
                this.btnLimpar.disabled = true;

                const containerExportar = document.getElementById('container-exportar');
                if (containerExportar) {
                    containerExportar.classList.add('hidden');
                }
            }
        }

        private iniciarEventos(): void {
            if (this.btnSalvar) {
                this.btnSalvar.addEventListener('click', (e) => { 
                    e.preventDefault(); 
                    if(this.form.checkValidity()) {
                        this.salvarChamado(); 
                    } else {
                        this.form.reportValidity();
                    }
                });
            }
            
            if (this.btnLimpar) {
                this.btnLimpar.addEventListener('click', () => {
                    this.limparFormulario();
                });
            }
            
            if (this.btnExportar) {
                this.btnExportar.addEventListener('click', () => {
                    this.exportarParaCSV();
                });
            }

            const btnRelatorio = document.getElementById('btn-relatorio-fechamento') as HTMLButtonElement;
            if (btnRelatorio) {
                btnRelatorio.addEventListener('click', () => {
                    this.gerarRelatorioFechamento();
                });
            }

            if (this.formFinalizar) {
                this.formFinalizar.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    await this.enviarFinalizacao();
                });
            }

            this.iniciarModelosRFB();
            this.iniciarPecasDaFinalizacao();

            if (this.btnNotificacoes && this.dropdownNotificacoes) {
                this.btnNotificacoes.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.dropdownNotificacoes.classList.toggle('hidden');
                });
                
                document.addEventListener('click', (e) => {
                    if (!this.btnNotificacoes.contains(e.target as Node) && !this.dropdownNotificacoes.contains(e.target as Node)) {
                        this.dropdownNotificacoes.classList.add('hidden');
                    }
                });
            }

            const inputSN = document.getElementById('sn') as HTMLInputElement;
            if (inputSN) {
                inputSN.addEventListener('blur', async () => {
                    const snVal = inputSN.value.trim();
                    if (!snVal) return;

                    try {
                        const req = await fetch(`/api/chamados-rfb/?q=${escapeHtml(snVal)}`);
                        const res = await req.json();

                        if (res.status === 'sucesso') {
                            const reincidentes = res.dados.filter((c: any) => c.sn.toUpperCase() === snVal.toUpperCase() && c.id !== this.idAtual);
                            
                            if (reincidentes.length > 0) {
                                const ultimo = reincidentes[0];
                                Swal.fire({
                                    title: '⚠️ Alerta de Reincidência',
                                    html: `Este equipamento (SN: <b>${escapeHtml(snVal)}</b>) já possui histórico no sistema!<br><br>
                                           <div style="text-align: left; background: #0f172a; padding: 10px; border-radius: 5px; color: #cbd5e1; font-size: 12px; margin-top: 10px; border: 1px solid #334155;">
                                              <b style="color: #38bdf8;">Último Ticket:</b> ${escapeHtml(ultimo.ticket)} (${ultimo.status.toUpperCase()})<br>
                                              <b style="color: #38bdf8;">Defeito:</b> ${escapeHtml(ultimo.descricao_defeito)}<br>
                                           </div>`,
                                    icon: 'warning',
                                    confirmButtonColor: '#f59e0b',
                                    confirmButtonText: 'Estou Ciente'
                                });
                            }
                        }
                    } catch (e) {
                        console.error('Falha ao checar reincidência de SN', e);
                    }
                });
            }

            if (this.btnViewTable) {
                this.btnViewTable.addEventListener('click', () => this.alternarView('table'));
            }
            
            if (this.btnViewKanban) {
                this.btnViewKanban.addEventListener('click', () => this.alternarView('kanban'));
            }

            if (this.inputPesquisa) {
                this.inputPesquisa.addEventListener('input', () => {
                    if (this.searchTimeout) clearTimeout(this.searchTimeout);
                    this.searchTimeout = window.setTimeout(() => {
                        this.paginaAtual = 1; 
                        this.carregarChamados();
                    }, 600); 
                });
            }

            if (this.selectFiltroStatus) {
                this.selectFiltroStatus.addEventListener('change', () => {
                    this.paginaAtual = 1;
                    this.carregarChamados();
                });
            }
            
            if (this.selectFiltroTipo) {
                this.selectFiltroTipo.addEventListener('change', () => {
                    this.paginaAtual = 1;
                    this.carregarChamados();
                });
            }

            if (this.selectFiltroEstado) {
                this.selectFiltroEstado.addEventListener('change', () => {
                    this.paginaAtual = 1;
                    this.carregarChamados();
                });
            }

            if (this.selectFiltroAnalista) {
                this.selectFiltroAnalista.addEventListener('change', () => {
                    this.paginaAtual = 1;
                    this.carregarChamados();
                });
            }

            if (this.btnPrevPage) {
                this.btnPrevPage.addEventListener('click', () => {
                    if (this.paginaAtual > 1) { 
                        this.paginaAtual--; 
                        this.carregarChamados(); 
                    }
                });
            }
            
            if (this.btnNextPage) {
                this.btnNextPage.addEventListener('click', () => {
                    if (this.paginaAtual < this.totalPaginas) { 
                        this.paginaAtual++; 
                        this.carregarChamados(); 
                    }
                });
            }

            if (this.selectEstado) {
                this.selectEstado.addEventListener('change', () => {
                    const uf = this.selectEstado.value;
                    if (uf) {
                        this.carregarCidadesIBGE(uf);
                    } else {
                        this.selectCidade.innerHTML = '<option value="" disabled selected></option>';
                        this.selectCidade.disabled = true;
                        this.selectCidade.classList.remove('has-value');
                    }
                });
            }

            if (this.formNovoAgendamento) {
                this.formNovoAgendamento.addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.salvarNovoAgendamento();
                });
            }

            const btnCancelarEdicaoAgend = document.getElementById('btn-cancelar-edicao-agendamento');
            if (btnCancelarEdicaoAgend) {
                btnCancelarEdicaoAgend.addEventListener('click', () => {
                    this.resetarFormAgendamento();
                });
            }

            const selectTipoPausa = document.getElementById('tipo_pausa') as HTMLSelectElement;
            if (selectTipoPausa) {
                selectTipoPausa.addEventListener('change', (e) => {
                    const val = (e.target as HTMLSelectElement).value;
                    const containerVisita = document.getElementById('container_data_visita');
                    const lblRegistro = document.getElementById('lbl_data_registro');
                    const inputVisita = document.getElementById('data_visita') as HTMLInputElement;
                    
                    if (val === 'agendamento') {
                        if (containerVisita) containerVisita.classList.remove('hidden');
                        if (lblRegistro) lblRegistro.innerText = 'Data do Contato (Pausa)';
                        if (inputVisita) inputVisita.required = true;
                    } else {
                        if (containerVisita) containerVisita.classList.add('hidden');
                        if (lblRegistro) lblRegistro.innerText = 'Início das Tentativas de Contato';
                        if (inputVisita) {
                            inputVisita.required = false;
                            inputVisita.value = ''; 
                        }
                    }
                });
            }

            document.querySelectorAll('.btn-fechar-modal').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const modal = (e.target as HTMLElement).closest('.fixed');
                    if (modal) {
                        modal.classList.add('hidden');
                        if (modal.id === 'modal-agendamento') this.resetarFormAgendamento();
                    }
                });
            });

            document.querySelectorAll('.btn-fechar-detalhes').forEach(btn => {
                btn.addEventListener('click', () => {
                    const modal = document.getElementById('modal-detalhes-chamado');
                    if (modal) modal.classList.add('hidden');
                });
            });

            this.inicializarZonasDropKanban();
        }

        private alternarView(mode: 'table' | 'kanban'): void {
            this.currentView = mode;
            if (mode === 'table') {
                this.kanbanView.classList.add('hidden');
                this.tableView.classList.remove('hidden');
                this.btnViewTable.classList.add('text-cyan-400', 'border-cyan-500/50', 'bg-[#1e293b]');
                this.btnViewTable.classList.remove('text-slate-400', 'border-transparent', 'bg-transparent');
                this.btnViewKanban.classList.remove('text-cyan-400', 'border-cyan-500/50', 'bg-[#1e293b]');
                this.btnViewKanban.classList.add('text-slate-400', 'border-transparent', 'bg-transparent');
            } else {
                this.tableView.classList.add('hidden');
                this.kanbanView.classList.remove('hidden');
                this.btnViewKanban.classList.add('text-cyan-400', 'border-cyan-500/50', 'bg-[#1e293b]');
                this.btnViewKanban.classList.remove('text-slate-400', 'border-transparent', 'bg-transparent');
                this.btnViewTable.classList.remove('text-cyan-400', 'border-cyan-500/50', 'bg-[#1e293b]');
                this.btnViewTable.classList.add('text-slate-400', 'border-transparent', 'bg-transparent');
            }
        }

        private async carregarChamados(): Promise<void> {
            if (this.containerChamados.children.length === 0) {
                this.containerChamados.innerHTML = '<tr><td colspan="7" class="text-center py-10"><span class="animate-pulse text-cyan-500">Sincronizando com o banco de dados...</span></td></tr>';
            }

            const status = this.selectFiltroStatus ? this.selectFiltroStatus.value : 'todos';
            const tipo = this.selectFiltroTipo ? this.selectFiltroTipo.value : 'todos';
            const estado = this.selectFiltroEstado ? this.selectFiltroEstado.value : 'todos';
            const analista = this.selectFiltroAnalista ? this.selectFiltroAnalista.value : 'todos';
            const busca = this.inputPesquisa ? this.inputPesquisa.value : '';
            
            try {
                const url = `/api/chamados-rfb/?status=${status}&tipo=${tipo}&estado=${escapeHtml(estado)}&analista=${escapeHtml(analista)}&q=${busca}&page=${this.paginaAtual}`;
                const resposta = await fetch(url);
                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    this.chamadosBaixadosCache = resultado.dados; 
                    this.totalPaginas = resultado.total_paginas;
                    this.infoPaginacao.innerText = `Mostrando página ${this.paginaAtual} de ${this.totalPaginas} (Total da Pesquisa: ${resultado.total})`;
                    
                    this.btnPrevPage.disabled = this.paginaAtual <= 1;
                    this.btnNextPage.disabled = this.paginaAtual >= this.totalPaginas;

                    this.renderizarTabela(resultado.dados);
                    this.renderizarKanban(resultado.dados);
                    this.atualizarSinoNotificacoes(resultado.dados);
                    
                    if (resultado.dashboard) {
                        this.atualizarDashboardGlobal(resultado.dashboard);
                        this.renderizarCartoesAcoesGlobais(resultado.dashboard.visitas_hoje, resultado.dashboard.abertos_sem_acao);
                    }
                }
            } catch (error) {
                Swal.fire('Erro', 'Falha ao buscar chamados no servidor.', 'error');
                this.containerChamados.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-rose-500 font-bold">Falha de rede.</td></tr>';
            }
        }

        private atualizarDashboardGlobal(dash: any): void {
            if (!dash) return;
            
            const setElementText = (id: string, text: string | number) => {
                const el = document.getElementById(id);
                if (el) el.innerText = text.toString();
            };

            setElementText('dash-abertos', dash.abertos);
            setElementText('dash-risco', dash.risco);
            setElementText('dash-estourado', dash.estourados);
            setElementText('dash-concluidos', dash.concluidos);
            setElementText('dash-no-prazo', dash.no_prazo);
            setElementText('dash-pct-no-prazo', dash.pct_no_prazo + '%');
            setElementText('dash-pct-concluidos-no-prazo', dash.pct_concluidos_no_prazo + '%');

            const ChartObj = (window as any).Chart;

            const renderDoughnut = (id: string, ref: any, labels: string[], data: number[], colors: string[]) => {
                const ctx = document.getElementById(id) as HTMLCanvasElement;
                if (ctx && ChartObj) {
                    if (ref) ref.destroy();
                    ctx.style.maxHeight = '180px';
                    return new ChartObj(ctx, {
                        type: 'doughnut',
                        data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
                        options: { 
                            responsive: true, 
                            maintainAspectRatio: false, 
                            plugins: { 
                                legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 10 }, boxWidth: 12 } } 
                            } 
                        }
                    });
                }
                return ref;
            };

            const renderBar = (id: string, ref: any, labels: string[], data: number[], color: string, label: string) => {
                const ctx = document.getElementById(id) as HTMLCanvasElement;
                if (ctx && ChartObj) {
                    if (ref) ref.destroy();
                    ctx.style.maxHeight = '180px';
                    return new ChartObj(ctx, {
                        type: 'bar',
                        data: { labels, datasets: [{ label, data, backgroundColor: color, borderRadius: 4 }] },
                        options: { 
                            responsive: true, 
                            maintainAspectRatio: false, 
                            plugins: { legend: { display: false } }, 
                            scales: { 
                                y: { beginAtZero: true, grid: { color: '#334155' }, ticks: { color: '#94a3b8', stepSize: 1 } }, 
                                x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 9 } } } 
                            } 
                        }
                    });
                }
                return ref;
            };

            this.instanciaGraficoSLA = renderDoughnut('graficoSlaStatus', this.instanciaGraficoSLA, ['Dentro do Prazo', 'Em Risco', 'Estourado'], [dash.no_prazo, dash.risco, dash.estourados], ['#10b981', '#f59e0b', '#f43f5e']);
            this.instanciaGraficoEquip = renderBar('graficoTopEquipamentos', this.instanciaGraficoEquip, dash.graficos.equips_labels, dash.graficos.equips_data, '#0ea5e9', 'Volumetria');
            this.instanciaGraficoGeo = renderBar('graficoGeoRisco', this.instanciaGraficoGeo, dash.graficos.geo_labels, dash.graficos.geo_data, '#f59e0b', 'Estouros');
            this.instanciaGraficoPecas = renderBar('graficoTopPecas', this.instanciaGraficoPecas, dash.graficos.pecas_labels, dash.graficos.pecas_data, '#a855f7', 'Peças Trocadas');
        }

        private renderizarCartoesAcoesGlobais(visitasHoje: any[], abertosSemAcao: any[]): void {
            const containerHoje = document.getElementById('cards-agendados-hoje');
            const containerAbertos = document.getElementById('cards-chamados-abertos');
            
            if (!containerHoje || !containerAbertos) return;

            containerHoje.innerHTML = '';
            containerAbertos.innerHTML = '';

            if (visitasHoje && visitasHoje.length > 0) {
                visitasHoje.forEach(c => containerHoje.appendChild(this.criarElementoCard(c, 'cyan')));
            } else {
                containerHoje.innerHTML = '<div class="text-[10px] text-slate-500 text-center py-6 font-medium">Nenhuma visita logística pendente para hoje.</div>';
            }

            if (abertosSemAcao && abertosSemAcao.length > 0) {
                abertosSemAcao.forEach(c => containerAbertos.appendChild(this.criarElementoCard(c, 'amber')));
            } else {
                containerAbertos.innerHTML = '<div class="text-[10px] text-slate-500 text-center py-6 font-medium">Nenhum chamado pendente de triagem.</div>';
            }
        }

        private criarElementoCard(chamado: any, cor: string): HTMLElement {
            const div = document.createElement('div');
            const corBorda = cor === 'cyan' ? 'border-cyan-500/30' : 'border-amber-500/30';
            const corTexto = cor === 'cyan' ? 'text-cyan-400' : 'text-amber-400';
            const icone = cor === 'cyan' ? '📅' : '⚠️';
            
            div.className = `bg-[#1e293b] border ${corBorda} rounded p-3 cursor-pointer hover:bg-[#334155] transition-colors`;
            
            div.innerHTML = `
                <div class="flex justify-between items-start mb-1.5">
                    <span class="font-bold text-white text-[11px]">${icone} ${escapeHtml(chamado.ticket)}</span>
                    <span class="text-[9px] ${corTexto} font-bold uppercase tracking-wider">${escapeHtml(chamado.cidade)}/${escapeHtml(chamado.estado)}</span>
                </div>
                <div class="text-[10px] text-slate-400 truncate mb-2">${escapeHtml(chamado.modelo_equipamento)} | SN: ${escapeHtml(chamado.sn)}</div>
                <div class="flex justify-between items-center text-[9px]">
                    <span class="bg-[#0f172a] px-2 py-0.5 rounded text-slate-300 font-medium">SLA: ${chamado.horas_consumidas.toFixed(1)}h / ${chamado.limite_sla}h</span>
                    <span class="${corTexto} font-bold uppercase">${escapeHtml(chamado.ultimo_agendamento_pendente || 'Aberto / Sem Ação')}</span>
                </div>
            `;
            
            div.addEventListener('click', () => this.abrirModalDetalhes(chamado));
            return div;
        }

        private atualizarSinoNotificacoes(dados: any[]): void {
            if (!this.listaNotificacoes || !document.getElementById('badge-notificacao')) return;

            let alertasHtml = '';
            let contadorCriticos = 0;

            dados.forEach(c => {
                if (c.status !== 'concluido') {
                    const limiteSLA = c.limite_sla || 120;
                    const horasConsumidas = typeof c.horas_consumidas === 'number' ? c.horas_consumidas : 0;
                    const percentualSLA = (horasConsumidas / limiteSLA) * 100;

                    if (percentualSLA >= 80) {
                        contadorCriticos++;
                        const isEstourado = percentualSLA >= 100;
                        const corSinal = isEstourado ? 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]' : 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]';
                        const corTexto = isEstourado ? 'text-rose-400' : 'text-amber-400';

                        alertasHtml += `
                            <div class="p-3 hover:bg-[#334155]/50 transition-colors cursor-pointer" onclick="document.getElementById('pesquisa-chamado').value = '${escapeHtml(c.ticket)}'; document.getElementById('pesquisa-chamado').dispatchEvent(new Event('input')); document.getElementById('dropdown-notificacoes').classList.add('hidden');">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="w-2 h-2 rounded-full ${corSinal} animate-pulse"></span>
                                    <span class="text-xs font-bold text-white">Ticket ${escapeHtml(c.ticket)}</span>
                                    <span class="text-[9px] ${corTexto} font-bold ml-auto">${horasConsumidas.toFixed(1)}h / ${limiteSLA}h</span>
                                </div>
                                <div class="text-[10px] text-slate-400 pl-4">${escapeHtml(c.cidade)}/${escapeHtml(c.estado)} - ${escapeHtml(c.modelo_equipamento)}</div>
                            </div>
                        `;
                    }
                }
            });

            const badge = document.getElementById('badge-notificacao') as HTMLElement;
            if (contadorCriticos > 0) {
                badge.innerText = contadorCriticos.toString();
                badge.classList.remove('hidden');
                this.listaNotificacoes.innerHTML = alertasHtml;
            } else {
                badge.classList.add('hidden');
                this.listaNotificacoes.innerHTML = '<div class="p-4 text-center text-xs text-slate-500 font-medium">Nenhum chamado em risco crítico no momento.</div>';
            }
        }

        private renderizarKanban(lista: any[]): void {
            const colAberto = document.getElementById('kb-col-aberto') as HTMLElement;
            const colAndamento = document.getElementById('kb-col-andamento') as HTMLElement;
            const colConcluido = document.getElementById('kb-col-concluido') as HTMLElement;

            if(!colAberto || !colAndamento || !colConcluido) return;

            colAberto.innerHTML = ''; 
            colAndamento.innerHTML = ''; 
            colConcluido.innerHTML = '';
            
            let counts = { aberto: 0, andamento: 0, concluido: 0 };

            lista.forEach(c => {
                const status = c.status || 'aberto';
                if(counts[status as keyof typeof counts] !== undefined) {
                    counts[status as keyof typeof counts]++;
                }

                const card = document.createElement('div');
                card.className = "kanban-card cursor-grab bg-[#1e293b] p-3 rounded-lg border border-[#334155] shadow-lg hover:border-cyan-500/50 hover:bg-[#253243] transition-all";
                card.draggable = true;
                card.setAttribute('data-id', c.id.toString());
                
                const percentualSLA = (c.horas_consumidas / (c.limite_sla || 120)) * 100;
                const corSla = percentualSLA >= 100 ? 'text-rose-400' : (percentualSLA >= 80 ? 'text-amber-400' : 'text-emerald-400');

                card.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <span class="font-bold text-white text-xs">🎫 ${escapeHtml(c.ticket)}</span>
                        <span class="text-[9px] text-slate-400 font-bold uppercase">${escapeHtml(c.cidade)}/${escapeHtml(c.estado)}</span>
                    </div>
                    <div class="text-[10px] text-slate-400 mb-2 truncate">${escapeHtml(c.modelo_equipamento)}</div>
                    <div class="flex justify-between items-center text-[9px] mb-2">
                        <span class="bg-[#0f172a] px-2 py-0.5 rounded border border-[#334155] font-bold ${corSla}">SLA: ${c.horas_consumidas.toFixed(1)}h / ${c.limite_sla}h</span>
                    </div>
                    ${c.ultimo_agendamento_pendente && status !== 'concluido' ? `
                        <div class="mt-2 text-[9px] font-bold text-cyan-300 bg-cyan-900/40 border border-cyan-500/30 px-2 py-1 rounded text-center w-full truncate">
                            ⏳ ${escapeHtml(c.ultimo_agendamento_pendente)}
                        </div>
                    ` : ''}
                `;

                card.addEventListener('dragstart', (e: DragEvent) => {
                    e.dataTransfer!.setData('text/plain', c.id.toString());
                    card.classList.add('opacity-40', 'scale-95');
                });
                
                card.addEventListener('dragend', () => {
                    card.classList.remove('opacity-40', 'scale-95');
                });
                
                card.addEventListener('dblclick', () => this.abrirModalDetalhes(c));

                if (status === 'aberto') {
                    colAberto.appendChild(card);
                } else if (status === 'andamento') {
                    colAndamento.appendChild(card);
                } else {
                    colConcluido.appendChild(card);
                }
            });

            document.getElementById('kb-count-aberto')!.innerText = counts.aberto.toString();
            document.getElementById('kb-count-andamento')!.innerText = counts.andamento.toString();
            document.getElementById('kb-count-concluido')!.innerText = counts.concluido.toString();
        }

        private inicializarZonasDropKanban(): void {
            document.querySelectorAll('.kanban-col').forEach(col => {
                col.addEventListener('dragover', (e: Event) => {
                    e.preventDefault(); 
                    (col as HTMLElement).classList.add('ring-2', 'ring-cyan-500/50', 'bg-[#1e293b]/70');
                });
                
                col.addEventListener('dragleave', (e: Event) => {
                    (col as HTMLElement).classList.remove('ring-2', 'ring-cyan-500/50', 'bg-[#1e293b]/70');
                });
                
                col.addEventListener('drop', async (e: Event) => {
                    e.preventDefault();
                    (col as HTMLElement).classList.remove('ring-2', 'ring-cyan-500/50', 'bg-[#1e293b]/70');
                    
                    const idStr = (e as DragEvent).dataTransfer!.getData('text/plain');
                    if(!idStr) return;

                    const chamado = this.chamadosBaixadosCache.find(x => x.id.toString() === idStr);
                    const novoStatus = (col as HTMLElement).getAttribute('data-status');

                    if (chamado && novoStatus && chamado.status !== novoStatus) {
                        if (novoStatus === 'concluido') {
                            this.abrirModalFinalizacao(chamado);
                        } else {
                            await this.atualizarStatusDireto(chamado.id, chamado, novoStatus);
                        }
                    }
                });
            });
        }

        private renderizarTabela(lista: any[]): void {
            this.containerChamados.innerHTML = ''; 
            const cargo = (window as any).CARGO_USUARIO_SESSAO || '';
            const ehGestao = cargo === 'ADMINISTRADOR' || cargo === 'GESTOR' || cargo === 'COORDENADOR' || cargo === 'GERENTE';

            if (lista.length === 0) {
                this.containerChamados.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-slate-500 font-medium">Nenhum chamado atende aos filtros atuais.</td></tr>';
                return;
            }

            lista.forEach((chamado: any) => {
                const limiteSLA = chamado.limite_sla || 120;
                const horasConsumidas = typeof chamado.horas_consumidas === 'number' ? chamado.horas_consumidas : 0;
                const percentualSLA = (horasConsumidas / limiteSLA) * 100;
                let percentualBarra = percentualSLA > 100 ? 100 : percentualSLA; 
                
                let corTexto = "text-emerald-400"; 
                let corBarra = "bg-emerald-500";
                
                if (percentualSLA >= 100) {
                    corTexto = "text-rose-400"; 
                    corBarra = "bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.5)]"; 
                } else if (percentualSLA >= 80) {
                    corTexto = "text-amber-400"; 
                    corBarra = "bg-amber-500";
                }

                const tr = document.createElement('tr');
                tr.className = "hover:bg-[#334155]/30 transition-colors border-b border-[#334155]/50 group cursor-pointer";
                tr.title = "Dê um duplo clique para ver todos os detalhes";
                
                tr.addEventListener('dblclick', () => {
                    this.abrirModalDetalhes(chamado);
                });
                
                let htmlStatus = '';
                if (ehGestao && chamado.status !== 'concluido') {
                    htmlStatus = `
                        <select class="select-alterar-status bg-[#0f172a] text-slate-200 border border-[#334155] rounded px-2 py-1 text-[10px] uppercase font-bold tracking-wider cursor-pointer focus:border-cyan-500 outline-none" data-id="${chamado.id}">
                            <option value="aberto" ${chamado.status === 'aberto' ? 'selected' : ''}>Aberto</option>
                            <option value="andamento" ${chamado.status === 'andamento' ? 'selected' : ''}>Em Andamento</option>
                        </select>
                    `;
                } else {
                    htmlStatus = `
                        <span class="inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider
                            ${chamado.status === 'aberto' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 
                            chamado.status === 'andamento' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 
                            'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'}">
                            ${escapeHtml(chamado.status || 'aberto')}
                        </span>
                    `;
                }

                tr.innerHTML = `
                    <td class="px-6 py-4 font-bold text-white">
                        ${escapeHtml(chamado.ticket)}
                        ${chamado.status === 'concluido' ? `<div class="text-[10px] text-emerald-400 font-normal mt-0.5">${chamado.sem_intervencao_tecnica ? '<span class="mr-1 px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 font-bold">Sem intervenção técnica</span>' : ''}Resolução: ${escapeHtml(chamado.resolucao_caso || 'N/A')}</div>` : ''}
                    </td>
                    <td class="px-6 py-4">
                        <div class="text-[10px] text-slate-500 uppercase">${escapeHtml(chamado.cidade)}/${escapeHtml(chamado.estado)}</div>
                    </td>
                    <td class="px-6 py-4">
                        <div class="text-white truncate max-w-[200px]">${escapeHtml(chamado.modelo_equipamento)}</div>
                    </td>
                    <td class="px-6 py-4 w-56">
                        <div class="flex flex-col mb-1">
                            <div class="flex justify-between items-end">
                                <span class="font-bold text-xs ${corTexto}">${horasConsumidas.toFixed(1)}h / ${limiteSLA}h</span>
                            </div>
                            <div class="w-full bg-[#0f172a] rounded-full h-2 mt-1 mb-1">
                                <div class="${corBarra} h-1.5 rounded-full" style="width: ${percentualBarra}%"></div>
                            </div>
                            ${chamado.status !== 'concluido' 
                                ? `<span class="text-[10px] ${percentualSLA >= 80 ? 'text-rose-400 font-bold animate-pulse' : 'text-slate-400'}">Expira: ${chamado.data_expiracao ? new Date(chamado.data_expiracao).toLocaleString('pt-BR', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'}) : '--'}</span>` 
                                : `<span class="text-[10px] text-emerald-500 font-bold uppercase tracking-wider">Fechado em: ${chamado.data_conclusao ? new Date(chamado.data_conclusao).toLocaleDateString('pt-BR') : '--'}</span>`
                            }
                            
                            ${chamado.ultimo_agendamento_pendente ? `
                                <div class="mt-2 text-[9px] font-bold text-cyan-300 bg-cyan-900/40 border border-cyan-500/30 px-2 py-1 rounded w-max tracking-wide flex items-center gap-1.5">
                                    <span class="animate-pulse h-1.5 w-1.5 bg-cyan-400 rounded-full inline-block"></span>
                                    ${escapeHtml(chamado.ultimo_agendamento_pendente)}
                                </div>
                            ` : ''}
                        </div>
                    </td>
                    <td class="px-6 py-4">
                        ${chamado.status !== 'concluido' 
                            ? (ehGestao 
                                ? `<input type="text" class="input-observacao w-full min-w-[120px] bg-[#0f172a] text-amber-400 border border-[#334155] rounded px-2 py-1.5 text-[10px] focus:border-amber-500 outline-none placeholder:text-slate-600 transition-colors" data-id="${chamado.id}" value="${escapeHtml(chamado.observacao || '')}" placeholder="Nota rápida...">`
                                : `<span class="text-[10px] text-amber-400 block max-w-[120px] truncate" title="${escapeHtml(chamado.observacao || '')}">${escapeHtml(chamado.observacao || '--')}</span>`
                            )
                            : '<span class="text-[10px] text-slate-600 italic">--</span>'
                        }
                    </td>
                    <td class="px-6 py-4 text-center">
                        ${htmlStatus}
                    </td>
                    <td class="px-4 py-4 w-48 align-middle sticky right-0 bg-[#1e293b] group-hover:bg-[#253243] shadow-[-5px_0_15px_rgba(0,0,0,0.4)] transition-colors z-10">
                        <div class="flex flex-col gap-2 justify-center">
                            ${ehGestao && chamado.status !== 'concluido' ? `
                                <div class="flex gap-1.5 justify-between">
                                    <button class="btn-editar flex-1 bg-[#334155] hover:bg-amber-600 text-white px-2 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-colors shadow-sm" title="Editar">Editar</button>
                                    <button class="btn-finalizar flex-1 bg-emerald-600 hover:bg-emerald-500 text-white px-2 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-colors shadow-sm" title="Finalizar Ticket">Finalizar</button>
                                </div>
                            ` : ''}
                            <button class="btn-agendar bg-cyan-900/40 text-cyan-400 border border-cyan-500/50 hover:bg-cyan-600 hover:text-white px-2 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-all shadow-sm w-full">Histórico / Pausas</button>
                        </div>
                    </td>
                `;

                if (ehGestao) {
                    const selectStatus = tr.querySelector('.select-alterar-status') as HTMLSelectElement;
                    if (selectStatus) {
                        selectStatus.addEventListener('click', (e) => e.stopPropagation()); 
                        selectStatus.addEventListener('change', async (e) => {
                            const novoStatus = (e.target as HTMLSelectElement).value;
                            await this.atualizarStatusDireto(chamado.id, chamado, novoStatus);
                        });
                    }

                    const inputObs = tr.querySelector('.input-observacao') as HTMLInputElement;
                    if (inputObs) {
                        inputObs.addEventListener('click', (e) => e.stopPropagation()); 
                        inputObs.addEventListener('change', async (e) => {
                            const novaObs = (e.target as HTMLInputElement).value;
                            await this.atualizarObservacaoDireto(chamado.id, chamado, novaObs);
                        });
                    }

                    const btnFinalizar = tr.querySelector('.btn-finalizar') as HTMLButtonElement;
                    if(btnFinalizar) {
                        btnFinalizar.addEventListener('click', (e) => { e.stopPropagation(); this.abrirModalFinalizacao(chamado); });
                    }

                    const btnEditar = tr.querySelector('.btn-editar') as HTMLButtonElement;
                    if(btnEditar) {
                        btnEditar.addEventListener('click', (e) => { e.stopPropagation(); this.prepararEdicao(chamado); });
                    }
                }

                const btnAgendar = tr.querySelector('.btn-agendar') as HTMLButtonElement;
                if(btnAgendar) {
                    btnAgendar.addEventListener('click', (e) => { e.stopPropagation(); this.abrirModalAgendamento(chamado.id, chamado.ticket); });
                }

                this.containerChamados.appendChild(tr);
            });
        }

        private async atualizarObservacaoDireto(chamadoId: number, chamadoAtual: any, novaObs: string): Promise<void> {
            try {
                const dados = {
                    id: chamadoId,
                    observacao: novaObs,
                    update_parcial: true
                };
                const req = await fetch('/api/chamados-rfb/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });
                const res = await req.json();
                if (res.status !== 'sucesso') {
                    Swal.fire('Erro', 'Erro ao salvar anotação: ' + res.mensagem, 'error');
                } else {
                    Swal.fire({ title: 'Salvo', icon: 'success', toast: true, position: 'top-end', showConfirmButton: false, timer: 1500 });
                }
            } catch (error) {
                Swal.fire('Erro', 'Erro de conexão ao anotar.', 'error');
            }
        }

        private async abrirModalDetalhes(chamado: any): Promise<void> {
            const modal = document.getElementById('modal-detalhes-chamado');
            if (!modal) return;

            const setTexto = (id: string, texto: string) => {
                const elemento = document.getElementById(id);
                if (elemento) elemento.innerText = texto;
            };

            setTexto('detalhe-modal-title', `Detalhes do Chamado - Ticket: ${escapeHtml(chamado.ticket)}`);
            setTexto('detalhe-ticket', chamado.ticket || '--');
            setTexto('detalhe-status', chamado.status || '--');
            setTexto('detalhe-data', chamado.data_abertura ? new Date(chamado.data_abertura).toLocaleString('pt-BR') : '--');
            setTexto('detalhe-local', `${escapeHtml(chamado.cidade || '--')} / ${escapeHtml(chamado.estado || '--')}`);
            setTexto('detalhe-equipamento', chamado.modelo_equipamento || '--');
            setTexto('detalhe-sn', chamado.sn || '--');
            setTexto('detalhe-defeito', chamado.descricao_defeito || 'Nenhum defeito detalhado.');
            setTexto('detalhe-resolucao', chamado.resolucao_caso || 'Não informada / Em aberto');
            setTexto('detalhe-peca', chamado.peca_utilizada || 'Nenhuma peça utilizada');
            setTexto('detalhe-tipo-chamado', chamado.tipo_chamado || 'Não classificado');
            setTexto('detalhe-sla', `${chamado.horas_consumidas.toFixed(1)}h / ${chamado.limite_sla}h`);
            setTexto('detalhe-observacao', chamado.observacao || 'Nenhuma observação registrada.');
            
            setTexto('detalhe-analista', chamado.analista_responsavel_nome || 'Não Atribuído');
            setTexto('detalhe-tecnico', chamado.sem_intervencao_tecnica ? 'Sem intervenção técnica' : (chamado.tecnico_atendimento_nome || 'Não Atribuído'));

            const containerHistorico = document.getElementById('detalhe-historico-agendamentos');
            if (containerHistorico) {
                containerHistorico.innerHTML = '<span class="text-xs text-slate-400 animate-pulse">Buscando histórico logístico...</span>';
                try {
                    const req = await fetch(`/api/chamados-rfb/${chamado.id}/agendamentos/`);
                    const res = await req.json();
                    
                    if (res.status === 'sucesso' && res.dados.length > 0) {
                        let html = '';
                        res.dados.forEach((a: any) => {
                            const ehSemResposta = a.tipo_pausa === 'sem_resposta';
                            const dataPrincipal = a.data_agendamento || a.data_inicio_tentativas;
                            const labelData = ehSemResposta ? 'Tentativas desde:' : 'Agendado para:';
                            let corStatus = a.status === 'pendente' ? 'text-blue-400' : (a.status === 'realizado' ? 'text-emerald-400' : 'text-rose-400');

                            html += `
                                <div class="bg-[#0f172a] border border-[#334155] rounded p-2 text-[10px]">
                                    <div class="flex justify-between items-center mb-1">
                                        <span class="font-bold text-white uppercase tracking-wider">${ehSemResposta ? 'Falta de Resposta' : 'Visita Técnica'}</span>
                                        <span class="uppercase font-bold ${corStatus}">${a.status}</span>
                                    </div>
                                    <div class="text-slate-400 grid grid-cols-2 gap-2 mt-1">
                                        <div><span class="block text-[#64748b]">Pausado em:</span> ${a.data_registro_pausa ? new Date(a.data_registro_pausa).toLocaleString('pt-BR') : '--'}</div>
                                        <div><span class="block text-[#64748b]">${labelData}</span> ${dataPrincipal ? new Date(dataPrincipal).toLocaleString('pt-BR') : '--'}</div>
                                    </div>
                                </div>
                            `;
                        });
                        containerHistorico.innerHTML = html;
                    } else {
                        containerHistorico.innerHTML = '<span class="text-[10px] text-slate-500">Nenhuma pausa ou agendamento registrado.</span>';
                    }
                } catch (e) {
                    containerHistorico.innerHTML = '<span class="text-xs text-rose-500">Erro ao carregar o histórico.</span>';
                }
            }
            
            modal.classList.remove('hidden');
        }

        // ------------------------------------------------------------ modelos do RFB (vindos do banco)
        private async carregarModelosRFB(): Promise<void> {
            try {
                const r = await (await fetch('/api/rfb/modelos/')).json();
                if (r.status !== 'sucesso') return;
                this.modelosRFB = r.dados;
                const sel = document.getElementById('modelo_equipamento') as HTMLSelectElement;
                const atual = sel.value;
                sel.innerHTML = '<option value="" disabled selected></option>' + this.modelosRFB.map((m: any) =>
                    `<option value="${Number(m.id)}">${escapeHtml(m.modelo)}</option>`).join('');
                sel.value = atual;
                sel.required = true;
            } catch (e) { /* o formulário continua, mas sem a lista de modelos */ }
        }

        /** Mostra o modelo do chamado ao editar. Se o modelo saiu do RFB ou não tem cadastro, ele continua visível. */
        private definirModeloNoFormulario(chamado: any): void {
            const sel = document.getElementById('modelo_equipamento') as HTMLSelectElement;
            sel.querySelectorAll('option[data-extra]').forEach((o) => o.remove());
            sel.required = true;
            if (chamado.equipamento_id && [...sel.options].some((o) => o.value === String(chamado.equipamento_id))) {
                sel.value = String(chamado.equipamento_id);
                return;
            }
            const extra = new Option(`${chamado.modelo_equipamento || ''}${chamado.equipamento_id ? ' (fora da lista do RFB)' : ' (sem cadastro)'}`, chamado.equipamento_id ? String(chamado.equipamento_id) : '');
            extra.setAttribute('data-extra', '1');
            sel.appendChild(extra);
            sel.value = extra.value;
            if (!chamado.equipamento_id) sel.required = false;   // chamado antigo: mantém o texto que já tinha
        }

        private iniciarModelosRFB(): void {
            const botao = document.getElementById('btn-modelos-rfb');
            const cargo = (window as any).CARGO_USUARIO_SESSAO || '';
            if (botao && (cargo === 'ADMINISTRADOR' || cargo === 'GESTOR')) {
                botao.classList.remove('hidden');
                botao.addEventListener('click', () => this.abrirModalModelosRFB());
            }
            document.getElementById('btn-add-modelo-rfb')?.addEventListener('click', async () => {
                const sel = document.getElementById('sel-add-modelo-rfb') as HTMLSelectElement;
                if (!sel.value) { Swal.fire('Aviso', 'Selecione um modelo para adicionar.', 'warning'); return; }
                await this.alterarModeloRFB(Number(sel.value), true);
            });
            document.getElementById('lista-modelos-rfb')?.addEventListener('click', async (e) => {
                const b = (e.target as HTMLElement).closest('[data-retirar]') as HTMLElement | null;
                if (!b) return;
                const ok = await Swal.fire({ title: 'Retirar do RFB?', text: 'O modelo some das listas do RFB, mas não é apagado e os chamados antigos continuam.', icon: 'warning',
                    showCancelButton: true, confirmButtonColor: '#0891b2', cancelButtonColor: '#64748b', confirmButtonText: 'Sim, retirar', cancelButtonText: 'Cancelar' });
                if (ok.isConfirmed) await this.alterarModeloRFB(Number(b.dataset.retirar), false);
            });
        }

        private async abrirModalModelosRFB(): Promise<void> {
            document.getElementById('modal-modelos-rfb')!.classList.remove('hidden');
            await this.desenharModelosRFB();
        }

        private async desenharModelosRFB(dados?: any[]): Promise<void> {
            const lista = document.getElementById('lista-modelos-rfb') as HTMLElement;
            try {
                let todos = dados;
                if (!todos) {
                    const r = await (await fetch('/api/rfb/modelos/?todos=1')).json();
                    if (r.status !== 'sucesso') { lista.textContent = r.mensagem; return; }
                    todos = r.dados;
                }
                const noRfb = todos!.filter((m: any) => m.rfb);
                lista.innerHTML = noRfb.length ? noRfb.map((m: any) => `
                    <div class="flex items-center justify-between gap-3 bg-[#0f172a] border border-[#334155] rounded-lg px-3 py-2">
                        <div class="min-w-0"><div class="text-sm font-semibold text-slate-100 truncate">${escapeHtml(m.modelo)}</div>
                            <div class="text-[11px] text-slate-500">PN ${escapeHtml(m.pn)} · ${Number(m.total_pecas)} peça(s) cadastrada(s)</div></div>
                        <button type="button" data-retirar="${Number(m.id)}" class="text-xs px-3 py-1.5 rounded-lg bg-rose-900/40 text-rose-300 hover:bg-rose-600 hover:text-white font-semibold transition-colors">Retirar</button>
                    </div>`).join('') : '<p class="text-xs text-slate-500">Nenhum modelo no RFB. Adicione abaixo.</p>';
                const sel = document.getElementById('sel-add-modelo-rfb') as HTMLSelectElement;
                sel.innerHTML = '<option value="">Selecione um modelo cadastrado...</option>' + todos!.filter((m: any) => !m.rfb)
                    .map((m: any) => `<option value="${Number(m.id)}">${escapeHtml(m.modelo)} (${escapeHtml(m.pn)})</option>`).join('');
            } catch (e) { lista.textContent = 'Erro ao carregar os modelos.'; }
        }

        private async alterarModeloRFB(id: number, rfb: boolean): Promise<void> {
            try {
                const r = await (await fetch('/api/rfb/modelos/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, rfb }) })).json();
                if (r.status !== 'sucesso') { Swal.fire('Erro', r.mensagem, 'error'); return; }
                await this.desenharModelosRFB(r.dados);
                await this.carregarModelosRFB();
                Swal.fire({ title: rfb ? 'Modelo adicionado ao RFB' : 'Modelo retirado do RFB', icon: 'success', toast: true, position: 'top-end', showConfirmButton: false, timer: 2500 });
            } catch (e) { Swal.fire('Erro', 'Falha na conexão.', 'error'); }
        }

        // ------------------------------------------------------------ peças padronizadas no encerramento
        private iniciarPecasDaFinalizacao(): void {
            document.getElementById('chk-sem-intervencao')?.addEventListener('change', () => this.aplicarSemIntervencao());
            document.getElementById('chk-sem-peca')?.addEventListener('change', () => {
                const sem = (document.getElementById('chk-sem-peca') as HTMLInputElement).checked;
                document.querySelectorAll('#lista-pecas-finalizar input[type=checkbox]').forEach((c) => {
                    const cb = c as HTMLInputElement;
                    if (sem) cb.checked = false;
                    cb.disabled = sem;
                });
            });
            document.getElementById('finalizacao_modelo')?.addEventListener('change', (e) => {
                const v = (e.target as HTMLSelectElement).value;
                this.carregarPecasDoModelo(v ? Number(v) : null);
            });
            document.getElementById('lista-pecas-finalizar')?.addEventListener('change', (e) => {
                if ((e.target as HTMLInputElement).checked) (document.getElementById('chk-sem-peca') as HTMLInputElement).checked = false;
            });
        }

        // Sem intervenção técnica: some o técnico de campo e a lista de peças (o chamado foi resolvido sem ir a campo).
        private aplicarSemIntervencao(): void {
            const sem = (document.getElementById('chk-sem-intervencao') as HTMLInputElement).checked;
            document.getElementById('bloco-tecnico-finalizar')?.classList.toggle('hidden', sem);
            document.getElementById('bloco-pecas-finalizar')?.classList.toggle('hidden', sem);
            (document.getElementById('finalizacao_tecnico') as HTMLSelectElement).required = !sem;
            if (sem) (document.getElementById('finalizacao_resolucao') as HTMLTextAreaElement).focus();
        }

        private prepararPecasDaFinalizacao(chamado: any): void {
            (document.getElementById('chk-sem-peca') as HTMLInputElement).checked = false;
            const bloco = document.getElementById('bloco-modelo-finalizar') as HTMLElement;
            const sel = document.getElementById('finalizacao_modelo') as HTMLSelectElement;
            if (chamado.equipamento_id) {
                bloco.classList.add('hidden');
                sel.value = '';
                this.carregarPecasDoModelo(Number(chamado.equipamento_id));
            } else {
                // Chamado antigo sem modelo cadastrado: escolher o modelo libera a lista de peças dele.
                bloco.classList.remove('hidden');
                sel.innerHTML = '<option value="">Este chamado não tem modelo cadastrado: escolha o modelo...</option>' + this.modelosRFB.map((m: any) =>
                    `<option value="${Number(m.id)}">${escapeHtml(m.modelo)}</option>`).join('');
                this.carregarPecasDoModelo(null);
            }
        }

        private async carregarPecasDoModelo(idEquipamento: number | null): Promise<void> {
            const lista = document.getElementById('lista-pecas-finalizar') as HTMLElement;
            const aviso = document.getElementById('aviso-pecas-finalizar') as HTMLElement;
            aviso.textContent = '';
            if (!idEquipamento) { lista.innerHTML = '<span class="text-slate-500">Escolha o modelo para ver as peças.</span>'; return; }
            lista.innerHTML = '<span class="text-slate-500">Carregando peças...</span>';
            try {
                const r = await (await fetch(`/api/modelo-equipamento/${idEquipamento}/pecas/`)).json();
                if (r.status !== 'sucesso') { lista.textContent = r.mensagem; return; }
                if (!r.dados.length) {
                    lista.innerHTML = '<span class="text-slate-500">Nenhuma peça cadastrada para este modelo.</span>';
                    aviso.innerHTML = 'Cadastre as peças em <a href="/gerenciar-modelo-equipamento/" class="underline">Modelos e peças</a> ou marque "Nenhuma peça utilizada".';
                    return;
                }
                lista.innerHTML = r.dados.map((p: any) => `
                    <label class="flex items-start gap-2 py-1 cursor-pointer hover:text-white">
                        <input type="checkbox" value="${Number(p.id)}" class="mt-0.5 accent-emerald-500">
                        <span><span class="font-mono text-cyan-300">${escapeHtml(p.part_number)}</span> <span class="text-slate-400">${escapeHtml(p.descricao || '')}</span>${p.equipamento_completo ? ' <span class="ml-1 px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px] font-bold">Equipamento completo</span>' : ''}</span>
                    </label>`).join('');
            } catch (e) { lista.textContent = 'Erro ao carregar as peças.'; }
        }

        private abrirModalFinalizacao(chamado: any): void {
            const modal = document.getElementById('modal-finalizar-chamado');
            if (!modal) return;
            
            document.getElementById('titulo-finalizar')!.innerText = `Finalizar Ticket: ${escapeHtml(chamado.ticket)}`;
            (document.getElementById('finalizacao_id') as HTMLInputElement).value = chamado.id;
            
            const agoraLocal = new Date();
            agoraLocal.setMinutes(agoraLocal.getMinutes() - agoraLocal.getTimezoneOffset());
            (document.getElementById('data_finalizacao_real') as HTMLInputElement).value = agoraLocal.toISOString().slice(0,16);
            
            (document.getElementById('finalizacao_resolucao') as HTMLTextAreaElement).value = chamado.resolucao_caso || '';
            (document.getElementById('finalizacao_tipo_chamado') as HTMLSelectElement).value = '';
            
            const selectTecnico = document.getElementById('finalizacao_tecnico') as HTMLSelectElement;
            if (selectTecnico) {
                selectTecnico.value = chamado.tecnico_atendimento_id ? chamado.tecnico_atendimento_id.toString() : '';
            }

            this.chamadoFinalizando = chamado;
            (document.getElementById('chk-sem-intervencao') as HTMLInputElement).checked = false;
            this.aplicarSemIntervencao();
            this.prepararPecasDaFinalizacao(chamado);

            modal.classList.remove('hidden');
        }

        private async enviarFinalizacao(): Promise<void> {
            const id = (document.getElementById('finalizacao_id') as HTMLInputElement).value;
            const dataF = (document.getElementById('data_finalizacao_real') as HTMLInputElement).value;
            const res = (document.getElementById('finalizacao_resolucao') as HTMLTextAreaElement).value;
            const tipoChamado = (document.getElementById('finalizacao_tipo_chamado') as HTMLSelectElement).value;
            const tecnico = (document.getElementById('finalizacao_tecnico') as HTMLSelectElement).value;

            // Peças padronizadas: só as cadastradas para o modelo do chamado (ou "nenhuma peça").
            const semIntervencao = (document.getElementById('chk-sem-intervencao') as HTMLInputElement).checked;
            const semPeca = semIntervencao || (document.getElementById('chk-sem-peca') as HTMLInputElement).checked;
            const idsPecas = Array.from(document.querySelectorAll('#lista-pecas-finalizar input[type=checkbox]:checked')).map((c) => Number((c as HTMLInputElement).value));
            const modeloEscolhido = (document.getElementById('finalizacao_modelo') as HTMLSelectElement).value;
            if (semIntervencao && !res.trim()) {
                Swal.fire('Aviso', 'Descreva como o chamado foi resolvido sem intervenção técnica.', 'warning');
                return;
            }
            if (!semPeca && idsPecas.length === 0) {
                Swal.fire('Aviso', 'Selecione as peças utilizadas ou marque "Nenhuma peça utilizada".', 'warning');
                return;
            }
            if (!semIntervencao && !(this.chamadoFinalizando && this.chamadoFinalizando.equipamento_id) && !modeloEscolhido) {
                Swal.fire('Aviso', 'Escolha o modelo cadastrado do chamado para registrar as peças.', 'warning');
                return;
            }

            try {
                const req = await fetch('/api/chamados-rfb/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        id: id, 
                        status: 'concluido', 
                        data_conclusao: dataF, 
                        resolucao_caso: res, 
                        sem_peca: semPeca,
                        sem_intervencao_tecnica: semIntervencao,
                        pecas_utilizadas_ids: semPeca ? [] : idsPecas,
                        equipamento_id: modeloEscolhido ? Number(modeloEscolhido) : undefined,
                        tipo_chamado: tipoChamado,
                        tecnico_atendimento_id: semIntervencao ? null : (tecnico ? Number(tecnico) : null)
                    })
                });
                const response = await req.json();
                
                if (response.status === 'sucesso') {
                    document.getElementById('modal-finalizar-chamado')!.classList.add('hidden');
                    Swal.fire({ title: 'Chamado Finalizado', icon: 'success', toast: true, position: 'top-end', showConfirmButton: false, timer: 3000 });
                    this.carregarChamados(); 
                } else {
                    Swal.fire('Erro', response.mensagem, 'error');
                }
            } catch (error) {
                Swal.fire('Erro', 'Falha na conexão ao finalizar.', 'error');
            }
        }

        private async atualizarStatusDireto(chamadoId: number, chamadoAtual: any, novoStatus: string): Promise<void> {
            const confirmacao = await Swal.fire({
                title: 'Atenção Operacional',
                text: `Alterar o Ticket ${escapeHtml(chamadoAtual.ticket)} para "${novoStatus.toUpperCase()}"?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#0891b2',
                cancelButtonColor: '#64748b',
                confirmButtonText: 'Sim, alterar status',
                cancelButtonText: 'Cancelar'
            });
            
            if (!confirmacao.isConfirmed) {
                this.carregarChamados(); 
                return;
            }

            try {
                const dados = {
                    id: chamadoId,
                    status: novoStatus,
                    update_parcial: true
                };

                const req = await fetch('/api/chamados-rfb/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });
                const res = await req.json();

                if (res.status === 'sucesso') {
                    Swal.fire({ title: 'Sucesso!', icon: 'success', toast: true, position: 'top-end', showConfirmButton: false, timer: 3000 });
                    this.carregarChamados(); 
                } else {
                    Swal.fire('Erro', res.mensagem, 'error');
                    this.carregarChamados();
                }
            } catch (error) {
                Swal.fire('Erro', 'Conexão perdida ao alterar status.', 'error');
                this.carregarChamados();
            }
        }

        private async salvarChamado(): Promise<void> {
            const ticket = (document.getElementById('ticket') as HTMLInputElement).value;
            const dataAbertura = (document.getElementById('data_abertura') as HTMLInputElement).value;
            const analista = (document.getElementById('analista_responsavel') as HTMLSelectElement).value;
            const tipoChamadoEl = document.getElementById('tipo_chamado') as HTMLSelectElement;
            
            const dados = {
                id: this.idAtual,
                ticket: ticket,
                data_abertura: dataAbertura,
                estado: this.selectEstado.value,
                cidade: this.selectCidade.value,
                equipamento_id: (document.getElementById('modelo_equipamento') as HTMLSelectElement).value ? Number((document.getElementById('modelo_equipamento') as HTMLSelectElement).value) : null,
                sn: (document.getElementById('sn') as HTMLInputElement).value,
                tipo_chamado: (tipoChamadoEl && tipoChamadoEl.value) ? tipoChamadoEl.value : 'Não informado',
                descricao_defeito: (document.getElementById('descricao_defeito') as HTMLInputElement).value,
                observacao: (document.getElementById('observacao') as HTMLInputElement)?.value || '',
                analista_responsavel_id: analista ? Number(analista) : null
            };

            try {
                const req = await fetch('/api/chamados-rfb/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });
                const res = await req.json();

                if (res.status === 'sucesso') {
                    Swal.fire('Excelente!', res.mensagem, 'success');
                    this.limparFormulario();
                    this.carregarChamados(); 
                } else Swal.fire('Erro de Validação', res.mensagem, 'warning');
            } catch (error) { Swal.fire('Erro Fatal', 'Erro de conexão.', 'error'); }
        }

        private gerarRelatorioFechamento(): void {
            if (this.chamadosBaixadosCache.length === 0) {
                Swal.fire('Aviso', 'Não há dados processados para gerar o relatório.', 'info');
                return;
            }

            const concluidos = this.chamadosBaixadosCache.filter(c => c.status === 'concluido');
            const totalFechados = concluidos.length;
            
            let fechadosNoPrazo = 0;
            let fechadosAtrasados = 0;
            let totalHorasUteis = 0;

            concluidos.forEach(c => {
                totalHorasUteis += c.horas_consumidas;
                if (c.horas_consumidas > c.limite_sla) fechadosAtrasados++;
                else fechadosNoPrazo++;
            });

            const adherence = totalFechados > 0 ? ((fechadosNoPrazo / totalFechados) * 100).toFixed(2) : '0.00';
            const tempoMedio = totalFechados > 0 ? (totalHorasUteis / totalFechados).toFixed(2) : '0.00';

            let csvContent = "\uFEFF"; 
            csvContent += "RELATÓRIO GERENCIAL DE FECHAMENTO (SLA ADHERENCE)\n\n";
            csvContent += `Volume Total de Chamados Fechados:;${totalFechados}\n`;
            csvContent += `SLA Adherence (No Prazo):;${adherence}%\n`;
            csvContent += `Volume Estourado:;${fechadosAtrasados}\n`;
            csvContent += `Tempo Médio de Reparo (MTTR):;${tempoMedio} horas\n\n`;
            
            csvContent += "TICKET;TIPO;ANALISTA;TECNICO;DATA ABERTURA;DATA CONCLUSAO;UF;MODELO;DEFEITO;RESOLUCAO;PECA;HORAS GASTAS;LIMITE SLA;RESULTADO\n";
            
            concluidos.forEach(c => {
                const resultado = c.horas_consumidas > c.limite_sla ? "ESTOURADO" : "NO PRAZO";
                const dCon = c.data_conclusao ? new Date(c.data_conclusao).toLocaleDateString('pt-BR') : '';
                const analista = c.analista_responsavel_nome || 'N/A';
                const tecnico = c.sem_intervencao_tecnica ? 'Sem intervenção técnica' : (c.tecnico_atendimento_nome || 'N/A');
                
                csvContent += `"${c.ticket}";"${c.tipo_chamado || ''}";"${analista}";"${tecnico}";"${new Date(c.data_abertura).toLocaleDateString('pt-BR')}";"${dCon}";"${c.estado}";"${c.modelo_equipamento}";"${c.descricao_defeito}";"${c.resolucao_caso}";"${c.peca_utilizada}";${c.horas_consumidas.toFixed(1)};${c.limite_sla};"${resultado}"\n`;
            });

            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement("a");
            link.setAttribute("href", URL.createObjectURL(blob));
            link.setAttribute("download", `Fechamento_SLA_RFB_${new Date().toISOString().slice(0, 10)}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        private async abrirModalAgendamento(chamadoId: number, ticket: string): Promise<void> {
            this.chamadoAgendamentoAberto = chamadoId;
            const modalTitle = document.getElementById('modal-agendamento-title');
            if(modalTitle) modalTitle.innerText = `Agendamento / Pausa - ${escapeHtml(ticket)}`;
            
            this.modalAgendamento.classList.remove('hidden');
            this.listaAgendamentos.innerHTML = '<tr><td colspan="5" class="p-4 text-center">Carregando histórico logístico...</td></tr>';

            try {
                const req = await fetch(`/api/chamados-rfb/${chamadoId}/agendamentos/`);
                const res = await req.json();
                if (res.status === 'sucesso') this.renderizarHistoricoAgendamentos(res.dados);
            } catch (e) {
                this.listaAgendamentos.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-rose-500">Erro de conexão.</td></tr>';
            }
        }

        private renderizarHistoricoAgendamentos(agendamentos: any[]): void {
            this.listaAgendamentos.innerHTML = '';
            if(agendamentos.length === 0) {
                this.listaAgendamentos.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-slate-500">Nenhum registro logístico / Sem pausas.</td></tr>';
                return;
            }

            agendamentos.forEach(a => {
                const tr = document.createElement('tr');
                const ehSemResposta = a.tipo_pausa === 'sem_resposta';
                
                tr.innerHTML = `
                    <td class="p-3">
                        <span class="block text-white font-bold">${ehSemResposta ? 'Falta de Resposta' : 'Visita Técnica'}</span>
                        <span class="text-[10px] text-slate-400">Pausa em: ${a.data_registro_pausa ? new Date(a.data_registro_pausa).toLocaleString('pt-BR') : '--'}</span>
                    </td>
                    <td class="p-3">
                        ${ehSemResposta 
                            ? `<span class="text-amber-400">Tentativas desde:<br>${a.data_inicio_tentativas ? new Date(a.data_inicio_tentativas).toLocaleString('pt-BR') : '--'}</span>`
                            : `<span class="text-cyan-400">Agendado para:<br>${a.data_agendamento ? new Date(a.data_agendamento).toLocaleString('pt-BR') : '--'}</span>`
                        }
                    </td>
                    <td class="p-3 text-[10px]">${a.data_resposta_cliente ? `Respondido em: ${new Date(a.data_resposta_cliente).toLocaleString('pt-BR')}` : '--'}</td>
                    <td class="p-3 uppercase font-bold text-[10px] ${a.status === 'pendente' ? 'text-blue-400' : 'text-slate-400'}">${escapeHtml(a.status)}</td>
                    <td class="p-3 text-center">
                        <div class="flex flex-col gap-1 items-center">
                            ${a.status === 'pendente' && !ehSemResposta ? `
                                <select class="atualizar-status-agendamento bg-[#1e293b] border border-[#334155] rounded text-[10px] py-1 px-2 focus:outline-none w-full" data-id="${a.id}">
                                    <option value="" disabled selected>Ação...</option>
                                    <option value="realizado" class="text-emerald-400">Realizado (Finalizar)</option>
                                    <option value="frustrado" class="text-rose-400">Frustrado (Retomar SLA)</option>
                                </select>
                            ` : ''}
                            ${a.status === 'pendente' && ehSemResposta ? `
                                <button class="btn-registrar-resposta bg-emerald-600 hover:bg-emerald-500 text-white px-2 py-1 rounded text-[10px] font-bold w-full" data-id="${a.id}">Registrar Resposta</button>
                            ` : ''}
                            ${a.status === 'pendente' ? `
                                <button class="btn-editar-agendamento bg-[#334155] hover:bg-amber-600 text-white px-2 py-1 rounded text-[10px] font-bold w-full" title="Editar Registro">Editar Dados</button>
                            ` : '<span class="text-[10px] text-slate-500">Concluído</span>'}
                        </div>
                    </td>
                `;

                const btnEditarAgendamento = tr.querySelector('.btn-editar-agendamento');
                if (btnEditarAgendamento) {
                    btnEditarAgendamento.addEventListener('click', () => this.prepararEdicaoAgendamento(a));
                }

                const btnResposta = tr.querySelector('.btn-registrar-resposta');
                if (btnResposta) {
                    btnResposta.addEventListener('click', async () => {
                        const dataResp = prompt("Informe a Data e Hora da Resposta do Cliente (YYYY-MM-DDTHH:MM):", new Date().toISOString().slice(0, 16));
                        if (dataResp) {
                            await fetch(`/api/chamados-rfb/agendamentos/${a.id}/resposta/`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ data_resposta: dataResp })
                            });
                            this.abrirModalAgendamento(this.chamadoAgendamentoAberto!, ""); 
                            this.carregarChamados();
                        }
                    });
                }

                const selectAcao = tr.querySelector('.atualizar-status-agendamento') as HTMLSelectElement;
                if (selectAcao) {
                    selectAcao.addEventListener('change', async (e) => {
                        await fetch(`/api/chamados-rfb/${this.chamadoAgendamentoAberto}/agendamentos/`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ agendamento_id: a.id, status: (e.target as HTMLSelectElement).value })
                        });
                        this.abrirModalAgendamento(this.chamadoAgendamentoAberto!, ""); 
                        this.carregarChamados();
                    });
                }
                this.listaAgendamentos.appendChild(tr);
            });
        }

        private prepararEdicaoAgendamento(a: any): void {
            (document.getElementById('agendamento_id_em_edicao') as HTMLInputElement).value = a.id;
            
            const selectTipo = document.getElementById('tipo_pausa') as HTMLSelectElement;
            selectTipo.value = a.tipo_pausa;
            selectTipo.dispatchEvent(new Event('change'));

            const formataParaInput = (isoString: string) => {
                if (!isoString) return '';
                const dt = new Date(isoString);
                dt.setMinutes(dt.getMinutes() - dt.getTimezoneOffset());
                return dt.toISOString().slice(0, 16);
            };

            const dataReg = a.data_registro_pausa || a.data_inicio_tentativas;
            (document.getElementById('data_registro') as HTMLInputElement).value = formataParaInput(dataReg);

            if (a.tipo_pausa === 'agendamento' && a.data_agendamento) {
                (document.getElementById('data_visita') as HTMLInputElement).value = formataParaInput(a.data_agendamento);
            }

            (document.getElementById('btn-submit-agendamento') as HTMLButtonElement).innerText = 'Atualizar';
            document.getElementById('btn-cancelar-edicao-agendamento')?.classList.remove('hidden');
        }

        private resetarFormAgendamento(): void {
            this.formNovoAgendamento.reset();
            (document.getElementById('agendamento_id_em_edicao') as HTMLInputElement).value = '';
            (document.getElementById('btn-submit-agendamento') as HTMLButtonElement).innerText = 'Registrar';
            document.getElementById('btn-cancelar-edicao-agendamento')?.classList.add('hidden');
            document.getElementById('tipo_pausa')?.dispatchEvent(new Event('change'));
        }

        private async salvarNovoAgendamento(): Promise<void> {
            if (!this.chamadoAgendamentoAberto) return;
            const agendamentoId = (document.getElementById('agendamento_id_em_edicao') as HTMLInputElement).value;
            const tipoPausaInp = (document.getElementById('tipo_pausa') as HTMLSelectElement).value;
            const dataRegistro = (document.getElementById('data_registro') as HTMLInputElement).value;
            const dataVisita = (document.getElementById('data_visita') as HTMLInputElement).value;
            
            if (tipoPausaInp === 'agendamento' && !dataVisita) {
                Swal.fire('Aviso', "A data da visita técnica é obrigatória para registrar um agendamento.", 'warning');
                return;
            }

            try {
                const req = await fetch(`/api/chamados-rfb/${this.chamadoAgendamentoAberto}/agendamentos/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        agendamento_id: agendamentoId || null,
                        chamado_id: this.chamadoAgendamentoAberto,
                        data_registro: dataRegistro,
                        data_visita: dataVisita,
                        tipo_pausa: tipoPausaInp 
                    })
                });
                const res = await req.json();
                
                if (res.status === 'sucesso') {
                    this.resetarFormAgendamento();
                    const event = new Event('change');
                    document.getElementById('tipo_pausa')!.dispatchEvent(event);
                    
                    this.abrirModalAgendamento(this.chamadoAgendamentoAberto, document.getElementById('modal-agendamento-title')!.innerText.replace('Logística - ', ''));
                    this.carregarChamados();
                } else {
                    Swal.fire('Erro', res.mensagem, 'error');
                }
            } catch (e) { Swal.fire('Erro', 'Falha ao registrar logística.', 'error'); }
        }

        private async carregarCidadesIBGE(uf: string, cidadePreSelecionada?: string): Promise<void> {
            this.selectCidade.innerHTML = '<option value="" disabled selected>Buscando...</option>';
            this.selectCidade.disabled = true;
            try {
                const req = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${uf}/municipios`);
                if (!req.ok) throw new Error("UF inválida");
                
                const cidades = await req.json();
                this.selectCidade.innerHTML = '<option value="" disabled selected></option>';
                cidades.forEach((cidade: any) => {
                    const option = document.createElement('option');
                    option.value = cidade.nome;
                    option.text = cidade.nome;
                    this.selectCidade.appendChild(option);
                });

                this.selectCidade.disabled = false;
                if (cidadePreSelecionada) {
                    this.selectCidade.value = cidadePreSelecionada;
                    this.selectCidade.classList.add('has-value');
                }
            } catch (error) {
                this.selectCidade.innerHTML = '<option value="" disabled selected></option>';
            }
        }

        private prepararEdicao(chamado: any): void {
            this.idAtual = chamado.id;
            (document.getElementById('ticket') as HTMLInputElement).value = chamado.ticket;
            const dataInput = document.getElementById('data_abertura') as HTMLInputElement;
            if(chamado.data_abertura) {
                const dt = new Date(chamado.data_abertura);
                if (!isNaN(dt.getTime())) dataInput.value = dt.toISOString().slice(0, 16);
            }

            this.selectEstado.value = chamado.estado;
            this.selectEstado.classList.add('has-value');
            this.carregarCidadesIBGE(chamado.estado, chamado.cidade);
            
            const selectEquipamento = document.getElementById('modelo_equipamento') as HTMLSelectElement;
            this.definirModeloNoFormulario(chamado);
            selectEquipamento.classList.add('has-value'); 
            
            (document.getElementById('sn') as HTMLInputElement).value = chamado.sn;
            
            const selectTipoChamado = document.getElementById('tipo_chamado') as HTMLSelectElement;
            selectTipoChamado.value = chamado.tipo_chamado || ''; 
            selectTipoChamado.classList.add('has-value');
            
            (document.getElementById('descricao_defeito') as HTMLInputElement).value = chamado.descricao_defeito;
            
            const selectAnalista = document.getElementById('analista_responsavel') as HTMLSelectElement;
            if (chamado.analista_responsavel_id && selectAnalista) {
                selectAnalista.value = chamado.analista_responsavel_id;
                selectAnalista.classList.add('has-value');
            }

            const campoObs = document.getElementById('observacao') as HTMLInputElement;
            if (campoObs) campoObs.value = chamado.observacao || '';

            this.btnSalvar.innerText = "Atualizar Registro";
            this.btnSalvar.classList.replace('bg-cyan-600', 'bg-amber-600');
            this.form.scrollIntoView({ behavior: 'smooth', block: 'start' });
            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.add('has-value'));
        }

        private limparFormulario(): void {
            this.form.reset();
            this.idAtual = null;
            this.selectCidade.innerHTML = '<option value="" disabled selected></option>';
            this.selectCidade.disabled = true;
            this.btnSalvar.innerText = "Registrar Chamado";
            this.btnSalvar.classList.replace('bg-amber-600', 'bg-cyan-600');
            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.remove('has-value'));
        }
        private async exportarParaCSV(): Promise<void> {
            try {
                Swal.fire({
                    title: 'Aguarde...',
                    text: 'Buscando todos os registros no banco de dados...',
                    allowOutsideClick: false,
                    didOpen: () => { Swal.showLoading(); }
                });

                // 1. Filtros ativos na tela
                const status = this.selectFiltroStatus ? this.selectFiltroStatus.value : 'todos';
                const tipo = this.selectFiltroTipo ? this.selectFiltroTipo.value : 'todos';
                const estado = this.selectFiltroEstado ? this.selectFiltroEstado.value : 'todos';
                const analista = this.selectFiltroAnalista ? this.selectFiltroAnalista.value : 'todos';
                const busca = this.inputPesquisa ? this.inputPesquisa.value : '';

                // 2. Primeira página, para saber o total de páginas
                const urlBase = `/api/chamados-rfb/?status=${encodeURIComponent(status)}&tipo=${encodeURIComponent(tipo)}&estado=${encodeURIComponent(estado)}&analista=${encodeURIComponent(analista)}&q=${encodeURIComponent(busca)}`;
                const resPrimeira = await fetch(`${urlBase}&page=1`);
                const jsonPrimeira = await resPrimeira.json();

                if (jsonPrimeira.status !== 'sucesso' || !jsonPrimeira.dados || jsonPrimeira.dados.length === 0) {
                    Swal.close();
                    Swal.fire('Aviso', "Não há dados para exportar com os filtros selecionados.", 'info');
                    return;
                }

                let todosChamados: any[] = [...jsonPrimeira.dados];
                const totalPaginas: number = jsonPrimeira.total_paginas || 1;

                // 3. Demais páginas em paralelo
                if (totalPaginas > 1) {
                    Swal.fire({
                        title: 'Aguarde...',
                        text: `Carregando ${jsonPrimeira.total || 'todos os'} chamados (${totalPaginas} páginas)...`,
                        allowOutsideClick: false,
                        didOpen: () => { Swal.showLoading(); }
                    });

                    const promessasPaginas: Promise<any>[] = [];
                    for (let p = 2; p <= totalPaginas; p++) {
                        promessasPaginas.push(fetch(`${urlBase}&page=${p}`).then(r => r.json()));
                    }

                    const resultados = await Promise.all(promessasPaginas);
                    resultados.forEach((res: any) => {
                        if (res.status === 'sucesso' && Array.isArray(res.dados)) {
                            todosChamados = todosChamados.concat(res.dados);
                        }
                    });
                }

                // 4. Cabeçalhos do CSV
                const cabecalhos = [
                    "Ticket", "Status", "Modelo", "Tipo", "Nº de Série", "Data Abertura", "Data Fechamento",
                    "Cidade", "UF", "Conclusão", "Peças Usadas", "SLA Consumido (h)", "Limite SLA (h)",
                    "SLA Estourado", "Data Agendamento", "Status Agendamento", "Histórico / Detalhes dos Agendamentos"
                ];

                const formatarData = (dataStr: any): string => {
                    if (!dataStr) return '';
                    const dt = new Date(dataStr);
                    return isNaN(dt.getTime()) ? '' : dt.toLocaleString('pt-BR');
                };

                // Aspas duplicadas + proteção contra "injeção de fórmula" ao abrir no Excel (=, +, -, @)
                const sanear = (valor: any): string => {
                    let texto = (valor !== null && valor !== undefined ? valor : '').toString();
                    if (/^[=+\-@\t\r]/.test(texto)) texto = "'" + texto;
                    return `"${texto.replace(/"/g, '""')}"`;
                };

                // 5. Uma linha por chamado
                const linhas = todosChamados.map((c: any) => {
                    const horasConsumidas = Number(c.horas_consumidas) || 0;
                    const limiteSLA = Number(c.limite_sla) || 120;
                    const horasFormatadas = horasConsumidas.toFixed(2).replace('.', ',');
                    const estourado = horasConsumidas > limiteSLA ? "Sim" : "Não";

                    const dataAgendamento = formatarData(c.data_agendamento_pendente || c.data_agendamento);
                    const statusAgendamento = c.ultimo_agendamento_pendente || c.status_agendamento || '';

                    let historicoAgendamentos = '';
                    if (Array.isArray(c.agendamentos)) {
                        historicoAgendamentos = c.agendamentos
                            .map((ag: any) => `${formatarData(ag.data || ag.data_agendamento)} - ${ag.status || ag.observacao || ''}`)
                            .join(' | ');
                    } else {
                        historicoAgendamentos = c.observacao_agendamento || c.historico_agendamentos || '';
                    }

                    return [
                        sanear(c.ticket),
                        sanear(c.status),
                        sanear(c.modelo_equipamento || c.modelo),
                        sanear(c.tipo_chamado || c.tipo),
                        sanear(c.sn || c.numero_serie),
                        sanear(formatarData(c.data_abertura)),
                        sanear(formatarData(c.data_conclusao || c.data_fechamento)),
                        sanear(c.cidade),
                        sanear(c.estado),
                        sanear(c.resolucao_caso),
                        sanear(c.peca_utilizada),
                        sanear(horasFormatadas),
                        sanear(limiteSLA),
                        sanear(estourado),
                        sanear(dataAgendamento),
                        sanear(statusAgendamento),
                        sanear(historicoAgendamentos)
                    ].join(";");
                });

                // 6. Download
                const csvContent = "\uFEFF" + cabecalhos.join(";") + "\n" + linhas.join("\n");
                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement("a");
                link.setAttribute("href", URL.createObjectURL(blob));
                link.setAttribute("download", `relatorio_auditoria_rfb_${new Date().getTime()}.csv`);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                Swal.close();

            } catch (error) {
                console.error('Erro na exportação para CSV:', error);
                Swal.fire('Erro', 'Ocorreu um erro ao buscar todos os registros e gerar o arquivo CSV.', 'error');
            }
        }
    }
    window.addEventListener('DOMContentLoaded', () => new G_RFBUI());
})();