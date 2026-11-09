"use strict";
/// <reference path="../BaseUI.ts" />
(() => {
    const CORES_STATUS = {
        rascunho: 'text-slate-300 bg-slate-700/50',
        emitido: 'text-cyan-300 bg-cyan-500/10',
        aprovado: 'text-emerald-300 bg-emerald-500/10',
        recusado: 'text-rose-300 bg-rose-500/10',
        cancelado: 'text-slate-500 bg-slate-800',
    };
    class PesquisaLaudosUI extends BaseUI {
        constructor() {
            super();
            this.pagina = 1;
            this.paginas = 1;
            this.el = (id) => document.getElementById(id);
            ['filtro-q', 'filtro-status', 'filtro-de', 'filtro-ate'].forEach((id) => {
                this.el(id).addEventListener(id === 'filtro-q' ? 'input' : 'change', () => this.recarregar());
            });
            this.el('pag-anterior').addEventListener('click', () => { if (this.pagina > 1) {
                this.pagina--;
                this.carregar();
            } });
            this.el('pag-proxima').addEventListener('click', () => { if (this.pagina < this.paginas) {
                this.pagina++;
                this.carregar();
            } });
            this.carregar();
            this.carregarPendentes();
        }
        recarregar() {
            window.clearTimeout(this.temporizador);
            this.temporizador = window.setTimeout(() => { this.pagina = 1; this.carregar(); }, 300);
        }
        // Laudos emitidos com a validade vencida: o usuário só informa se foram aprovados ou não.
        async carregarPendentes() {
            const painel = document.getElementById('painel-pendentes');
            const lista = document.getElementById('lista-pendentes');
            try {
                const r = await (await fetch('/api/orcamentos/pendentes-decisao/')).json();
                if (r.status !== 'sucesso' || r.dados.length === 0) {
                    painel.classList.add('hidden');
                    return;
                }
                painel.classList.remove('hidden');
                lista.innerHTML = r.dados.map((o) => `
                    <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-[#0f172a] border border-[#334155] rounded-lg px-4 py-3">
                        <div class="text-sm text-slate-200">
                            <span class="font-mono text-cyan-300">${escapeHtml(o.numero)}</span>
                            <span class="mx-1 text-slate-600">·</span>${escapeHtml(o.cliente_nome)}
                            <span class="mx-1 text-slate-600">·</span><span class="text-slate-400">${escapeHtml(o.equip_modelo)}</span>
                            <span class="block text-[11px] text-amber-400/90 mt-0.5">Venceu em ${escapeHtml(formatarDataBr(o.validade_ate))} (há ${Number(o.dias_vencido)} dia(s)) · ${escapeHtml(formatarMoeda(o.valor_total))}</span>
                        </div>
                        <div class="flex gap-2 shrink-0">
                            <button type="button" class="btn-decisao px-3 py-1.5 rounded-md text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500" data-id="${Number(o.id)}" data-numero="${escapeHtml(o.numero)}" data-status="aprovado">Foi aprovado</button>
                            <button type="button" class="btn-decisao px-3 py-1.5 rounded-md text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500" data-id="${Number(o.id)}" data-numero="${escapeHtml(o.numero)}" data-status="recusado">Não foi aprovado</button>
                        </div>
                    </div>`).join('');
                lista.querySelectorAll('.btn-decisao').forEach((b) => {
                    b.addEventListener('click', () => {
                        const el = b;
                        this.registrarDecisao(Number(el.dataset.id), el.dataset.numero || '', el.dataset.status || '');
                    });
                });
            }
            catch (e) {
                painel.classList.add('hidden'); // o aviso é um extra: se falhar, a pesquisa segue normal
            }
        }
        async registrarDecisao(id, numero, status) {
            const aprovado = status === 'aprovado';
            let motivo = '';
            if (aprovado) {
                const ok = await Mensagem.confirmar(`Marcar o orçamento ${numero} como APROVADO?`, 'Resposta do cliente', 'Sim, foi aprovado');
                if (!ok)
                    return;
            }
            else {
                const escolhido = await Mensagem.motivoRecusa(numero); // já serve de confirmação
                if (escolhido === null)
                    return;
                motivo = escolhido;
            }
            try {
                const r = await (await fetch(`/api/orcamentos/${id}/status/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status, motivo_recusa: motivo }),
                })).json();
                if (r.status !== 'sucesso') {
                    await Mensagem.erro(r.mensagem || 'Não foi possível registrar a resposta.');
                    return;
                }
                this.carregarPendentes();
                this.carregar();
            }
            catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }
        async carregar() {
            const corpo = document.getElementById('tabela-laudos');
            const params = new URLSearchParams({
                q: this.el('filtro-q').value, status: this.el('filtro-status').value,
                de: this.el('filtro-de').value, ate: this.el('filtro-ate').value, page: String(this.pagina),
            });
            try {
                const r = await (await fetch('/api/orcamentos/?' + params.toString())).json();
                if (r.status !== 'sucesso') {
                    corpo.innerHTML = `<tr><td colspan="8" class="px-4 py-10 text-center text-red-500">${escapeHtml(r.mensagem)}</td></tr>`;
                    return;
                }
                this.paginas = r.paginas;
                if (r.dados.length === 0) {
                    corpo.innerHTML = '<tr><td colspan="8" class="px-4 py-10 text-center text-slate-500">Nenhum laudo encontrado.</td></tr>';
                }
                else {
                    corpo.innerHTML = r.dados.map((o) => `
                        <tr class="border-t border-[#334155]/50 hover:bg-slate-800/40">
                            <td class="px-4 py-3 font-mono text-cyan-300 whitespace-nowrap">${escapeHtml(o.numero)}</td>
                            <td class="px-4 py-3 text-slate-300 whitespace-nowrap">${escapeHtml(formatarDataBr(o.data_emissao))}</td>
                            <td class="px-4 py-3 text-slate-200">${escapeHtml(o.cliente_nome)}</td>
                            <td class="px-4 py-3 text-slate-300">${escapeHtml(o.equip_modelo)}<span class="block text-[10px] text-slate-500">${escapeHtml(o.equip_sn)}</span></td>
                            <td class="px-4 py-3 text-slate-400">${escapeHtml(o.ticket)}</td>
                            <td class="px-4 py-3"><span class="px-2 py-1 rounded-md text-[11px] font-semibold ${CORES_STATUS[o.status] || ''}">${escapeHtml(o.status_nome)}</span></td>
                            <td class="px-4 py-3 text-right text-emerald-400 font-semibold whitespace-nowrap">${escapeHtml(formatarMoeda(o.valor_total))}</td>
                            <td class="px-4 py-3 text-right whitespace-nowrap">
                                <a class="text-cyan-300 hover:text-cyan-200 text-xs mr-3" href="/orcamentos/emissao/?id=${Number(o.id)}">Abrir</a>
                                <a class="text-slate-300 hover:text-cyan-200 text-xs mr-3" href="/orcamentos/emissao/?copiar=${encodeURIComponent(o.numero)}" title="Criar um laudo novo com os dados deste">Copiar</a>
                                <button type="button" class="btn-word text-slate-300 hover:text-white text-xs" data-id="${Number(o.id)}" data-numero="${escapeHtml(o.numero)}" data-cliente="${escapeHtml(o.cliente_nome)}">Word</button>
                            </td>
                        </tr>`).join('');
                }
                corpo.querySelectorAll('.btn-word').forEach((b) => {
                    b.addEventListener('click', () => {
                        const el = b;
                        const cliente = (el.dataset.cliente || '').replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_+|_+$/g, '');
                        baixarDocumento(`/api/orcamentos/${el.dataset.id}/docx/`, `Laudo_${el.dataset.numero}${cliente ? '_' + cliente : ''}`);
                    });
                });
                document.getElementById('resumo-laudos').textContent =
                    `${r.total} laudo(s) · página ${r.pagina} de ${r.paginas}`;
                this.el('pag-anterior').disabled = this.pagina <= 1;
                this.el('pag-proxima').disabled = this.pagina >= this.paginas;
            }
            catch (e) {
                corpo.innerHTML = '<tr><td colspan="8" class="px-4 py-10 text-center text-red-500">Erro ao conectar com o servidor.</td></tr>';
            }
        }
    }
    document.addEventListener('DOMContentLoaded', () => new PesquisaLaudosUI());
})();
