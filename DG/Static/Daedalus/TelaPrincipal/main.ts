/// <reference path="../baseUI.ts" />

(() => {
    const STATUS_FUNCIONAL = 1;
    const STATUS_DEFEITO = 2;
    const MAX_FOTOS = 10;
    const MAX_BYTES_POR_FOTO = 10 * 1024 * 1024;
    const TIPOS_DE_IMAGEM = ['image/jpeg', 'image/png', 'image/webp'];
    const CARGO_ADMINISTRADOR = 'Administrador';

    const OPCAO_SELECIONE = '<option value="" disabled selected>Selecione...</option>';

    interface OpcaoDeLista {
        id: number;
        [campo: string]: any;
    }

    class TriagemUI extends BaseUI {
        private botaoSalvar = obterElemento<HTMLButtonElement>('btn-salvar');
        private botaoLimpar = obterElemento<HTMLButtonElement>('btn-limpar');
        private formulario = obterElemento<HTMLFormElement>('form-triagem');
        private alternadorDeStatus = obterElemento<HTMLInputElement>('funcional');
        private textoDoStatus = obterElemento<HTMLSpanElement>('status-texto');

        private fotosPendentes: File[] = [];

        constructor() {
            super();
            this.iniciarEventos();
            this.preencherDataDeHoje();
            this.carregarListas();
        }

        private iniciarEventos(): void {
            this.botaoSalvar.addEventListener('click', () => this.salvarTriagem());
            this.botaoLimpar.addEventListener('click', () => this.limparFormulario());
            obterElemento('equipamento').addEventListener('change', () => this.carregarPecasDoModelo());
            obterElemento('input-fotos').addEventListener('change', (evento) => this.selecionarFotos(evento));
            this.alternadorDeStatus.addEventListener('change', () => this.atualizarTextoDoStatus());
        }

        private atualizarTextoDoStatus(): void {
            if (this.alternadorDeStatus.checked) {
                this.textoDoStatus.innerText = 'Funcional';
                this.textoDoStatus.classList.replace('text-rose-400', 'text-emerald-400');
            } else {
                this.restaurarStatusDefeito();
            }
        }

        private restaurarStatusDefeito(): void {
            this.textoDoStatus.innerText = 'Defeito';
            this.textoDoStatus.classList.replace('text-emerald-400', 'text-rose-400');
        }

        private preencherDataDeHoje(): void {
            definirValorDoCampo('data', new Date().toLocaleDateString('pt-BR'));
        }

        private async carregarListas(): Promise<void> {
            try {
                const [clientes, equipamentos, tecnicos, funcionarios] = await Promise.all([
                    buscarJson('/api/empresa/?tipo=2'),
                    buscarJson('/api/modelo-equipamento/'),
                    buscarJson('/api/tecnico/'),
                    buscarJson('/api/funcionario/'),
                ]);

                this.preencherSelect('cliente', clientes, (cliente) => [cliente.razao_social || cliente.nome, cliente.id]);
                this.preencherSelect('equipamento', equipamentos, (modelo) => [`${modelo.pn} - ${modelo.modelo}`, modelo.id]);
                this.preencherSelect('tecnico', tecnicos, (tecnico) => [`${tecnico.nome} (${tecnico.nome_empresa})`, tecnico.id]);
                this.preencherSelect(
                    'analista',
                    funcionarios,
                    (funcionario) => [`${funcionario.nome} - ${funcionario.cargo}`, funcionario.id],
                    (funcionario) => funcionario.cargo && funcionario.cargo !== CARGO_ADMINISTRADOR
                );
            } catch (erro) {
                console.error('Erro ao carregar selects:', erro);
            }
        }

        private preencherSelect(
            idDoSelect: string,
            resposta: { status: string; dados: OpcaoDeLista[] },
            comoOpcao: (item: OpcaoDeLista) => [string, number],
            incluir: (item: OpcaoDeLista) => boolean = () => true
        ): void {
            const select = obterElemento<HTMLSelectElement>(idDoSelect);
            select.innerHTML = OPCAO_SELECIONE;
            if (resposta.status !== 'sucesso') return;

            resposta.dados.filter(incluir).forEach((item) => {
                const [texto, valor] = comoOpcao(item);
                select.add(new Option(texto, String(valor)));
            });
        }

        private async carregarPecasDoModelo(): Promise<void> {
            const select = obterElemento<HTMLSelectElement>('peca-trocada');
            const idEquipamento = valorDoCampo('equipamento');
            select.innerHTML = '<option value="">Carregando...</option>';

            try {
                const resultado = await buscarJson(`/api/modelo-equipamento/pecas/?id_equipamento=${idEquipamento}`);
                const pecas: { id: number; part_number: string; descricao: string }[] =
                    resultado.status === 'sucesso' ? resultado.dados : [];

                select.innerHTML = pecas.length
                    ? '<option value="">Nenhuma / outra (descrever ao lado)</option>'
                    : '<option value="">Este modelo não tem peças cadastradas</option>';
                pecas.forEach((peca) => {
                    const texto = peca.descricao ? `${peca.part_number} - ${peca.descricao}` : peca.part_number;
                    select.add(new Option(texto, String(peca.id)));
                });
            } catch (erro) {
                select.innerHTML = '<option value="">Não foi possível carregar as peças</option>';
            }
        }

        private selecionarFotos(evento: Event): void {
            const campo = evento.target as HTMLInputElement;

            Array.from(campo.files || []).forEach((arquivo) => {
                if (!TIPOS_DE_IMAGEM.includes(arquivo.type)) {
                    alert(`"${arquivo.name}": use JPG, PNG ou WEBP.`);
                } else if (arquivo.size > MAX_BYTES_POR_FOTO) {
                    alert(`"${arquivo.name}" excede 10 MB.`);
                } else if (this.fotosPendentes.length >= MAX_FOTOS) {
                    alert(`Limite de ${MAX_FOTOS} fotos por triagem.`);
                } else {
                    this.fotosPendentes.push(arquivo);
                }
            });

            campo.value = '';
            this.desenharPrevia();
        }

        private desenharPrevia(): void {
            const area = obterElemento('previa-fotos');
            area.querySelectorAll('img').forEach((imagem) => URL.revokeObjectURL(imagem.src));
            area.innerHTML = '';

            this.fotosPendentes.forEach((arquivo, indice) => {
                const item = document.createElement('div');
                item.className = 'relative group aspect-square rounded-lg overflow-hidden border border-[#334155] bg-slate-900';

                const imagem = document.createElement('img');
                imagem.src = URL.createObjectURL(arquivo);
                imagem.alt = arquivo.name;
                imagem.className = 'w-full h-full object-cover';

                const remover = document.createElement('button');
                remover.type = 'button';
                remover.textContent = '✕';
                remover.title = 'Remover';
                remover.className = 'absolute top-1 right-1 w-6 h-6 rounded-full bg-black/70 text-rose-300 text-xs hover:bg-rose-600 hover:text-white';
                remover.addEventListener('click', () => {
                    this.fotosPendentes.splice(indice, 1);
                    this.desenharPrevia();
                });

                item.append(imagem, remover);
                area.appendChild(item);
            });
        }

        private async enviarFotos(idTriagem: number): Promise<string[]> {
            const falhas: string[] = [];

            for (const arquivo of this.fotosPendentes) {
                const corpo = new FormData();
                corpo.append('id_triagem', String(idTriagem));
                corpo.append('arquivo', arquivo);
                try {
                    const resultado = await requisitarJson('/api/triagem/fotos/', { method: 'POST', body: corpo });
                    if (resultado.status !== 'sucesso') falhas.push(`${arquivo.name}: ${resultado.mensagem}`);
                } catch (erro) {
                    falhas.push(`${arquivo.name}: falha de comunicação`);
                }
            }
            return falhas;
        }

        private montarDadosDaTriagem(): Record<string, unknown> {
            return {
                n_ticket: parseInt(valorDoCampo('ticket')),
                nf: parseInt(valorDoCampo('nf')) || 0,
                cidade: valorDoCampo('Cidade'),
                estado: valorDoCampo('Estado'),
                id_cliente: parseInt(valorDoCampo('cliente')),
                id_equipamento: parseInt(valorDoCampo('equipamento')),
                id_tecnico: parseInt(valorDoCampo('tecnico')),
                id_analista: parseInt(valorDoCampo('analista')),
                sn: valorDoCampo('nserie'),
                status_peca: this.alternadorDeStatus.checked ? STATUS_FUNCIONAL : STATUS_DEFEITO,
                troca: valorDoCampo('troca'),
                id_peca_trocada: valorDoCampo('peca-trocada') || null,
                defeito_usuario: valorDoCampo('defeitoAlegado'),
                defeito_tecnico: valorDoCampo('constatacao'),
                defeito_constatado: valorDoCampo('defeitoResumo'),
                testes: valorDoCampo('testes'),
                analise: valorDoCampo('analise'),
                conclusao: valorDoCampo('conclusao'),
            };
        }

        private camposObrigatoriosPreenchidos(): boolean {
            return ['ticket', 'nserie', 'cliente', 'equipamento', 'tecnico', 'analista'].every((id) => valorDoCampo(id));
        }

        private async montarAvisoDeSucesso(mensagem: string, idTriagem?: number): Promise<string> {
            const aviso = mensagem || 'Triagem salva com sucesso!';
            if (!this.fotosPendentes.length || !idTriagem) return aviso;

            const falhas = await this.enviarFotos(idTriagem);
            return falhas.length
                ? `${aviso}\n\nAlgumas fotos não foram enviadas (anexe-as depois na tela de visualização):\n- ${falhas.join('\n- ')}`
                : `${aviso}\n${this.fotosPendentes.length} foto(s) anexada(s).`;
        }

        private async salvarTriagem(): Promise<void> {
            if (!this.camposObrigatoriosPreenchidos()) {
                alert('Preencha todos os campos obrigatórios e selecione as listas!');
                return;
            }

            try {
                const resultado = await enviarJson('/api/triagem/', this.montarDadosDaTriagem());
                if (resultado.status !== 'sucesso') {
                    alert('Erro do Servidor: ' + resultado.mensagem);
                    return;
                }
                alert(await this.montarAvisoDeSucesso(resultado.mensagem, resultado.id_gerado));
                this.limparFormulario();
            } catch (erro) {
                console.error('Falha na requisição:', erro);
                alert('Erro ao comunicar com o servidor.');
            }
        }

        private limparFormulario(): void {
            this.formulario.reset();
            this.restaurarStatusDefeito();
            this.fotosPendentes = [];
            this.desenharPrevia();
            obterElemento<HTMLSelectElement>('peca-trocada').innerHTML = '<option value="">Selecione o modelo primeiro</option>';
            marcarRotulosFlutuantes(false);
            this.preencherDataDeHoje();
        }
    }

    window.addEventListener('DOMContentLoaded', () => new TriagemUI());
})();
