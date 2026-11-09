/// <reference path="../BaseUI.ts" />

(() => {
    class G_funcionarioUI extends BaseUI {
        private btnSalvar: HTMLButtonElement;
        private btnLimpar: HTMLButtonElement;
        private form: HTMLFormElement;
        private listaFuncionarios: HTMLElement;
        
        // Memória da tela: null = Inserção | number = Alteração
        private idAtual: number | null = null;
        private isProcessando: boolean = false; // Trava de segurança para duplo-clique
        
        constructor() {
            super(); 
            
            this.btnSalvar = document.getElementById('btn-salvar-funcionario') as HTMLButtonElement;
            this.btnLimpar = document.getElementById('btn-limpar') as HTMLButtonElement;
            this.form = document.getElementById('form-cadastro-funcionario') as HTMLFormElement;
            this.listaFuncionarios = document.getElementById('lista-funcionarios') as HTMLElement;

            this.iniciarEventos();
            this.carregarFuncionarios();
            this.carregarSolicitacoes();
            this.verificarPermissoes(); 
        }

        private iniciarEventos(): void {
            // 1. PREVENÇÃO DE TRAVAMENTO E RELOAD (Tecla Enter)
            this.form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.salvarFuncionario();
            });

            // Escuta do clique no botão
            this.btnSalvar.addEventListener('click', (e) => {
                e.preventDefault();
                this.salvarFuncionario();
            });
            
            this.btnLimpar.addEventListener('click', () => this.limparFormulario());

            // 2. ATIVAÇÃO DOS FILTROS (Busca e Cargo)
            const inputPesquisa = document.getElementById('pesquisa-funcionario') as HTMLInputElement;
            const selectFiltro = document.getElementById('filtro-cargo') as HTMLSelectElement;

            if (inputPesquisa) {
                inputPesquisa.addEventListener('input', () => this.filtrarListaVisuais());
            }
            if (selectFiltro) {
                selectFiltro.addEventListener('change', () => this.filtrarListaVisuais());
            }
        }

        // ==========================================
        // REGRA DE NEGÓCIO: CONTROLE DE ACESSO
        // ==========================================
        private verificarPermissoes(): void {
            const cargoUsuarioLogado: string = (window as any).CARGO_USUARIO_SESSAO || "Administrador"; 

            if (cargoUsuarioLogado === "Funcionário" || cargoUsuarioLogado === "Analista de Triagem") {
                const inputs = this.form.querySelectorAll('input, select');
                inputs.forEach(input => (input as HTMLInputElement).disabled = true);
                
                this.btnSalvar.style.display = 'none';
                this.btnLimpar.style.display = 'none';
            } 
            else if (cargoUsuarioLogado === "Gestor") {
                const selectCargo = document.getElementById('cargo') as HTMLSelectElement;
                Array.from(selectCargo.options).forEach(option => {
                    if (option.value === "Administrador" || option.value === "Gestor") {
                        option.disabled = true; 
                        option.style.display = 'none'; 
                    }
                });
            }
        }

        // ==========================================
        // LÓGICA DE SALVAR / ALTERAR (POST)
        // ==========================================
        private async salvarFuncionario(): Promise<void> {
            if (this.isProcessando) return; // Impede sobreposição de envios

            const nome = (document.getElementById('nome') as HTMLInputElement).value.trim();
            const cargo = (document.getElementById('cargo') as HTMLSelectElement).value;
            const login = (document.getElementById('login') as HTMLInputElement).value.trim(); 
            const senha = (document.getElementById('senha') as HTMLInputElement).value;
            const email = (document.getElementById('email') as HTMLInputElement).value.trim();

            // Validações
            if (!nome || !cargo || !login) {
                Mensagem.aviso("Preencha todos os campos obrigatórios (Nome, Cargo e Login)!");
                return;
            }

            const apenasNumeros = /^\d+$/;
            if (!apenasNumeros.test(login)) {
                Mensagem.aviso("Formato Inválido: O campo 'Login de Acesso' deve conter apenas números (ex: matrícula).");
                (document.getElementById('login') as HTMLInputElement).value = ""; 
                return;
            }

            if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                Mensagem.aviso("O e-mail informado não parece válido. Confira e tente novamente.");
                return;
            }

            if (this.idAtual === null && !senha) {
                Mensagem.aviso("Para cadastrar um novo funcionário, a senha é obrigatória!");
                return;
            }

            const cargoUsuarioLogado: string = (window as any).CARGO_USUARIO_SESSAO || "Administrador"; 
            if (cargoUsuarioLogado === "Gestor" && (cargo === "Administrador" || cargo === "Gestor")) {
                Mensagem.aviso("Operação bloqueada: Você não tem privilégios para criar cargos de nível Gestor ou Administrador.");
                return;
            }

            // 3. BLINDAGEM DE INTERFACE
            this.isProcessando = true;
            const textoOriginal = this.btnSalvar.innerText;
            this.btnSalvar.disabled = true;
            this.btnSalvar.innerText = "Processando...";
            this.btnSalvar.classList.add('opacity-50', 'cursor-not-allowed');

            // Garantimos o envio das duas chaves (id e id_funcionario) para evitar rejeições do Back-end
            const dados = {
                id: this.idAtual,
                id_funcionario: this.idAtual,
                nome: nome,
                cargo: cargo,
                login: parseInt(login, 10), 
                email: email,
                senha: senha || "" // Envia string vazia ao invés de null para evitar erro de tipo no Django
            };

            try {
                const resposta = await fetch('/api/funcionario/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });

                // Se a resposta for um Erro 500 do Django (HTML), interceptamos para não quebrar o JS
                const contentType = resposta.headers.get("content-type");
                if (contentType && contentType.indexOf("application/json") !== -1) {
                    const resultado = await resposta.json();
                    if (resultado.status === 'sucesso') {
                        Mensagem.sucesso(resultado.mensagem || "Salvo com sucesso!");
                        this.limparFormulario();
                        this.carregarFuncionarios();
                        this.carregarSolicitacoes();   // redefinir a senha encerra o pedido pendente
                    } else {
                        Mensagem.erro(resultado.mensagem, "Não foi possível salvar");
                    }
                } else {
                    throw new Error("O servidor não retornou JSON. O Login pode já estar em uso ou houve erro interno.");
                }

            } catch (error: any) {
                console.error("Falha na requisição:", error);
                Mensagem.erro(error.message, "Erro crítico ao salvar");
            } finally {
                // Restaura o botão independentemente de sucesso ou erro
                this.isProcessando = false;
                this.btnSalvar.disabled = false;
                this.btnSalvar.innerText = textoOriginal;
                this.btnSalvar.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        }

        // ==========================================
        // LÓGICA DE LISTAGEM (GET) E FILTROS VISUAIS
        // ==========================================
        private async carregarFuncionarios(): Promise<void> {
            this.listaFuncionarios.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10 animate-pulse">Carregando dados do servidor...</p>';

            try {
                const resposta = await fetch('/api/funcionario/');
                
                if (!resposta.ok) throw new Error("Falha no servidor.");
                
                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    this.listaFuncionarios.innerHTML = ''; 
                    
                    if (!resultado.dados || resultado.dados.length === 0) {
                        this.listaFuncionarios.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Nenhum funcionário cadastrado.</p>';
                        return;
                    }

                    resultado.dados.forEach((func: any) => {
                        let corCargo = "text-slate-400";
                        if (func.cargo === "Administrador") corCargo = "text-fuchsia-500";
                        if (func.cargo === "Gestor") corCargo = "text-amber-500";
                        if (func.cargo === "Analista de Triagem") corCargo = "text-emerald-400";
                        if (func.cargo === "Funcionário") corCargo = "text-cyan-400";

                        const card = document.createElement('div');
                        // Classes e datasets para os filtros visuais funcionarem
                        card.className = "card-funcionario bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group";
                        card.dataset.nome = func.nome ? func.nome.toLowerCase() : '';
                        card.dataset.login = func.login ? func.login.toString().toLowerCase() : '';
                        card.dataset.cargo = func.cargo || '';
                        
                        // Mapeia tanto id quanto id_funcionario para evitar problemas na API
                        const funcId = func.id || func.id_funcionario;

                        card.innerHTML = `
                            <div class="flex justify-between items-start mb-2">
                                <span class="text-xs font-bold ${corCargo} uppercase tracking-wider">${func.cargo}</span>
                                <span class="text-[10px] text-slate-500 font-mono">ID: ${funcId}</span>
                            </div>
                            <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${escapeHtml(func.nome)}</h3>
                            <p class="text-xs text-slate-400 mt-1 font-mono">Login: ${func.login}</p>
                            <p class="text-xs text-slate-500 mt-1">${escapeHtml(func.email || 'Sem e-mail cadastrado')}</p>
                            <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-end">
                                <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                            </div>
                        `;

                        card.addEventListener('dblclick', () => {
                            this.prepararEdicao(funcId, func.nome, func.cargo, func.login, func.email || '');
                        });

                        this.listaFuncionarios.appendChild(card);
                    });
                } else {
                    this.listaFuncionarios.innerHTML = `<p class="text-sm font-bold text-rose-500 col-span-full text-center py-10">Erro do Servidor: ${escapeHtml(resultado.mensagem)}</p>`;
                }
            } catch (error) {
                this.listaFuncionarios.innerHTML = '<p class="text-sm font-bold text-rose-500 col-span-full text-center py-10">Erro crítico ao tentar conectar com o servidor.</p>';
            }
        }

        // ==========================================
        // SOLICITAÇÕES DE REDEFINIÇÃO DE SENHA
        // ==========================================
        private async carregarSolicitacoes(): Promise<void> {
            const painel = document.getElementById('painel-solicitacoes') as HTMLElement | null;
            const lista = document.getElementById('lista-solicitacoes') as HTMLElement | null;
            if (!painel || !lista) return;

            try {
                const resposta = await fetch('/api/solicitacoes-senha/');
                const resultado = await resposta.json();
                lista.innerHTML = '';

                // Sem permissão (Funcionário/Analista) ou sem pedidos: o painel fica escondido.
                if (resultado.status !== 'sucesso' || resultado.dados.length === 0) {
                    painel.classList.add('hidden');
                    return;
                }
                painel.classList.remove('hidden');

                resultado.dados.forEach((pedido: any) => {
                    const item = document.createElement('div');
                    item.className = 'flex items-center justify-between gap-4 bg-[#0f172a] border border-[#334155] rounded-lg px-4 py-3';
                    item.innerHTML = `
                        <span class="text-xs text-slate-300"><span class="font-bold text-white">${escapeHtml(pedido.nome)}</span> (matrícula ${escapeHtml(pedido.login)}) pediu redefinição em ${escapeHtml(pedido.data)}</span>
                        <button type="button" class="px-3 py-1.5 rounded-md text-[10px] font-bold uppercase text-white bg-amber-600 hover:bg-amber-500 shrink-0">Redefinir senha</button>
                    `;
                    item.querySelector('button')!.addEventListener('click', () => {
                        this.prepararEdicao(pedido.id_funcionario, pedido.nome, pedido.cargo, pedido.login, pedido.email || '');
                        (document.getElementById('senha') as HTMLInputElement).focus();
                    });
                    lista.appendChild(item);
                });
            } catch (error) {
                console.error('Falha ao carregar solicitações:', error);
            }
        }

        private filtrarListaVisuais(): void {
            const buscaInput = document.getElementById('pesquisa-funcionario') as HTMLInputElement;
            const filtroSelect = document.getElementById('filtro-cargo') as HTMLSelectElement;
            
            const busca = buscaInput ? buscaInput.value.toLowerCase() : '';
            const filtroCargo = filtroSelect ? filtroSelect.value : 'todos';
            
            const cards = this.listaFuncionarios.querySelectorAll('.card-funcionario');
            
            cards.forEach(c => {
                const card = c as HTMLElement;
                const nome = card.dataset.nome || '';
                const login = card.dataset.login || '';
                const cargo = card.dataset.cargo || '';
                
                const atendeBusca = nome.includes(busca) || login.includes(busca);
                const atendeFiltro = filtroCargo === 'todos' || cargo === filtroCargo;
                
                if (atendeBusca && atendeFiltro) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }

        private prepararEdicao(id: number, nome: string, cargo: string, login: number, email: string): void {
            const cargoUsuarioLogado: string = (window as any).CARGO_USUARIO_SESSAO || "Administrador"; 
            if (cargoUsuarioLogado === "Funcionário" || cargoUsuarioLogado === "Analista de Triagem") {
                Mensagem.aviso("Você não tem permissão para alterar dados de funcionários.");
                return;
            }

            this.idAtual = id;
            (document.getElementById('nome') as HTMLInputElement).value = nome;
            (document.getElementById('cargo') as HTMLSelectElement).value = cargo;
            (document.getElementById('login') as HTMLInputElement).value = login.toString();
            (document.getElementById('senha') as HTMLInputElement).value = ""; 
            (document.getElementById('email') as HTMLInputElement).value = email;

            this.btnSalvar.innerText = "Atualizar Registro";
            this.btnSalvar.classList.replace('bg-cyan-600', 'bg-amber-600');
            this.btnSalvar.classList.replace('hover:bg-cyan-500', 'hover:bg-amber-500');
            this.btnSalvar.classList.replace('shadow-[0_0_15px_rgba(6,182,212,0.3)]', 'shadow-[0_0_15px_rgba(245,158,11,0.3)]');
            
            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.add('has-value'));
            this.form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        private limparFormulario(): void {
            this.form.reset();
            this.idAtual = null;

            this.btnSalvar.innerText = "Salvar Funcionário";
            this.btnSalvar.classList.replace('bg-amber-600', 'bg-cyan-600');
            this.btnSalvar.classList.replace('hover:bg-amber-500', 'hover:bg-cyan-500');
            this.btnSalvar.classList.replace('shadow-[0_0_15px_rgba(245,158,11,0.3)]', 'shadow-[0_0_15px_rgba(6,182,212,0.3)]');

            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.remove('has-value'));
        }
    }

    window.addEventListener('DOMContentLoaded', () => {
        new G_funcionarioUI();
    });

})();