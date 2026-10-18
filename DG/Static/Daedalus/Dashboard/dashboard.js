"use strict";
/// <reference path="../baseUI.ts" />
(() => {
    const COR = {
        texto: '#94a3b8', eixo: '#334155', ciano: '#22d3ee', rosa: '#fb7185', ambar: '#fbbf24',
        verde: '#34d399', indigo: '#818cf8', cinza: '#64748b'
    };
    const STATUS = {
        critico: { rotulo: 'Crítico', classe: 'bg-rose-500/15 text-rose-300 border-rose-500/40', cor: COR.rosa },
        atencao: { rotulo: 'Atenção', classe: 'bg-amber-500/15 text-amber-300 border-amber-500/40', cor: COR.ambar },
        destaque: { rotulo: 'Destaque', classe: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40', cor: COR.verde },
        normal: { rotulo: 'Normal', classe: 'bg-slate-500/15 text-slate-300 border-slate-500/40', cor: COR.ciano },
        insuficiente: { rotulo: 'Amostra pequena', classe: 'bg-slate-700/30 text-slate-500 border-slate-600/40', cor: COR.cinza }
    };
    const NIVEL = {
        critico: { borda: 'border-rose-500', icone: '▲', cor: 'text-rose-400' },
        atencao: { borda: 'border-amber-500', icone: '●', cor: 'text-amber-400' },
        info: { borda: 'border-cyan-500', icone: 'i', cor: 'text-cyan-400' },
        positivo: { borda: 'border-emerald-500', icone: '✓', cor: 'text-emerald-400' }
    };
    const FILTROS = ['prestadora', 'tecnico', 'cliente', 'estado', 'equipamento', 'analista'];
    const ROTULO_FILTRO = {
        prestadora: 'Prestadora', tecnico: 'Técnico', cliente: 'Cliente',
        estado: 'Estado', equipamento: 'Modelo', analista: 'Analista'
    };
    const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const pct = (v) => `${Number(v).toFixed(1).replace('.', ',')}%`;
    const el = (id) => document.getElementById(id);
    class DashboardUI extends BaseUI {
        constructor() {
            super();
            this.charts = {};
            this.dados = null;
            this.abaAtual = 'geral';
            this.estado = { preset: '90', inicio: '', fim: '', comparar: true };
            FILTROS.forEach(f => this.estado[f] = '');
            this.lerUrl();
            this.ligarEventos();
            this.destacarPreset();
            this.mostrarAba('geral');
            this.carregar();
        }
        // ---------------- estado e filtros ----------------
        iso(d) {
            const m = String(d.getMonth() + 1).padStart(2, '0');
            const dia = String(d.getDate()).padStart(2, '0');
            return `${d.getFullYear()}-${m}-${dia}`;
        }
        aplicarPreset(p) {
            const hoje = new Date();
            const recuar = (dias) => { const d = new Date(hoje); d.setDate(d.getDate() - dias); return this.iso(d); };
            this.estado.preset = p;
            if (p === 'tudo') {
                this.estado.inicio = '';
                this.estado.fim = '';
            }
            else if (p === 'ano') {
                this.estado.inicio = `${hoje.getFullYear()}-01-01`;
                this.estado.fim = this.iso(hoje);
            }
            else {
                this.estado.inicio = recuar(parseInt(p) - 1);
                this.estado.fim = this.iso(hoje);
            }
            el('filtro-inicio').value = this.estado.inicio;
            el('filtro-fim').value = this.estado.fim;
        }
        lerUrl() {
            const q = new URLSearchParams(window.location.search);
            if (Array.from(q.keys()).length === 0) {
                this.aplicarPreset('90');
                return;
            }
            this.estado.preset = q.get('preset') || 'custom';
            this.estado.inicio = q.get('inicio') || '';
            this.estado.fim = q.get('fim') || '';
            this.estado.comparar = q.get('comparar') !== '0';
            FILTROS.forEach(f => this.estado[f] = q.get(f) || '');
            if (['7', '30', '90', 'ano', 'tudo'].includes(this.estado.preset))
                this.aplicarPreset(this.estado.preset);
            el('filtro-inicio').value = this.estado.inicio;
            el('filtro-fim').value = this.estado.fim;
            el('chk-comparar').checked = this.estado.comparar;
        }
        params(comPreset = false) {
            const q = new URLSearchParams();
            if (this.estado.inicio)
                q.set('inicio', this.estado.inicio);
            if (this.estado.fim)
                q.set('fim', this.estado.fim);
            if (!this.estado.comparar)
                q.set('comparar', '0');
            FILTROS.forEach(f => { if (this.estado[f])
                q.set(f, this.estado[f]); });
            if (comPreset)
                q.set('preset', this.estado.preset);
            return q;
        }
        setFiltro(chave, valor) {
            this.estado[chave] = valor;
            this.carregar();
        }
        destacarPreset() {
            document.querySelectorAll('.preset-btn').forEach((b) => {
                const ativo = b.dataset.preset === this.estado.preset;
                b.classList.toggle('bg-cyan-600', ativo);
                b.classList.toggle('text-white', ativo);
                b.classList.toggle('text-slate-400', !ativo);
            });
        }
        ligarEventos() {
            document.querySelectorAll('.preset-btn').forEach(b => b.addEventListener('click', () => {
                this.aplicarPreset(b.dataset.preset);
                this.destacarPreset();
                this.carregar();
            }));
            el('btn-aplicar').addEventListener('click', () => {
                this.estado.preset = 'custom';
                this.estado.inicio = el('filtro-inicio').value;
                this.estado.fim = el('filtro-fim').value;
                this.destacarPreset();
                this.carregar();
            });
            el('chk-comparar').addEventListener('change', () => {
                this.estado.comparar = el('chk-comparar').checked;
                this.carregar();
            });
            document.querySelectorAll('.filtro-sel').forEach(s => s.addEventListener('change', () => {
                const chave = s.id.replace('f-', '');
                this.setFiltro(chave, s.value);
            }));
            el('btn-limpar').addEventListener('click', () => {
                FILTROS.forEach(f => this.estado[f] = '');
                this.carregar();
            });
            document.querySelectorAll('.tab-btn').forEach(b => b.addEventListener('click', () => this.mostrarAba(b.dataset.tab)));
            el('sel-dimensao').addEventListener('change', () => this.desenharDimensao());
            el('sel-ordem').addEventListener('change', () => this.desenharTabelaTecnicos());
            window.addEventListener('resize', () => Object.values(this.charts).forEach((c) => c.resize()));
        }
        mostrarAba(aba) {
            this.abaAtual = aba;
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('hidden', p.id !== `tab-${aba}`));
            document.querySelectorAll('.tab-btn').forEach(b => {
                const ativo = b.dataset.tab === aba;
                b.classList.toggle('text-cyan-400', ativo);
                b.classList.toggle('border-b-2', ativo);
                b.classList.toggle('border-cyan-400', ativo);
                b.classList.toggle('text-slate-500', !ativo);
            });
            if (this.dados && !this.dados.vazio)
                this.desenharAba(aba);
        }
        // ---------------- dados ----------------
        async carregar() {
            const consulta = this.params().toString();
            window.history.replaceState(null, '', `?${this.params(true).toString()}`);
            el('btn-exportar').href = `/api/dashboard/exportar/?${consulta}`;
            try {
                const resposta = await fetch(`/api/dashboard/?${consulta}`);
                const res = await resposta.json();
                if (res.status !== 'sucesso') {
                    alert('Erro: ' + res.mensagem);
                    return;
                }
                this.dados = res.dados;
                this.preencherOpcoes(res.dados.opcoes);
                this.desenharFiltrosAtivos();
                const vazio = !!res.dados.vazio;
                el('estado-vazio').classList.toggle('hidden', !vazio);
                el('conteudo-dashboard').classList.toggle('hidden', vazio);
                if (vazio) {
                    el('periodo-info').innerText = '';
                    return;
                }
                this.desenharPeriodo();
                this.desenharKpis();
                this.desenharAba(this.abaAtual);
            }
            catch (erro) {
                console.error('Erro na busca de dados', erro);
            }
        }
        preencherOpcoes(op) {
            const montar = (id, titulo, itens, chave) => {
                const sel = el(id);
                sel.innerHTML = `<option value="">${titulo}</option>` + itens.map(i => `<option value="${esc(i.id)}">${esc(i.nome)}</option>`).join('');
                sel.value = this.estado[chave] || '';
            };
            montar('f-prestadora', 'Todas as prestadoras', op.prestadoras, 'prestadora');
            montar('f-tecnico', 'Todos os técnicos', op.tecnicos, 'tecnico');
            montar('f-cliente', 'Todos os clientes', op.clientes, 'cliente');
            montar('f-estado', 'Todos os estados', op.estados.map((e) => ({ id: e, nome: e })), 'estado');
            montar('f-equipamento', 'Todos os modelos', op.equipamentos, 'equipamento');
            montar('f-analista', 'Todos os analistas', op.analistas, 'analista');
        }
        desenharFiltrosAtivos() {
            const caixa = el('filtros-ativos');
            caixa.innerHTML = '';
            let algum = false;
            FILTROS.forEach(f => {
                if (!this.estado[f])
                    return;
                algum = true;
                const sel = el(`f-${f}`);
                const texto = sel.selectedOptions[0] ? sel.selectedOptions[0].text : this.estado[f];
                const chip = document.createElement('button');
                chip.className = 'flex items-center gap-1 bg-cyan-500/10 border border-cyan-500/40 text-cyan-300 text-[11px] px-2 py-1 rounded-full';
                chip.innerHTML = `<span>${esc(ROTULO_FILTRO[f])}: <b>${esc(texto)}</b></span><span class="text-cyan-500">✕</span>`;
                chip.addEventListener('click', () => this.setFiltro(f, ''));
                caixa.appendChild(chip);
            });
            if (!algum)
                caixa.innerHTML = '<span class="text-[11px] text-slate-600">nenhum (clique em um gráfico para filtrar)</span>';
            el('btn-limpar').classList.toggle('hidden', !algum);
        }
        desenharPeriodo() {
            const m = this.dados.meta;
            const br = (s) => s.split('-').reverse().join('/');
            const gran = { dia: 'dia', semana: 'semana', mes: 'mês' };
            let txt = `${br(m.inicio)} a ${br(m.fim)} · agrupado por ${gran[m.granularidade]}`;
            if (m.anterior)
                txt += ` · comparado a ${br(m.anterior.inicio)} a ${br(m.anterior.fim)}`;
            el('periodo-info').innerText = txt;
        }
        // ---------------- KPIs ----------------
        delta(id, kpi, tipo, menorMelhor) {
            const alvo = el(id);
            if (kpi.delta === null || kpi.delta === undefined) {
                alvo.innerHTML = '';
                return;
            }
            const valor = tipo === 'pct' ? kpi.delta_pct : kpi.delta;
            if (valor === null || valor === undefined) {
                alvo.innerHTML = '';
                return;
            }
            const sobe = valor > 0;
            const zero = Math.abs(valor) < 0.05;
            let cor = 'text-slate-400';
            if (!zero && menorMelhor !== null)
                cor = (sobe === menorMelhor) ? 'text-rose-400' : 'text-emerald-400';
            const seta = zero ? '■' : (sobe ? '▲' : '▼');
            const sinal = sobe ? '+' : '';
            const unidade = tipo === 'pct' ? '%' : ' p.p.';
            alvo.innerHTML = `<span class="${cor} font-bold">${seta} ${sinal}${String(valor).replace('.', ',')}${unidade}</span> <span class="text-slate-500">vs. período anterior</span>`;
        }
        desenharKpis() {
            const k = this.dados.kpis;
            el('k-triagens').innerText = String(k.triagens.valor);
            this.delta('k-triagens-delta', k.triagens, 'pct', null);
            el('k-triagens-sub').innerText = `${k.defeitos} com defeito · ${k.nff} NFF`;
            el('k-nff').innerText = pct(k.taxa_nff.valor);
            this.delta('k-nff-delta', k.taxa_nff, 'pp', true);
            el('k-nff-marcador').style.left = `${Math.min(99, Math.max(0, k.taxa_nff.valor))}%`;
            el('k-div').innerText = k.comparaveis ? pct(k.divergencia.valor) : '--';
            this.delta('k-div-delta', k.divergencia, 'pp', true);
            el('k-div-sub').innerText = k.comparaveis ? `${k.divergentes} de ${k.comparaveis} comparáveis` : 'sem diagnósticos comparáveis';
            el('k-reinc').innerText = String(k.reincidencia.series);
            el('k-reinc-sub').innerText = k.reincidencia.series
                ? `${k.reincidencia.triagens} triagens (${pct(k.reincidencia.pct)} do total)` : 'nenhuma série repetida';
            const a = k.tecnicos_alerta;
            el('k-alerta').innerText = `${a.criticos + a.atencao}`;
            el('k-alerta-sub').innerText = `${a.criticos} crítico(s), ${a.atencao} atenção · ${a.avaliados} avaliados`;
            this.desenharSpark('spark-triagens', this.dados.serie.pontos.map((p) => p.total), COR.ciano);
            this.desenharSpark('spark-nff', this.dados.serie.pontos.map((p) => p.taxa_nff), COR.rosa);
        }
        desenharSpark(id, valores, cor) {
            const c = this.grafico(id);
            c.setOption({
                animation: false, grid: { left: 0, right: 0, top: 4, bottom: 2 },
                xAxis: { type: 'category', show: false, data: valores.map((_, i) => i) },
                yAxis: { type: 'value', show: false, min: 0 },
                series: [{ type: 'line', data: valores, smooth: true, symbol: 'none', connectNulls: true,
                        lineStyle: { color: cor, width: 2 }, areaStyle: { color: cor, opacity: 0.15 } }]
            }, true);
        }
        // ---------------- gráficos ----------------
        grafico(id) {
            const dom = el(id);
            let c = this.charts[id];
            if (!c || c.getDom() !== dom) {
                if (c)
                    c.dispose();
                c = echarts.init(dom, null, { renderer: 'canvas' });
                this.charts[id] = c;
            }
            return c;
        }
        desenharAba(aba) {
            if (aba === 'geral') {
                this.desenharInsights();
                this.desenharTendencia();
                this.desenharDimensao();
            }
            if (aba === 'tecnicos') {
                this.desenharFunil();
                this.desenharTabelaTecnicos();
            }
            if (aba === 'causas') {
                this.desenharPareto();
                this.desenharPecas();
                this.desenharTreemap();
                this.desenharTransicoes();
                this.desenharReincidencia();
            }
            if (aba === 'detalhe')
                this.desenharRecentes();
            setTimeout(() => Object.values(this.charts).forEach((c) => c.resize()), 50);
        }
        estiloBase() {
            return {
                textStyle: { color: COR.texto },
                tooltip: { backgroundColor: '#0f172a', borderColor: COR.eixo, textStyle: { color: '#e2e8f0', fontSize: 12 } }
            };
        }
        desenharInsights() {
            const caixa = el('lista-insights');
            const itens = this.dados.insights;
            if (!itens.length) {
                caixa.innerHTML = '<p class="text-xs text-slate-500">Poucos dados para gerar insights neste recorte.</p>';
                return;
            }
            caixa.innerHTML = itens.map((i, idx) => {
                const n = NIVEL[i.nivel];
                const botao = i.filtro ? `<button data-idx="${idx}" class="btn-insight mt-1 text-[10px] font-bold uppercase text-cyan-400 hover:text-cyan-300">Filtrar por isso →</button>` : '';
                return `<div class="border-l-4 ${n.borda} bg-[#0f172a] rounded-r-lg px-3 py-2">
                    <p class="text-xs font-bold text-slate-100"><span class="${n.cor} mr-1">${n.icone}</span>${esc(i.titulo)}</p>
                    <p class="text-[11px] text-slate-400 mt-0.5">${esc(i.texto)}</p>${botao}</div>`;
            }).join('');
            caixa.querySelectorAll('.btn-insight').forEach(b => b.addEventListener('click', () => {
                const filtro = itens[parseInt(b.dataset.idx)].filtro;
                Object.keys(filtro).forEach(k => this.estado[k] = String(filtro[k]));
                this.carregar();
            }));
        }
        desenharTendencia() {
            const pontos = this.dados.serie.pontos;
            const ref = this.dados.meta.referencia_nff;
            const c = this.grafico('chart-tendencia');
            c.setOption({
                ...this.estiloBase(),
                grid: { left: 44, right: 44, top: 36, bottom: pontos.length > 14 ? 64 : 34 },
                legend: { top: 0, textStyle: { color: COR.texto }, data: ['Triagens', 'Taxa de NFF'] },
                tooltip: { ...this.estiloBase().tooltip, trigger: 'axis' },
                xAxis: { type: 'category', data: pontos.map(p => p.rotulo), axisLine: { lineStyle: { color: COR.eixo } }, axisLabel: { color: COR.texto } },
                yAxis: [
                    { type: 'value', name: 'Triagens', minInterval: 1, splitLine: { lineStyle: { color: COR.eixo, opacity: 0.4 } }, axisLabel: { color: COR.texto } },
                    { type: 'value', name: 'NFF %', min: 0, max: 100, splitLine: { show: false }, axisLabel: { color: COR.texto, formatter: '{value}%' } }
                ],
                dataZoom: pontos.length > 14 ? [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8, borderColor: COR.eixo, textStyle: { color: COR.texto } }] : [],
                series: [
                    { name: 'Triagens', type: 'bar', data: pontos.map(p => p.total), itemStyle: { color: COR.ciano, opacity: 0.75, borderRadius: [3, 3, 0, 0] } },
                    { name: 'Taxa de NFF', type: 'line', yAxisIndex: 1, data: pontos.map(p => p.taxa_nff), smooth: false, connectNulls: false,
                        symbolSize: 7, lineStyle: { color: COR.rosa, width: 2 }, itemStyle: { color: COR.rosa },
                        markArea: { silent: true, itemStyle: { color: 'rgba(251,191,36,0.08)' },
                            label: { color: COR.ambar, fontSize: 10, position: 'insideTopRight', formatter: 'referência 20%–50%' },
                            data: [[{ yAxis: ref.min }, { yAxis: ref.max }]] },
                        markLine: { silent: true, symbol: 'none', lineStyle: { color: COR.cinza, type: 'dashed' },
                            label: { color: COR.texto, formatter: `média ${this.dados.meta.p_medio}%` }, data: [{ yAxis: this.dados.meta.p_medio }] } }
                ]
            }, true);
        }
        desenharDimensao() {
            const chave = el('sel-dimensao').value;
            const itens = this.dados.dimensoes[chave] || [];
            const c = this.grafico('chart-dimensao');
            c.off('click');
            c.setOption({
                ...this.estiloBase(),
                grid: { left: 8, right: 60, top: 28, bottom: 8, containLabel: true },
                legend: { top: 0, textStyle: { color: COR.texto } },
                tooltip: { ...this.estiloBase().tooltip, trigger: 'axis', axisPointer: { type: 'shadow' },
                    formatter: (ps) => {
                        const d = itens[ps[0].dataIndex];
                        return `<b>${esc(d.nome)}</b><br/>${d.total} triagens<br/>NFF: <b>${pct(d.taxa_nff)}</b> (IC 95%: ${pct(d.ic_inf)} a ${pct(d.ic_sup)})<br/>${STATUS[d.status].rotulo}`;
                    } },
                xAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: COR.eixo, opacity: 0.4 } }, axisLabel: { color: COR.texto } },
                yAxis: { type: 'category', inverse: true, data: itens.map(i => i.nome), axisLabel: { color: '#cbd5e1', width: 150, overflow: 'truncate' }, axisLine: { lineStyle: { color: COR.eixo } } },
                series: [
                    { name: 'Defeito confirmado', type: 'bar', stack: 't', data: itens.map(i => i.acertos), itemStyle: { color: COR.ciano } },
                    { name: 'Peça funcional (NFF)', type: 'bar', stack: 't',
                        data: itens.map(i => ({ value: i.nff, taxa: i.taxa_nff })),
                        itemStyle: { color: COR.rosa }, label: { show: true, position: 'right', color: '#e2e8f0', formatter: (p) => pct(p.data.taxa) } }
                ]
            }, true);
            c.on('click', (p) => {
                const d = itens[p.dataIndex];
                if (d)
                    this.setFiltro(chave, String(d.id));
            });
        }
        desenharFunil() {
            const tecnicos = this.dados.tecnicos;
            const p = this.dados.meta.p_medio / 100;
            const nmax = Math.max(10, ...tecnicos.map(t => t.total)) * 1.15;
            const limite = (z, n) => 100 * (p + z * Math.sqrt(p * (1 - p) / n));
            const curva = (z) => {
                const pts = [];
                for (let i = 0; i <= 40; i++) {
                    const n = Math.max(this.dados.meta.min_amostra, Math.round(this.dados.meta.min_amostra + (nmax - this.dados.meta.min_amostra) * i / 40));
                    pts.push([n, Math.min(100, Math.max(0, limite(z, n)))]);
                }
                return pts;
            };
            const linha = (nome, z, cor, tipo) => ({
                name: nome, type: 'line', data: curva(z), symbol: 'none', silent: true, tooltip: { show: false },
                lineStyle: { color: cor, type: tipo, width: 1.5 }
            });
            const c = this.grafico('chart-funil');
            c.off('click');
            c.setOption({
                ...this.estiloBase(),
                grid: { left: 48, right: 24, top: 40, bottom: 44 },
                legend: { top: 0, textStyle: { color: COR.texto, fontSize: 10 }, data: ['Limite 3σ', 'Limite 2σ', 'Limite inferior 2σ'] },
                tooltip: { ...this.estiloBase().tooltip, trigger: 'item',
                    formatter: (pt) => {
                        if (pt.seriesType !== 'scatter')
                            return '';
                        const v = pt.data.value;
                        return `<b>${esc(v[2])}</b><br/>${v[0]} triagens<br/>NFF: <b>${pct(v[1])}</b> (IC 95%: ${pct(v[5])} a ${pct(v[6])})<br/>${STATUS[v[3]].rotulo}${v[7] !== null ? ` (z = ${v[7]})` : ''}`;
                    } },
                xAxis: { type: 'value', name: 'Triagens do técnico (n)', nameLocation: 'middle', nameGap: 26, min: 0, max: Math.ceil(nmax),
                    splitLine: { show: false }, axisLabel: { color: COR.texto }, axisLine: { lineStyle: { color: COR.eixo } } },
                yAxis: { type: 'value', name: 'NFF %', min: 0, max: 100, splitLine: { lineStyle: { color: COR.eixo, opacity: 0.4 } }, axisLabel: { color: COR.texto, formatter: '{value}%' } },
                series: [
                    linha('Limite 3σ', 3, COR.rosa, 'dashed'),
                    linha('Limite 2σ', 2, COR.ambar, 'dashed'),
                    linha('Limite inferior 2σ', -2, COR.verde, 'dotted'),
                    { name: 'Técnicos', type: 'scatter', symbolSize: 13,
                        data: tecnicos.map(t => ({
                            value: [t.total, t.taxa_nff, t.nome, t.status, t.id, t.ic_inf, t.ic_sup, t.z],
                            itemStyle: { color: STATUS[t.status].cor, borderColor: '#0f172a', borderWidth: 1 },
                            label: { show: ['critico', 'atencao', 'destaque'].includes(t.status), formatter: t.nome, position: 'right', color: '#e2e8f0', fontSize: 10 }
                        })),
                        markLine: { silent: true, symbol: 'none', lineStyle: { color: COR.cinza }, label: { color: COR.texto, formatter: `média ${this.dados.meta.p_medio}%` }, data: [{ yAxis: this.dados.meta.p_medio }] } }
                ]
            }, true);
            c.on('click', (pt) => {
                if (pt.seriesType === 'scatter')
                    this.setFiltro('tecnico', String(pt.data.value[4]));
            });
        }
        desenharTabelaTecnicos() {
            const ordem = el('sel-ordem').value;
            const sev = { critico: 0, atencao: 1, normal: 2, destaque: 3, insuficiente: 4 };
            const lista = [...this.dados.tecnicos];
            if (ordem === 'ic')
                lista.sort((a, b) => (sev[a.status] - sev[b.status]) || (b.ic_inf - a.ic_inf));
            if (ordem === 'taxa')
                lista.sort((a, b) => b.taxa_nff - a.taxa_nff);
            if (ordem === 'volume')
                lista.sort((a, b) => b.total - a.total);
            if (ordem === 'melhor')
                lista.sort((a, b) => (b.status === 'destaque' ? 1 : 0) - (a.status === 'destaque' ? 1 : 0) || a.taxa_nff - b.taxa_nff);
            const corpo = el('tabela-tecnicos');
            corpo.innerHTML = lista.map(t => {
                const s = STATUS[t.status];
                return `<tr class="linha-tec cursor-pointer hover:bg-slate-800/50" data-id="${t.id}">
                    <td class="py-2 pr-3"><div class="font-bold text-slate-200">${esc(t.nome)}</div><div class="text-[10px] text-slate-500">${esc(t.prestadora)}</div></td>
                    <td class="py-2 pr-3 text-right text-slate-300">${t.total}</td>
                    <td class="py-2 pr-3"><div class="flex items-center gap-2">
                        <div class="relative w-28 h-2 bg-slate-700/60 rounded" title="IC 95%: ${pct(t.ic_inf)} a ${pct(t.ic_sup)}">
                            <div class="absolute h-2 rounded bg-rose-500/40" style="left:${t.ic_inf}%;width:${Math.max(1, t.ic_sup - t.ic_inf)}%"></div>
                            <div class="absolute -top-0.5 h-3 w-1 rounded bg-white" style="left:${Math.min(99, t.taxa_nff)}%"></div>
                        </div><span class="text-slate-200 font-bold">${pct(t.taxa_nff)}</span></div></td>
                    <td class="py-2 pr-3 text-right text-slate-300">${t.divergencias}</td>
                    <td class="py-2"><span class="border ${s.classe} text-[10px] font-bold px-2 py-0.5 rounded-full">${s.rotulo}</span></td></tr>`;
            }).join('');
            corpo.querySelectorAll('.linha-tec').forEach(tr => tr.addEventListener('click', () => this.setFiltro('tecnico', tr.dataset.id)));
        }
        desenharPecas() {
            const p = this.dados.pecas;
            el('pecas-nota').innerText = p.itens.length
                ? `${p.com_peca} triagens com peça do catálogo informada (${p.sem_peca} sem peça ficaram de fora). NFF = trocada, mas a bancada achou funcional.`
                : 'Nenhuma triagem deste recorte tem peça do catálogo informada. Selecione a peça trocada na triagem.';
            el('tabela-pecas').innerHTML = p.itens.map((i) => `<tr>
                <td class="py-2 pr-3"><div class="font-mono text-cyan-400">${esc(i.part_number)}</div><div class="text-[10px] text-slate-500">${esc(i.descricao)}</div></td>
                <td class="py-2 text-right text-slate-300">${i.trocas}</td>
                <td class="py-2 text-right text-slate-300">${i.nff}</td>
                <td class="py-2 pl-3"><span class="font-bold" style="color:${this.corNff(i.taxa_nff)}">${pct(i.taxa_nff)}</span></td></tr>`).join('');
        }
        desenharPareto() {
            const p = this.dados.pareto_defeitos;
            el('pareto-nota').innerText = p.total
                ? `${p.total} defeitos confirmados com descrição${p.sem_registro ? ` (${p.sem_registro} sem descrição ficaram de fora)` : ''}. A linha mostra o acumulado.`
                : 'Sem defeitos confirmados com descrição neste recorte.';
            const c = this.grafico('chart-pareto');
            c.setOption({
                ...this.estiloBase(),
                grid: { left: 40, right: 44, top: 28, bottom: 90 },
                tooltip: { ...this.estiloBase().tooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
                xAxis: { type: 'category', data: p.itens.map((i) => i.rotulo), axisLabel: { color: '#cbd5e1', rotate: 35, width: 110, overflow: 'truncate', fontSize: 10 }, axisLine: { lineStyle: { color: COR.eixo } } },
                yAxis: [
                    { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: COR.eixo, opacity: 0.4 } }, axisLabel: { color: COR.texto } },
                    { type: 'value', min: 0, max: 100, splitLine: { show: false }, axisLabel: { color: COR.texto, formatter: '{value}%' } }
                ],
                series: [
                    { name: 'Ocorrências', type: 'bar', data: p.itens.map((i) => i.qtd), itemStyle: { color: COR.ciano, borderRadius: [3, 3, 0, 0] } },
                    { name: 'Acumulado', type: 'line', yAxisIndex: 1, data: p.itens.map((i) => i.acumulado_pct), symbolSize: 6,
                        lineStyle: { color: COR.ambar }, itemStyle: { color: COR.ambar },
                        markLine: { silent: true, symbol: 'none', lineStyle: { color: COR.cinza, type: 'dashed' }, label: { color: COR.texto, formatter: '80%' }, data: [{ yAxis: 80 }] } }
                ]
            }, true);
        }
        corNff(taxa) {
            // verde (0%) -> âmbar (35%) -> vermelho (70%+)
            const t = Math.min(1, taxa / 70);
            const mix = (a, b, k) => a.map((v, i) => Math.round(v + (b[i] - v) * k));
            const rgb = t < 0.5 ? mix([16, 185, 129], [245, 158, 11], t * 2) : mix([245, 158, 11], [225, 29, 72], (t - 0.5) * 2);
            return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
        }
        desenharTreemap() {
            const modelos = this.dados.modelos;
            const c = this.grafico('chart-treemap');
            c.off('click');
            c.setOption({
                ...this.estiloBase(),
                tooltip: { ...this.estiloBase().tooltip, formatter: (p) => `<b>${esc(p.data.name)}</b><br/>PN ${esc(p.data.pn)}<br/>${p.data.value} triagens · NFF <b>${pct(p.data.taxa)}</b> (${p.data.nff})` },
                series: [{ type: 'treemap', roam: false, nodeClick: false, breadcrumb: { show: false }, width: '100%', height: '100%',
                        label: { show: true, color: '#fff', fontSize: 11, formatter: (p) => `${p.data.name}\n${pct(p.data.taxa)} NFF` },
                        itemStyle: { borderColor: '#0f172a', borderWidth: 2, gapWidth: 2 },
                        data: modelos.map(m => ({ name: m.modelo, pn: m.pn, id: m.id, value: m.total, nff: m.nff, taxa: m.taxa_nff,
                            itemStyle: { color: this.corNff(m.taxa_nff) } })) }]
            }, true);
            c.on('click', (p) => { if (p.data && p.data.id)
                this.setFiltro('equipamento', String(p.data.id)); });
        }
        desenharTransicoes() {
            const t = this.dados.transicoes;
            const caixa = el('lista-transicoes');
            if (!t.itens.length) {
                caixa.innerHTML = `<p class="text-xs text-slate-500">${t.comparaveis ? 'Nenhuma divergência entre campo e bancada neste recorte.' : 'Sem triagens com diagnóstico do técnico e defeito constatado preenchidos.'}</p>`;
                return;
            }
            caixa.innerHTML = `<p class="text-[11px] text-slate-400 mb-1">${t.divergentes} de ${t.comparaveis} diagnósticos comparáveis divergem (${pct(t.pct_div)}).</p>` +
                t.itens.map((i) => `<div>
                    <div class="flex justify-between text-xs"><span class="text-slate-300"><span class="text-amber-300">${esc(i.diagnostico)}</span> → <span class="text-cyan-300">${esc(i.constatado)}</span></span><span class="text-slate-400 font-bold">${i.qtd}</span></div>
                    <div class="h-1.5 bg-slate-700/60 rounded mt-1"><div class="h-1.5 rounded bg-amber-500/70" style="width:${i.pct}%"></div></div></div>`).join('');
        }
        desenharReincidencia() {
            const itens = this.dados.reincidencia.itens;
            el('tabela-reincidencia').innerHTML = itens.length ? itens.map(i => `<tr>
                <td class="py-2 font-mono text-slate-200">${esc(i.sn)}</td><td class="py-2 text-slate-300">${esc(i.modelo)}</td>
                <td class="py-2 text-right text-indigo-300 font-bold">${i.vezes}</td><td class="py-2 text-right text-slate-400">${esc(i.ultima)}</td></tr>`).join('')
                : '<tr><td colspan="4" class="py-3 text-slate-500">Nenhuma série repetida neste recorte.</td></tr>';
        }
        desenharRecentes() {
            const itens = this.dados.recentes;
            el('tabela-recentes').innerHTML = itens.map(t => {
                const resultado = t.status === 1
                    ? '<span class="border bg-rose-500/15 text-rose-300 border-rose-500/40 text-[10px] font-bold px-2 py-0.5 rounded-full">NFF</span>'
                    : '<span class="border bg-cyan-500/15 text-cyan-300 border-cyan-500/40 text-[10px] font-bold px-2 py-0.5 rounded-full">Defeito</span>';
                const diverg = t.divergente ? ' <span title="Diagnóstico diverge da bancada" class="text-amber-300 font-bold">≠</span>' : '';
                return `<tr class="hover:bg-slate-800/50">
                    <td class="py-2 pr-3 text-slate-400">${esc(t.data)}</td><td class="py-2 pr-3 text-slate-200">${esc(t.ticket)}</td>
                    <td class="py-2 pr-3 font-mono text-slate-300">${esc(t.sn)}</td><td class="py-2 pr-3 text-slate-300">${esc(t.tecnico)}</td>
                    <td class="py-2 pr-3 text-slate-300">${esc(t.cliente)}</td><td class="py-2 pr-3 text-slate-300">${esc(t.modelo)}</td>
                    <td class="py-2 pr-3">${resultado}${diverg}</td>
                    <td class="py-2"><a class="text-cyan-400 hover:text-cyan-300 font-bold" href="/visualizar/?id=${t.id}">abrir</a></td></tr>`;
            }).join('');
        }
    }
    window.addEventListener('DOMContentLoaded', () => new DashboardUI());
})();
