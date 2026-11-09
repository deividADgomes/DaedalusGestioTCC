"use strict";
/// <reference path="../BaseUI.ts" />
(() => {
    class VisualizarUI extends BaseUI {
        constructor() {
            super();
            this.idAtual = null;
            this.carregarDados();
            this.iniciarEventos();
            this.carregarHistorico();
        }
        iniciarEventos() {
            const btnExportar = document.getElementById('btn-exportar-word');
            if (btnExportar) {
                btnExportar.addEventListener('click', () => {
                    if (this.idAtual) {
                        // Chama a rota que cria e descarrega o ficheiro DOCX
                        window.location.href = `/api/triagem/exportar-docx/?id=${this.idAtual}`;
                    }
                    else {
                        Mensagem.erro("Erro: ID da triagem não encontrado para exportação.");
                    }
                });
            }
        }
        // Correções feitas depois que a triagem foi salva (quem alterou, quando e o que mudou)
        async carregarHistorico() {
            const id = new URLSearchParams(window.location.search).get('id');
            if (!id)
                return;
            try {
                const res = await (await fetch(`/api/triagem/historico/?id=${id}`)).json();
                if (res.status !== 'sucesso' || res.dados.length === 0)
                    return; // sem correções: a seção nem aparece
                const lista = document.getElementById('lista-historico');
                lista.innerHTML = res.dados.map((h) => `
                    <li class="bg-[#0f172a] border border-[#334155] rounded-lg px-4 py-3">
                        <p class="text-xs text-slate-400"><span class="font-semibold text-slate-200">${escapeHtml(h.usuario)}</span> em ${escapeHtml(new Date(h.quando).toLocaleString('pt-BR'))}</p>
                        <ul class="mt-1 space-y-0.5">${h.alteracoes.map((a) => `
                            <li class="text-xs text-slate-300"><span class="text-cyan-400">${escapeHtml(a.campo)}:</span>
                                <span class="text-slate-500 line-through">${escapeHtml(a.de)}</span> → ${escapeHtml(a.para)}</li>`).join('')}
                        </ul>
                    </li>`).join('');
                document.getElementById('secao-historico')?.classList.remove('hidden');
            }
            catch (e) { /* o histórico é um extra: se falhar, o laudo continua visível */ }
        }
        async carregarDados() {
            const urlParams = new URLSearchParams(window.location.search);
            this.idAtual = urlParams.get('id');
            if (!this.idAtual) {
                Mensagem.aviso("ID da triagem não fornecido.");
                window.location.href = '/pesquisa/';
                return;
            }
            try {
                const resposta = await fetch(`/api/triagem/?id=${this.idAtual}`);
                const res = await resposta.json();
                if (res.status === 'sucesso') {
                    const d = res.dado;
                    // CABEÇALHO
                    document.getElementById('label-ticket').innerText = `Ticket #${d.n_ticket || ''} - Analisado por ${escapeHtml(d.nome_analista || '')}`;
                    // SESSÃO 1: DADOS DA ORDEM
                    document.getElementById('v-ticket').value = d.n_ticket || "";
                    document.getElementById('v-nf').value = d.nf || "";
                    document.getElementById('v-cidade').value = d.cidade || "";
                    document.getElementById('v-estado').value = d.estado || "";
                    document.getElementById('v-cliente').value = d.nome_cliente || "";
                    document.getElementById('v-tecnico').value = d.nome_tecnico || "";
                    document.getElementById('v-analista').value = d.nome_analista || "";
                    // SESSÃO 2: EQUIPAMENTO/PEÇA
                    document.getElementById('v-equipamento').value = d.nome_equipamento || "";
                    document.getElementById('v-sn').value = d.sn || "";
                    document.getElementById('v-troca').value = d.troca || "";
                    const motivoIndevida = d.troca_indevida === true && d.motivo_troca_indevida
                        ? d.motivo_troca_indevida + (d.justificativa_troca_indevida ? ': ' + d.justificativa_troca_indevida : '') : '';
                    document.getElementById('v-motivo-indevida').value = motivoIndevida;
                    document.getElementById('v-motivo-indevida-grupo').classList.toggle('hidden', !motivoIndevida);
                    document.getElementById('v-ct').value = d.ct || '';
                    document.getElementById('v-ct-grupo').classList.toggle('hidden', !d.ct);
                    document.getElementById('v-troca-indevida').value = d.troca_indevida === true ? 'Sim' : d.troca_indevida === false ? 'Não' : 'Não informado';
                    // SESSÃO 3: LAUDO
                    document.getElementById('v-defeito_usuario').value = d.defeito_usuario || "Não informado";
                    document.getElementById('v-defeito_tecnico').value = d.defeito_tecnico || "Não informado";
                    document.getElementById('v-defeito_constatado').value = d.defeito_constatado || "Não informado";
                    document.getElementById('v-testes').value = d.testes || "Não informado";
                    document.getElementById('v-analise').value = d.analise || "Não informado";
                    document.getElementById('v-conclusao').value = d.conclusao || "Não informado";
                    // TRATAMENTO DO STATUS (VERDE/VERMELHO)
                    const statusElem = document.getElementById('v-status');
                    statusElem.value = d.status_peca === 1 ? "FUNCIONAL" : "NÃO FUNCIONAL / COM DEFEITO";
                    statusElem.classList.add(d.status_peca === 1 ? "text-emerald-400" : "text-rose-400");
                    document.getElementById('btn-editar').href = `/triagem/?id=${this.idAtual}`;
                    // Mostrar a tela suavemente
                    document.getElementById('container-visualizacao')?.classList.remove('opacity-0');
                }
                else {
                    Mensagem.erro(res.mensagem, "Erro do Servidor");
                }
            }
            catch (e) {
                Mensagem.erro("Erro grave de comunicação com o servidor.");
            }
        }
    }
    window.addEventListener('DOMContentLoaded', () => new VisualizarUI());
})();
