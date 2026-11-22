"use strict";
(() => {
    class TecnicoUI extends BaseUI {
        constructor() {
            super();
            this.botaoSalvar = obterElemento('btn-salvar-tecnico');
            this.botaoLimpar = obterElemento('btn-limpar');
            this.formulario = obterElemento('form-cadastro-tecnico');
            this.listaTecnicos = obterElemento('lista-tecnicos');
            this.campoPesquisa = obterElemento('pesquisa-tecnico');
            this.idAtual = null;
            this.tecnicos = [];
            this.empresas = [];
            this.iniciarEventos();
            this.carregarEmpresasNoSelect().then(() => this.carregarTecnicos());
        }
        iniciarEventos() {
            this.botaoSalvar.addEventListener('click', () => this.salvarTecnico());
            this.botaoLimpar.addEventListener('click', () => this.limparFormulario());
            this.campoPesquisa.addEventListener('input', () => this.filtrarTecnicos());
        }
        async carregarEmpresasNoSelect() {
            const select = obterElemento('empresa');
            try {
                const resultado = await buscarJson('/api/empresa/');
                if (resultado.status !== 'sucesso')
                    return;
                this.empresas = resultado.dados;
                select.innerHTML = '<option value="" disabled selected>Selecione a empresa...</option>';
                this.empresas.forEach((empresa) => {
                    const cnpj = empresa.cnpj ? formatarCnpj(empresa.cnpj) : 'Sem CNPJ';
                    select.add(new Option(`${empresa.razao_social} - CNPJ: ${cnpj}`, String(empresa.id)));
                });
            }
            catch (erro) {
                console.error('Erro crítico ao carregar empresas para o select', erro);
            }
        }
        async salvarTecnico() {
            const nome = valorDoCampo('nome');
            const idEmpresa = valorDoCampo('empresa');
            if (!nome || !idEmpresa) {
                alert('Os campos Nome e Empresa Vinculada são obrigatórios!');
                return;
            }
            try {
                const resultado = await enviarJson('/api/tecnico/', {
                    id: this.idAtual,
                    nome,
                    id_empresa: parseInt(idEmpresa),
                });
                if (resultado.status !== 'sucesso') {
                    alert('Erro: ' + resultado.mensagem);
                    return;
                }
                alert(resultado.mensagem);
                this.limparFormulario();
                this.carregarTecnicos();
            }
            catch (erro) {
                console.error('Falha na requisição:', erro);
                alert('Erro ao comunicar com o servidor.');
            }
        }
        async carregarTecnicos() {
            this.listaTecnicos.innerHTML = htmlMensagemNeutra('Carregando dados do servidor...');
            try {
                const resultado = await buscarJson('/api/tecnico/');
                if (resultado.status !== 'sucesso') {
                    this.listaTecnicos.innerHTML = htmlMensagemErro(`Erro do Servidor: ${resultado.mensagem}`);
                    return;
                }
                this.tecnicos = resultado.dados;
                this.renderizarCards(this.tecnicos);
            }
            catch (erro) {
                this.listaTecnicos.innerHTML = htmlMensagemErro('Erro crítico ao tentar conectar com o servidor.');
            }
        }
        localizarEmpresa(tecnico) {
            return this.empresas.find((empresa) => (tecnico.id_empresa && empresa.id == tecnico.id_empresa) ||
                empresa.razao_social === tecnico.nome_empresa);
        }
        renderizarCards(tecnicos) {
            this.listaTecnicos.innerHTML = '';
            if (tecnicos.length === 0) {
                this.listaTecnicos.innerHTML = htmlMensagemNeutra('Nenhum técnico encontrado.');
                return;
            }
            tecnicos.forEach((tecnico) => {
                const empresa = this.localizarEmpresa(tecnico);
                const cnpj = empresa ? formatarCnpj(empresa.cnpj) : 'Não localizado';
                const card = document.createElement('div');
                card.className = 'bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group';
                card.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <span class="text-xs font-bold text-emerald-400 uppercase tracking-wider">Técnico de Campo</span>
                        <span class="text-[10px] text-slate-500 font-mono">ID: ${tecnico.id}</span>
                    </div>
                    <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${escapeHtml(tecnico.nome)}</h3>
                    <p class="text-xs text-slate-400 mt-1">Empresa: <span class="text-slate-300 font-medium">${escapeHtml(tecnico.nome_empresa || 'Não informada')}</span></p>
                    <p class="text-xs text-slate-400 mt-1">CNPJ: <span class="text-slate-300 font-medium">${cnpj}</span></p>
                    <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-end">
                        <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                    </div>
                `;
                card.addEventListener('dblclick', () => {
                    this.prepararEdicao(tecnico.id, tecnico.nome, tecnico.id_empresa || empresa?.id || null);
                });
                this.listaTecnicos.appendChild(card);
            });
        }
        filtrarTecnicos() {
            const termo = this.campoPesquisa.value.toLowerCase();
            const filtrados = this.tecnicos.filter((tecnico) => tecnico.nome.toLowerCase().includes(termo) ||
                (tecnico.nome_empresa && tecnico.nome_empresa.toLowerCase().includes(termo)));
            this.renderizarCards(filtrados);
        }
        prepararEdicao(id, nome, idEmpresa) {
            this.idAtual = id;
            definirValorDoCampo('nome', nome);
            if (idEmpresa)
                definirValorDoCampo('empresa', idEmpresa.toString());
            aplicarModoEdicao(this.botaoSalvar, 'Alterar Registro');
            marcarRotulosFlutuantes(true);
            this.formulario.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        limparFormulario() {
            this.formulario.reset();
            this.idAtual = null;
            aplicarModoInsercao(this.botaoSalvar, 'Salvar Técnico');
            marcarRotulosFlutuantes(false);
        }
    }
    window.addEventListener('DOMContentLoaded', () => new TecnicoUI());
})();
