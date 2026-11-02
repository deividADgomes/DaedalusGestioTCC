/// <reference path="../baseUI.ts" />

(() => {
    interface PecaModelo {
        part_number: string;
        descricao: string;
    }

    interface CandidataPartSurfer extends PecaModelo {
        selecionada: boolean;
        somente_local: boolean;
    }

    interface ModeloApi {
        id: number;
        pn: string;
        modelo: string;
        total_pecas?: number;
    }

    class ModeloEquipamentoUI extends BaseUI {
        private botaoSalvar = obterElemento<HTMLButtonElement>('btn-salvar-modelo');
        private botaoLimpar = obterElemento<HTMLButtonElement>('btn-limpar');
        private formulario = obterElemento<HTMLFormElement>('form-cadastro-modelo');
        private listaModelos = obterElemento('lista-modelos');
        private campoPesquisa = obterElemento<HTMLInputElement>('pesquisa-modelo');

        private idAtual: number | null = null;
        private modelos: ModeloApi[] = [];
        private pecas: PecaModelo[] = [];
        private candidatas: CandidataPartSurfer[] = [];

        constructor() {
            super();
            this.iniciarEventos();
            this.iniciarEventosDePecas();
            this.carregarModelos();
        }

        private iniciarEventos(): void {
            this.botaoSalvar.addEventListener('click', () => this.salvarModelo());
            this.botaoLimpar.addEventListener('click', () => this.limparFormulario());
            this.campoPesquisa.addEventListener('input', () => this.filtrarModelos());
        }

        private iniciarEventosDePecas(): void {
            const aoClicar: Record<string, () => void> = {
                'btn-add-peca': () => this.adicionarPecaDoFormulario(),
                'btn-importar-pecas': () => this.importarLista(),
                'btn-salvar-pecas': () => this.salvarPecas(),
                'btn-partsurfer': () => this.buscarNoPartSurfer(),
                'ps-fechar': () => this.fecharPartSurfer(),
                'ps-aplicar': () => this.aplicarSelecaoDoPartSurfer(),
                'ps-marcar-todas': () => this.marcarCandidatas(true),
                'ps-desmarcar': () => this.marcarCandidatas(false),
            };
            Object.entries(aoClicar).forEach(([id, acao]) => {
                document.getElementById(id)?.addEventListener('click', acao);
            });

            document.getElementById('peca-pn')?.addEventListener('keydown', (evento) => {
                if ((evento as KeyboardEvent).key === 'Enter') {
                    evento.preventDefault();
                    this.adicionarPecaDoFormulario();
                }
            });
            document.getElementById('ps-filtro')?.addEventListener('input', () => this.desenharCandidatas());
        }

        private async salvarModelo(): Promise<void> {
            const pn = valorDoCampo('pn');
            const modelo = valorDoCampo('modelo');

            if (!pn || !modelo) {
                alert('Preencha todos os campos obrigatórios (PN e Modelo)!');
                return;
            }

            try {
                const resultado = await enviarJson('/api/modelo-equipamento/', { id: this.idAtual, pn, modelo });
                if (resultado.status !== 'sucesso') {
                    alert('Erro: ' + resultado.mensagem);
                    return;
                }
                alert(resultado.mensagem);
                const idSalvo: number = resultado.id_gerado;
                this.limparFormulario();
                this.carregarModelos();
                if (idSalvo) this.prepararEdicao(idSalvo, pn, modelo);
            } catch (erro) {
                console.error('Falha na requisição:', erro);
                alert('Erro ao comunicar com o servidor.');
            }
        }

        private async carregarModelos(): Promise<void> {
            this.listaModelos.innerHTML = htmlMensagemNeutra('Carregando dados do servidor...');

            try {
                const resultado = await buscarJson('/api/modelo-equipamento/');
                if (resultado.status !== 'sucesso') {
                    this.listaModelos.innerHTML = htmlMensagemErro(`Erro do Servidor: ${resultado.mensagem}`);
                    return;
                }
                this.modelos = resultado.dados;
                this.filtrarModelos();
            } catch (erro) {
                this.listaModelos.innerHTML = htmlMensagemErro('Erro crítico ao tentar conectar com o servidor.');
            }
        }

        private filtrarModelos(): void {
            const termo = this.campoPesquisa.value.toLowerCase();

            const filtrados = this.modelos.filter(
                (modelo) => modelo.modelo.toLowerCase().includes(termo) || modelo.pn.toLowerCase().includes(termo)
            );

            this.renderizarCards(filtrados);
        }

        private renderizarCards(modelos: ModeloApi[]): void {
            this.listaModelos.innerHTML = '';

            if (modelos.length === 0) {
                this.listaModelos.innerHTML = htmlMensagemNeutra('Nenhum equipamento encontrado.');
                return;
            }

            modelos.forEach((equipamento) => {
                const card = document.createElement('div');
                card.className = 'bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group';
                card.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <span class="text-xs font-bold text-cyan-400 uppercase tracking-wider">Equipamento</span>
                        <span class="text-[10px] text-slate-500 font-mono">ID: ${equipamento.id}</span>
                    </div>
                    <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${escapeHtml(equipamento.modelo)}</h3>
                    <p class="text-xs text-slate-400 mt-1 font-mono">PN: ${escapeHtml(equipamento.pn)}</p>
                    <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-between">
                        <span class="text-[10px] text-emerald-400 font-bold uppercase tracking-widest">${equipamento.total_pecas || 0} peça(s)</span>
                        <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                    </div>
                `;
                card.addEventListener('dblclick', () => this.prepararEdicao(equipamento.id, equipamento.pn, equipamento.modelo));
                this.listaModelos.appendChild(card);
            });
        }

        private prepararEdicao(id: number, pn: string, modelo: string): void {
            this.idAtual = id;
            definirValorDoCampo('pn', pn);
            definirValorDoCampo('modelo', modelo);

            aplicarModoEdicao(this.botaoSalvar, 'Alterar Registro');
            marcarRotulosFlutuantes(true);
            this.formulario.scrollIntoView({ behavior: 'smooth', block: 'start' });
            this.abrirPecas(id, modelo);
        }

        private limparFormulario(): void {
            this.formulario.reset();
            this.idAtual = null;

            aplicarModoInsercao(this.botaoSalvar, 'Salvar Equipamento');
            marcarRotulosFlutuantes(false);
            document.getElementById('secao-pecas')?.classList.add('hidden');
            this.fecharPartSurfer();
            this.pecas = [];
        }

        private async abrirPecas(id: number, modelo: string): Promise<void> {
            obterElemento('pecas-modelo-nome').innerText = modelo;
            document.getElementById('secao-pecas')?.classList.remove('hidden');
            this.pecas = [];
            this.fecharPartSurfer();
            this.desenharPecas();

            try {
                const resultado = await buscarJson(`/api/modelo-equipamento/pecas/?id_equipamento=${id}`);
                if (resultado.status === 'sucesso' && this.idAtual === id) {
                    this.pecas = this.converterPecas(resultado.dados);
                    this.desenharPecas();
                }
            } catch (erro) {
                console.error('Falha ao carregar peças:', erro);
            }
        }

        private converterPecas(dados: PecaModelo[]): PecaModelo[] {
            return dados.map((peca) => ({ part_number: peca.part_number, descricao: peca.descricao || '' }));
        }

        private adicionarPeca(partNumber: string, descricao: string): boolean {
            const chave = partNumber.trim().toUpperCase();
            if (!chave) return false;

            const descricaoLimpa = descricao.trim();
            const existente = this.pecas.find((peca) => peca.part_number === chave);
            if (!existente) {
                this.pecas.push({ part_number: chave, descricao: descricaoLimpa });
            } else if (descricaoLimpa) {
                existente.descricao = descricaoLimpa;
            }
            return true;
        }

        private adicionarPecaDoFormulario(): void {
            const campoPn = obterElemento<HTMLInputElement>('peca-pn');
            const campoDescricao = obterElemento<HTMLInputElement>('peca-descricao');

            if (!this.adicionarPeca(campoPn.value, campoDescricao.value)) {
                alert('Informe o Part Number da peça.');
                return;
            }
            [campoPn, campoDescricao].forEach((campo) => {
                campo.value = '';
                campo.classList.remove('has-value');
            });
            campoPn.focus();
            this.desenharPecas();
        }

        private importarLista(): void {
            const areaDeTexto = obterElemento<HTMLTextAreaElement>('peca-colar');
            let importadas = 0;

            areaDeTexto.value.split(/\r?\n/).forEach((linha) => {
                const [partNumber, ...resto] = linha.split(/[;\t]/);
                if (this.adicionarPeca(partNumber || '', resto.join(' ').trim())) importadas++;
            });

            areaDeTexto.value = '';
            this.desenharPecas();
            if (importadas === 0) alert('Nenhuma linha válida encontrada.');
        }

        private desenharPecas(): void {
            const lista = obterElemento('lista-pecas');
            lista.innerHTML = '';
            document.getElementById('pecas-vazio')?.classList.toggle('hidden', this.pecas.length > 0);

            [...this.pecas]
                .sort((a, b) => a.part_number.localeCompare(b.part_number))
                .forEach((peca) => {
                    const item = document.createElement('li');
                    item.className = 'flex items-center justify-between py-2 gap-3';
                    item.innerHTML = `<div class="min-w-0"><span class="font-mono text-cyan-400 text-xs">${escapeHtml(peca.part_number)}</span>
                        <span class="text-slate-300 text-xs ml-3">${escapeHtml(peca.descricao)}</span></div>
                        <button type="button" class="text-[10px] font-bold uppercase text-rose-400 hover:text-rose-300">Remover</button>`;
                    item.querySelector('button')?.addEventListener('click', () => {
                        this.pecas = this.pecas.filter((outra) => outra.part_number !== peca.part_number);
                        this.desenharPecas();
                    });
                    lista.appendChild(item);
                });
        }

        private async salvarPecas(): Promise<void> {
            if (!this.idAtual) return;

            try {
                const resultado = await enviarJson('/api/modelo-equipamento/pecas/', {
                    id_equipamento: this.idAtual,
                    pecas: this.pecas,
                });
                if (resultado.status !== 'sucesso') {
                    alert('Erro: ' + resultado.mensagem);
                    return;
                }
                this.pecas = this.converterPecas(resultado.dados);
                this.desenharPecas();
                this.carregarModelos();
                alert(resultado.mensagem);
            } catch (erro) {
                alert('Erro ao comunicar com o servidor.');
            }
        }

        private async buscarNoPartSurfer(): Promise<void> {
            if (!this.idAtual) return;

            const id = this.idAtual;
            const botao = obterElemento<HTMLButtonElement>('btn-partsurfer');
            const rotuloOriginal = botao.innerText;
            botao.disabled = true;
            botao.innerText = 'Consultando...';

            try {
                const resultado = await requisitarJson(`/api/modelo-equipamento/${id}/partsurfer/`, { method: 'POST' });
                if (resultado.status !== 'sucesso') {
                    alert(resultado.mensagem);
                    return;
                }
                if (this.idAtual !== id) return;

                this.candidatas = this.combinarComPecasLocais(resultado.dados);
                obterElemento('partsurfer-msg').innerText = resultado.mensagem + ' Marque as que este modelo usa.';
                definirValorDoCampo('ps-filtro', '');
                document.getElementById('painel-partsurfer')?.classList.remove('hidden');
                this.desenharCandidatas();
            } catch (erro) {
                alert('Erro ao comunicar com o servidor.');
            } finally {
                botao.disabled = false;
                botao.innerText = rotuloOriginal;
            }
        }

        private combinarComPecasLocais(vindasDoPartSurfer: CandidataPartSurfer[]): CandidataPartSurfer[] {
            const locais = new Set(this.pecas.map((peca) => peca.part_number));
            const candidatas = vindasDoPartSurfer.map((candidata) => ({
                ...candidata,
                selecionada: candidata.selecionada || locais.has(candidata.part_number),
            }));

            this.pecas.forEach((peca) => {
                if (!candidatas.some((candidata) => candidata.part_number === peca.part_number)) {
                    candidatas.push({ ...peca, selecionada: true, somente_local: true });
                }
            });
            return candidatas;
        }

        private desenharCandidatas(): void {
            const filtro = valorDoCampo('ps-filtro').trim().toLowerCase();
            const lista = obterElemento('ps-lista');
            lista.innerHTML = '';

            this.candidatas
                .filter((candidata) =>
                    !filtro ||
                    candidata.part_number.toLowerCase().includes(filtro) ||
                    candidata.descricao.toLowerCase().includes(filtro)
                )
                .forEach((candidata) => {
                    const item = document.createElement('li');
                    item.className = 'py-1.5';
                    item.innerHTML = `<label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox" class="accent-cyan-500" ${candidata.selecionada ? 'checked' : ''}>
                        <span class="font-mono text-cyan-400">${escapeHtml(candidata.part_number)}</span>
                        <span class="text-slate-300">${escapeHtml(candidata.descricao)}</span>
                        ${candidata.somente_local ? '<span class="text-[10px] text-amber-400">(não veio do PartSurfer)</span>' : ''}
                    </label>`;
                    item.querySelector('input')?.addEventListener('change', (evento) => {
                        candidata.selecionada = (evento.target as HTMLInputElement).checked;
                    });
                    lista.appendChild(item);
                });
        }

        private marcarCandidatas(marcada: boolean): void {
            this.candidatas.forEach((candidata) => {
                candidata.selecionada = marcada;
            });
            this.desenharCandidatas();
        }

        private aplicarSelecaoDoPartSurfer(): void {
            this.pecas = this.candidatas
                .filter((candidata) => candidata.selecionada)
                .map((candidata) => ({ part_number: candidata.part_number, descricao: candidata.descricao }));
            this.desenharPecas();
            this.fecharPartSurfer();
        }

        private fecharPartSurfer(): void {
            document.getElementById('painel-partsurfer')?.classList.add('hidden');
            this.candidatas = [];
        }
    }

    window.addEventListener('DOMContentLoaded', () => new ModeloEquipamentoUI());
})();
