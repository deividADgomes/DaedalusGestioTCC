"use strict";
/// <reference path="../baseUI.ts" />
(() => {
    class VisualizarUI extends BaseUI {
        constructor() {
            super();
            this.idAtual = null;
            this.totalFotos = 0;
            this.carregarDados();
            this.iniciarEventos();
        }
        iniciarEventos() {
            document.getElementById('input-fotos')?.addEventListener('change', (e) => this.enviarFotos(e));
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
        // ==========================================
        // FOTOS
        // ==========================================
        desenharGaleria(fotos) {
            this.totalFotos = fotos.length;
            const galeria = document.getElementById('galeria-fotos');
            galeria.innerHTML = '';
            document.getElementById('galeria-vazia')?.classList.toggle('hidden', fotos.length > 0);
            fotos.forEach(f => {
                const item = document.createElement('div');
                item.className = 'relative aspect-square rounded-lg overflow-hidden border border-[#334155] bg-slate-900';
                const link = document.createElement('a');
                link.href = f.url;
                link.target = '_blank';
                link.rel = 'noopener';
                const img = document.createElement('img');
                img.src = f.url;
                img.alt = f.legenda || 'Foto da triagem';
                img.loading = 'lazy';
                img.className = 'w-full h-full object-cover hover:opacity-90 transition-opacity';
                link.appendChild(img);
                const rem = document.createElement('button');
                rem.type = 'button';
                rem.textContent = '✕';
                rem.title = 'Excluir foto';
                rem.className = 'absolute top-1 right-1 w-6 h-6 rounded-full bg-black/70 text-rose-300 text-xs hover:bg-rose-600 hover:text-white';
                rem.addEventListener('click', () => this.excluirFoto(f.id));
                item.append(link, rem);
                galeria.appendChild(item);
            });
        }
        async recarregarFotos() {
            const res = await fetch(`/api/triagem/fotos/?id_triagem=${this.idAtual}`).then(r => r.json());
            if (res.status === 'sucesso') {
                this.desenharGaleria(res.dados);
            }
        }
        async enviarFotos(e) {
            const input = e.target;
            const arquivos = Array.from(input.files || []);
            input.value = '';
            const falhas = [];
            for (const arq of arquivos) {
                const fd = new FormData();
                fd.append('id_triagem', String(this.idAtual));
                fd.append('arquivo', arq);
                try {
                    const res = await fetch('/api/triagem/fotos/', { method: 'POST', body: fd }).then(r => r.json());
                    if (res.status !== 'sucesso') {
                        falhas.push(`${arq.name}: ${res.mensagem}`);
                    }
                }
                catch (err) {
                    falhas.push(`${arq.name}: falha de comunicação`);
                }
            }
            await this.recarregarFotos();
            if (falhas.length) {
                alert('Algumas fotos não foram enviadas:\n- ' + falhas.join('\n- '));
            }
        }
        async excluirFoto(id) {
            if (!confirm('Excluir esta foto?')) {
                return;
            }
            try {
                const res = await fetch(`/api/triagem/fotos/?id=${id}`, { method: 'DELETE' }).then(r => r.json());
                if (res.status !== 'sucesso') {
                    alert('Erro: ' + res.mensagem);
                }
            }
            catch (err) {
                alert('Erro ao comunicar com o servidor.');
            }
            await this.recarregarFotos();
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
                    document.getElementById('v-peca').value = d.peca_trocada || "";
                    this.desenharGaleria(d.fotos || []);
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
