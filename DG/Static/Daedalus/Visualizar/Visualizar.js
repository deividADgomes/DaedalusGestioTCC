"use strict";
/// <reference path="../baseUI.ts" />
(() => {
    class VisualizarUI extends BaseUI {
        constructor() {
            super();
            this.idAtual = null;
            this.carregarDados();
            this.iniciarEventos();
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
                        alert("Erro: ID da triagem não encontrado para exportação.");
                    }
                });
            }
        }
        async carregarDados() {
            const urlParams = new URLSearchParams(window.location.search);
            this.idAtual = urlParams.get('id');
            if (!this.idAtual) {
                alert("ID da triagem não fornecido.");
                window.location.href = '/pesquisa/';
                return;
            }
            try {
                const resposta = await fetch(`/api/triagem/?id=${this.idAtual}`);
                const res = await resposta.json();
                if (res.status === 'sucesso') {
                    const d = res.dado;
                    // CABEÇALHO
                    document.getElementById('label-ticket').innerText = `Ticket #${d.n_ticket || ''} - Analisado por ${d.nome_analista || ''}`;
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
                    // Mostrar a tela suavemente
                    document.getElementById('container-visualizacao')?.classList.remove('opacity-0');
                }
                else {
                    alert("Erro do Servidor: " + res.mensagem);
                }
            }
            catch (e) {
                alert("Erro grave de comunicação com o servidor.");
            }
        }
    }
    window.addEventListener('DOMContentLoaded', () => new VisualizarUI());
})();
