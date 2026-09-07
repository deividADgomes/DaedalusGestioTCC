/// <reference path="../baseUI.ts" />
declare const Chart: any;

(() => {
    class DashboardUI extends BaseUI {
        private charts: { [key: string]: any } = {};
        private dadosCache: any = null;

        constructor() {
            super()
            Chart.defaults.color = '#94a3b8';
            Chart.defaults.borderColor = '#334155';
            
            this.iniciarFiltros();
            this.carregarDados();
        }

        private iniciarFiltros(): void {
            document.getElementById('btn-filtrar')?.addEventListener('click', () => this.carregarDados());
            document.getElementById('toggle-tecnico')?.addEventListener('change', () => this.renderizarTecnicos());
            // Evento para o novo filtro de analistas
            document.getElementById('toggle-analista')?.addEventListener('change', () => this.renderizarAnalistas());
        }

        private async carregarDados(): Promise<void> {
            const inicio = (document.getElementById('filtro-inicio') as HTMLInputElement).value;
            const fim = (document.getElementById('filtro-fim') as HTMLInputElement).value;
            
            try {
                const res = await (await fetch(`/api/dashboard/?inicio=${inicio}&fim=${fim}`)).json();

                if (res.status === 'sucesso') {
                    if (res.vazio) {
                        alert("Não há dados no período selecionado.");
                        return;
                    }
                    this.dadosCache = res.dados;
                    this.atualizarKPIs(res.dados);
                    this.renderizarTecnicos();
                    this.renderizarAnalistas();
                    this.renderizarStatus();
                    this.renderizarClientes();
                    this.renderizarPecas();
                } else {
                    alert("Erro: " + res.mensagem);
                }
            } catch (e) {
                console.error("Erro na busca de dados", e);
            }
        }

        private atualizarKPIs(d: any): void {
            (document.getElementById('kpi-total') as HTMLElement).innerText = d.resumo.total;
            (document.getElementById('kpi-erros') as HTMLElement).innerText = d.resumo.erros;
            
            (document.getElementById('kpi-cliente-nome') as HTMLElement).innerText = d.top_cliente.nome || 'Nenhum';
            (document.getElementById('kpi-cliente-equip') as HTMLElement).innerHTML = `Equipamento: <span class="font-bold text-white">${d.top_cliente.equipamento_top || '-'}</span>`;
            (document.getElementById('kpi-cliente-defeito') as HTMLElement).innerHTML = `Pior Defeito: <span class="font-bold">${d.top_cliente.defeito_top || '-'}</span>`;

            // Agora a Peça recebe o Modelo junto
            (document.getElementById('kpi-peca-nome') as HTMLElement).innerText = d.top_peca_kpi.nome;
            (document.getElementById('kpi-peca-modelo') as HTMLElement).innerHTML = `Modelo: <span class="font-bold">${d.top_peca_kpi.modelo}</span>`;
            (document.getElementById('kpi-peca-qtd') as HTMLElement).innerText = `${d.top_peca_kpi.total} trocas efetuadas`;
        }

        private renderizarTecnicos(): void {
            const ctx = (document.getElementById('chartTecnicos') as HTMLCanvasElement).getContext('2d');
            const modo = (document.getElementById('toggle-tecnico') as HTMLSelectElement).value;
            
            if (this.charts['tecnicos']) this.charts['tecnicos'].destroy();

            const labels = this.dadosCache.tecnicos.map((t: any) => t.nome);
            const valores = this.dadosCache.tecnicos.map((t: any) => modo === 'erros' ? t.erros : t.sucessos);
            const cor = modo === 'erros' ? '#f43f5e' : '#10b981';

            this.charts['tecnicos'] = new Chart(ctx, {
                type: 'bar',
                data: { labels: labels, datasets: [{ label: modo === 'erros' ? 'Erros' : 'Sucessos', data: valores, backgroundColor: cor, borderRadius: 4 }] },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }

        // AGORA ANALISTAS TÊM FILTRO IGUAL AOS TÉCNICOS
        private renderizarAnalistas(): void {
            const ctx = (document.getElementById('chartAnalistas') as HTMLCanvasElement).getContext('2d');
            const modo = (document.getElementById('toggle-analista') as HTMLSelectElement).value;

            if (this.charts['analistas']) this.charts['analistas'].destroy();

            const labels = this.dadosCache.analistas.map((a: any) => a.nome);
            
            let valores, cor, legenda;
            if (modo === 'erros') {
                valores = this.dadosCache.analistas.map((a: any) => a.erros);
                cor = '#f43f5e'; legenda = 'Com Defeito';
            } else if (modo === 'sucessos') {
                valores = this.dadosCache.analistas.map((a: any) => a.sucessos);
                cor = '#10b981'; legenda = 'Funcionais';
            } else {
                valores = this.dadosCache.analistas.map((a: any) => a.total);
                cor = '#8b5cf6'; legenda = 'Total Triagens';
            }

            this.charts['analistas'] = new Chart(ctx, {
                type: 'bar',
                data: { labels: labels, datasets: [{ label: legenda, data: valores, backgroundColor: cor, borderRadius: 4 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }

        private renderizarStatus(): void {
            const ctx = (document.getElementById('chartStatus') as HTMLCanvasElement).getContext('2d');
            if (this.charts['status']) this.charts['status'].destroy();

            this.charts['status'] = new Chart(ctx, {
                type: 'doughnut',
                data: { labels: ['Funcional', 'Com Defeito'], datasets: [{ data: [this.dadosCache.resumo.funcionais, this.dadosCache.resumo.erros], backgroundColor: ['#10b981', '#f43f5e'], borderWidth: 0 }] },
                options: { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { legend: { position: 'bottom' } } }
            });
        }

        // GRÁFICO DE CLIENTES AGORA É EMPILHADO (STACKED) MOSTRANDO ERROS VS SUCESSOS
        private renderizarClientes(): void {
            const ctx = (document.getElementById('chartClientes') as HTMLCanvasElement).getContext('2d');
            if (this.charts['clientes']) this.charts['clientes'].destroy();

            const labels = this.dadosCache.clientes_grafico.map((c: any) => c.nome);
            const dataSucessos = this.dadosCache.clientes_grafico.map((c: any) => c.sucessos);
            const dataErros = this.dadosCache.clientes_grafico.map((c: any) => c.erros);

            this.charts['clientes'] = new Chart(ctx, {
                type: 'bar',
                data: { 
                    labels: labels, 
                    datasets: [
                        { label: 'Funcional', data: dataSucessos, backgroundColor: '#10b981', borderRadius: 2 },
                        { label: 'Com Defeito', data: dataErros, backgroundColor: '#f43f5e', borderRadius: 2 }
                    ] 
                },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false, 
                    plugins: { legend: { display: true, position: 'top', labels: { boxWidth: 12 } } },
                    scales: {
                        x: { stacked: true },
                        y: { stacked: true }
                    }
                }
            });
        }

        // PEÇAS AGORA MOSTRAM NOME E MODELO NO GRÁFICO
        private renderizarPecas(): void {
            const ctx = (document.getElementById('chartPecas') as HTMLCanvasElement).getContext('2d');
            if (this.charts['pecas']) this.charts['pecas'].destroy();

            // Formata o label para ficar: "Teclado (Thinkpad T14)"
            const labels = this.dadosCache.pecas.map((p: any) => `${p.nome} (${p.modelo})`);

            this.charts['pecas'] = new Chart(ctx, {
                type: 'bar',
                data: { labels: labels, datasets: [{ label: 'Trocas', data: this.dadosCache.pecas.map((p: any) => p.total), backgroundColor: '#f59e0b', borderRadius: 4 }] },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }
    }

    window.addEventListener('DOMContentLoaded', () => new DashboardUI());
})();