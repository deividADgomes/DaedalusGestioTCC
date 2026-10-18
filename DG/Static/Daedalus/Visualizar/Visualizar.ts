/// <reference path="../baseUI.ts" />
(() => {
    class VisualizarUI extends BaseUI {
        private idAtual: string | null = null;
        private totalFotos = 0;

        constructor() {
            super();
            this.carregarDados();
            this.iniciarEventos();
        }

        private iniciarEventos(): void {
            document.getElementById('input-fotos')?.addEventListener('change', (e) => this.enviarFotos(e));
            const btnExportar = document.getElementById('btn-exportar-word');
            if (btnExportar) {
                btnExportar.addEventListener('click', () => {
                    if (this.idAtual) {
                        // Chama a rota que cria e descarrega o ficheiro DOCX
                        window.location.href = `/api/triagem/exportar-docx/?id=${this.idAtual}`;
                    } else {
                        alert("Erro: ID da triagem não encontrado para exportação.");
                    }
                });
            }
        }

        // ==========================================
        // FOTOS
        // ==========================================
        private desenharGaleria(fotos: any[]): void {
            this.totalFotos = fotos.length;
            const galeria = document.getElementById('galeria-fotos') as HTMLElement;
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

        private async recarregarFotos(): Promise<void> {
            const res = await fetch(`/api/triagem/fotos/?id_triagem=${this.idAtual}`).then(r => r.json());
            if (res.status === 'sucesso') { this.desenharGaleria(res.dados); }
        }

        private async enviarFotos(e: Event): Promise<void> {
            const input = e.target as HTMLInputElement;
            const arquivos = Array.from(input.files || []);
            input.value = '';
            const falhas: string[] = [];
            for (const arq of arquivos) {
                const fd = new FormData();
                fd.append('id_triagem', String(this.idAtual));
                fd.append('arquivo', arq);
                try {
                    const res = await fetch('/api/triagem/fotos/', { method: 'POST', body: fd }).then(r => r.json());
                    if (res.status !== 'sucesso') { falhas.push(`${arq.name}: ${res.mensagem}`); }
                } catch (err) {
                    falhas.push(`${arq.name}: falha de comunicação`);
                }
            }
            await this.recarregarFotos();
            if (falhas.length) { alert('Algumas fotos não foram enviadas:\n- ' + falhas.join('\n- ')); }
        }

        private async excluirFoto(id: number): Promise<void> {
            if (!confirm('Excluir esta foto?')) { return; }
            try {
                const res = await fetch(`/api/triagem/fotos/?id=${id}`, { method: 'DELETE' }).then(r => r.json());
                if (res.status !== 'sucesso') { alert('Erro: ' + res.mensagem); }
            } catch (err) {
                alert('Erro ao comunicar com o servidor.');
            }
            await this.recarregarFotos();
        }

        private async carregarDados(): Promise<void> {
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
                    (document.getElementById('label-ticket') as HTMLElement).innerText = `Ticket #${d.n_ticket || ''} - Analisado por ${d.nome_analista || ''}`;
                    
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
                    (document.getElementById('v-peca') as HTMLInputElement).value = d.peca_trocada || "";
                    this.desenharGaleria(d.fotos || []);
                    
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

                    // Mostrar a tela suavemente
                    document.getElementById('container-visualizacao')?.classList.remove('opacity-0');
                } else {
                    alert("Erro do Servidor: " + res.mensagem);
                }
            } catch (e) {
                alert("Erro grave de comunicação com o servidor.");
            }
        }
    }

    window.addEventListener('DOMContentLoaded', () => new VisualizarUI());
})();