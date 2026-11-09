/// <reference path="../BaseUI.ts" />
declare const echarts: any;

(() => {
    type Aba = 'executiva' | 'operacao' | 'qualidade' | 'comercial' | 'pecas' | 'insights';
    const ROTAS: Record<string, string> = { executiva: 'executivo', operacao: 'operacao', qualidade: 'qualidade', comercial: 'comercial', pecas: 'pecas' };
    const COR = { ciano: '#06b6d4', verde: '#10b981', ambar: '#f59e0b', laranja: '#fb923c', vermelho: '#f43f5e', cinza: '#64748b', texto: '#94a3b8', linha: '#334155' };

    class DashboardBIUI extends BaseUI {
        private aba: Aba = 'executiva';
        private graficos: any[] = [];
        private opcoes: any = { ufs: [], analistas: [], modelos: [], clientes: [] };
        private modoTV = false;
        private temporizador: number | undefined;
        private painel = document.getElementById('painel-bi') as HTMLElement;

        constructor() {
            super();
            this.lerEndereco();
            this.ligarEventos();
            this.carregarOpcoes().then(() => { this.lerEndereco(); this.atualizarTela(); });
            this.carregarContadorInsights();
            if (['Administrador', 'Gestor'].includes((window as any).CARGO_USUARIO_SESSAO)) {
                (document.getElementById('btn-atualizar') as HTMLElement).classList.remove('hidden');
            }
        }

        // ------------------------------------------------------------ utilidades
        private el<T extends HTMLElement>(id: string): T { return document.getElementById(id) as T; }
        private iso(d: Date): string { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }

        private fmt(v: number | null | undefined, unidade: string = 'num'): string {
            if (v === null || v === undefined) return '—';
            if (unidade === 'pct') return `${v.toFixed(1).replace('.', ',')}%`;
            if (unidade === 'moeda') return formatarMoeda(v);
            if (unidade === 'horas') return `${v.toFixed(1).replace('.', ',')} h`;
            if (unidade === 'dias') return `${v.toFixed(1).replace('.', ',')} dias`;
            return Math.round(v).toLocaleString('pt-BR');
        }

        // ------------------------------------------------------------ filtros e endereço
        private parametros(extra: boolean = true): URLSearchParams {
            const p = new URLSearchParams();
            const campos: Record<string, string> = { inicio: 'f-inicio', fim: 'f-fim', uf: 'f-uf', analista: 'f-analista', modelo: 'f-modelo', cliente: 'f-cliente', tecnico: 'f-tecnico' };
            Object.keys(campos).forEach((k) => { const v = this.el<HTMLInputElement>(campos[k]).value; if (v) p.set(k, v); });
            if (this.el<HTMLInputElement>('f-historico').checked) p.set('historico', '1');
            if (this.el<HTMLSelectElement>('f-comparar').value === 'ano') p.set('comparar', 'ano');
            if (extra) p.set('aba', this.aba);
            return p;
        }

        private lerEndereco(): void {
            const p = new URLSearchParams(window.location.search);
            const a = p.get('aba') as Aba | null;
            if (a && ['executiva', 'operacao', 'qualidade', 'comercial', 'pecas', 'insights'].includes(a)) this.aba = a;
            const hoje = new Date();
            const ini = new Date(hoje); ini.setDate(hoje.getDate() - 29);
            this.el<HTMLInputElement>('f-inicio').value = p.get('inicio') || this.iso(ini);
            this.el<HTMLInputElement>('f-fim').value = p.get('fim') || this.iso(hoje);
            (['uf', 'analista', 'modelo', 'cliente', 'tecnico'] as const).forEach((k) => {
                const sel = this.el<HTMLSelectElement>('f-' + k);
                const v = p.get(k) || '';
                if (v && ![...sel.options].some((o) => o.value === v)) sel.appendChild(new Option(v, v));
                sel.value = v;
            });
            this.el<HTMLInputElement>('f-historico').checked = p.get('historico') === '1';
            this.el<HTMLSelectElement>('f-comparar').value = p.get('comparar') === 'ano' ? 'ano' : 'anterior';
        }

        private async carregarOpcoes(): Promise<void> {
            try {
                const r = await (await fetch('/api/bi/filtros/')).json();
                if (r.status !== 'sucesso') return;
                this.opcoes = r.dados;
                const preencher = (id: string, itens: { v: any; t: string }[]) => {
                    const sel = this.el<HTMLSelectElement>(id);
                    const atual = sel.value;
                    sel.innerHTML = sel.options[0].outerHTML + itens.map((i) => `<option value="${escapeHtml(i.v)}">${escapeHtml(i.t)}</option>`).join('');
                    sel.value = atual;
                };
                preencher('f-uf', r.dados.ufs.map((u: string) => ({ v: u, t: u })));
                preencher('f-analista', r.dados.analistas.map((a: any) => ({ v: a.id_funcionario, t: a.nome })));
                preencher('f-modelo', r.dados.modelos.map((m: any) => ({ v: m.id_equipamento, t: m.modelo })));
                preencher('f-tecnico', (r.dados.tecnicos || []).map((t: any) => ({ v: t.id_tecnico, t: t.nome })));
                preencher('f-cliente', r.dados.clientes.map((c: any) => ({ v: c.cliente_id, t: c.cliente__razao_social })));
            } catch (e) { /* os filtros continuam utilizáveis sem as listas */ }
        }

        /** Datas de cada atalho de período. Semestre e ano "atuais" vão do começo do semestre/ano até hoje. */
        private intervalo(nome: string): [Date, Date] {
            const hoje = new Date();
            const ini = new Date(hoje);
            if (nome === '7') ini.setDate(hoje.getDate() - 6);
            else if (nome === '30') ini.setDate(hoje.getDate() - 29);
            else if (nome === 'trimestre') ini.setDate(hoje.getDate() - 89);
            else if (nome === 'mes') ini.setDate(1);
            else if (nome === '6m') { ini.setMonth(hoje.getMonth() - 6); ini.setDate(ini.getDate() + 1); }
            else if (nome === '12m') { ini.setFullYear(hoje.getFullYear() - 1); ini.setDate(ini.getDate() + 1); }
            else if (nome === 'semestre') ini.setMonth(hoje.getMonth() < 6 ? 0 : 6, 1);
            else if (nome === 'ano') ini.setMonth(0, 1);
            return [ini, hoje];
        }

        private aplicarPreset(nome: string): void {
            const [ini, fim] = this.intervalo(nome);
            this.el<HTMLInputElement>('f-inicio').value = this.iso(ini);
            this.el<HTMLInputElement>('f-fim').value = this.iso(fim);
            // Períodos "do início do semestre/ano até hoje" comparam melhor com o mesmo período do ano passado.
            this.el<HTMLSelectElement>('f-comparar').value = (nome === 'semestre' || nome === 'ano') ? 'ano' : 'anterior';
            this.atualizarTela();
        }

        private definirFiltro(id: string, valor: string): void {
            const sel = this.el<HTMLSelectElement>(id);
            if (valor && ![...sel.options].some((o) => o.value === valor)) sel.appendChild(new Option(valor, valor));
            sel.value = valor;
            this.atualizarTela();
        }

        private atualizarChips(): void {
            const itens: { id: string; rotulo: string }[] = [];
            (['uf', 'analista', 'modelo', 'cliente', 'tecnico'] as const).forEach((k) => {
                const sel = this.el<HTMLSelectElement>('f-' + k);
                if (sel.value) itens.push({ id: 'f-' + k, rotulo: `${sel.closest('label')?.firstChild?.textContent?.trim()}: ${sel.selectedOptions[0]?.text || sel.value}` });
            });
            this.el('chips-filtros').innerHTML = itens.map((i) => `
                <button type="button" data-limpar="${i.id}" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs font-semibold" aria-label="Remover filtro ${escapeHtml(i.rotulo)}">
                    ${escapeHtml(i.rotulo)} <span aria-hidden="true">×</span></button>`).join('');
            const ini = this.el<HTMLInputElement>('f-inicio').value, fim = this.el<HTMLInputElement>('f-fim').value;
            this.el('texto-periodo').textContent = `Período: ${formatarDataBr(ini)} a ${formatarDataBr(fim)} · comparado com ${this.el<HTMLSelectElement>('f-comparar').value === 'ano' ? 'o mesmo período do ano anterior' : 'o período anterior de mesmo tamanho'}`;
            document.querySelectorAll('.preset').forEach((b) => {
                const [i, f] = this.intervalo((b as HTMLElement).dataset.preset as string);
                b.classList.toggle('on', ini === this.iso(i) && fim === this.iso(f));
            });
        }

        private ligarEventos(): void {
            document.querySelectorAll('.preset').forEach((b) => b.addEventListener('click', () => this.aplicarPreset((b as HTMLElement).dataset.preset as string)));
            ['f-inicio', 'f-fim', 'f-uf', 'f-analista', 'f-modelo', 'f-cliente', 'f-tecnico', 'f-historico', 'f-comparar'].forEach((id) => this.el(id).addEventListener('change', () => this.atualizarTela()));
            this.el('chips-filtros').addEventListener('click', (e) => {
                const b = (e.target as HTMLElement).closest('[data-limpar]') as HTMLElement | null;
                if (b) this.definirFiltro(b.dataset.limpar as string, '');
            });
            this.el('btn-limpar').addEventListener('click', () => {
                ['f-uf', 'f-analista', 'f-modelo', 'f-cliente', 'f-tecnico'].forEach((id) => (this.el<HTMLSelectElement>(id).value = ''));
                this.el<HTMLInputElement>('f-historico').checked = false;
                this.aplicarPreset('30');
            });
            document.querySelectorAll('.aba').forEach((b) => b.addEventListener('click', () => { this.aba = (b as HTMLElement).dataset.aba as Aba; this.atualizarTela(); }));
            this.el('btn-atualizar').addEventListener('click', () => this.atualizarAgora());
            this.el('btn-tv').addEventListener('click', () => this.alternarTV());
            this.painel.addEventListener('click', (e) => {
                const csv = (e.target as HTMLElement).closest('[data-csv]') as HTMLElement | null;
                if (csv) this.exportarTabela(csv.dataset.csv as string);
                const pecaRegioes = (e.target as HTMLElement).closest('[data-peca-regioes]') as HTMLElement | null;
                if (pecaRegioes) this.abrirRegioesDaPeca(`id_peca=${Number(pecaRegioes.dataset.pecaRegioes)}`);
                if ((e.target as HTMLElement).closest('#btn-peca-regioes')) {
                    const pn = (document.getElementById('busca-peca-regioes') as HTMLInputElement).value.trim();
                    if (pn) this.abrirRegioesDaPeca(`pn=${encodeURIComponent(pn)}`); else Mensagem.aviso('Digite o PN da peça.');
                }
                const chamados = (e.target as HTMLElement).closest('[data-chamados]') as HTMLElement | null;
                if (chamados) this.abrirChamadosDoAnalista(Number(chamados.dataset.analista), chamados.dataset.nome || '', chamados.dataset.situacao || 'todos');
                const lido = (e.target as HTMLElement).closest('[data-lido]') as HTMLElement | null;
                if (lido) this.marcarInsight(Number(lido.dataset.id), lido.dataset.lido === '1');
            });
            window.addEventListener('resize', () => this.graficos.forEach((g) => g.resize()));
        }

        private atualizarTela(): void {
            window.history.replaceState(null, '', '?' + this.parametros().toString());
            this.atualizarChips();
            document.querySelectorAll('.aba').forEach((b) => b.setAttribute('aria-selected', String((b as HTMLElement).dataset.aba === this.aba)));
            this.carregar();
        }

        // ------------------------------------------------------------ carga e desenho
        private async carregar(silencioso: boolean = false): Promise<void> {
            this.graficos.forEach((g) => g.dispose());
            this.graficos = [];
            if (!silencioso) {
                this.painel.innerHTML = '<div class="grid grid-cols-1 md:grid-cols-3 gap-4">' + '<div class="bi-card h-28 animate-pulse"></div>'.repeat(6) + '</div>';
            }
            this.painel.setAttribute('aria-busy', 'true');
            try {
                if (this.aba === 'insights') { await this.desenharInsights(); return; }
                const r = await (await fetch(`/api/bi/${ROTAS[this.aba]}/?${this.parametros(false).toString()}`)).json();
                if (r.status !== 'sucesso') { this.painel.innerHTML = this.erro(r.mensagem); return; }
                const pendentes: { id: string; opcao: any; clique?: (nome: string, dado: any, indice: number) => void }[] = [];
                const html = ({ executiva: () => this.htmlExecutiva(r.dados), operacao: () => this.htmlOperacao(r.dados, pendentes),
                    qualidade: () => this.htmlQualidade(r.dados, pendentes), comercial: () => this.htmlComercial(r.dados, pendentes),
                    pecas: () => this.htmlPecas(r.dados, pendentes) } as Record<string, () => string>)[this.aba]();
                this.painel.innerHTML = html;
                this.iniciarGraficos(pendentes);
            } catch (e) {
                this.painel.innerHTML = this.erro('Não foi possível conectar ao servidor.');
            } finally {
                this.painel.setAttribute('aria-busy', 'false');
            }
        }

        // Janela com os chamados de um analista (ativos, atendidos, cancelados ou todos), respeitando os filtros do dashboard.
        private async abrirChamadosDoAnalista(idAnalista: number, nome: string, situacao: string): Promise<void> {
            const rotulos: Record<string, string> = { todos: 'todos os chamados', ativos: 'chamados ativos', atendidos: 'chamados atendidos', cancelados: 'chamados cancelados' };
            try {
                const params = this.parametros(false);
                params.set('id_analista', String(idAnalista));
                params.set('situacao', situacao);
                const r = await (await fetch(`/api/bi/chamados-analista/?${params.toString()}`)).json();
                if (r.status !== 'sucesso') { await Mensagem.erro(r.mensagem); return; }
                const dia = (d: string | null) => d ? formatarDataBr(d.slice(0, 10)) : '—';
                const linhas = r.dados.itens.map((c: any) => `<tr style="border-top:1px solid #33415566">
                    <td style="padding:6px;white-space:nowrap;font-weight:600">${escapeHtml(c.ticket)}</td>
                    <td style="padding:6px;white-space:nowrap">${escapeHtml(c.estado)} / ${escapeHtml(c.cidade)}</td>
                    <td style="padding:6px">${escapeHtml(c.modelo || '—')}</td>
                    <td style="padding:6px;white-space:nowrap">${escapeHtml(c.status)}${c.sem_intervencao_tecnica ? '<br><span style="font-size:10px;color:#67e8f9">sem intervenção técnica</span>' : ''}</td>
                    <td style="padding:6px;white-space:nowrap">${escapeHtml(dia(c.aberto_em))}</td>
                    <td style="padding:6px;white-space:nowrap">${escapeHtml(dia(c.concluido_em))}</td>
                    <td style="padding:6px;white-space:nowrap">${c.ativo ? this.chipSla(c.pct) : '—'}</td></tr>`).join('');
                await Swal.fire({
                    title: `${escapeHtml(nome)}: ${rotulos[situacao] || situacao} (${r.dados.total})`, width: 900, confirmButtonText: 'Fechar', confirmButtonColor: '#64748b',
                    html: r.dados.itens.length === 0 ? '<p style="opacity:.7">Nenhum chamado.</p>'
                        : `<div style="max-height:420px;overflow:auto;font-size:12px;text-align:left"><table style="width:100%"><thead><tr style="opacity:.6">
                            <th style="padding:6px;text-align:left">Ticket</th><th style="text-align:left">UF / Cidade</th><th style="text-align:left">Modelo</th><th style="text-align:left">Status</th>
                            <th style="text-align:left">Aberto</th><th style="text-align:left">Concluído</th><th style="text-align:left">SLA</th></tr></thead><tbody>${linhas}</tbody></table></div>
                            ${r.dados.limitado ? '<p style="font-size:11px;opacity:.6;margin-top:8px">Mostrando os 300 mais recentes.</p>' : ''}`
                });
            } catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }

        // Regiões onde uma peça foi usada no período escolhido (por macrorregião, estado e cidade).
        private async abrirRegioesDaPeca(consulta: string): Promise<void> {
            try {
                const params = this.parametros(false);
                const r = await (await fetch(`/api/bi/peca-regioes/?${params.toString()}&${consulta}`)).json();
                if (r.status !== 'sucesso') { await Mensagem.aviso(r.mensagem, 'Peça'); return; }
                const d = r.dados;
                const bloco = (titulo: string, itens: any[], extra = (x: any) => '') => itens.length === 0 ? '' : `
                    <p style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;opacity:.6;margin:12px 0 4px">${titulo}</p>
                    <table style="width:100%">${itens.map((x) => `<tr style="border-top:1px solid #33415566"><td style="padding:4px 6px">${escapeHtml(x.nome)}${extra(x)}</td>
                        <td style="padding:4px 6px;text-align:right;font-weight:bold">${x.usos}</td><td style="padding:4px 6px;text-align:right;opacity:.7">${x.pct}%</td></tr>`).join('')}</table>`;
                await Swal.fire({
                    title: `${escapeHtml(d.peca.part_number)}: onde é mais usada`, width: 620, confirmButtonText: 'Fechar', confirmButtonColor: '#64748b',
                    html: d.total === 0 ? `<p style="opacity:.7">Nenhum uso desta peça em chamados concluídos entre ${escapeHtml(formatarDataBr(d.periodo.inicio))} e ${escapeHtml(formatarDataBr(d.periodo.fim))}.</p>`
                        : `<div style="text-align:left;font-size:13px;max-height:440px;overflow:auto"><p style="opacity:.7;font-size:12px">${escapeHtml(d.peca.descricao)} · ${d.total} uso(s) entre ${escapeHtml(formatarDataBr(d.periodo.inicio))} e ${escapeHtml(formatarDataBr(d.periodo.fim))}</p>
                            ${bloco('Por macrorregião', d.macro)}${bloco('Por estado', d.estados)}${bloco('Cidades que mais usam (10 maiores)', d.cidades, (x: any) => ` <span style="opacity:.5">/ ${escapeHtml(x.uf)}</span>`)}</div>`
                });
            } catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }

        private erro(mensagem: string): string {
            return `<div class="bi-card text-center"><p class="text-rose-400 font-semibold">${escapeHtml(mensagem)}</p>
                <button type="button" onclick="location.reload()" class="mt-3 px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm font-semibold">Tentar de novo</button></div>`;
        }

        private vazio(texto: string): string { return `<p class="text-sm text-slate-500 py-6 text-center">${escapeHtml(texto)}</p>`; }

        private cartao(titulo: string, corpo: string, extra: string = '', botaoCsv: string = ''): string {
            return `<section class="bi-card ${extra}"><div class="flex items-start justify-between gap-2"><h2>${escapeHtml(titulo)}</h2>${botaoCsv ? `<button type="button" data-csv="${botaoCsv}" class="text-[11px] text-cyan-400 hover:text-cyan-300 font-semibold">Exportar CSV</button>` : ''}</div>${corpo}</section>`;
        }

        private grafico(id: string, descricao: string, altura: string = 'h-72'): string {
            return `<div id="${id}" class="${altura} w-full" role="img" aria-label="${escapeHtml(descricao)}"></div>`;
        }

        private aviso(texto: string): string {
            return `<p class="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">${escapeHtml(texto)}</p>`;
        }

        private chip(texto: string, cor: 'ok' | 'warn' | 'bad' | 'info' | 'mut'): string {
            const c = { ok: 'text-emerald-300 bg-emerald-500/10', warn: 'text-amber-300 bg-amber-500/10', bad: 'text-rose-300 bg-rose-500/10', info: 'text-cyan-300 bg-cyan-500/10', mut: 'text-slate-300 bg-slate-700/50' }[cor];
            return `<span class="px-2 py-0.5 rounded-md text-[11px] font-semibold ${c}">${escapeHtml(texto)}</span>`;
        }

        private chipSla(pct: number): string {
            return this.chip(`${pct.toFixed(0)}%`, pct > 100 ? 'bad' : pct >= 80 ? 'warn' : pct >= 60 ? 'info' : 'ok');
        }

        private cartaoKpi(k: any): string {
            let delta = '';
            if (k.atual !== null && k.anterior !== null && k.anterior !== undefined) {
                const sinal = k.tendencia === 'up' ? '▲' : k.tendencia === 'down' ? '▼' : '■';
                const cor = k.bom === true ? 'text-emerald-400' : k.bom === false ? 'text-rose-400' : 'text-slate-400';
                const mudanca = k.unidade === 'pct' ? `${Math.abs(k.diferenca).toFixed(1).replace('.', ',')} pp`
                    : k.variacao_pct !== null ? `${Math.abs(k.variacao_pct).toFixed(1).replace('.', ',')}%` : this.fmt(Math.abs(k.diferenca), k.unidade);
                const palavra = k.tendencia === 'up' ? 'subiu' : k.tendencia === 'down' ? 'caiu' : 'ficou igual';
                delta = `<div class="mt-1"><span class="${cor} text-xs font-semibold" aria-label="${palavra} ${escapeHtml(mudanca)}">${sinal} ${escapeHtml(mudanca)}</span>
                    <span class="text-[11px] text-slate-500">antes: ${escapeHtml(this.fmt(k.anterior, k.unidade))}</span></div>`;
            }
            let meta = '';
            if (k.meta !== null && k.meta !== undefined && k.atual !== null) {
                meta = `<div class="mt-1">${this.chip(`meta ${this.fmt(k.meta, k.unidade)}`, k.atual >= k.meta ? 'ok' : 'warn')}</div>`;
            }
            const poucos = k.n !== null && k.n !== undefined && k.n < 10 ? ' · poucos dados' : '';
            const n = k.n !== null && k.n !== undefined ? `<div class="text-[11px] text-slate-500 mt-1">n = ${Number(k.n)}${poucos}</div>` : '';
            return `<div class="bi-card" title="${escapeHtml(k.dica || '')}"><div class="text-xs text-slate-400">${escapeHtml(k.rotulo)}</div>
                <div class="text-2xl font-extrabold text-white mt-1">${escapeHtml(this.fmt(k.atual, k.unidade))}</div>${delta}${meta}${n}</div>`;
        }

        private tabela(id: string, cabecalho: string[], linhas: string[][], vazio: string = 'Sem dados no período.'): string {
            if (!linhas.length) return this.vazio(vazio);
            return `<div class="overflow-x-auto"><table class="bi-table" id="${id}"><thead><tr>${cabecalho.map((c) => `<th scope="col">${escapeHtml(c)}</th>`).join('')}</tr></thead>
                <tbody>${linhas.map((l) => `<tr>${l.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
        }

        // ------------------------------------------------------------ gráficos (ECharts)
        private base(): any {
            return {
                textStyle: { color: COR.texto }, animationDuration: 400,
                grid: { left: 8, right: 16, top: 30, bottom: 8, containLabel: true },
                tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: '#0f172a', borderColor: COR.linha, textStyle: { color: '#e2e8f0' } },
                legend: { textStyle: { color: COR.texto }, top: 0 },
            };
        }

        private eixo(tipo: 'category' | 'value', dados?: string[]): any {
            return { type: tipo, data: dados, axisLine: { lineStyle: { color: COR.linha } }, splitLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: COR.texto, hideOverlap: true }, minInterval: 1 };
        }

        private barras(categorias: string[], series: { nome: string; dados: number[]; cor: string; empilhado?: boolean }[], horizontal: boolean = false): any {
            return {
                ...this.base(),
                legend: series.length > 1 ? this.base().legend : undefined,
                xAxis: horizontal ? this.eixo('value') : this.eixo('category', categorias),
                yAxis: horizontal ? { ...this.eixo('category', categorias), inverse: true } : this.eixo('value'),
                series: series.map((s) => ({ name: s.nome, type: 'bar', data: s.dados, stack: s.empilhado ? 'total' : undefined, itemStyle: { color: s.cor, borderRadius: 3 }, barMaxWidth: 28 })),
            };
        }

        private linhas(categorias: string[], series: { nome: string; dados: (number | null)[]; cor: string; area?: boolean }[], meta?: number): any {
            return {
                ...this.base(), tooltip: { ...this.base().tooltip, axisPointer: { type: 'line' } },
                xAxis: this.eixo('category', categorias), yAxis: this.eixo('value'),
                series: series.map((s, i) => ({
                    name: s.nome, type: 'line', data: s.dados, smooth: true, symbolSize: 6, itemStyle: { color: s.cor }, lineStyle: { width: 3 },
                    areaStyle: s.area ? { opacity: 0.12 } : undefined,
                    markLine: i === 0 && meta !== undefined ? { symbol: 'none', lineStyle: { color: COR.cinza, type: 'dashed' }, label: { color: COR.texto, formatter: `meta ${meta}%` }, data: [{ yAxis: meta }] } : undefined,
                })),
            };
        }

        private iniciarGraficos(pendentes: { id: string; opcao: any; clique?: (nome: string, dado: any, indice: number) => void }[]): void {
            if (typeof echarts === 'undefined') {
                pendentes.forEach((p) => { const e = document.getElementById(p.id); if (e) e.innerHTML = this.vazio('Os gráficos não puderam ser carregados (biblioteca indisponível). As tabelas continuam disponíveis.'); });
                return;
            }
            pendentes.forEach((p) => {
                const alvo = document.getElementById(p.id);
                if (!alvo) return;
                const g = echarts.init(alvo, undefined, { renderer: 'canvas' });
                g.setOption(p.opcao);
                if (p.clique) g.on('click', (ev: any) => p.clique!(ev.name, ev.data, ev.dataIndex));
                this.graficos.push(g);
            });
        }

        // ------------------------------------------------------------ visão executiva
        private htmlExecutiva(d: any): string {
            const semData = d.historico_sem_data > 0 && !this.el<HTMLInputElement>('f-historico').checked
                ? this.aviso(`${d.historico_sem_data} triagens antigas não têm data e ficam fora dos indicadores por período. Marque "Incluir triagens antigas" para somá-las.`) : '';
            const insights = d.insights.length
                ? d.insights.map((i: any) => this.linhaInsight(i, false)).join('')
                : this.vazio('Nenhum aviso pendente. Tudo em ordem por aqui.');
            return `<div class="flex flex-col gap-4">${semData}
                <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">${d.kpis.map((k: any) => this.cartaoKpi(k)).join('')}</div>
                ${this.cartao('Insights pendentes', insights + `<button type="button" class="mt-3 text-xs text-cyan-400 hover:text-cyan-300 font-semibold" onclick="document.querySelector('[data-aba=insights]').click()">Ver todos os insights →</button>`)}</div>`;
        }

        // ------------------------------------------------------------ operação e SLA
        private htmlOperacao(d: any, pend: any[]): string {
            const f = d.faixas, a = d.aging, c = d.concluidos, ag = d.agendamentos;
            const criticos = (f.faixa_80_100 + f.acima_100);
            const kpis = [
                { rotulo: 'Chamados ativos', unidade: 'num', atual: d.total_ativos, anterior: null, n: d.total_ativos },
                { rotulo: 'Críticos (acima de 80%)', unidade: 'num', atual: criticos, anterior: null, n: null },
                { rotulo: 'Estourados (acima de 100%)', unidade: 'num', atual: f.acima_100, anterior: null, n: null },
                { rotulo: 'Dentro do SLA (concluídos)', unidade: 'pct', atual: c.pct, ...c.comparacao_pct, meta: d.meta_sla, n: c.total, dica: 'Concluídos no período dentro do limite' },
                { rotulo: 'Tempo médio de resolução', unidade: 'horas', atual: c.mttr, ...c.comparacao_mttr, menor_melhor: true, n: c.total },
                { rotulo: 'Agendamentos frustrados', unidade: 'pct', atual: ag.taxa_frustrados, anterior: null, n: ag.realizado + ag.frustrado },
            ];
            pend.push({ id: 'g-faixas', opcao: {
                ...this.base(), legend: undefined, tooltip: { ...this.base().tooltip, axisPointer: { type: 'shadow' } },
                xAxis: this.eixo('category', ['Até 60%', '60–80%', '80–100%', 'Acima de 100%']), yAxis: this.eixo('value'),
                series: [{ type: 'bar', barMaxWidth: 56, label: { show: true, position: 'top', color: '#e2e8f0' }, data: [
                    { value: f.ate_60, itemStyle: { color: COR.verde } }, { value: f.faixa_60_80, itemStyle: { color: COR.ambar } },
                    { value: f.faixa_80_100, itemStyle: { color: COR.laranja } }, { value: f.acima_100, itemStyle: { color: COR.vermelho } }] }] } });
            pend.push({ id: 'g-aging', opcao: this.barras(['Até 24 h', '24–48 h', '48–72 h', '72–120 h', 'Mais de 120 h'], [{ nome: 'Chamados', dados: [a.ate_24h, a['24_48h'], a['48_72h'], a['72_120h'], a.acima_120h], cor: COR.ciano }]) });
            pend.push({ id: 'g-vazao', opcao: this.linhas(d.vazao.map((v: any) => formatarDataBr(v.semana)), [{ nome: 'Abertos', dados: d.vazao.map((v: any) => v.abertos), cor: COR.ambar }, { nome: 'Concluídos', dados: d.vazao.map((v: any) => v.concluidos), cor: COR.verde }]) });
            pend.push({ id: 'g-tendencia', opcao: this.linhas(d.tendencia.map((t: any) => formatarDataBr(t.data)), [{ nome: '% do backlog dentro do limite', dados: d.tendencia.map((t: any) => t.pct_no_prazo), cor: COR.ciano, area: true }], d.meta_sla) });
            pend.push({ id: 'g-uf', opcao: this.barras(d.por_uf.map((u: any) => u.uf), [
                { nome: 'Estourados', dados: d.por_uf.map((u: any) => u.estourados), cor: COR.vermelho, empilhado: true },
                { nome: 'Críticos (80–100%)', dados: d.por_uf.map((u: any) => u.criticos - u.estourados), cor: COR.laranja, empilhado: true },
                { nome: 'Demais ativos', dados: d.por_uf.map((u: any) => u.ativos - u.criticos), cor: COR.cinza, empilhado: true }], true),
                clique: (nome: string) => this.definirFiltro('f-uf', nome) });
            pend.push({ id: 'g-analista', opcao: this.barras(d.por_analista.map((p: any) => p.nome), [{ nome: 'Chamados ativos', dados: d.por_analista.map((p: any) => p.ativos), cor: COR.ciano }], true),
                clique: (nome: string) => { const a2 = this.opcoes.analistas.find((x: any) => x.nome === nome); if (a2) this.definirFiltro('f-analista', String(a2.id_funcionario)); } });

            const tabelaCriticos = this.tabela('t-criticos', ['Ticket', 'UF / Cidade', 'Modelo', 'SLA', 'Analista', 'Aberto há'],
                d.criticos.map((x: any) => [`<a class="text-cyan-300 hover:underline" href="/gerenciar-chamados-rfb/">${escapeHtml(x.ticket)}</a>`, escapeHtml(`${x.uf} / ${x.cidade}`), escapeHtml(x.modelo),
                    this.chipSla(x.pct), escapeHtml(x.analista), escapeHtml(this.fmt(x.horas_abertas, 'horas'))]), 'Nenhum chamado acima de 60% do SLA.');
            // Histórico por analista: os números são botões que abrem a lista de chamados daquela situação.
            const numero = (n: number, a: any, situacao: string, cor: string) => n > 0
                ? `<button type="button" data-chamados data-analista="${Number(a.id_analista)}" data-nome="${escapeHtml(a.nome)}" data-situacao="${situacao}" class="font-bold ${cor} hover:underline" title="Ver os chamados">${n}</button>`
                : `<span class="text-slate-500">${n}</span>`;
            const tabelaAnalistas = this.tabela('t-hist-analistas',
                ['Analista', 'Total', 'Ativos', 'Atendidos', 'Cancelados', '% atendidos', 'Sem intervenção', 'SLA estourado (ativos)', 'Abertos no período'],
                d.historico_analistas.map((a: any) => [escapeHtml(a.nome), numero(a.total, a, 'todos', 'text-slate-100'), numero(a.ativos, a, 'ativos', 'text-cyan-300'),
                    numero(a.atendidos, a, 'atendidos', 'text-emerald-300'), numero(a.cancelados, a, 'cancelados', 'text-slate-300'),
                    a.pct_atendidos === null ? '—' : `${a.pct_atendidos}%`, String(a.sem_intervencao), a.estourados ? `<span class="text-rose-400 font-bold">${a.estourados}</span>` : '0',
                    String(a.no_periodo)]), 'Nenhum chamado cadastrado.');
            // Regiões com mais chamados (histórico completo; o período só alimenta "Abertos no período")
            const rg = d.regioes;
            const maiorPct = Math.max(1, ...[...rg.macro, ...rg.estados, ...rg.cidades].map((x: any) => x.pct));
            const barra = (pct: number) => `<div class="flex items-center gap-2"><div class="h-1.5 rounded-full bg-cyan-500" style="width:${Math.max(2, Math.round(pct / maiorPct * 80))}px"></div><span>${pct}%</span></div>`;
            const colunas = (primeira: string) => [primeira, 'Total', '% do total', 'Ativos', 'Atendidos', 'SLA estourado (ativos)', 'Abertos no período'];
            const linhaRegiao = (nome: string, x: any) => [nome, `<span class="font-bold text-slate-100">${x.total}</span>`, barra(x.pct), String(x.ativos), String(x.atendidos),
                x.estourados ? `<span class="text-rose-400 font-bold">${x.estourados}</span>` : '0', String(x.no_periodo)];
            const tabMacro = this.tabela('t-regioes-macro', colunas('Macrorregião'), rg.macro.map((x: any) => linhaRegiao(escapeHtml(x.nome), x)), 'Nenhum chamado cadastrado.');
            const tabEstados = this.tabela('t-regioes-estados', colunas('Estado'), rg.estados.map((x: any) => linhaRegiao(escapeHtml(x.nome), x)), 'Nenhum chamado cadastrado.');
            const tabCidades = this.tabela('t-regioes-cidades', colunas('Cidade / UF'), rg.cidades.map((x: any) => linhaRegiao(`${escapeHtml(x.nome)} / ${escapeHtml(x.uf)}`, x)), 'Nenhum chamado com cidade informada.');
            const chipsAreas = rg.areas.map((a: any) => `<span class="inline-block mr-2 mb-2 px-2.5 py-1 rounded-md bg-slate-800 text-xs text-slate-300">${escapeHtml(a.nome)}: <strong class="text-slate-100">${a.total}</strong> (${a.pct}%)</span>`).join('');
            const cartaoRegioes = this.cartao('Regiões com mais chamados',
                `<div class="mb-3">${chipsAreas}</div>
                 <p class="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Por macrorregião</p>${tabMacro}
                 <p class="text-[11px] uppercase tracking-wider text-slate-500 mt-4 mb-1">Estados com mais chamados${rg.total_estados > rg.estados.length ? ` (${rg.estados.length} de ${rg.total_estados})` : ''}</p>${tabEstados}
                 <p class="text-[11px] text-slate-500 mt-2">${rg.total_geral} chamado(s) no total, contando todo o histórico. UF, modelo e analista do filtro valem; o período só limita "Abertos no período".</p>`,
                '', 't-regioes-estados|chamados_por_estado');
            const cartaoCidades = this.cartao(`Cidades com mais chamados${rg.total_cidades > rg.cidades.length ? ` (${rg.cidades.length} de ${rg.total_cidades})` : ''}`, tabCidades, '', 't-regioes-cidades|chamados_por_cidade');
            // Peças mais utilizadas (chamados RFB concluídos no período), previsão de uso e região que mais usa cada peça
            const pu = d.pecas_utilizadas;
            const setas: Record<string, string> = { subindo: '<span class="text-amber-400" title="Uso em alta">▲</span>', caindo: '<span class="text-emerald-400" title="Uso em queda">▼</span>', 'estável': '<span class="text-slate-400" title="Uso estável">►</span>' };
            const tabPecas = this.tabela('t-pecas-uso',
                ['Peça', 'Usos no período', '% do total', 'Média por dia', `Previsão (próx. ${pu.periodo_dias} dias)`, 'Em estoque', 'Cobre (dias)', 'Comprar (sugestão)', 'Região que mais usa'],
                pu.itens.map((p: any) => [
                    `<button type="button" data-peca-regioes="${Number(p.id_peca)}" class="text-left hover:underline" title="Ver as regiões desta peça"><span class="font-mono text-cyan-300">${escapeHtml(p.part_number)}</span><span class="block text-[10px] text-slate-500">${escapeHtml((p.descricao || '').slice(0, 60))}</span></button>`,
                    `<span class="font-bold text-slate-100">${p.usos}</span>`, `${p.pct}%`, String(p.media_dia).replace('.', ','),
                    `<span class="font-semibold">${p.previsao}</span> ${setas[p.tendencia] || ''}<span class="block text-[10px] text-slate-500">${p.metodo === 'média' ? 'poucos dados: repete o período' : 'tendência do período'}</span>`,
                    p.saldo === null ? '—' : String(p.saldo), p.cobertura_dias === null ? '—' : String(p.cobertura_dias),
                    p.comprar === null ? '—' : (p.comprar > 0 ? `<span class="text-amber-400 font-bold">${p.comprar}</span>` : '0'),
                    `${escapeHtml(p.regiao_top.uf)} <span class="text-slate-500">(${p.regiao_top.pct}%)</span>`]),
                'Nenhuma peça utilizada em chamados concluídos neste período.');
            const cartaoPecas = this.cartao('Peças mais utilizadas e previsão de uso',
                `<div class="flex flex-wrap items-center gap-2 mb-3">
                    <input id="busca-peca-regioes" placeholder="PN de uma peça para ver as regiões que mais a usam" class="flex-1 min-w-[220px] bg-[#0f172a] border border-[#334155] rounded-lg py-2 px-3 text-xs text-slate-200 outline-none focus:border-cyan-500">
                    <button type="button" id="btn-peca-regioes" class="px-4 py-2 rounded-lg text-xs font-semibold text-white bg-cyan-600 hover:bg-cyan-500">Ver regiões</button>
                 </div>${tabPecas}
                 <p class="text-[11px] text-slate-500 mt-2">Conta as peças registradas como utilizadas nos chamados RFB <strong>concluídos no período escolhido</strong> (${pu.total_usos} uso(s) em ${pu.total_pecas} peça(s) diferente(s); cada chamado conta uma vez por peça).
                    A previsão é para os próximos ${pu.periodo_dias} dias, seguindo a tendência do período (com menos de 4 usos ela só repete o período). "Cobre" são os dias de estoque no ritmo atual e "Comprar" é a previsão menos o saldo. Clique no PN de uma peça para ver as regiões.</p>`,
                '', 't-pecas-uso|pecas_mais_utilizadas');
            return `<div class="flex flex-col gap-4">
                <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">${kpis.map((k) => this.cartaoKpi(k)).join('')}</div>
                <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    ${this.cartao('Backlog por faixa de SLA', this.grafico('g-faixas', `Chamados por faixa de SLA: até 60%: ${f.ate_60}; 60 a 80%: ${f.faixa_60_80}; 80 a 100%: ${f.faixa_80_100}; acima de 100%: ${f.acima_100}`))}
                    ${this.cartao('Idade do backlog (desde a abertura)', this.grafico('g-aging', 'Chamados ativos por tempo desde a abertura'))}
                    ${this.cartao('Tendência do SLA (retrato diário)', d.tendencia.length ? this.grafico('g-tendencia', 'Percentual do backlog dentro do limite por dia') : this.vazio('O retrato diário começa a ser gravado hoje. Em alguns dias a tendência aparece aqui.'))}
                    ${this.cartao('Vazão semanal (abertos × concluídos)', d.vazao.length ? this.grafico('g-vazao', 'Chamados abertos e concluídos por semana') : this.vazio('Sem chamados no período.'))}
                    ${this.cartao('Concentração por UF (clique para filtrar)', d.por_uf.length ? this.grafico('g-uf', 'Chamados ativos por UF') : this.vazio('Sem chamados ativos.'))}
                    ${this.cartao('Carga por analista (clique para filtrar)', d.por_analista.length ? this.grafico('g-analista', 'Chamados ativos por analista') : this.vazio('Sem chamados ativos.'))}
                </div>
                ${this.cartao('Histórico de chamados por analista', tabelaAnalistas + '<p class="text-[11px] text-slate-500 mt-2">Todo o histórico de cada analista: <strong>ativos</strong> são os em andamento e <strong>atendidos</strong> os concluídos. Clique em um número para ver os chamados. O período escolhido só limita a coluna "Abertos no período"; UF, modelo e analista do filtro valem para tudo.</p>', '', 't-hist-analistas|historico_chamados_por_analista')}
                ${cartaoRegioes}
                ${cartaoCidades}
                ${cartaoPecas}
                ${this.cartao('Chamados críticos (acima de 60% do SLA)', tabelaCriticos, '', 't-criticos|chamados_criticos')}</div>`;
        }

        // ------------------------------------------------------------ qualidade
        private htmlQualidade(d: any, pend: any[]): string {
            const aviso = d.historico_sem_data > 0 && !this.el<HTMLInputElement>('f-historico').checked
                ? this.aviso(`${d.historico_sem_data} triagens antigas não têm data e ficam fora do período. Marque "Incluir triagens antigas" para somá-las.`) : '';
            const kpis = [
                { rotulo: 'Triagens no período', unidade: 'num', atual: d.total, anterior: null, n: d.total },
                { rotulo: 'Com defeito', unidade: 'pct', ...d.taxa_defeito, n: d.total, dica: 'Triagens com status não funcional ÷ total' },
                { rotulo: 'Peças funcionais (NFF)', unidade: 'pct', ...d.nff.taxa, n: d.total,
                  dica: d.nff.ic_inf === null ? 'Peças trocadas que a bancada constatou funcionais ÷ total'
                      : `Peças trocadas que a bancada constatou funcionais ÷ total. Intervalo de confiança de 95%: ${d.nff.ic_inf}% a ${d.nff.ic_sup}%. Referência da literatura: ${d.nff.referencia[0]}% a ${d.nff.referencia[1]}%` },
                { rotulo: 'Trocas indevidas', unidade: 'pct', ...d.troca_indevida.taxa, n: d.troca_indevida.informadas,
                  dica: `Triagens em que a troca da peça foi marcada como indevida ÷ triagens com essa informação preenchida (${d.troca_indevida.indevidas} de ${d.troca_indevida.informadas}). Triagens antigas, sem a informação, não entram.` },
                { rotulo: 'Equipamentos reincidentes (2+ triagens)', unidade: 'num', atual: d.reincidencia.total, anterior: null, n: null, dica: 'Mesmo número de série, em todo o histórico' },
            ];
            pend.push({ id: 'g-pareto', opcao: {
                ...this.base(), legend: undefined,
                xAxis: this.eixo('category', d.pareto.map((p: any) => p.nome)),
                yAxis: [this.eixo('value'), { ...this.eixo('value'), max: 100, axisLabel: { color: COR.texto, formatter: '{value}%' }, splitLine: { show: false } }],
                series: [{ name: 'Ocorrências', type: 'bar', data: d.pareto.map((p: any) => p.qtd), itemStyle: { color: COR.ciano, borderRadius: 3 }, barMaxWidth: 36 },
                    { name: '% acumulado', type: 'line', yAxisIndex: 1, data: d.pareto.map((p: any) => p.acumulado), itemStyle: { color: COR.ambar }, lineStyle: { width: 3 } }] } });
            pend.push({ id: 'g-modelo', opcao: this.barras(d.por_modelo.map((m: any) => `${m.modelo || '—'} (n=${m.total})`), [{ nome: '% com defeito', dados: d.por_modelo.map((m: any) => m.taxa), cor: COR.vermelho }], true),
                clique: (_n: string, _d: any, indice: number) => { const m = d.por_modelo[indice]; if (m && m.id_modelo) this.definirFiltro('f-modelo', String(m.id_modelo)); } });
            pend.push({ id: 'g-volume', opcao: { ...this.barras(d.volume_semanal.map((v: any) => formatarDataBr(v.semana)), [{ nome: 'Triagens', dados: d.volume_semanal.map((v: any) => v.total), cor: COR.ciano }, { nome: 'Com defeito', dados: d.volume_semanal.map((v: any) => v.defeitos), cor: COR.vermelho }]) } });
            pend.push({ id: 'g-pecas', opcao: this.barras(d.pecas_trocadas.map((p: any) => `${p.peca} (${p.modelo || '—'})`), [{ nome: 'Trocas', dados: d.pecas_trocadas.map((p: any) => p.qtd), cor: COR.ambar }], true) });
            pend.push({ id: 'g-tecnico', opcao: this.barras(d.por_tecnico.map((p: any) => p.nome || '—'), [{ nome: 'Triagens', dados: d.por_tecnico.map((p: any) => p.total), cor: COR.ciano }], true) });
            // NFF por técnico: funnel plot (carta de controle p) + tabela com intervalo de confiança
            const fun = d.funil;
            const corStatus: Record<string, string> = { critico: COR.vermelho, atencao: COR.ambar, destaque: COR.verde, normal: COR.ciano };
            if (fun.limites.length > 1 && fun.pontos.length) {
                const linhaLimite = (nome: string, campo: string, cor: string, tracejado: string) => ({
                    name: nome, type: 'line', silent: true, showSymbol: false, data: fun.limites.map((l: any) => [l.n, l[campo]]),
                    lineStyle: { color: cor, width: 1.5, type: tracejado }, itemStyle: { color: cor } });
                const nIni = fun.limites[0].n, nFim = fun.limites[fun.limites.length - 1].n;
                pend.push({ id: 'g-funil-nff', opcao: {
                    ...this.base(), legend: undefined,
                    tooltip: { trigger: 'item', backgroundColor: '#0f172a', borderColor: COR.linha, textStyle: { color: '#e2e8f0' },
                        formatter: (p: any) => p.seriesType === 'scatter' ? `${escapeHtml(p.name)}<br/>${p.value[1]}% de NFF em ${p.value[0]} triagens` : '' },
                    xAxis: { ...this.eixo('value'), name: 'Triagens do técnico', nameLocation: 'middle', nameGap: 30, nameTextStyle: { color: COR.texto }, min: fun.min_amostra },
                    yAxis: { ...this.eixo('value'), name: '% NFF', nameTextStyle: { color: COR.texto }, min: 0, max: 100, axisLabel: { color: COR.texto, formatter: '{value}%' } },
                    series: [
                        linhaLimite('Limite 3σ (sup.)', 'sup3', COR.vermelho, 'dashed'), linhaLimite('Limite 3σ (inf.)', 'inf3', COR.vermelho, 'dashed'),
                        linhaLimite('Limite 2σ (sup.)', 'sup2', COR.ambar, 'dotted'), linhaLimite('Limite 2σ (inf.)', 'inf2', COR.ambar, 'dotted'),
                        { name: 'Média', type: 'line', silent: true, showSymbol: false, data: [[nIni, fun.p_medio], [nFim, fun.p_medio]], lineStyle: { color: COR.cinza, width: 1.5 }, itemStyle: { color: COR.cinza } },
                        { name: 'Técnicos', type: 'scatter', symbolSize: 12,
                          data: fun.pontos.map((t: any) => ({ name: t.nome, value: [t.n, t.taxa], itemStyle: { color: corStatus[t.status] || COR.ciano } })) },
                    ] } });
            }
            const situacao = (st: string): string => ({
                critico: this.chip('Fora do limite (3σ)', 'bad'), atencao: this.chip('Atenção (2σ)', 'warn'), destaque: this.chip('Destaque positivo', 'ok'),
                normal: this.chip('Dentro do padrão', 'mut'), insuficiente: this.chip(`Menos de ${fun.min_amostra} triagens`, 'mut') } as Record<string, string>)[st] || '';
            const tabNff = this.tabela('t-nff-tecnico', ['Técnico', 'Triagens', 'Peças funcionais', 'Taxa de NFF', 'IC 95%', 'Diagnósticos contrariados', 'Situação'],
                d.controle_tecnicos.map((t: any) => [escapeHtml(t.nome || '—'), String(t.total), String(t.nff), `${t.taxa_nff}%`, `${t.ic_inf}% a ${t.ic_sup}%`, String(t.divergencias), situacao(t.status)]),
                'Sem triagens no período.');
            const dg = d.diagnosticos;
            const tabMotivosIndevida = this.tabela('t-motivos-indevida', ['Motivo da troca indevida', 'Qtde', '% das trocas indevidas'],
                d.troca_indevida.motivos.map((m: any) => [escapeHtml(m.nome), `<span class="font-bold text-slate-100">${m.quantidade}</span>`, `${m.pct}%`]),
                'Nenhuma troca indevida no período.');
            const tabDiag = this.tabela('t-diagnosticos', ['Diagnóstico do técnico de campo', 'Constatado na bancada', 'Qtde', '% das divergências'],
                dg.itens.map((i: any) => [escapeHtml(i.diagnostico), escapeHtml(i.constatado), String(i.qtd), `${i.pct}%`]),
                'Nenhum diagnóstico divergente no período.');
            const tabReinc = this.tabela('t-reinc', ['Nº de série', 'Modelo', 'Triagens'], d.reincidencia.lista.map((r: any) => [escapeHtml(r.sn), escapeHtml(r.modelo || '—'), this.chip(String(r.n), r.n >= 3 ? 'bad' : 'warn')]), 'Nenhum equipamento com mais de uma triagem.');
            return `<div class="flex flex-col gap-4">${aviso}
                <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">${kpis.map((k) => this.cartaoKpi(k)).join('')}</div>
                <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    ${this.cartao('Pareto de defeitos constatados', d.pareto.length ? this.grafico('g-pareto', 'Defeitos mais frequentes e percentual acumulado') + '<p class="text-[11px] text-slate-500 mt-2">Os defeitos são digitados à mão; variações de escrita são agrupadas automaticamente.</p>' : this.vazio('Sem defeitos registrados no período.'))}
                    ${this.cartao('Taxa de defeito por modelo (clique para filtrar)', d.por_modelo.length ? this.grafico('g-modelo', 'Percentual de triagens com defeito por modelo') + '<p class="text-[11px] text-slate-500 mt-2">Modelos com poucas triagens (n baixo) variam muito; interprete com cuidado.</p>' : this.vazio('Sem triagens no período.'))}
                    ${this.cartao('Volume semanal de triagens', d.volume_semanal.length ? this.grafico('g-volume', 'Triagens por semana') : this.vazio('A data das triagens passou a ser gravada recentemente: a série aparece conforme o histórico cresce.'))}
                    ${this.cartao('Peças mais trocadas', d.pecas_trocadas.length ? this.grafico('g-pecas', 'Peças mais trocadas por modelo') : this.vazio('Sem trocas registradas.'))}
                    ${this.cartao('Triagens por técnico', d.por_tecnico.length ? this.grafico('g-tecnico', 'Triagens por técnico') : this.vazio('Sem triagens no período.'))}
                    ${this.cartao('NFF por técnico (carta de controle)', fun.limites.length > 1 && fun.pontos.length
                        ? this.grafico('g-funil-nff', 'Taxa de NFF de cada técnico contra os limites de controle') + `<p class="text-[11px] text-slate-500 mt-2">Cada ponto é um técnico (só com ${fun.min_amostra}+ triagens). Fora das linhas tracejadas (3σ) a taxa é estatisticamente atípica para aquele volume; a média é ${fun.p_medio}%.</p>`
                        : this.vazio('Sem técnicos com triagens suficientes para a carta de controle.'))}
                    ${this.cartao('Técnicos: taxa de NFF e intervalo de confiança', tabNff + `<p class="text-[11px] text-slate-500 mt-2">O intervalo de 95% (Wilson) mostra a incerteza: com poucas triagens ele é largo e a taxa não deve ser usada para cobrar ninguém.</p>`, '', 't-nff-tecnico|nff-por-tecnico')}
                    ${this.cartao('Diagnóstico do técnico × constatado na bancada', (dg.comparaveis ? `<p class="text-xs text-slate-400 mb-2">${dg.divergentes} de ${dg.comparaveis} diagnósticos comparáveis (${dg.pct_div}%) foram contrariados na bancada.</p>` : '') + tabDiag, '', 't-diagnosticos|diagnosticos-divergentes')}
                    ${this.cartao('Motivos das trocas indevidas', tabMotivosIndevida, '', 't-motivos-indevida|motivos_troca_indevida')}
                    ${this.cartao('Reincidência por número de série', tabReinc, '', 't-reinc|reincidencia')}
                </div></div>`;
        }

        // ------------------------------------------------------------ comercial
        private htmlComercial(d: any, pend: any[]): string {
            const fin = d.financeiro;
            const k = (rotulo: string, unidade: string, c: any, n: number | null, dica = '') => ({ rotulo, unidade, ...c, n, dica });
            const kpis = [
                k('Valor emitido', 'moeda', fin.valor_emitido, d.amostras.emitidos), k('Valor aprovado', 'moeda', fin.valor_aprovado, null),
                k('Taxa de aprovação', 'pct', fin.taxa_aprovacao, d.amostras.decididos, 'Aprovados ÷ (aprovados + recusados)'),
                k('Ticket médio', 'moeda', fin.ticket_medio, d.amostras.emitidos), k('Margem bruta', 'pct', fin.margem_pct, d.amostras.emitidos, '(valor − custo das peças) ÷ valor'),
                { rotulo: 'Em aberto (aguardando decisão)', unidade: 'moeda', atual: d.pipeline.valor, anterior: null, n: d.pipeline.qtd, dica: 'Laudos emitidos sem decisão do cliente' },
                { rotulo: 'Tempo até a decisão', unidade: 'dias', atual: d.tempo_decisao.media_dias, anterior: null, n: d.tempo_decisao.n },
            ];
            pend.push({ id: 'g-funil', opcao: { ...this.base(), tooltip: { trigger: 'item', backgroundColor: '#0f172a', borderColor: COR.linha, textStyle: { color: '#e2e8f0' } }, legend: undefined,
                series: [{ type: 'funnel', left: '8%', width: '84%', top: 10, bottom: 10, sort: 'none', gap: 4, label: { color: '#f8fafc', formatter: '{b}: {c}' },
                    itemStyle: { borderColor: '#0f172a', borderWidth: 1 }, data: d.funil.map((e: any, i: number) => ({ name: e.etapa, value: e.valor, itemStyle: { color: [COR.cinza, '#0891b2', COR.ciano, COR.verde][i] } })) }] } });
            pend.push({ id: 'g-valor-semanal', opcao: this.barras(d.valor_semanal.map((v: any) => formatarDataBr(v.semana)), [{ nome: 'Valor emitido (R$)', dados: d.valor_semanal.map((v: any) => v.valor), cor: COR.ciano }]) });
            pend.push({ id: 'g-clientes', opcao: this.barras(d.top_clientes.map((c: any) => c.nome), [{ nome: 'Valor (R$)', dados: d.top_clientes.map((c: any) => c.valor), cor: COR.ciano }], true) });
            pend.push({ id: 'g-uf-valor', opcao: this.barras(d.por_uf.map((c: any) => c.nome), [{ nome: 'Valor (R$)', dados: d.por_uf.map((c: any) => c.valor), cor: COR.verde }], true),
                clique: (nome: string) => this.definirFiltro('f-uf', nome) });
            const tabVencer = this.tabela('t-vencer', ['Laudo', 'Cliente', 'Valor', 'Vence em'], d.a_vencer.map((x: any) => [
                `<a class="text-cyan-300 hover:underline" href="/orcamentos/emissao/?id=${Number(x.id)}">${escapeHtml(x.numero)}</a>`, escapeHtml(x.cliente_nome), escapeHtml(formatarMoeda(x.valor)), escapeHtml(formatarDataBr(x.validade_ate))]), 'Nenhum laudo vence nos próximos 3 dias.');
            return `<div class="flex flex-col gap-4">
                <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">${kpis.map((x) => this.cartaoKpi(x)).join('')}</div>
                <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    ${this.cartao('Funil: da triagem à aprovação', this.grafico('g-funil', 'Funil: triagens, laudos criados, emitidos e aprovados'))}
                    ${this.cartao('Valor emitido por semana', d.valor_semanal.length ? this.grafico('g-valor-semanal', 'Valor emitido por semana') : this.vazio('Sem laudos emitidos no período.'))}
                    ${this.cartao('Clientes por valor', d.top_clientes.length ? this.grafico('g-clientes', 'Valor emitido por cliente') : this.vazio('Sem laudos emitidos no período.'))}
                    ${this.cartao('Valor por UF (clique para filtrar)', d.por_uf.length ? this.grafico('g-uf-valor', 'Valor emitido por UF') : this.vazio('Sem laudos emitidos no período.'))}
                </div>
                ${this.cartao('Laudos que vencem em até 3 dias', tabVencer, '', 't-vencer|laudos_a_vencer')}</div>`;
        }

        // ------------------------------------------------------------ peças e custos
        private htmlPecas(d: any, pend: any[]): string {
            pend.push({ id: 'g-orcadas', opcao: this.barras(d.top_orcadas.map((p: any) => p.pn), [{ nome: 'Quantidade', dados: d.top_orcadas.map((p: any) => p.qtd), cor: COR.ciano }], true) });
            pend.push({ id: 'g-forn', opcao: this.barras(d.concentracao.map((c: any) => c.nome), [{ nome: '% das cotações (90 dias)', dados: d.concentracao.map((c: any) => c.pct), cor: COR.ambar }], true) });
            const variacoes = this.tabela('t-var', ['Peça (PN)', 'De', 'Para', 'Variação', 'Data'], d.variacoes.map((v: any) => [escapeHtml(v.pn), escapeHtml(formatarMoeda(v.de)), escapeHtml(formatarMoeda(v.para)),
                this.chip(`${v.variacao_pct > 0 ? '+' : ''}${v.variacao_pct.toFixed(1).replace('.', ',')}%`, v.variacao_pct > 0 ? 'bad' : 'ok'), escapeHtml(formatarDataBr(v.data))]), 'Nenhuma peça com duas ou mais cotações no último ano.');
            const melhor = this.tabela('t-melhor', ['Peça (PN)', 'Melhor fornecedor', 'Valor', 'Fornecedores'], d.melhor_fornecedor.map((m: any) => [escapeHtml(m.pn), escapeHtml(m.fornecedor), escapeHtml(formatarMoeda(m.valor)), String(m.fornecedores)]), 'Sem cotações para as peças mais orçadas.');
            const velhas = this.tabela('t-velhas', ['Peça (PN)', 'Descrição', 'Última cotação', 'Idade'], d.cotacoes_velhas.map((v: any) => [escapeHtml(v.pn), escapeHtml(v.descricao), escapeHtml(formatarDataBr(v.ultima)), this.chip(`${v.dias} dias`, 'warn')]), `Nenhuma cotação com mais de ${d.dias_cotacao_velha} dias.`);
            const semCot = this.tabela('t-semcot', ['Peça (PN)', 'Descrição'], d.sem_cotacao.map((v: any) => [escapeHtml(v.part_number), escapeHtml(v.descricao)]), 'Todas as peças dos modelos têm cotação.');
            return `<div class="flex flex-col gap-4">
                ${d.itens_sem_cotacao_em_laudos ? this.aviso(`${d.itens_sem_cotacao_em_laudos} peça(s) foram orçadas em laudos sem cotação cadastrada (valor digitado à mão).`) : ''}
                <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    ${this.cartao('Peças mais orçadas (quantidade)', d.top_orcadas.length ? this.grafico('g-orcadas', 'Peças mais orçadas') : this.vazio('Sem laudos emitidos no período.'))}
                    ${this.cartao('Concentração de fornecedores (90 dias)', d.concentracao.length ? this.grafico('g-forn', 'Participação de cada fornecedor nas cotações') : this.vazio('Sem cotações nos últimos 90 dias.'))}
                    ${this.cartao('Variação de preço (última × anterior)', variacoes, '', 't-var|variacao_de_preco')}
                    ${this.cartao('Melhor fornecedor nas peças mais orçadas', melhor, '', 't-melhor|melhor_fornecedor')}
                    ${this.cartao(`Cotações com mais de ${d.dias_cotacao_velha} dias`, velhas, '', 't-velhas|cotacoes_velhas')}
                    ${this.cartao('Peças dos modelos sem nenhuma cotação', semCot, '', 't-semcot|pecas_sem_cotacao')}
                </div></div>`;
        }

        // ------------------------------------------------------------ insights
        private linhaInsight(i: any, comBotao: boolean = true): string {
            const cor = i.severidade === 'critico' ? 'bad' : i.severidade === 'atencao' ? 'warn' : 'info';
            const rotulo = i.severidade === 'critico' ? 'Crítico' : i.severidade === 'atencao' ? 'Atenção' : 'Informativo';
            return `<div class="flex flex-wrap items-start justify-between gap-3 py-3 border-t border-[#334155] first:border-0 ${i.lido ? 'opacity-60' : ''}">
                <div class="min-w-0"><div class="flex items-center gap-2">${this.chip(rotulo, cor as any)}<span class="font-semibold text-slate-100 text-sm">${escapeHtml(i.titulo)}</span></div>
                    <p class="text-xs text-slate-400 mt-1">${escapeHtml(i.texto)}</p>
                    <p class="text-[11px] text-slate-500 mt-1">${escapeHtml(new Date(i.criado_em).toLocaleString('pt-BR'))}${i.link ? ` · <a class="text-cyan-400 hover:underline" href="${escapeHtml(i.link)}">Abrir</a>` : ''}</p></div>
                ${comBotao ? `<button type="button" data-id="${Number(i.id)}" data-lido="${i.lido ? '0' : '1'}" class="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold">${i.lido ? 'Marcar como não lido' : 'Marcar como lido'}</button>` : ''}</div>`;
        }

        private async desenharInsights(): Promise<void> {
            const r = await (await fetch('/api/bi/insights/')).json();
            if (r.status !== 'sucesso') { this.painel.innerHTML = this.erro(r.mensagem); return; }
            this.painel.innerHTML = this.cartao('Insights e alertas', r.dados.length ? r.dados.map((i: any) => this.linhaInsight(i)).join('')
                : this.vazio('Nenhum insight gerado ainda. Eles aparecem conforme o sistema detecta riscos e oportunidades (SLA, laudos a vencer, picos, reincidência).'));
        }

        private async carregarContadorInsights(): Promise<void> {
            try {
                const r = await (await fetch('/api/bi/insights/?nao_lidos=1')).json();
                const badge = this.el('badge-insights');
                const n = r.status === 'sucesso' ? r.dados.length : 0;
                badge.textContent = String(n);
                badge.classList.toggle('hidden', n === 0);
            } catch (e) { /* o contador é apenas informativo */ }
        }

        private async marcarInsight(id: number, lido: boolean): Promise<void> {
            const r = await (await fetch(`/api/bi/insights/${id}/lido/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lido }) })).json();
            if (r.status !== 'sucesso') { Mensagem.erro(r.mensagem); return; }
            this.carregarContadorInsights();
            this.carregar(true);
        }

        // ------------------------------------------------------------ ações
        private async atualizarAgora(): Promise<void> {
            const btn = this.el<HTMLButtonElement>('btn-atualizar');
            btn.disabled = true;
            try {
                const r = await (await fetch('/api/bi/atualizar/', { method: 'POST' })).json();
                if (r.status === 'sucesso') { Mensagem.sucesso('Indicadores atualizados.'); this.carregarContadorInsights(); this.carregar(); }
                else Mensagem.erro(r.mensagem);
            } catch (e) { Mensagem.erro('Erro ao comunicar com o servidor.'); } finally { btn.disabled = false; }
        }

        private alternarTV(): void {
            this.modoTV = !this.modoTV;
            const btn = this.el('btn-tv');
            if (this.modoTV) {
                (document.documentElement as any).requestFullscreen?.().catch(() => { /* alguns navegadores bloqueiam: segue sem tela cheia */ });
                this.temporizador = window.setInterval(() => this.carregar(true), 60000);
                btn.textContent = 'Sair do modo TV';
                document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && this.modoTV) this.alternarTV(); }, { once: true });
            } else {
                window.clearInterval(this.temporizador);
                if (document.fullscreenElement) document.exitFullscreen();
                btn.textContent = 'Modo TV';
            }
        }

        private exportarTabela(spec: string): void {
            const [idTabela, nome] = spec.split('|');
            const tabela = document.getElementById(idTabela) as HTMLTableElement | null;
            if (!tabela) return;
            const celula = (t: string) => { let x = t.replace(/\s+/g, ' ').trim(); if (/^[=+\-@]/.test(x)) x = "'" + x; return `"${x.replace(/"/g, '""')}"`; };
            const linhas = [...tabela.rows].map((r) => [...r.cells].map((c) => celula(c.innerText)).join(';'));
            const blob = new Blob(['\uFEFF' + linhas.join('\n')], { type: 'text/csv;charset=utf-8;' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `${nome}_${this.iso(new Date())}.csv`;
            document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(a.href);
        }
    }

    document.addEventListener('DOMContentLoaded', () => new DashboardBIUI());
})();
