/// <reference path="../baseUI.ts" />

(() => {
    class G_funcionarioUI extends BaseUI {
        private btnSalvar: HTMLButtonElement;
        private btnLimpar: HTMLButtonElement;
        private form: HTMLFormElement;
        private listaFuncionarios: HTMLElement;
        
        // Memória da tela: null = Inserção | number = Alteração
        private idAtual: number | null = null;
        
        constructor() {
            super(); // Traz a lógica de menus do BaseUI
            
            // Mapeamento dos elementos
            this.btnSalvar = document.getElementById('btn-salvar-funcionario') as HTMLButtonElement;
            this.btnLimpar = document.getElementById('btn-limpar') as HTMLButtonElement;
            this.form = document.getElementById('form-cadastro-funcionario') as HTMLFormElement;
            this.listaFuncionarios = document.getElementById('lista-funcionarios') as HTMLElement;

            this.iniciarEventos();
            this.carregarFuncionarios();
            this.carregarSolicitacoes();
            this.verificarPermissoes(); // Applica as regras de bloqueio de tela
        }

        private iniciarEventos(): void {
            this.btnSalvar.addEventListener('click', () => this.salvarFuncionario());
            this.btnLimpar.addEventListener('click', () => this.limparFormulario());
        }

        // ==========================================
        // REGRA DE NEGÓCIO: CONTROLE DE ACESSO
        // ==========================================
        private verificarPermissoes(): void {
            // TODO: Substituir pela leitura real do usuário logado futuramente
            const cargoUsuarioLogado: string = document.body.dataset.cargo || "";

            if (cargoUsuarioLogado === "Funcionário" || cargoUsuarioLogado === "Analista de Triagem") {
                // Bloqueia o formulário inteiro para leitura
                const inputs = this.form.querySelectorAll('input, select');
                inputs.forEach(input => (input as HTMLInputElement).disabled = true);
                
                this.btnSalvar.style.display = 'none';
                this.btnLimpar.style.display = 'none';
            } 
            else if (cargoUsuarioLogado === "Gestor") {
                // Remove as opções Administrador e Gestor do campo Select para que ele não consiga criar novos
                const selectCargo = document.getElementById('cargo') as HTMLSelectElement;
                Array.from(selectCargo.options).forEach(option => {
                    if (option.value === "Administrador" || option.value === "Gestor") {
                        option.disabled = true; // Desabilita a opção na lista
                        option.style.display = 'none'; // Esconde visualmente
                    }
                });
            }
        }

        // ==========================================
        // LÓGICA DE SALVAR / ALTERAR (POST)
        // ==========================================
        private async salvarFuncionario(): Promise<void> {
            const nome = (document.getElementById('nome') as HTMLInputElement).value;
            const cargo = (document.getElementById('cargo') as HTMLSelectElement).value;
            const login = (document.getElementById('login') as HTMLInputElement).value; // Pegamos como texto primeiro
            const senha = (document.getElementById('senha') as HTMLInputElement).value;
            const email = (document.getElementById('email') as HTMLInputElement).value.trim();

            // 1. Validação de campos vazios
            if (!nome || !cargo || !login || !email) {
                alert("Preencha todos os campos obrigatórios (Nome, Cargo, Login e E-mail)!");
                return;
            }

            // 2. NOVA VALIDAÇÃO: Verifica se o login possui APENAS números
            const apenasNumeros = /^\d+$/;
            if (!apenasNumeros.test(login)) {
                alert("Formato Inválido: O campo 'Login de Acesso' deve conter apenas números (ex: matrícula).");
                // Limpa o campo errado para o usuário tentar de novo
                (document.getElementById('login') as HTMLInputElement).value = ""; 
                return;
            }

            // 3. Validação de senha para novos cadastros
            if (this.idAtual === null && !senha) {
                alert("Para cadastrar um novo funcionário, a senha é obrigatória!");
                return;
            }

            // O resto do código continua igual...
            const cargoUsuarioLogado: string = document.body.dataset.cargo || "";
            if (cargoUsuarioLogado === "Gestor" && (cargo === "Administrador" || cargo === "Gestor")) {
                alert("Operação bloqueada: Você não tem privilégios para criar cargos de nível Gestor ou Administrador.");
                return;
            }

            const dados = {
                id: this.idAtual,
                nome: nome,
                cargo: cargo,
                login: parseInt(login), // Agora é 100% seguro converter!
                email: email,
                senha: senha ? senha : null 
            };
            try {
                const resposta = await fetch('/api/funcionario/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });

                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    alert(resultado.mensagem);
                    this.limparFormulario();
                    this.carregarFuncionarios();
                    this.carregarSolicitacoes();
                } else {
                    alert("Erro: " + resultado.mensagem);
                }
            } catch (error) {
                console.error("Falha na requisição:", error);
                alert("Erro ao comunicar com o servidor.");
            }
        }

        // ==========================================
        // LÓGICA DE LISTAGEM (GET)
        // ==========================================
        private async carregarFuncionarios(): Promise<void> {
            this.listaFuncionarios.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Carregando dados do servidor...</p>';

            try {
                const resposta = await fetch('/api/funcionario/');
                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    this.listaFuncionarios.innerHTML = ''; 
                    
                    if (resultado.dados.length === 0) {
                        this.listaFuncionarios.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Nenhum funcionário cadastrado.</p>';
                        return;
                    }

                    resultado.dados.forEach((func: any) => {
                        // Cores dinâmicas por cargo
                        let corCargo = "text-slate-400";
                        if (func.cargo === "Administrador") corCargo = "text-fuchsia-500";
                        if (func.cargo === "Gestor") corCargo = "text-amber-500";
                        if (func.cargo === "Analista de Triagem") corCargo = "text-emerald-400";
                        if (func.cargo === "Funcionário") corCargo = "text-cyan-400";

                        const card = document.createElement('div');
                        card.className = "bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group";
                        
                        card.innerHTML = `
                            <div class="flex justify-between items-start mb-2">
                                <span class="text-xs font-bold ${corCargo} uppercase tracking-wider">${func.cargo}</span>
                                <span class="text-[10px] text-slate-500 font-mono">ID: ${func.id}</span>
                            </div>
                            <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${this.escapar(func.nome)}</h3>
                            <p class="text-xs text-slate-400 mt-1 font-mono">Login: ${func.login}</p>
                            <p class="text-xs text-slate-500 mt-1 truncate">${this.escapar(func.email || 'sem e-mail cadastrado')}</p>
                            <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-end">
                                <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                            </div>
                        `;

                        card.addEventListener('dblclick', () => {
                            this.prepararEdicao(func.id, func.nome, func.cargo, func.login, func.email || '');
                        });

                        this.listaFuncionarios.appendChild(card);
                    });
                } else {
                    this.listaFuncionarios.innerHTML = `<p class="text-sm font-bold text-red-500 col-span-full text-center py-10">Erro do Servidor: ${resultado.mensagem}</p>`;
                }
            } catch (error) {
                this.listaFuncionarios.innerHTML = '<p class="text-sm font-bold text-red-500 col-span-full text-center py-10">Erro crítico ao tentar conectar com o servidor.</p>';
            }
        }

        private escapar(valor: any): string {
            const mapa: { [c: string]: string } = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
            return String(valor ?? '').replace(/[&<>"']/g, (c) => mapa[c]);
        }

        // ==========================================
        // SOLICITAÇÕES DE REDEFINIÇÃO DE SENHA (UC09)
        // ==========================================
        private async carregarSolicitacoes(): Promise<void> {
            const painel = document.getElementById('painel-solicitacoes') as HTMLElement | null;
            const lista = document.getElementById('lista-solicitacoes') as HTMLElement | null;
            if (!painel || !lista) return;

            try {
                const resposta = await fetch('/api/solicitacoes-senha/');
                const resultado = await resposta.json();
                lista.innerHTML = '';

                if (resultado.status !== 'sucesso' || resultado.dados.length === 0) {
                    painel.classList.add('hidden');
                    return;
                }
                painel.classList.remove('hidden');

                resultado.dados.forEach((pedido: any) => {
                    const item = document.createElement('div');
                    item.className = 'flex items-center justify-between gap-4 bg-[#0f172a] border border-[#334155] rounded-lg px-4 py-3';
                    item.innerHTML = `
                        <span class="text-xs text-slate-300"><span class="font-bold text-white">${this.escapar(pedido.nome)}</span> (matrícula ${this.escapar(pedido.login)}) pediu redefinição em ${this.escapar(pedido.data)}</span>
                        <button type="button" class="px-3 py-1.5 rounded-md text-[10px] font-bold uppercase text-white bg-amber-600 hover:bg-amber-500">Redefinir senha</button>
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

        private prepararEdicao(id: number, nome: string, cargo: string, login: number, email: string): void {
            const cargoUsuarioLogado: string = document.body.dataset.cargo || "";
            if (cargoUsuarioLogado === "Funcionário" || cargoUsuarioLogado === "Analista de Triagem") {
                alert("Você não tem permissão para alterar dados de funcionários.");
                return;
            }

            this.idAtual = id;
            (document.getElementById('nome') as HTMLInputElement).value = nome;
            (document.getElementById('cargo') as HTMLSelectElement).value = cargo;
            (document.getElementById('login') as HTMLInputElement).value = login.toString();
            (document.getElementById('email') as HTMLInputElement).value = email;
            (document.getElementById('senha') as HTMLInputElement).value = ""; // Senha sempre vem limpa por segurança

            this.btnSalvar.innerText = "Alterar Registro";
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