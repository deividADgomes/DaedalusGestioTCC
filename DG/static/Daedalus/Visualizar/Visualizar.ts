/// <reference path="../BaseUI.ts" />
(() => {
    class VisualizarUI extends BaseUI {
        private idAtual: string | null = null;

        constructor() {
            super();
            this.carregarDados();
            this.iniciarEventos();
            this.carregarHistorico();
        }

        private iniciarEventos(): void {
            const btnExportar = document.getElementById('btn-exportar-word');
            if (btnExportar) {
                btnExportar.addEventListener('click', () => {
                    if (this.idAtual) {
                        // Chama a rota que cria e descarrega o ficheiro DOCX
                        window.location.href = `/api/triagem/exportar-docx/?id=${this.idAtual}`;
                    } else {
                        Mensagem.erro("Erro: ID da triagem não encontrado para exportação.");
                    }
                });
            }
        }

        // Correções feitas depois que a triagem foi salva (quem alterou, quando e o que mudou)
        private async carregarHistorico(): Promise<void> {
            const id = new URLSearchParams(window.location.search).get('id');
            if (!id) return;
            try {
                const res = await (await fetch(`/api/triagem/historico/?id=${id}`)).json();
                if (res.status !== 'sucesso' || res.dados.length === 0) return;   // sem correções: a seção nem aparece
                const lista = document.getElementById('lista-historico') as HTMLElement;
                lista.innerHTML = res.dados.map((h: any) => `
                    <li class="bg-[#0f172a] border border-[#334155] rounded-lg px-4 py-3">
                        <p class="text-xs text-slate-400"><span class="font-semibold text-slate-200">${escapeHtml(h.usuario)}</span> em ${escapeHtml(new Date(h.quando).toLocaleString('pt-BR'))}</p>
                        <ul class="mt-1 space-y-0.5">${h.alteracoes.map((a: any) => `
                            <li class="text-xs text-slate-300"><span class="text-cyan-400">${escapeHtml(a.campo)}:</span>
                                <span class="text-slate-500 line-through">${escapeHtml(a.de)}</span> → ${escapeHtml(a.para)}</li>`).join('')}
                        </ul>
                    </li>`).join('');
                document.getElementById('secao-historico')?.classList.remove('hidden');
            } catch (e) { /* o histórico é um extra: se falhar, o laudo continua visível */ }
        }

        private async carregarDados(): Promise<void> {
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
                    (document.getElementById('label-ticket') as HTMLElement).innerText = `Ticket #${d.n_ticket || ''} - Analisado por ${escapeHtml(d.nome_analista || '')}`;
                    
                    // SESSÃO 1: DADOS DA ORDEM
                    (document.getElementById('v-ticket') as HTMLInputElement).value = d.n_ticket || "";
                    (document.getElementById('v-nf') as HTMLInputElement).value = d.nf || "";
                    (document.getElementById('v-cidade') as HTMLInputElement).value = d.cidade || "";
                    (document.getElementById('v-estado') as HTMLInputElement).value = d.estado || "";
                    (document.getElementById('v-cliente') as HTMLInputElement).value = d.nome_cliente || "";
                    (document.getElementById('v-tecnico') as HTMLInputElement).value = d.nome_tecnico || "";
                    (document.getElementById('v-analista') as HTMLInputElement).value = d.nome_analista || "";

                    // SESSÃO 2: EQUIPAMENTO/PEÇA
                    (document.getElementById('v-equipamento') as HTMLInputElement).value = d.nome_equipamento || "";
                    (document.getElementById('v-sn') as HTMLInputElement).value = d.sn || "";
                    (document.getElementById('v-troca') as HTMLInputElement).value = d.troca || "";
                    const motivoIndevida = d.troca_indevida === true && d.motivo_troca_indevida
                        ? d.motivo_troca_indevida + (d.justificativa_troca_indevida ? ': ' + d.justificativa_troca_indevida : '') : '';
                    (document.getElementById('v-motivo-indevida') as HTMLInputElement).value = motivoIndevida;
                    document.getElementById('v-motivo-indevida-grupo')!.classList.toggle('hidden', !motivoIndevida);
                    (document.getElementById('v-ct') as HTMLInputElement).value = d.ct || '';
                    document.getElementById('v-ct-grupo')!.classList.toggle('hidden', !d.ct);
                    (document.getElementById('v-troca-indevida') as HTMLInputElement).value = d.troca_indevida === true ? 'Sim' : d.troca_indevida === false ? 'Não' : 'Não informado';
                    
                    // SESSÃO 3: LAUDO
                    (document.getElementById('v-defeito_usuario') as HTMLTextAreaElement).value = d.defeito_usuario || "Não informado";
                    (document.getElementById('v-defeito_tecnico') as HTMLTextAreaElement).value = d.defeito_tecnico || "Não informado";
                    (document.getElementById('v-defeito_constatado') as HTMLInputElement).value = d.defeito_constatado || "Não informado";
                    (document.getElementById('v-testes') as HTMLInputElement).value = d.testes || "Não informado";
                    (document.getElementById('v-analise') as HTMLTextAreaElement).value = d.analise || "Não informado";
                    (document.getElementById('v-conclusao') as HTMLTextAreaElement).value = d.conclusao || "Não informado";

                    // TRATAMENTO DO STATUS (VERDE/VERMELHO)
                    const statusElem = document.getElementById('v-status') as HTMLInputElement;
                    statusElem.value = d.status_peca === 1 ? "FUNCIONAL" : "NÃO FUNCIONAL / COM DEFEITO";
                    statusElem.classList.add(d.status_peca === 1 ? "text-emerald-400" : "text-rose-400");

                    (document.getElementById('btn-editar') as HTMLAnchorElement).href = `/triagem/?id=${this.idAtual}`;

                    // Mostrar a tela suavemente
                    document.getElementById('container-visualizacao')?.classList.remove('opacity-0');
                } else {
                    Mensagem.erro(res.mensagem, "Erro do Servidor");
                }
            } catch (e) {
                Mensagem.erro("Erro grave de comunicação com o servidor.");
            }
        }
    }

    window.addEventListener('DOMContentLoaded', () => new VisualizarUI());
})();