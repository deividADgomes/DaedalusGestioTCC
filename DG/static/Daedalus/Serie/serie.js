"use strict";
/// <reference path="../BaseUI.ts" />
(() => {
    const ROTULO = {
        triagem: { nome: 'Triagem', cor: 'bg-cyan-500' },
        orcamento: { nome: 'Laudo', cor: 'bg-amber-500' },
        rfb: { nome: 'Chamado RFB', cor: 'bg-emerald-500' },
    };
    class Serie {
        constructor() {
            const form = document.getElementById('form-serie');
            form.addEventListener('submit', (e) => { e.preventDefault(); this.buscar(); });
            // Vem de um link (ex.: aviso de reincidência): /serie/?sn=ABC123
            const sn = new URLSearchParams(window.location.search).get('sn');
            if (sn) {
                document.getElementById('campo-sn').value = sn;
                this.buscar();
            }
        }
        async buscar() {
            const sn = document.getElementById('campo-sn').value.trim();
            if (!sn)
                return;
            const lista = document.getElementById('serie-eventos');
            const resumo = document.getElementById('serie-resumo');
            const vazio = document.getElementById('serie-vazio');
            lista.innerHTML = '';
            vazio.classList.add('hidden');
            resumo.classList.add('hidden');
            try {
                const res = await (await fetch(`/api/serie/?sn=${encodeURIComponent(sn)}`)).json();
                if (res.status !== 'sucesso') {
                    await Mensagem.erro(res.mensagem);
                    return;
                }
                const d = res.dado;
                history.replaceState(null, '', `/serie/?sn=${encodeURIComponent(sn)}`);
                if (d.eventos.length === 0) {
                    vazio.classList.remove('hidden');
                    return;
                }
                resumo.innerText = `${d.resumo.triagem} triagem(ns), ${d.resumo.orcamento} laudo(s) e ${d.resumo.rfb} chamado(s) RFB para o número de série ${d.sn}.`;
                resumo.classList.remove('hidden');
                lista.innerHTML = d.eventos.map((e) => {
                    const r = ROTULO[e.tipo] || { nome: e.tipo, cor: 'bg-slate-500' };
                    const data = e.data ? new Date(e.data).toLocaleDateString('pt-BR') : 'Sem data (registro antigo)';
                    return `<li class="ml-6">
                        <span class="absolute -left-[7px] mt-1.5 w-3.5 h-3.5 rounded-full ${r.cor} border-2 border-[#0f172a]"></span>
                        <div class="bg-[#1e293b] border border-[#334155] rounded-lg px-4 py-3">
                            <p class="text-[11px] text-slate-500">${escapeHtml(data)} · ${escapeHtml(r.nome)}</p>
                            <a href="${escapeHtml(e.url)}" class="text-sm font-semibold text-cyan-300 hover:text-cyan-200">${escapeHtml(e.titulo)}</a>
                            <span class="ml-2 text-[11px] text-slate-300">${escapeHtml(e.status)}</span>
                            <p class="text-xs text-slate-400 mt-0.5">${escapeHtml(e.detalhe)}</p>
                            ${e.texto ? `<p class="text-xs text-slate-500 mt-1">${escapeHtml(e.texto)}</p>` : ''}
                        </div>
                    </li>`;
                }).join('');
            }
            catch (err) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }
    }
    window.addEventListener('DOMContentLoaded', () => { new Serie(); });
})();
