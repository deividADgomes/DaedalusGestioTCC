/// <reference path="../baseUI.ts" />

(() => {
    class G_tecnicoUI extends BaseUI {
        private btnSalvar: HTMLButtonElement;
        private btnLimpar: HTMLButtonElement;
        private form: HTMLFormElement;
        private listaTecnicos: HTMLElement;
        private inputPesquisa: HTMLInputElement;
        
        private idAtual: number | null = null;
        private todosTecnicosCache: any[] = []; 
        private empresasCache: any[] = [];
        
        constructor() {
            super();
            this.btnSalvar = document.getElementById('btn-salvar-tecnico') as HTMLButtonElement;
            this.btnLimpar = document.getElementById('btn-limpar') as HTMLButtonElement;
            this.form = document.getElementById('form-cadastro-tecnico') as HTMLFormElement;
            this.listaTecnicos = document.getElementById('lista-tecnicos') as HTMLElement;
            this.inputPesquisa = document.getElementById('pesquisa-tecnico') as HTMLInputElement;

            this.iniciarEventos();
            this.verificarPermissoes();
            
            this.carregarEmpresasDropdown().then(() => {
                this.carregarTecnicos();
            });
        }

        private iniciarEventos(): void {
            this.btnSalvar.addEventListener('click', () => this.salvarTecnico());
            this.btnLimpar.addEventListener('click', () => this.limparFormulario());
            
            if (this.inputPesquisa) {
                this.inputPesquisa.addEventListener('input', () => this.filtrarTecnicos());
            }
        }

        private verificarPermissoes(): void {
            const cargoUsuarioLogado: string = "Administrador"; // TODO: Mudar para leitura real do login

            if (cargoUsuarioLogado === "Funcionário") {
                const inputs = this.form.querySelectorAll('input, select');
                inputs.forEach(input => (input as HTMLInputElement).disabled = true);
                
                this.btnSalvar.style.display = 'none';
                this.btnLimpar.style.display = 'none';
            }
        }

        // ==========================================
        // UTILITÁRIOS E FORMATAÇÃO
        // ==========================================
        private formatarCNPJ(valor: string): string {
            if (!valor || valor === 'Não informado' || valor === 'Não localizado' || valor === 'Sem CNPJ') return valor;
            
            let v = String(valor).replace(/\D/g, ''); // Garante que é string e remove letras
            if (v.length > 14) v = v.substring(0, 14);

            v = v.replace(/^(\d{2})(\d)/, '$1.$2');
            v = v.replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3');
            v = v.replace(/\.(\d{3})(\d)/, '.$1/$2');
            v = v.replace(/(\d{4})(\d)/, '$1-$2');
            
            return v;
        }

        // ==========================================
        // COMUNICAÇÃO: CARREGAR EMPRESAS (SELECT)
        // ==========================================
        private async carregarEmpresasDropdown(): Promise<void> {
            const selectEmpresa = document.getElementById('empresa') as HTMLSelectElement;
            
            try {
                const resposta = await fetch('/api/empresa/');
                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    this.empresasCache = resultado.dados;
                    selectEmpresa.innerHTML = '<option value="" disabled selected>Selecione a empresa...</option>';
                    
                    resultado.dados.forEach((emp: any) => {
                        const option = document.createElement('option');
                        option.value = emp.id || emp.id_empresa;
                        
                        // Formata o CNPJ antes de adicionar ao select
                        const cnpj = emp.cnpj ? this.formatarCNPJ(emp.cnpj) : "Sem CNPJ";
                        option.text = emp.razao_social + ' - CNPJ: ' + cnpj ;
                        
                        selectEmpresa.appendChild(option);
                    });
                }
            } catch (error) {
                console.error("Erro crítico ao carregar empresas para o select", error);
            }
        }

        // ==========================================
        // COMUNICAÇÃO: SALVAR / ALTERAR (POST)
        // ==========================================
        private async salvarTecnico(): Promise<void> {
            const nome = (document.getElementById('nome') as HTMLInputElement).value;
            const idEmpresa = (document.getElementById('empresa') as HTMLSelectElement).value;

            if (!nome || !idEmpresa) {
                alert("Os campos Nome e Empresa Vinculada são obrigatórios!");
                return;
            }

            const dados = {
                id: this.idAtual,
                nome: nome,
                id_empresa: parseInt(idEmpresa)
            };

            try {
                const resposta = await fetch('/api/tecnico/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });

                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    alert(resultado.mensagem);
                    this.limparFormulario();
                    this.carregarTecnicos(); 
                } else {
                    alert("Erro: " + resultado.mensagem);
                }
            } catch (error) {
                console.error("Falha na requisição:", error);
                alert("Erro ao comunicar com o servidor.");
            }
        }

        // ==========================================
        // COMUNICAÇÃO: LISTAR TÉCNICOS (GET)
        // ==========================================
        private async carregarTecnicos(): Promise<void> {
            this.listaTecnicos.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Carregando dados do servidor...</p>';

            try {
                const resposta = await fetch('/api/tecnico/');
                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    this.todosTecnicosCache = resultado.dados; 
                    this.renderizarCards(this.todosTecnicosCache);
                } else {
                    this.listaTecnicos.innerHTML = `<p class="text-sm font-bold text-red-500 col-span-full text-center py-10">Erro do Servidor: ${resultado.mensagem}</p>`;
                }
            } catch (error) {
                this.listaTecnicos.innerHTML = '<p class="text-sm font-bold text-red-500 col-span-full text-center py-10">Erro crítico ao tentar conectar com o servidor.</p>';
            }
        }

        // ==========================================
        // MANIPULAÇÃO DE INTERFACE E FILTROS
        // ==========================================
        private renderizarCards(lista: any[]): void {
            this.listaTecnicos.innerHTML = ''; 
            
            if (lista.length === 0) {
                this.listaTecnicos.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Nenhum técnico encontrado.</p>';
                return;
            }

            lista.forEach((tec: any) => {
                
                // Busca blindada: Tenta achar pelo ID. Se não tiver ID, acha pelo Nome!
                const empresaVinculada = this.empresasCache.find(e => 
                    (tec.id_empresa && e.id == tec.id_empresa) || 
                    (e.razao_social === tec.nome_empresa)
                );
                
                // Formata o CNPJ antes de jogar no cartão
                const cnpjEmpresa = empresaVinculada ? this.formatarCNPJ(empresaVinculada.cnpj) : 'Não localizado';

                const card = document.createElement('div');
                card.className = "bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group";
                
                card.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <span class="text-xs font-bold text-emerald-400 uppercase tracking-wider">Técnico de Campo</span>
                        <span class="text-[10px] text-slate-500 font-mono">ID: ${tec.id}</span>
                    </div>
                    <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${tec.nome}</h3>
                    <p class="text-xs text-slate-400 mt-1">Empresa: <span class="text-slate-300 font-medium">${tec.nome_empresa || 'Não informada'}</span></p>
                    
                    <p class="text-xs text-slate-400 mt-1">CNPJ: <span class="text-slate-300 font-medium">${cnpjEmpresa}</span></p>
                    
                    <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-end">
                        <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                    </div>
                `;

                card.addEventListener('dblclick', () => {
                    const idDaEmpresaParaEditar = tec.id_empresa || (empresaVinculada ? empresaVinculada.id : null);
                    this.prepararEdicao(tec.id, tec.nome, idDaEmpresaParaEditar);
                });

                this.listaTecnicos.appendChild(card);
            });
        }

        private filtrarTecnicos(): void {
            const termoPesquisa = this.inputPesquisa.value.toLowerCase();
            
            const listaFiltrada = this.todosTecnicosCache.filter(tec => 
                tec.nome.toLowerCase().includes(termoPesquisa) || 
                (tec.nome_empresa && tec.nome_empresa.toLowerCase().includes(termoPesquisa))
            );

            this.renderizarCards(listaFiltrada);
        }

        private prepararEdicao(id: number, nome: string, id_empresa: number): void {
            const cargoUsuarioLogado: string = "Administrador"; // TODO: Mudar para leitura real
            
            if (cargoUsuarioLogado === "Funcionário") {
                alert("Você não tem permissão para alterar dados de técnicos.");
                return;
            }

            this.idAtual = id;
            (document.getElementById('nome') as HTMLInputElement).value = nome;
            
            if (id_empresa) {
                (document.getElementById('empresa') as HTMLSelectElement).value = id_empresa.toString();
            }

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

            this.btnSalvar.innerText = "Salvar Técnico";
            this.btnSalvar.classList.replace('bg-amber-600', 'bg-cyan-600');
            this.btnSalvar.classList.replace('hover:bg-amber-500', 'hover:bg-cyan-500');
            this.btnSalvar.classList.replace('shadow-[0_0_15px_rgba(245,158,11,0.3)]', 'shadow-[0_0_15px_rgba(6,182,212,0.3)]');

            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.remove('has-value'));
        }
    }

    window.addEventListener('DOMContentLoaded', () => {
        new G_tecnicoUI();
    });

})();