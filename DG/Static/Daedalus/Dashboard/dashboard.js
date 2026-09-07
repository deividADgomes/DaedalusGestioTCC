"use strict";
/// <reference path="../baseUI.ts" />
(() => {
    class DashboardUI extends BaseUI {
        constructor() {
            super();
            this.charts = {};
            this.dadosCache = null;
            Chart.defaults.color = '#94a3b8';
            Chart.defaults.borderColor = '#334155';
            this.iniciarFiltros();
            this.carregarDados();
        }
        iniciarFiltros() {
            document.getElementById('btn-filtrar')?.addEventListener('click', () => this.carregarDados());
            document.getElementById('toggle-tecnico')?.addEventListener('change', () => this.renderizarTecnicos());
            // Evento para o novo filtro de analistas
            document.getElementById('toggle-analista')?.addEventListener('change', () => this.renderizarAnalistas());
        }
        async carregarDados() {
            const inicio = document.getElementById('filtro-inicio').value;
            const fim = document.getElementById('filtro-fim').value;
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
                }
                else {
                    alert("Erro: " + res.mensagem);
                }
            }
            catch (e) {
                console.error("Erro na busca de dados", e);
            }
        }
        atualizarKPIs(d) {
            document.getElementById('kpi-total').innerText = d.resumo.total;
            document.getElementById('kpi-erros').innerText = d.resumo.erros;
            document.getElementById('kpi-cliente-nome').innerText = d.top_cliente.nome || 'Nenhum';
            document.getElementById('kpi-cliente-equip').innerHTML = `Equipamento: <span class="font-bold text-white">${d.top_cliente.equipamento_top || '-'}</span>`;
            document.getElementById('kpi-cliente-defeito').innerHTML = `Pior Defeito: <span class="font-bold">${d.top_cliente.defeito_top || '-'}</span>`;
            // Agora a Peça recebe o Modelo junto
            document.getElementById('kpi-peca-nome').innerText = d.top_peca_kpi.nome;
            document.getElementById('kpi-peca-modelo').innerHTML = `Modelo: <span class="font-bold">${d.top_peca_kpi.modelo}</span>`;
            document.getElementById('kpi-peca-qtd').innerText = `${d.top_peca_kpi.total} trocas efetuadas`;
        }
        renderizarTecnicos() {
            const ctx = document.getElementById('chartTecnicos').getContext('2d');
            const modo = document.getElementById('toggle-tecnico').value;
            if (this.charts['tecnicos'])
                this.charts['tecnicos'].destroy();
            const labels = this.dadosCache.tecnicos.map((t) => t.nome);
            const valores = this.dadosCache.tecnicos.map((t) => modo === 'erros' ? t.erros : t.sucessos);
            const cor = modo === 'erros' ? '#f43f5e' : '#10b981';
            this.charts['tecnicos'] = new Chart(ctx, {
                type: 'bar',
                data: { labels: labels, datasets: [{ label: modo === 'erros' ? 'Erros' : 'Sucessos', data: valores, backgroundColor: cor, borderRadius: 4 }] },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }
        // AGORA ANALISTAS TÊM FILTRO IGUAL AOS TÉCNICOS
        renderizarAnalistas() {
            const ctx = document.getElementById('chartAnalistas').getContext('2d');
            const modo = document.getElementById('toggle-analista').value;
            if (this.charts['analistas'])
                this.charts['analistas'].destroy();
            const labels = this.dadosCache.analistas.map((a) => a.nome);
            let valores, cor, legenda;
            if (modo === 'erros') {
                valores = this.dadosCache.analistas.map((a) => a.erros);
                cor = '#f43f5e';
                legenda = 'Com Defeito';
            }
            else if (modo === 'sucessos') {
                valores = this.dadosCache.analistas.map((a) => a.sucessos);
                cor = '#10b981';
                legenda = 'Funcionais';
            }
            else {
                valores = this.dadosCache.analistas.map((a) => a.total);
                cor = '#8b5cf6';
                legenda = 'Total Triagens';
            }
            this.charts['analistas'] = new Chart(ctx, {
                type: 'bar',
                data: { labels: labels, datasets: [{ label: legenda, data: valores, backgroundColor: cor, borderRadius: 4 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }
        renderizarStatus() {
            const ctx = document.getElementById('chartStatus').getContext('2d');
            if (this.charts['status'])
                this.charts['status'].destroy();
            this.charts['status'] = new Chart(ctx, {
                type: 'doughnut',
                data: { labels: ['Funcional', 'Com Defeito'], datasets: [{ data: [this.dadosCache.resumo.funcionais, this.dadosCache.resumo.erros], backgroundColor: ['#10b981', '#f43f5e'], borderWidth: 0 }] },
                options: { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { legend: { position: 'bottom' } } }
            });
        }
        // GRÁFICO DE CLIENTES AGORA É EMPILHADO (STACKED) MOSTRANDO ERROS VS SUCESSOS
        renderizarClientes() {
            const ctx = document.getElementById('chartClientes').getContext('2d');
            if (this.charts['clientes'])
                this.charts['clientes'].destroy();
            const labels = this.dadosCache.clientes_grafico.map((c) => c.nome);
            const dataSucessos = this.dadosCache.clientes_grafico.map((c) => c.sucessos);
            const dataErros = this.dadosCache.clientes_grafico.map((c) => c.erros);
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
        renderizarPecas() {
            const ctx = document.getElementById('chartPecas').getContext('2d');
            if (this.charts['pecas'])
                this.charts['pecas'].destroy();
            // Formata o label para ficar: "Teclado (Thinkpad T14)"
            const labels = this.dadosCache.pecas.map((p) => `${p.nome} (${p.modelo})`);
            this.charts['pecas'] = new Chart(ctx, {
                type: 'bar',
                data: { labels: labels, datasets: [{ label: 'Trocas', data: this.dadosCache.pecas.map((p) => p.total), backgroundColor: '#f59e0b', borderRadius: 4 }] },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }
    }
    window.addEventListener('DOMContentLoaded', () => new DashboardUI());
})();
