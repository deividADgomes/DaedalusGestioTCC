"use strict";
/// <reference path="BaseUI.ts" />
/**
 * Recursos do cabeçalho comum a todas as telas:
 *  - sino de avisos (carrega ao abrir a página e ao clicar; nunca em intervalo, para não renovar a sessão);
 *  - busca global (ticket, número de série, NF, laudo, chamado RFB);
 *  - encerramento por inatividade: a sessão do servidor já expira em 30 minutos sem uso; aqui a tela
 *    também sai sozinha, para não ficar aberta mostrando dados, e uma atividade renova a sessão.
 */
(() => {
    const INATIVIDADE_MS = 30 * 60 * 1000; // igual ao SESSION_COOKIE_AGE do servidor
    const RENOVAR_A_CADA_MS = 5 * 60 * 1000;
    const el = (id) => document.getElementById(id);
    const fechar = (...ids) => ids.forEach((id) => el(id)?.classList.add('hidden'));
    // ------------------------------------------------------------ avisos
    const COR_NIVEL = { critico: 'bg-rose-500', atencao: 'bg-amber-500', info: 'bg-cyan-500' };
    async function carregarAvisos() {
        const painel = el('painel-avisos');
        const badge = el('badge-avisos');
        if (!painel || !badge)
            return;
        try {
            const r = await (await fetch('/api/avisos/')).json();
            if (r.status !== 'sucesso')
                return;
            const d = r.dado;
            badge.innerText = d.total > 99 ? '99+' : String(d.total);
            badge.classList.toggle('hidden', d.total === 0);
            painel.innerHTML = d.itens.length === 0
                ? '<p class="px-4 py-5 text-xs text-slate-400 text-center">Nada pendente por aqui.</p>'
                : `<p class="px-4 pt-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">Avisos</p><ul>${d.itens.map((i) => `
                    <li><a href="${escapeHtml(i.url)}" class="flex items-start gap-3 px-4 py-3 hover:bg-[#0f172a] transition-colors">
                        <span class="mt-1 w-2 h-2 rounded-full flex-shrink-0 ${COR_NIVEL[i.nivel] || 'bg-slate-500'}"></span>
                        <span class="text-xs text-slate-200">${escapeHtml(i.texto)}</span></a></li>`).join('')}</ul>`;
        }
        catch (e) { /* o sino é um extra: se falhar, a tela segue normal */ }
    }
    // ------------------------------------------------------------ busca global
    let temporizadorBusca;
    async function buscar(termo) {
        const caixa = el('resultado-busca');
        if (!caixa)
            return;
        if (termo.trim().length < 2) {
            caixa.classList.add('hidden');
            return;
        }
        try {
            const r = await (await fetch(`/api/busca/?q=${encodeURIComponent(termo.trim())}`)).json();
            if (r.status !== 'sucesso')
                return;
            caixa.innerHTML = r.dados.length === 0
                ? '<p class="px-4 py-4 text-xs text-slate-400">Nada encontrado.</p>'
                : `<ul class="max-h-96 overflow-y-auto divide-y divide-[#334155]/60">${r.dados.map((i) => `
                    <li><a href="${escapeHtml(i.url)}" class="block px-4 py-2.5 hover:bg-[#0f172a] transition-colors">
                        <span class="block text-xs font-semibold text-cyan-300">${escapeHtml(i.titulo)}</span>
                        <span class="block text-[11px] text-slate-400">${escapeHtml(i.detalhe)}</span></a></li>`).join('')}</ul>`;
            caixa.classList.remove('hidden');
        }
        catch (e) { /* sem resultado: a busca simplesmente não abre */ }
    }
    // ------------------------------------------------------------ inatividade
    let ultimaAtividade = Date.now();
    let ultimaRenovacao = Date.now();
    let houveAtividade = false;
    function registrarAtividade() {
        ultimaAtividade = Date.now();
        houveAtividade = true;
    }
    function vigiarInatividade() {
        ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach((ev) => window.addEventListener(ev, registrarAtividade, { passive: true }));
        window.setInterval(() => {
            const agora = Date.now();
            if (agora - ultimaAtividade >= INATIVIDADE_MS) {
                window.location.href = '/logout/';
                return;
            }
            // Quem está usando a tela mantém a sessão viva, mesmo escrevendo um formulário longo sem enviar nada.
            if (houveAtividade && agora - ultimaRenovacao >= RENOVAR_A_CADA_MS) {
                houveAtividade = false;
                ultimaRenovacao = agora;
                fetch('/api/sessao/ping/').catch(() => { });
            }
        }, 30 * 1000);
    }
    document.addEventListener('DOMContentLoaded', () => {
        carregarAvisos();
        vigiarInatividade();
        el('btn-avisos')?.addEventListener('click', (e) => {
            e.stopPropagation();
            fechar('resultado-busca');
            el('painel-avisos')?.classList.toggle('hidden');
            carregarAvisos();
        });
        const campo = el('busca-global');
        campo?.addEventListener('input', () => {
            window.clearTimeout(temporizadorBusca);
            temporizadorBusca = window.setTimeout(() => buscar(campo.value), 300);
        });
        campo?.addEventListener('focus', () => { if (campo.value.trim().length >= 2)
            buscar(campo.value); });
        campo?.addEventListener('keydown', (e) => { if (e.key === 'Escape')
            fechar('resultado-busca'); });
        // Clicar fora fecha os painéis
        document.addEventListener('click', (e) => {
            const alvo = e.target;
            if (!alvo.closest('#painel-avisos') && !alvo.closest('#btn-avisos'))
                fechar('painel-avisos');
            if (!alvo.closest('#resultado-busca') && !alvo.closest('#busca-global'))
                fechar('resultado-busca');
        });
    });
})();
