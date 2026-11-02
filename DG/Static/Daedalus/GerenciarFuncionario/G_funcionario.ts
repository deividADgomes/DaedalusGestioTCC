/// <reference path="../baseUI.ts" />

(() => {
    const CARGO_ADMINISTRADOR = 'Administrador';
    const CARGO_GESTOR = 'Gestor';
    const CARGO_ANALISTA = 'Analista de Triagem';
    const CARGO_FUNCIONARIO = 'Funcionário';
    const CARGOS_SOMENTE_LEITURA = [CARGO_FUNCIONARIO, CARGO_ANALISTA];
    const CARGOS_DE_GESTAO = [CARGO_ADMINISTRADOR, CARGO_GESTOR];

    const COR_POR_CARGO: Record<string, string> = {
        [CARGO_ADMINISTRADOR]: 'text-fuchsia-500',
        [CARGO_GESTOR]: 'text-amber-500',
        [CARGO_ANALISTA]: 'text-emerald-400',
        [CARGO_FUNCIONARIO]: 'text-cyan-400',
    };
    const COR_CARGO_PADRAO = 'text-slate-400';

    interface FuncionarioApi {
        id: number;
        nome: string;
        cargo: string;
        login: number;
        email: string | null;
    }

    interface SolicitacaoSenhaApi {
        id_funcionario: number;
        nome: string;
        cargo: string;
        login: number;
        email: string | null;
        data: string;
    }

    class FuncionarioUI extends BaseUI {
        private botaoSalvar = obterElemento<HTMLButtonElement>('btn-salvar-funcionario');
        private botaoLimpar = obterElemento<HTMLButtonElement>('btn-limpar');
        private formulario = obterElemento<HTMLFormElement>('form-cadastro-funcionario');
        private listaFuncionarios = obterElemento('lista-funcionarios');
        private campoPesquisa = obterElemento<HTMLInputElement>('pesquisa-funcionario');
        private filtroCargo = obterElemento<HTMLSelectElement>('filtro-cargo');

        private idAtual: number | null = null;
        private funcionarios: FuncionarioApi[] = [];

        constructor() {
            super();
            this.iniciarEventos();
            this.carregarFuncionarios();
            this.carregarSolicitacoes();
            this.aplicarRestricoesDoCargo();
        }

        private get cargoLogado(): string {
            return document.body.dataset.cargo || '';
        }

        private iniciarEventos(): void {
            this.botaoSalvar.addEventListener('click', () => this.salvarFuncionario());
            this.botaoLimpar.addEventListener('click', () => this.limparFormulario());
            this.campoPesquisa.addEventListener('input', () => this.filtrarFuncionarios());
            this.filtroCargo.addEventListener('change', () => this.filtrarFuncionarios());
        }

        private aplicarRestricoesDoCargo(): void {
            if (CARGOS_SOMENTE_LEITURA.includes(this.cargoLogado)) {
                this.formulario.querySelectorAll('input, select').forEach((campo) => {
                    (campo as HTMLInputElement).disabled = true;
                });
                this.botaoSalvar.style.display = 'none';
                this.botaoLimpar.style.display = 'none';
                return;
            }

            if (this.cargoLogado === CARGO_GESTOR) {
                Array.from(obterElemento<HTMLSelectElement>('cargo').options).forEach((opcao) => {
                    if (CARGOS_DE_GESTAO.includes(opcao.value)) {
                        opcao.disabled = true;
                        opcao.style.display = 'none';
                    }
                });
            }
        }

        private validarFormulario(nome: string, cargo: string, login: string, email: string, senha: string): string | null {
            if (!nome || !cargo || !login || !email) {
                return 'Preencha todos os campos obrigatórios (Nome, Cargo, Login e E-mail)!';
            }
            if (!/^\d+$/.test(login)) {
                definirValorDoCampo('login', '');
                return "Formato Inválido: O campo 'Login de Acesso' deve conter apenas números (ex: matrícula).";
            }
            if (this.idAtual === null && !senha) {
                return 'Para cadastrar um novo funcionário, a senha é obrigatória!';
            }
            if (this.cargoLogado === CARGO_GESTOR && CARGOS_DE_GESTAO.includes(cargo)) {
                return 'Operação bloqueada: Você não tem privilégios para criar cargos de nível Gestor ou Administrador.';
            }
            return null;
        }

        private async salvarFuncionario(): Promise<void> {
            const nome = valorDoCampo('nome');
            const cargo = valorDoCampo('cargo');
            const login = valorDoCampo('login');
            const senha = valorDoCampo('senha');
            const email = valorDoCampo('email').trim();

            const erroDeValidacao = this.validarFormulario(nome, cargo, login, email, senha);
            if (erroDeValidacao) {
                alert(erroDeValidacao);
                return;
            }

            try {
                const resultado = await enviarJson('/api/funcionario/', {
                    id: this.idAtual,
                    nome,
                    cargo,
                    login: parseInt(login),
                    email,
                    senha: senha || null,
                });
                if (resultado.status !== 'sucesso') {
                    alert('Erro: ' + resultado.mensagem);
                    return;
                }
                alert(resultado.mensagem);
                this.limparFormulario();
                this.carregarFuncionarios();
                this.carregarSolicitacoes();
            } catch (erro) {
                console.error('Falha na requisição:', erro);
                alert('Erro ao comunicar com o servidor.');
            }
        }

        private async carregarFuncionarios(): Promise<void> {
            this.listaFuncionarios.innerHTML = htmlMensagemNeutra('Carregando dados do servidor...');

            try {
                const resultado = await buscarJson('/api/funcionario/');
                if (resultado.status !== 'sucesso') {
                    this.listaFuncionarios.innerHTML = htmlMensagemErro(`Erro do Servidor: ${resultado.mensagem}`);
                    return;
                }
                this.funcionarios = resultado.dados;
                this.filtrarFuncionarios();
            } catch (erro) {
                this.listaFuncionarios.innerHTML = htmlMensagemErro('Erro crítico ao tentar conectar com o servidor.');
            }
        }

        private filtrarFuncionarios(): void {
            const termo = this.campoPesquisa.value.toLowerCase();
            const cargo = this.filtroCargo.value;

            const filtrados = this.funcionarios.filter((funcionario) => {
                if (cargo !== 'todos' && funcionario.cargo !== cargo) return false;
                return (
                    funcionario.nome.toLowerCase().includes(termo) ||
                    String(funcionario.login).includes(termo) ||
                    (funcionario.email || '').toLowerCase().includes(termo)
                );
            });

            this.renderizarCards(filtrados);
        }

        private renderizarCards(funcionarios: FuncionarioApi[]): void {
            this.listaFuncionarios.innerHTML = '';

            if (funcionarios.length === 0) {
                this.listaFuncionarios.innerHTML = htmlMensagemNeutra('Nenhum funcionário encontrado.');
                return;
            }

            funcionarios.forEach((funcionario) => {
                const corDoCargo = COR_POR_CARGO[funcionario.cargo] || COR_CARGO_PADRAO;

                const card = document.createElement('div');
                card.className = 'bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group';
                card.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <span class="text-xs font-bold ${corDoCargo} uppercase tracking-wider">${escapeHtml(funcionario.cargo)}</span>
                        <span class="text-[10px] text-slate-500 font-mono">ID: ${funcionario.id}</span>
                    </div>
                    <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${escapeHtml(funcionario.nome)}</h3>
                    <p class="text-xs text-slate-400 mt-1 font-mono">Login: ${funcionario.login}</p>
                    <p class="text-xs text-slate-500 mt-1 truncate">${escapeHtml(funcionario.email || 'sem e-mail cadastrado')}</p>
                    <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-end">
                        <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                    </div>
                `;
                card.addEventListener('dblclick', () => {
                    this.prepararEdicao(funcionario.id, funcionario.nome, funcionario.cargo, funcionario.login, funcionario.email || '');
                });
                this.listaFuncionarios.appendChild(card);
            });
        }

        private async carregarSolicitacoes(): Promise<void> {
            const painel = document.getElementById('painel-solicitacoes');
            const lista = document.getElementById('lista-solicitacoes');
            if (!painel || !lista) return;

            try {
                const resultado = await buscarJson('/api/solicitacoes-senha/');
                lista.innerHTML = '';

                if (resultado.status !== 'sucesso' || resultado.dados.length === 0) {
                    painel.classList.add('hidden');
                    return;
                }
                painel.classList.remove('hidden');
                resultado.dados.forEach((pedido: SolicitacaoSenhaApi) => lista.appendChild(this.criarItemDeSolicitacao(pedido)));
            } catch (erro) {
                console.error('Falha ao carregar solicitações:', erro);
            }
        }

        private criarItemDeSolicitacao(pedido: SolicitacaoSenhaApi): HTMLElement {
            const item = document.createElement('div');
            item.className = 'flex items-center justify-between gap-4 bg-[#0f172a] border border-[#334155] rounded-lg px-4 py-3';
            item.innerHTML = `
                <span class="text-xs text-slate-300"><span class="font-bold text-white">${escapeHtml(pedido.nome)}</span> (matrícula ${escapeHtml(pedido.login)}) pediu redefinição em ${escapeHtml(pedido.data)}</span>
                <button type="button" class="px-3 py-1.5 rounded-md text-[10px] font-bold uppercase text-white bg-amber-600 hover:bg-amber-500">Redefinir senha</button>
            `;
            item.querySelector('button')!.addEventListener('click', () => {
                this.prepararEdicao(pedido.id_funcionario, pedido.nome, pedido.cargo, pedido.login, pedido.email || '');
                obterElemento('senha').focus();
            });
            return item;
        }

        private prepararEdicao(id: number, nome: string, cargo: string, login: number, email: string): void {
            if (CARGOS_SOMENTE_LEITURA.includes(this.cargoLogado)) {
                alert('Você não tem permissão para alterar dados de funcionários.');
                return;
            }

            this.idAtual = id;
            definirValorDoCampo('nome', nome);
            definirValorDoCampo('cargo', cargo);
            definirValorDoCampo('login', login.toString());
            definirValorDoCampo('email', email);
            definirValorDoCampo('senha', '');

            aplicarModoEdicao(this.botaoSalvar, 'Alterar Registro');
            marcarRotulosFlutuantes(true);
            this.formulario.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        private limparFormulario(): void {
            this.formulario.reset();
            this.idAtual = null;

            aplicarModoInsercao(this.botaoSalvar, 'Salvar Funcionário');
            marcarRotulosFlutuantes(false);
        }
    }

    window.addEventListener('DOMContentLoaded', () => new FuncionarioUI());
})();
