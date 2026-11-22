/// <reference path="../baseUI.ts" />

(() => {
    const STATUS_FUNCIONAL = 1;
    const TEXTO_NAO_INFORMADO = 'Não informado';

    interface FotoApi {
        id: number;
        url: string;
        legenda: string;
    }

    interface TriagemDetalhe {
        n_ticket: number;
        nf: number;
        cidade: string;
        estado: string;
        sn: string;
        status_peca: number;
        troca: string;
        peca_trocada: string | null;
        nome_cliente: string;
        nome_equipamento: string;
        nome_tecnico: string;
        nome_analista: string;
        defeito_usuario: string;
        defeito_tecnico: string;
        defeito_constatado: string;
        testes: string;
        analise: string;
        conclusao: string;
        fotos: FotoApi[];
    }

    class VisualizarUI extends BaseUI {
        private idAtual: string | null = null;

        constructor() {
            super();
            this.carregarDados();
            this.iniciarEventos();
        }

        private iniciarEventos(): void {
            document.getElementById('input-fotos')?.addEventListener('change', (evento) => this.enviarFotos(evento));
            document.getElementById('btn-exportar-word')?.addEventListener('click', () => {
                if (!this.idAtual) {
                    alert('Erro: ID da triagem não encontrado para exportação.');
                    return;
                }
                window.location.href = `/api/triagem/exportar-docx/?id=${this.idAtual}`;
            });
        }

        private criarMiniatura(foto: FotoApi): HTMLElement {
            const item = document.createElement('div');
            item.className = 'relative aspect-square rounded-lg overflow-hidden border border-[#334155] bg-slate-900';

            const link = document.createElement('a');
            link.href = foto.url;
            link.target = '_blank';
            link.rel = 'noopener';

            const imagem = document.createElement('img');
            imagem.src = foto.url;
            imagem.alt = foto.legenda || 'Foto da triagem';
            imagem.loading = 'lazy';
            imagem.className = 'w-full h-full object-cover hover:opacity-90 transition-opacity';
            link.appendChild(imagem);

            const excluir = document.createElement('button');
            excluir.type = 'button';
            excluir.textContent = '✕';
            excluir.title = 'Excluir foto';
            excluir.className = 'absolute top-1 right-1 w-6 h-6 rounded-full bg-black/70 text-rose-300 text-xs hover:bg-rose-600 hover:text-white';
            excluir.addEventListener('click', () => this.excluirFoto(foto.id));

            item.append(link, excluir);
            return item;
        }

        private desenharGaleria(fotos: FotoApi[]): void {
            const galeria = obterElemento('galeria-fotos');
            galeria.innerHTML = '';
            document.getElementById('galeria-vazia')?.classList.toggle('hidden', fotos.length > 0);
            fotos.forEach((foto) => galeria.appendChild(this.criarMiniatura(foto)));
        }

        private async recarregarFotos(): Promise<void> {
            const resultado = await buscarJson(`/api/triagem/fotos/?id_triagem=${this.idAtual}`);
            if (resultado.status === 'sucesso') this.desenharGaleria(resultado.dados);
        }

        private async enviarFotos(evento: Event): Promise<void> {
            const campo = evento.target as HTMLInputElement;
            const arquivos = Array.from(campo.files || []);
            campo.value = '';

            const falhas: string[] = [];
            for (const arquivo of arquivos) {
                const corpo = new FormData();
                corpo.append('id_triagem', String(this.idAtual));
                corpo.append('arquivo', arquivo);
                try {
                    const resultado = await requisitarJson('/api/triagem/fotos/', { method: 'POST', body: corpo });
                    if (resultado.status !== 'sucesso') falhas.push(`${arquivo.name}: ${resultado.mensagem}`);
                } catch (erro) {
                    falhas.push(`${arquivo.name}: falha de comunicação`);
                }
            }

            await this.recarregarFotos();
            if (falhas.length) alert('Algumas fotos não foram enviadas:\n- ' + falhas.join('\n- '));
        }

        private async excluirFoto(id: number): Promise<void> {
            if (!confirm('Excluir esta foto?')) return;

            try {
                const resultado = await requisitarJson(`/api/triagem/fotos/?id=${id}`, { method: 'DELETE' });
                if (resultado.status !== 'sucesso') alert('Erro: ' + resultado.mensagem);
            } catch (erro) {
                alert('Erro ao comunicar com o servidor.');
            }
            await this.recarregarFotos();
        }

        private preencherDetalhes(triagem: TriagemDetalhe): void {
            obterElemento('label-ticket').innerText =
                `Ticket #${triagem.n_ticket || ''} - Analisado por ${triagem.nome_analista || ''}`;

            const camposDaOrdem: Record<string, string | number | null> = {
                'v-ticket': triagem.n_ticket,
                'v-nf': triagem.nf,
                'v-cidade': triagem.cidade,
                'v-estado': triagem.estado,
                'v-cliente': triagem.nome_cliente,
                'v-tecnico': triagem.nome_tecnico,
                'v-analista': triagem.nome_analista,
                'v-equipamento': triagem.nome_equipamento,
                'v-sn': triagem.sn,
                'v-troca': triagem.troca,
                'v-peca': triagem.peca_trocada,
            };
            Object.entries(camposDaOrdem).forEach(([id, valor]) => definirValorDoCampo(id, String(valor || '')));

            const camposDoLaudo: Record<string, string> = {
                'v-defeito_usuario': triagem.defeito_usuario,
                'v-defeito_tecnico': triagem.defeito_tecnico,
                'v-defeito_constatado': triagem.defeito_constatado,
                'v-testes': triagem.testes,
                'v-analise': triagem.analise,
                'v-conclusao': triagem.conclusao,
            };
            Object.entries(camposDoLaudo).forEach(([id, valor]) => definirValorDoCampo(id, valor || TEXTO_NAO_INFORMADO));

            this.desenharGaleria(triagem.fotos || []);
            this.exibirStatus(triagem.status_peca);
        }

        private exibirStatus(status: number): void {
            const funcional = status === STATUS_FUNCIONAL;
            const campo = obterElemento<HTMLInputElement>('v-status');
            campo.value = funcional ? 'FUNCIONAL' : 'NÃO FUNCIONAL / COM DEFEITO';
            campo.classList.add(funcional ? 'text-emerald-400' : 'text-rose-400');
        }

        private async carregarDados(): Promise<void> {
            this.idAtual = new URLSearchParams(window.location.search).get('id');

            if (!this.idAtual) {
                alert('ID da triagem não fornecido.');
                window.location.href = '/pesquisa/';
                return;
            }

            try {
                const resultado = await buscarJson(`/api/triagem/?id=${this.idAtual}`);
                if (resultado.status !== 'sucesso') {
                    alert('Erro do Servidor: ' + resultado.mensagem);
                    return;
                }
                this.preencherDetalhes(resultado.dado);
                document.getElementById('container-visualizacao')?.classList.remove('opacity-0');
            } catch (erro) {
                alert('Erro grave de comunicação com o servidor.');
            }
        }
    }

    window.addEventListener('DOMContentLoaded', () => new VisualizarUI());
})();
