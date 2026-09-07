/// <reference path="../baseUI.ts" />

(() => {
    class G_empresaUI extends BaseUI {
        private btnSalvar: HTMLButtonElement;
        private btnLimpar: HTMLButtonElement;
        private form: HTMLFormElement;
        private listaEmpresas: HTMLElement;
        private inputPesquisa: HTMLInputElement;
        private selectFiltro: HTMLSelectElement;

        private idAtual: number | null = null;
        private todasEmpresasCache: any[] = []; // Guardamos em memória para a pesquisa ser instantânea

        constructor() {
            super();

            this.btnSalvar = document.getElementById('btn-salvar-empresa') as HTMLButtonElement;
            this.btnLimpar = document.getElementById('btn-limpar') as HTMLButtonElement;
            this.form = document.getElementById('form-cadastro-empresa') as HTMLFormElement;
            this.listaEmpresas = document.getElementById('lista-empresas') as HTMLElement;
            this.inputPesquisa = document.getElementById('pesquisa-empresa') as HTMLInputElement;
            this.selectFiltro = document.getElementById('filtro-tipo') as HTMLSelectElement;

            this.iniciarEventos();
            this.carregarEmpresas();
        }

        private iniciarEventos(): void {
            this.btnSalvar.addEventListener('click', () => this.salvarEmpresa());
            this.btnLimpar.addEventListener('click', () => this.limparFormulario());
            
            // Evento para aplicar a máscara enquanto digita
            const inputCnpj = document.getElementById('cnpj') as HTMLInputElement;
            if (inputCnpj) {
                inputCnpj.addEventListener('input', (e) => this.aplicarMascaraCNPJ(e));
            }

            // Eventos para a barra de pesquisa e filtro
            if (this.inputPesquisa) {
                this.inputPesquisa.addEventListener('input', () => this.filtrarEmpresas());
            }
            if (this.selectFiltro) {
                this.selectFiltro.addEventListener('change', () => this.filtrarEmpresas());
            }
        }

        // ==========================================
        // REGRAS DE NEGÓCIO: VALIDAÇÃO E MÁSCARA CNPJ
        // ==========================================
        
        // Formata qualquer texto para o padrão 00.000.000/0000-00
        private formatarCNPJ(valor: string): string {
            if (!valor) return '';
            let v = valor.replace(/\D/g, ''); // Remove letras e caracteres
            if (v.length > 14) v = v.substring(0, 14); // Limita a 14 números

            v = v.replace(/^(\d{2})(\d)/, '$1.$2');
            v = v.replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3');
            v = v.replace(/\.(\d{3})(\d)/, '.$1/$2');
            v = v.replace(/(\d{4})(\d)/, '$1-$2');
            
            return v;
        }

        private aplicarMascaraCNPJ(evento: Event): void {
            const input = evento.target as HTMLInputElement;
            input.value = this.formatarCNPJ(input.value);
        }

        // Algoritmo Matemático Oficial do CNPJ (Módulo 11)
        private validarCNPJ(cnpj: string): boolean {
            cnpj = cnpj.replace(/[^\d]+/g, ''); 
            if (cnpj === '' || cnpj.length !== 14 || /^(\d)\1+$/.test(cnpj)) return false;

            let tamanho = cnpj.length - 2;
            let numeros = cnpj.substring(0, tamanho);
            let digitos = cnpj.substring(tamanho);
            let soma = 0;
            let pos = tamanho - 7;
            
            for (let i = tamanho; i >= 1; i--) {
                soma += parseInt(numeros.charAt(tamanho - i)) * pos--;
                if (pos < 2) pos = 9;
            }
            let resultado = soma % 11 < 2 ? 0 : 11 - soma % 11;
            if (resultado !== parseInt(digitos.charAt(0))) return false;

            tamanho = tamanho + 1;
            numeros = cnpj.substring(0, tamanho);
            soma = 0;
            pos = tamanho - 7;
            
            for (let i = tamanho; i >= 1; i--) {
                soma += parseInt(numeros.charAt(tamanho - i)) * pos--;
                if (pos < 2) pos = 9;
            }
            resultado = soma % 11 < 2 ? 0 : 11 - soma % 11;
            if (resultado !== parseInt(digitos.charAt(1))) return false;

            return true;
        }

        // ==========================================
        // COMUNICAÇÃO: SALVAR / ALTERAR (POST)
        // ==========================================
        private async salvarEmpresa(): Promise<void> {
            const inputCnpj = document.getElementById('cnpj') as HTMLInputElement;
            const cnpjFormatado = inputCnpj.value;
            const razaoSocial = (document.getElementById('razaoSocial') as HTMLInputElement).value;
            const tipo = (document.getElementById('tipo') as HTMLSelectElement).value;

            if (!cnpjFormatado || !razaoSocial || !tipo) {
                alert("Preencha todos os campos obrigatórios!");
                return;
            }

            if (!this.validarCNPJ(cnpjFormatado)) {
                alert("O CNPJ informado é inválido. Verifique os números e tente novamente.");
                inputCnpj.focus(); 
                inputCnpj.classList.add('border-rose-500'); 
                return; 
            } else {
                inputCnpj.classList.remove('border-rose-500'); 
            }

            const dados = {
                id: this.idAtual,
                cnpj: cnpjFormatado.replace(/\D/g, ''), // Envia apenas os números puros
                razaoSocial: razaoSocial, 
                tipo: tipo
            };

            try {
                const resposta = await fetch('/api/empresa/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });

                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    alert(resultado.mensagem);
                    this.limparFormulario();
                    this.carregarEmpresas();
                } else {
                    alert("Erro: " + resultado.mensagem);
                }
            } catch (error) {
                console.error("Falha na requisição:", error);
                alert("Erro ao comunicar com o servidor.");
            }
        }

        // ==========================================
        // COMUNICAÇÃO E RENDERIZAÇÃO: LISTAR (GET)
        // ==========================================
        private async carregarEmpresas(): Promise<void> {
            this.listaEmpresas.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Carregando empresas cadastradas...</p>';

            try {
                const resposta = await fetch('/api/empresa/');
                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    this.todasEmpresasCache = resultado.dados; // Salva para a pesquisa
                    this.renderizarCards(this.todasEmpresasCache);
                } else {
                    this.listaEmpresas.innerHTML = `<p class="text-sm font-bold text-rose-500 col-span-full text-center py-10">Erro do Servidor: ${resultado.mensagem}</p>`;
                }
            } catch (error) {
                this.listaEmpresas.innerHTML = '<p class="text-sm font-bold text-rose-500 col-span-full text-center py-10">Erro crítico ao tentar conectar com o servidor.</p>';
            }
        }

        private renderizarCards(lista: any[]): void {
            this.listaEmpresas.innerHTML = ''; 
            
            if (lista.length === 0) {
                this.listaEmpresas.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Nenhuma empresa encontrada.</p>';
                return;
            }

            lista.forEach((emp: any) => {
                const tipoNome = emp.tipo === 1 || emp.tipo == '1' ? "Prestadora" : "Cliente";
                const corTipo = emp.tipo === 1 || emp.tipo == '1' ? "text-amber-400" : "text-emerald-400";

                const card = document.createElement('div');
                card.className = "bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group";
                card.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <span class="text-xs font-bold ${corTipo} uppercase tracking-wider">${tipoNome}</span>
                        <span class="text-[10px] text-slate-500 font-mono">ID: ${emp.id}</span>
                    </div>
                    <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${emp.razao_social}</h3>
                    <p class="text-xs text-slate-400 mt-1 font-mono">${this.formatarCNPJ(emp.cnpj)}</p>
                    <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-end">
                        <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                    </div>
                `;

                card.addEventListener('dblclick', () => {
                    this.prepararEdicao(emp.id, emp.cnpj, emp.razao_social, emp.tipo);
                });

                this.listaEmpresas.appendChild(card);
            });
        }

        // Pesquisa e Filtros
        private filtrarEmpresas(): void {
            const termoPesquisa = this.inputPesquisa.value.toLowerCase().replace(/\D/g, ''); // Remove máscara para pesquisar CNPJ
            const termoTexto = this.inputPesquisa.value.toLowerCase();
            const filtroTipo = this.selectFiltro.value; // 'todos', '1', ou '2'

            const listaFiltrada = this.todasEmpresasCache.filter(emp => {
                // Filtra pelo tipo
                if (filtroTipo !== 'todos' && String(emp.tipo) !== filtroTipo) return false;

                // Filtra por Razão Social ou CNPJ puro
                const razaoMatch = emp.razao_social && emp.razao_social.toLowerCase().includes(termoTexto);
                const cnpjMatch = emp.cnpj && emp.cnpj.includes(termoPesquisa);

                return razaoMatch || cnpjMatch;
            });

            this.renderizarCards(listaFiltrada);
        }

        // ==========================================
        // MANIPULAÇÃO DA INTERFACE DÚPLICE
        // ==========================================
        private prepararEdicao(id: number, cnpj: string, razaoSocial: string, tipo: number): void {
            this.idAtual = id;
            
            // Joga o CNPJ na tela já com a máscara bonitinha
            (document.getElementById('cnpj') as HTMLInputElement).value = this.formatarCNPJ(cnpj); 
            (document.getElementById('razaoSocial') as HTMLInputElement).value = razaoSocial;
            (document.getElementById('tipo') as HTMLSelectElement).value = tipo.toString();

            // Sinais visuais de modo de Alteração
            this.btnSalvar.innerText = "Alterar Registro";
            this.btnSalvar.classList.replace('bg-cyan-600', 'bg-amber-600');
            this.btnSalvar.classList.replace('hover:bg-cyan-500', 'hover:bg-amber-500');
            this.btnSalvar.classList.replace('shadow-[0_0_15px_rgba(6,182,212,0.3)]', 'shadow-[0_0_15px_rgba(245,158,11,0.3)]');
            
            // Força as labels a flutuarem
            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.add('has-value'));

            this.form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        private limparFormulario(): void {
            this.form.reset();
            this.idAtual = null;

            const inputCnpj = document.getElementById('cnpj') as HTMLInputElement;
            if(inputCnpj) inputCnpj.classList.remove('border-rose-500');

            // Retorna ao visual padrão de Inserção
            this.btnSalvar.innerText = "Salvar Empresa";
            this.btnSalvar.classList.replace('bg-amber-600', 'bg-cyan-600');
            this.btnSalvar.classList.replace('hover:bg-amber-500', 'hover:bg-cyan-500');
            this.btnSalvar.classList.replace('shadow-[0_0_15px_rgba(245,158,11,0.3)]', 'shadow-[0_0_15px_rgba(6,182,212,0.3)]');

            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.remove('has-value'));
        }
    }

    // Inicialização segura
    window.addEventListener('DOMContentLoaded', () => {
        new G_empresaUI();
    });

})();