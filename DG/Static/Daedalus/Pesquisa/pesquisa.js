"use strict";
(() => {
    const STATUS_FUNCIONAL = 1;
    const COR_FUNCIONAL = 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20';
    const COR_NAO_FUNCIONAL = 'text-rose-400 bg-rose-400/10 border-rose-400/20';
    class PesquisaUI extends BaseUI {
        constructor() {
            super();
            this.listaPesquisa = obterElemento('lista-pesquisa');
            this.campoPesquisa = obterElemento('input-pesquisa');
            this.filtroStatus = obterElemento('filtro-status');
            this.triagens = [];
            this.campoPesquisa.addEventListener('input', () => this.filtrarTriagens());
            this.filtroStatus.addEventListener('change', () => this.filtrarTriagens());
            this.carregarTriagens();
        }
        async carregarTriagens() {
            try {
                const resultado = await buscarJson('/api/triagem/');
                if (resultado.status !== 'sucesso') {
                    this.listaPesquisa.innerHTML = `<p class="text-sm text-red-500 col-span-full text-center py-10">Erro: ${escapeHtml(resultado.mensagem)}</p>`;
                    return;
                }
                this.triagens = resultado.dados;
                this.renderizarCards(this.triagens);
            }
            catch (erro) {
                this.listaPesquisa.innerHTML = '<p class="text-sm text-red-500 col-span-full text-center py-10">Erro crítico ao conectar com o servidor.</p>';
            }
        }
        criarCard(triagem) {
            const funcional = triagem.status_peca === STATUS_FUNCIONAL;
            const corDoStatus = funcional ? COR_FUNCIONAL : COR_NAO_FUNCIONAL;
            const textoDoStatus = funcional ? 'Funcional' : 'Não Funcional';
            const card = document.createElement('a');
            card.href = `/visualizar/?id=${triagem.id}`;
            card.className = 'bg-[#1e293b] rounded-xl border border-[#334155] shadow-lg hover:border-cyan-500/50 hover:shadow-cyan-500/10 transition-all cursor-pointer group flex flex-col overflow-hidden no-underline block';
            card.innerHTML = `
                <div class="p-4 border-b border-[#334155] flex justify-between items-center bg-[#0f172a]/30">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg bg-cyan-900/50 flex items-center justify-center border border-cyan-700/50">
                            <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        </div>
                        <div>
                            <h3 class="text-sm font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">Ticket #${triagem.n_ticket}</h3>
                            <p class="text-[10px] text-slate-500 font-mono">SN: ${escapeHtml(triagem.sn)}</p>
                        </div>
                    </div>
                    <span class="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider border ${corDoStatus}">${textoDoStatus}</span>
                </div>

                <div class="p-4 flex-1 flex flex-col gap-4">
                    <div class="grid grid-cols-2 gap-2 text-xs">
                        <div>
                            <p class="text-slate-500 uppercase text-[9px] font-bold tracking-wider">Cliente</p>
                            <p class="text-slate-300 truncate font-medium" title="${escapeHtml(triagem.nome_cliente)}">${escapeHtml(triagem.nome_cliente || 'N/A')}</p>
                        </div>
                        <div>
                            <p class="text-slate-500 uppercase text-[9px] font-bold tracking-wider">Analista Resp.</p>
                            <p class="text-slate-300 truncate font-medium" title="${escapeHtml(triagem.nome_analista)}">${escapeHtml(triagem.nome_analista || 'N/A')}</p>
                        </div>
                    </div>

                    <div class="w-full h-px bg-[#334155]/50"></div>

                    <div class="space-y-3 flex-1">
                        <div>
                            <p class="text-indigo-400 uppercase text-[9px] font-bold tracking-wider mb-1">Alegação do Usuário</p>
                            <p class="text-slate-400 text-xs italic line-clamp-2" title="${escapeHtml(triagem.defeito_usuario)}">"${escapeHtml(triagem.defeito_usuario || 'Não informado.')}"</p>
                        </div>
                        <div>
                            <p class="text-amber-400 uppercase text-[9px] font-bold tracking-wider mb-1">Constatação do Técnico</p>
                            <p class="text-slate-400 text-xs italic line-clamp-2" title="${escapeHtml(triagem.defeito_tecnico)}">"${escapeHtml(triagem.defeito_tecnico || 'Não informado.')}"</p>
                        </div>
                        <div>
                            <p class="text-emerald-400 uppercase text-[9px] font-bold tracking-wider mb-1">Conclusão do Laboratório</p>
                            <p class="text-slate-300 text-xs font-medium line-clamp-2" title="${escapeHtml(triagem.conclusao)}">${escapeHtml(triagem.conclusao || 'Não informado.')}</p>
                        </div>
                    </div>
                </div>

                <div class="px-4 py-2 bg-cyan-900/20 border-t border-cyan-900/50 flex justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <span class="text-[10px] text-cyan-400 font-bold uppercase tracking-widest">Clique para abrir (Rodinha do mouse para nova aba)</span>
                </div>
            `;
            return card;
        }
        renderizarCards(triagens) {
            this.listaPesquisa.innerHTML = '';
            if (triagens.length === 0) {
                this.listaPesquisa.innerHTML = '<div class="col-span-full text-center py-16 text-slate-500">Nenhum laudo encontrado com estes filtros.</div>';
                return;
            }
            triagens.forEach((triagem) => this.listaPesquisa.appendChild(this.criarCard(triagem)));
        }
        filtrarTriagens() {
            const termo = this.campoPesquisa.value.toLowerCase();
            const status = this.filtroStatus.value;
            const filtradas = this.triagens.filter((triagem) => {
                const bateTexto = triagem.sn.toLowerCase().includes(termo) ||
                    triagem.n_ticket.toString().includes(termo) ||
                    (triagem.nome_cliente && triagem.nome_cliente.toLowerCase().includes(termo)) ||
                    (triagem.nome_analista && triagem.nome_analista.toLowerCase().includes(termo));
                const bateStatus = status === 'todos' || triagem.status_peca.toString() === status;
                return bateTexto && bateStatus;
            });
            this.renderizarCards(filtradas);
        }
    }
    window.addEventListener('DOMContentLoaded', () => new PesquisaUI());
})();
