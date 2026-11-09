/// <reference path="../BaseUI.ts" />
(() => {
    const NOMES_STATUS: Record<string, string> = {
        rascunho: 'Rascunho', emitido: 'Emitido', aprovado: 'Aprovado', recusado: 'Recusado', cancelado: 'Cancelado',
    };
    const BARRAS_STATUS: Record<string, string> = {
        rascunho: 'bg-slate-500', emitido: 'bg-cyan-500', aprovado: 'bg-emerald-500', recusado: 'bg-rose-500', cancelado: 'bg-slate-700',
    };

    class EstatisticasLaudosUI extends BaseUI {
        private de = document.getElementById('est-de') as HTMLInputElement;
        private ate = document.getElementById('est-ate') as HTMLInputElement;

        constructor() {
            super();
            this.de.addEventListener('change', () => this.carregar());
            this.ate.addEventListener('change', () => this.carregar());
            (document.getElementById('est-limpar') as HTMLElement).addEventListener('click', () => {
                this.de.value = ''; this.ate.value = ''; this.carregar();
            });
            this.carregar();
        }

        private kpi(titulo: string, valor: string, cor = 'text-white'): string {
            return `<div class="bg-[#1e293b] rounded-xl border border-[#334155] p-4">
                <p class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">${escapeHtml(titulo)}</p>
                <p class="text-xl font-bold mt-1 ${cor}">${escapeHtml(valor)}</p></div>`;
        }

        private ranking(id: string, itens: any[], comValor: boolean): void {
            const el = document.getElementById(id) as HTMLElement;
            if (!itens.length) { el.innerHTML = '<p class="text-xs text-slate-500 py-4 text-center">Sem dados no período.</p>'; return; }
            el.innerHTML = `<table class="w-full text-xs"><tbody>${itens.map((i) => `
                <tr class="border-t border-[#334155]/50 first:border-0">
                    <td class="py-2 pr-2 text-slate-200">${escapeHtml(i.nome)}</td>
                    <td class="py-2 px-2 text-right text-slate-400 whitespace-nowrap">${Number(i.quantidade)}×</td>
                    ${comValor ? `<td class="py-2 pl-2 text-right text-emerald-400 whitespace-nowrap">${escapeHtml(formatarMoeda(i.valor))}</td>` : ''}
                </tr>`).join('')}</tbody></table>`;
        }

        private async carregar(): Promise<void> {
            const params = new URLSearchParams({ de: this.de.value, ate: this.ate.value });
            try {
                const r = await (await fetch('/api/orcamentos/estatisticas/?' + params.toString())).json();
                if (r.status !== 'sucesso') { Mensagem.erro(r.mensagem); return; }
                const d = r.dado;

                (document.getElementById('est-kpis') as HTMLElement).innerHTML =
                    this.kpi('Laudos no período', String(d.total)) +
                    this.kpi('Valor emitido', formatarMoeda(d.valor_emitido), 'text-cyan-300') +
                    this.kpi('Valor aprovado', formatarMoeda(d.valor_aprovado), 'text-emerald-400') +
                    this.kpi('Ticket médio', formatarMoeda(d.ticket_medio)) +
                    this.kpi('Taxa de aprovação', d.taxa_aprovacao === null ? '—' : `${String(d.taxa_aprovacao).replace('.', ',')}%`, 'text-amber-300');

                const maxStatus = Math.max(1, ...Object.values(d.por_status) as number[]);
                (document.getElementById('est-status') as HTMLElement).innerHTML = Object.keys(NOMES_STATUS).map((s) => {
                    const n = d.por_status[s] || 0;
                    return `<div><div class="flex justify-between text-xs text-slate-300 mb-1"><span>${NOMES_STATUS[s]}</span><span>${n}</span></div>
                        <div class="h-2 rounded bg-slate-800"><div class="h-2 rounded ${BARRAS_STATUS[s]}" style="width:${(n / maxStatus) * 100}%"></div></div></div>`;
                }).join('');

                const elMeses = document.getElementById('est-meses') as HTMLElement;
                if (!d.por_mes.length) {
                    elMeses.innerHTML = '<p class="text-xs text-slate-500 w-full text-center self-center">Sem laudos emitidos no período.</p>';
                } else {
                    const maxMes = Math.max(1, ...d.por_mes.map((m: any) => m.valor));
                    elMeses.innerHTML = d.por_mes.map((m: any) => {
                        const [a, mes] = m.mes.split('-');
                        return `<div class="flex flex-col items-center justify-end h-full min-w-[3.5rem]" title="${escapeHtml(formatarMoeda(m.valor))} · ${Number(m.quantidade)} laudo(s)">
                            <span class="text-[10px] text-slate-400 mb-1">${escapeHtml(formatarMoeda(m.valor).replace(/\s/g, ' '))}</span>
                            <div class="w-8 rounded-t bg-cyan-500" style="height:${Math.max(4, (m.valor / maxMes) * 100)}px"></div>
                            <span class="text-[10px] text-slate-500 mt-1">${mes}/${a.slice(2)}</span></div>`;
                    }).join('');
                }

                this.ranking('est-pecas', d.pecas_mais_orcadas, true);
                this.ranking('est-clientes', d.top_clientes, true);
                this.ranking('est-modelos', d.top_modelos, false);
                this.ranking('est-recusas', d.motivos_recusa, false);
            } catch (e) {
                Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }
    }
    document.addEventListener('DOMContentLoaded', () => new EstatisticasLaudosUI());
})();
