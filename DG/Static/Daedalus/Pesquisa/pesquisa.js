"use strict";
/// <reference path="../baseUI.ts" />
(() => {
    class PesquisaUI extends BaseUI {
        constructor() {
            super();
            this.todasTriagensCache = [];
            this.listaPesquisa = document.getElementById('lista-pesquisa');
            this.inputPesquisa = document.getElementById('input-pesquisa');
            this.filtroStatus = document.getElementById('filtro-status');
            this.iniciarEventos();
            this.carregarTriagens();
        }
        iniciarEventos() {
            this.inputPesquisa.addEventListener('input', () => this.filtrarTriagens());
            this.filtroStatus.addEventListener('change', () => this.filtrarTriagens());
        }
        async carregarTriagens() {
            try {
                const resposta = await fetch('/api/triagem/');
                const resultado = await resposta.json();
                if (resultado.status === 'sucesso') {
                    this.todasTriagensCache = resultado.dados;
                    this.renderizarCards(this.todasTriagensCache);
                }
                else {
                    this.listaPesquisa.innerHTML = `<p class="text-sm text-red-500 col-span-full text-center py-10">Erro: ${resultado.mensagem}</p>`;
                }
            }
            catch (error) {
                this.listaPesquisa.innerHTML = '<p class="text-sm text-red-500 col-span-full text-center py-10">Erro crítico ao conectar com o servidor.</p>';
            }
        }
        renderizarCards(lista) {
            this.listaPesquisa.innerHTML = '';
            if (lista.length === 0) {
                this.listaPesquisa.innerHTML = '<div class="col-span-full text-center py-16 text-slate-500">Nenhum laudo encontrado com estes filtros.</div>';
                return;
            }
            lista.forEach((tri) => {
                const isFuncional = tri.status_peca === 1;
                const statusColor = isFuncional ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20" : "text-rose-400 bg-rose-400/10 border-rose-400/20";
                const statusText = isFuncional ? "Funcional" : "Não Funcional";
                // 1. Transformando o card em um link real (Tag <a> em vez de <div>)
                const card = document.createElement('a');
                // 2. Setando a URL do link
                card.href = `/visualizar/?id=${tri.id}`;
                // Classes de estilo mantidas iguais
                card.className = "bg-[#1e293b] rounded-xl border border-[#334155] shadow-lg hover:border-cyan-500/50 hover:shadow-cyan-500/10 transition-all cursor-pointer group flex flex-col overflow-hidden no-underline block";
                card.innerHTML = `
                    <div class="p-4 border-b border-[#334155] flex justify-between items-center bg-[#0f172a]/30">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-lg bg-cyan-900/50 flex items-center justify-center border border-cyan-700/50">
                                <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                            </div>
                            <div>
                                <h3 class="text-sm font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">Ticket #${tri.n_ticket}</h3>
                                <p class="text-[10px] text-slate-500 font-mono">SN: ${tri.sn}</p>
                            </div>
                        </div>
                        <span class="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider border ${statusColor}">${statusText}</span>
                    </div>

                    <div class="p-4 flex-1 flex flex-col gap-4">
                        
                        <div class="grid grid-cols-2 gap-2 text-xs">
                            <div>
                                <p class="text-slate-500 uppercase text-[9px] font-bold tracking-wider">Cliente</p>
                                <p class="text-slate-300 truncate font-medium" title="${tri.nome_cliente}">${tri.nome_cliente || 'N/A'}</p>
                            </div>
                            <div>
                                <p class="text-slate-500 uppercase text-[9px] font-bold tracking-wider">Analista Resp.</p>
                                <p class="text-slate-300 truncate font-medium" title="${tri.nome_analista}">${tri.nome_analista || 'N/A'}</p>
                            </div>
                        </div>

                        <div class="w-full h-px bg-[#334155]/50"></div>

                        <div class="space-y-3 flex-1">
                            <div>
                                <p class="text-indigo-400 uppercase text-[9px] font-bold tracking-wider mb-1">Alegação do Usuário</p>
                                <p class="text-slate-400 text-xs italic line-clamp-2" title="${tri.defeito_usuario || ''}">"${tri.defeito_usuario || 'Não informado.'}"</p>
                            </div>
                            <div>
                                <p class="text-amber-400 uppercase text-[9px] font-bold tracking-wider mb-1">Constatação do Técnico</p>
                                <p class="text-slate-400 text-xs italic line-clamp-2" title="${tri.defeito_tecnico || ''}">"${tri.defeito_tecnico || 'Não informado.'}"</p>
                            </div>
                            <div>
                                <p class="text-emerald-400 uppercase text-[9px] font-bold tracking-wider mb-1">Conclusão do Laboratório</p>
                                <p class="text-slate-300 text-xs font-medium line-clamp-2" title="${tri.conclusao || ''}">${tri.conclusao || 'Não informado.'}</p>
                            </div>
                        </div>
                    </div>

                    <div class="px-4 py-2 bg-cyan-900/20 border-t border-cyan-900/50 flex justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                        <span class="text-[10px] text-cyan-400 font-bold uppercase tracking-widest">Clique para abrir (Rodinha do mouse para nova aba)</span>
                    </div>
                `;
                // Como agora é uma tag <a>, não precisamos mais do card.addEventListener('dblclick'...)
                // O navegador já sabe como redirecionar ou abrir nova aba nativamente!
                this.listaPesquisa.appendChild(card);
            });
        }
        filtrarTriagens() {
            const termo = this.inputPesquisa.value.toLowerCase();
            const status = this.filtroStatus.value;
            const filtrada = this.todasTriagensCache.filter(tri => {
                const bateTexto = tri.sn.toLowerCase().includes(termo) ||
                    tri.n_ticket.toString().includes(termo) ||
                    (tri.nome_cliente && tri.nome_cliente.toLowerCase().includes(termo)) ||
                    (tri.nome_analista && tri.nome_analista.toLowerCase().includes(termo));
                const bateStatus = status === "todos" || tri.status_peca.toString() === status;
                return bateTexto && bateStatus;
            });
            this.renderizarCards(filtrada);
        }
    }
    window.addEventListener('DOMContentLoaded', () => new PesquisaUI());
})();
