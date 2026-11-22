/// <reference path="../baseUI.ts" />

(() => {
    const TIPO_PRESTADORA = 1;
    const COR_BORDA_ERRO = 'border-rose-500';

    interface EmpresaApi {
        id: number;
        razao_social: string;
        cnpj: string;
        tipo: number;
    }

    class EmpresaUI extends BaseUI {
        private botaoSalvar = obterElemento<HTMLButtonElement>('btn-salvar-empresa');
        private botaoLimpar = obterElemento<HTMLButtonElement>('btn-limpar');
        private formulario = obterElemento<HTMLFormElement>('form-cadastro-empresa');
        private listaEmpresas = obterElemento('lista-empresas');
        private campoPesquisa = obterElemento<HTMLInputElement>('pesquisa-empresa');
        private filtroTipo = obterElemento<HTMLSelectElement>('filtro-tipo');
        private campoCnpj = obterElemento<HTMLInputElement>('cnpj');

        private idAtual: number | null = null;
        private empresas: EmpresaApi[] = [];

        constructor() {
            super();
            this.iniciarEventos();
            this.carregarEmpresas();
        }

        private iniciarEventos(): void {
            this.botaoSalvar.addEventListener('click', () => this.salvarEmpresa());
            this.botaoLimpar.addEventListener('click', () => this.limparFormulario());
            this.campoCnpj.addEventListener('input', () => {
                this.campoCnpj.value = formatarCnpj(this.campoCnpj.value);
            });
            this.campoPesquisa.addEventListener('input', () => this.filtrarEmpresas());
            this.filtroTipo.addEventListener('change', () => this.filtrarEmpresas());
        }

        private calcularDigitoVerificador(base: string): number {
            let peso = base.length - 7;
            let soma = 0;
            for (const digito of base) {
                soma += parseInt(digito) * peso--;
                if (peso < 2) peso = 9;
            }
            const resto = soma % 11;
            return resto < 2 ? 0 : 11 - resto;
        }

        private validarCnpj(valor: string): boolean {
            const cnpj = valor.replace(/\D/g, '');
            if (cnpj.length !== 14 || /^(\d)\1+$/.test(cnpj)) return false;

            const primeiroDigito = this.calcularDigitoVerificador(cnpj.substring(0, 12));
            const segundoDigito = this.calcularDigitoVerificador(cnpj.substring(0, 13));
            return primeiroDigito === parseInt(cnpj[12]) && segundoDigito === parseInt(cnpj[13]);
        }

        private async salvarEmpresa(): Promise<void> {
            const cnpjFormatado = this.campoCnpj.value;
            const razaoSocial = valorDoCampo('razaoSocial');
            const tipo = valorDoCampo('tipo');

            if (!cnpjFormatado || !razaoSocial || !tipo) {
                alert('Preencha todos os campos obrigatórios!');
                return;
            }

            if (!this.validarCnpj(cnpjFormatado)) {
                alert('O CNPJ informado é inválido. Verifique os números e tente novamente.');
                this.campoCnpj.focus();
                this.campoCnpj.classList.add(COR_BORDA_ERRO);
                return;
            }
            this.campoCnpj.classList.remove(COR_BORDA_ERRO);

            try {
                const resultado = await enviarJson('/api/empresa/', {
                    id: this.idAtual,
                    cnpj: cnpjFormatado.replace(/\D/g, ''),
                    razaoSocial,
                    tipo,
                });
                if (resultado.status !== 'sucesso') {
                    alert('Erro: ' + resultado.mensagem);
                    return;
                }
                alert(resultado.mensagem);
                this.limparFormulario();
                this.carregarEmpresas();
            } catch (erro) {
                console.error('Falha na requisição:', erro);
                alert('Erro ao comunicar com o servidor.');
            }
        }

        private async carregarEmpresas(): Promise<void> {
            this.listaEmpresas.innerHTML = htmlMensagemNeutra('Carregando empresas cadastradas...');

            try {
                const resultado = await buscarJson('/api/empresa/');
                if (resultado.status !== 'sucesso') {
                    this.listaEmpresas.innerHTML = htmlMensagemErro(`Erro do Servidor: ${resultado.mensagem}`);
                    return;
                }
                this.empresas = resultado.dados;
                this.renderizarCards(this.empresas);
            } catch (erro) {
                this.listaEmpresas.innerHTML = htmlMensagemErro('Erro crítico ao tentar conectar com o servidor.');
            }
        }

        private renderizarCards(empresas: EmpresaApi[]): void {
            this.listaEmpresas.innerHTML = '';

            if (empresas.length === 0) {
                this.listaEmpresas.innerHTML = htmlMensagemNeutra('Nenhuma empresa encontrada.');
                return;
            }

            empresas.forEach((empresa) => {
                const prestadora = Number(empresa.tipo) === TIPO_PRESTADORA;
                const nomeDoTipo = prestadora ? 'Prestadora' : 'Cliente';
                const corDoTipo = prestadora ? 'text-amber-400' : 'text-emerald-400';

                const card = document.createElement('div');
                card.className = 'bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group';
                card.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <span class="text-xs font-bold ${corDoTipo} uppercase tracking-wider">${nomeDoTipo}</span>
                        <span class="text-[10px] text-slate-500 font-mono">ID: ${empresa.id}</span>
                    </div>
                    <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${escapeHtml(empresa.razao_social)}</h3>
                    <p class="text-xs text-slate-400 mt-1 font-mono">${formatarCnpj(empresa.cnpj)}</p>
                    <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-end">
                        <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                    </div>
                `;
                card.addEventListener('dblclick', () => this.prepararEdicao(empresa));
                this.listaEmpresas.appendChild(card);
            });
        }

        private filtrarEmpresas(): void {
            const termoTexto = this.campoPesquisa.value.toLowerCase();
            const termoCnpj = termoTexto.replace(/\D/g, '');
            const tipoSelecionado = this.filtroTipo.value;

            const filtradas = this.empresas.filter((empresa) => {
                if (tipoSelecionado !== 'todos' && String(empresa.tipo) !== tipoSelecionado) return false;
                const bateRazao = empresa.razao_social && empresa.razao_social.toLowerCase().includes(termoTexto);
                const bateCnpj = termoCnpj !== '' && empresa.cnpj && empresa.cnpj.includes(termoCnpj);
                return bateRazao || bateCnpj;
            });

            this.renderizarCards(filtradas);
        }

        private prepararEdicao(empresa: EmpresaApi): void {
            this.idAtual = empresa.id;
            this.campoCnpj.value = formatarCnpj(empresa.cnpj);
            definirValorDoCampo('razaoSocial', empresa.razao_social);
            definirValorDoCampo('tipo', empresa.tipo.toString());

            aplicarModoEdicao(this.botaoSalvar, 'Alterar Registro');
            marcarRotulosFlutuantes(true);
            this.formulario.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        private limparFormulario(): void {
            this.formulario.reset();
            this.idAtual = null;
            this.campoCnpj.classList.remove(COR_BORDA_ERRO);

            aplicarModoInsercao(this.botaoSalvar, 'Salvar Empresa');
            marcarRotulosFlutuantes(false);
        }
    }

    window.addEventListener('DOMContentLoaded', () => new EmpresaUI());
})();
