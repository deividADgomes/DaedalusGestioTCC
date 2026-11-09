"use strict";
/// <reference path="../BaseUI.ts" />
(() => {
    class G_modeloEquipamento extends BaseUI {
        constructor() {
            super();
            this.idAtual = null;
            this.equipAtual = null;
            this.pecas = [];
            this.candidatas = [];
            this.sujo = false; // há peças editadas e ainda não salvas
            // ==========================================
            // LÓGICA DE LISTAGEM (GET)
            // ==========================================
            this.buscaAtual = 0; // descarta respostas antigas quando o usuário continua digitando
            this.btnSalvar = document.getElementById('btn-salvar-modelo');
            this.btnLimpar = document.getElementById('btn-limpar');
            this.form = document.getElementById('form-cadastro-modelo');
            this.listaModeloEquip = document.getElementById('lista-modelos');
            this.iniciarEventos();
            this.iniciarEventosPecas();
            this.carregarModelos(); // Busca os dados do servidor ao abrir a tela
        }
        iniciarEventos() {
            this.btnSalvar.addEventListener('click', () => this.salvarModelo());
            this.btnLimpar.addEventListener('click', () => this.pedirLimpar());
            // Pesquisa por modelo, PN, tipo, marca ou peça vinculada
            let espera;
            document.getElementById('pesquisa-modelo')?.addEventListener('input', () => {
                window.clearTimeout(espera);
                espera = window.setTimeout(() => this.carregarModelos(), 300);
            });
        }
        // ==========================================
        // LÓGICA DE SALVAR / ALTERAR (POST)
        // ==========================================
        async salvarModelo() {
            // Presumindo que os IDs dos inputs no seu HTML sejam 'pn' e 'modelo'
            const pn = document.getElementById('pn').value;
            const modelo = document.getElementById('modelo').value;
            const tipo = document.getElementById('tipo').value.trim();
            const marca = document.getElementById('marca').value.trim();
            if (!pn || !modelo) {
                Mensagem.aviso("Preencha todos os campos obrigatórios (PN e Modelo)!");
                return;
            }
            if (this.sujo && !(await this.confirmarDescarte()))
                return; // salvar o modelo fecha a edição das peças
            // O pacote de dados alinhado com o EquipamentoDTO
            const dados = {
                id: this.idAtual,
                pn: pn,
                modelo: modelo,
                tipo: tipo,
                marca: marca
            };
            try {
                const resposta = await fetch('/api/modelo-equipamento/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });
                const resultado = await resposta.json();
                if (resultado.status === 'sucesso') {
                    Mensagem.sucesso(resultado.mensagem);
                    this.limparFormulario();
                    this.carregarModelos(); // Atualiza a grid
                }
                else {
                    Mensagem.erro(resultado.mensagem);
                }
            }
            catch (error) {
                console.error("Falha na requisição:", error);
                Mensagem.erro("Erro ao comunicar com o servidor.");
            }
        }
        async carregarModelos() {
            const busca = (document.getElementById('pesquisa-modelo')?.value || '').trim();
            const numero = ++this.buscaAtual;
            if (!busca)
                this.listaModeloEquip.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Carregando dados do servidor...</p>';
            try {
                const resposta = await fetch(`/api/modelo-equipamento/?q=${encodeURIComponent(busca)}`);
                const resultado = await resposta.json();
                if (numero !== this.buscaAtual)
                    return;
                if (resultado.status === 'sucesso') {
                    this.listaModeloEquip.innerHTML = '';
                    if (resultado.dados.length === 0) {
                        this.listaModeloEquip.innerHTML = `<p class="text-sm font-medium text-slate-500 col-span-full text-center py-10">${busca ? 'Nenhum modelo ou peça encontrado para "' + escapeHtml(busca) + '".' : 'NENHUM EQUIPAMENTO CADASTRADO.'}</p>`;
                        return;
                    }
                    resultado.dados.forEach((equip) => {
                        const card = document.createElement('div');
                        card.className = "bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group";
                        card.innerHTML = `
                            <div class="flex justify-between items-start mb-2">
                                <span class="text-xs font-bold text-cyan-400 uppercase tracking-wider">Equipamento</span>
                                <span class="text-[10px] text-slate-500 font-mono">ID: ${escapeHtml(equip.id)}</span>
                            </div>
                            <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${escapeHtml(equip.modelo)}</h3>
                            <p class="text-xs text-slate-400 mt-1 font-mono">PN: ${escapeHtml(equip.pn)}</p>
                            <p class="text-xs text-slate-500 mt-1">${escapeHtml([equip.tipo, equip.marca].filter(Boolean).join(' · ') || 'Tipo e marca não informados')}${equip.rfb ? ' <span class="ml-1 px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 text-[10px] font-bold">RFB</span>' : ''}</p>
                            <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-between items-center">
                                <button type="button" class="btn-pecas px-3 py-1.5 rounded-md text-[11px] font-semibold text-cyan-300 bg-slate-800 hover:bg-slate-700 transition-colors">Peças (${Number(equip.total_pecas) || 0})</button>
                                <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                            </div>
                        `;
                        // "Peças" e duplo clique abrem a edição do modelo, com a seção de peças logo abaixo do formulário
                        const abrir = () => this.abrirModeloParaEdicao(equip);
                        card.querySelector('.btn-pecas').addEventListener('click', (e) => { e.stopPropagation(); abrir(); });
                        card.addEventListener('dblclick', abrir);
                        this.listaModeloEquip.appendChild(card);
                    });
                }
                else {
                    this.listaModeloEquip.innerHTML = `<p class="text-sm font-bold text-red-500 col-span-full text-center py-10">Erro do Servidor: ${escapeHtml(resultado.mensagem)}</p>`;
                }
            }
            catch (error) {
                this.listaModeloEquip.innerHTML = '<p class="text-sm font-bold text-red-500 col-span-full text-center py-10">Erro crítico ao tentar conectar com o servidor.</p>';
            }
        }
        // ==========================================
        // PEÇAS DO EQUIPAMENTO: seleção (PartSurfer) + cotações manuais
        // ==========================================
        ehGestao() {
            const cargo = window.CARGO_USUARIO_SESSAO;
            return cargo === 'Administrador' || cargo === 'Gestor';
        }
        criarModal(titulo, largura) {
            const fundo = document.createElement('div');
            fundo.className = 'fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4';
            fundo.innerHTML = `
                <div class="bg-[#1e293b] border border-[#334155] rounded-xl shadow-2xl w-full ${largura} max-h-[90vh] flex flex-col">
                    <div class="flex items-center justify-between px-5 py-4 border-b border-[#334155]">
                        <h3 class="text-sm font-bold text-slate-100">${escapeHtml(titulo)}</h3>
                        <button type="button" class="modal-fechar text-slate-400 hover:text-white text-xl leading-none" aria-label="Fechar">&times;</button>
                    </div>
                    <div class="modal-corpo flex-1 overflow-y-auto p-5"></div>
                </div>`;
            document.body.appendChild(fundo);
            const fechar = () => fundo.remove();
            fundo.querySelector('.modal-fechar').addEventListener('click', fechar);
            fundo.addEventListener('mousedown', (e) => { if (e.target === fundo)
                fechar(); });
            return { fundo, corpo: fundo.querySelector('.modal-corpo'), fechar };
        }
        // ---------- Modal de cotações (lançamento manual) ----------
        async abrirModalCotacoes(idPeca, partNumber) {
            const { corpo, fechar } = this.criarModal(`Cotações — ${partNumber}`, 'max-w-2xl');
            corpo.innerHTML = '<p class="text-xs text-slate-500 text-center py-6">Carregando...</p>';
            let fornecedores = [];
            try {
                const r = await (await fetch('/api/empresa/?tipo=3')).json();
                if (r.status === 'sucesso')
                    fornecedores = r.dados;
            }
            catch (e) { /* segue sem fornecedores: o aviso aparece abaixo */ }
            const hoje = new Date();
            const hojeIso = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-${String(hoje.getDate()).padStart(2, '0')}`;
            const opcoes = fornecedores.map((f) => `<option value="${Number(f.id)}">${escapeHtml(f.razao_social)}</option>`).join('');
            const semFornecedor = fornecedores.length === 0
                ? '<p class="text-xs text-amber-400 mb-3">Nenhum fornecedor cadastrado. Cadastre em <a href="/gerenciar-empresa/" class="underline">Gerenciar → Empresa</a> escolhendo o tipo "Fornecedor".</p>'
                : '';
            corpo.innerHTML = `
                ${semFornecedor}
                <p class="cot-universal text-[11px] text-cyan-300/80 bg-cyan-500/5 border border-cyan-500/20 rounded-lg px-3 py-2 mb-3">O valor é universal: vale para todos os modelos que usam este Part Number.</p>
                <div class="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-2">
                    <div class="sm:col-span-2">
                        <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Fornecedor</label>
                        <select class="cot-fornecedor w-full bg-[#0f172a] border border-[#334155] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                            <option value="">Selecione...</option>${opcoes}
                        </select>
                    </div>
                    <div>
                        <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Valor (R$)</label>
                        <input type="text" inputmode="decimal" class="cot-valor w-full bg-[#0f172a] border border-[#334155] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500" placeholder="0,00">
                    </div>
                    <div>
                        <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Data da cotação</label>
                        <input type="date" max="${hojeIso}" value="${hojeIso}" class="cot-data w-full bg-[#0f172a] border border-[#334155] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                    </div>
                </div>
                <div class="flex gap-3 items-end mb-5">
                    <div class="flex-1">
                        <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Observação (opcional)</label>
                        <input type="text" maxlength="255" class="cot-obs w-full bg-[#0f172a] border border-[#334155] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500">
                    </div>
                    <button type="button" class="cot-salvar px-4 py-2 rounded-lg text-xs font-semibold text-white bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50">Registrar</button>
                </div>
                <div class="cot-historico"></div>`;
            const elHist = corpo.querySelector('.cot-historico');
            const gestao = this.ehGestao();
            const carregarHistorico = async () => {
                try {
                    const r = await (await fetch(`/api/pecas/${idPeca}/cotacoes/`)).json();
                    if (r.status !== 'sucesso') {
                        elHist.innerHTML = `<p class="text-xs text-red-500">${escapeHtml(r.mensagem)}</p>`;
                        return;
                    }
                    const aviso = corpo.querySelector('.cot-universal');
                    if (aviso && Array.isArray(r.modelos)) {
                        const nomes = r.modelos.map((m) => m.modelo).join(', ');
                        aviso.textContent = r.modelos.length > 1
                            ? `Valor universal: vale para os ${r.modelos.length} modelos que usam este Part Number (${nomes}).`
                            : 'Valor universal: vale para todos os modelos que usam este Part Number (hoje só este modelo usa).';
                    }
                    if (r.cotacoes.length === 0) {
                        elHist.innerHTML = '<p class="text-xs text-slate-500 text-center py-4">Nenhuma cotação registrada.</p>';
                        return;
                    }
                    const rs = r.resumo;
                    const variacao = rs && rs.variacao_pct !== null && rs.variacao_pct !== 0
                        ? `<span class="${rs.variacao_pct > 0 ? 'text-rose-400' : 'text-emerald-400'} font-semibold">${rs.variacao_pct > 0 ? '▲' : '▼'} ${escapeHtml(String(Math.abs(rs.variacao_pct)).replace('.', ','))}%</span> contra a cotação anterior do mesmo fornecedor`
                        : 'Sem variação em relação à cotação anterior do mesmo fornecedor';
                    const resumo = rs ? `
                        <div class="mb-3 rounded-lg border border-[#334155] bg-slate-900/40 px-3 py-2 text-[11px] text-slate-300">
                            <p>Melhor preço atual: <span class="text-emerald-400 font-semibold">${escapeHtml(formatarMoeda(rs.melhor.valor))}</span> (${escapeHtml(rs.melhor.fornecedor)}). ${variacao}.</p>
                            ${rs.por_fornecedor.length > 1 ? `<p class="mt-1 text-slate-400">Última cotação de cada fornecedor: ${rs.por_fornecedor.map((f) => `${escapeHtml(f.fornecedor)} ${escapeHtml(formatarMoeda(f.valor))}`).join(' · ')}</p>` : ''}
                        </div>` : '';
                    elHist.innerHTML = resumo + `
                        <div class="max-h-60 overflow-y-auto border border-[#334155] rounded-lg">
                            <table class="w-full text-left text-xs">
                                <thead class="bg-slate-800 text-slate-400 uppercase sticky top-0"><tr>
                                    <th class="px-3 py-2">Data</th><th class="px-3 py-2">Fornecedor</th><th class="px-3 py-2 text-right">Valor</th><th class="px-3 py-2">Obs.</th><th class="px-3 py-2"></th>
                                </tr></thead>
                                <tbody>${r.cotacoes.map((c, i) => `
                                    <tr class="border-t border-[#334155]/50">
                                        <td class="px-3 py-2 whitespace-nowrap text-slate-300">${escapeHtml(formatarDataBr(c.data_cotacao))}${i === 0 ? ' <span class="text-[10px] text-emerald-400">(atual)</span>' : ''}</td>
                                        <td class="px-3 py-2 text-slate-300">${escapeHtml(c.fornecedor)}</td>
                                        <td class="px-3 py-2 text-right text-emerald-400 font-semibold whitespace-nowrap">${escapeHtml(formatarMoeda(c.valor))}</td>
                                        <td class="px-3 py-2 text-slate-400">${escapeHtml(c.observacao)}</td>
                                        <td class="px-3 py-2 text-right">${gestao ? `<button type="button" class="cot-excluir text-[11px] text-rose-400 hover:text-rose-300" data-id="${Number(c.id)}">Excluir</button>` : ''}</td>
                                    </tr>`).join('')}
                                </tbody>
                            </table>
                        </div>`;
                    elHist.querySelectorAll('.cot-excluir').forEach((b) => {
                        b.addEventListener('click', async () => {
                            if (!(await Mensagem.confirmar('Esta ação não pode ser desfeita.', 'Excluir esta cotação?', 'Sim, excluir')))
                                return;
                            const resp = await (await fetch(`/api/cotacoes/${b.dataset.id}/`, { method: 'DELETE' })).json();
                            if (resp.status !== 'sucesso')
                                Mensagem.erro(resp.mensagem);
                            await carregarHistorico();
                            this.atualizarCotacoes();
                        });
                    });
                }
                catch (e) {
                    elHist.innerHTML = '<p class="text-xs text-red-500">Erro ao carregar o histórico.</p>';
                }
            };
            const btnSalvar = corpo.querySelector('.cot-salvar');
            btnSalvar.addEventListener('click', async () => {
                const fornecedorId = corpo.querySelector('.cot-fornecedor').value;
                const valor = corpo.querySelector('.cot-valor').value.trim();
                const data = corpo.querySelector('.cot-data').value;
                if (!fornecedorId || !valor || !data) {
                    Mensagem.aviso('Informe fornecedor, valor e data da cotação.');
                    return;
                }
                btnSalvar.disabled = true;
                try {
                    const resp = await (await fetch(`/api/pecas/${idPeca}/cotacoes/`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            fornecedor_id: Number(fornecedorId), valor, data_cotacao: data,
                            observacao: corpo.querySelector('.cot-obs').value
                        })
                    })).json();
                    if (resp.status !== 'sucesso') {
                        Mensagem.erro(resp.mensagem);
                        return;
                    }
                    corpo.querySelector('.cot-valor').value = '';
                    corpo.querySelector('.cot-obs').value = '';
                    await carregarHistorico();
                    this.atualizarCotacoes();
                }
                catch (e) {
                    Mensagem.erro('Erro ao comunicar com o servidor.');
                }
                finally {
                    btnSalvar.disabled = false;
                }
            });
            corpo.closest('.fixed').addEventListener('keydown', (e) => { if (e.key === 'Escape')
                fechar(); });
            await carregarHistorico();
        }
        // ==========================================
        // MANIPULAÇÃO DA INTERFACE DÚPLICE
        // ==========================================
        // ==========================================
        // EDIÇÃO DO MODELO + SEÇÃO "PEÇAS DO MODELO"
        // ==========================================
        async confirmarDescarte() {
            return Mensagem.confirmar('Há alterações nas peças que ainda não foram salvas. Deseja descartá-las?', 'Alterações não salvas', 'Sim, descartar');
        }
        async pedirLimpar() {
            if (this.sujo && !(await this.confirmarDescarte()))
                return;
            this.limparFormulario();
        }
        // "Peças" e duplo clique no card abrem a edição do modelo, com a seção de peças logo abaixo do formulário
        async abrirModeloParaEdicao(equip) {
            if (this.sujo && this.idAtual !== equip.id && !(await this.confirmarDescarte()))
                return;
            this.prepararEdicao(equip.id, equip.pn, equip.modelo, equip.tipo || '', equip.marca || '');
            this.abrirPecas(equip);
        }
        prepararEdicao(id, pn, modelo, tipo, marca) {
            this.idAtual = id;
            document.getElementById('pn').value = pn;
            document.getElementById('modelo').value = modelo;
            document.getElementById('tipo').value = tipo;
            document.getElementById('marca').value = marca;
            // Sinais visuais de modo de Alteração
            this.btnSalvar.innerText = "Alterar Registro";
            this.btnSalvar.classList.replace('bg-cyan-600', 'bg-amber-600');
            this.btnSalvar.classList.replace('hover:bg-cyan-500', 'hover:bg-amber-500');
            this.btnSalvar.classList.replace('shadow-[0_0_15px_rgba(6,182,212,0.3)]', 'shadow-[0_0_15px_rgba(245,158,11,0.3)]');
            // Ativa o Floating Label
            document.querySelectorAll('#form-cadastro-modelo .input-dynamic').forEach(input => input.classList.add('has-value'));
            this.form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        limparFormulario() {
            this.form.reset();
            this.idAtual = null;
            // Retorna ao visual padrão de Inserção
            this.btnSalvar.innerText = "Salvar Equipamento";
            this.btnSalvar.classList.replace('bg-amber-600', 'bg-cyan-600');
            this.btnSalvar.classList.replace('hover:bg-amber-500', 'hover:bg-cyan-500');
            this.btnSalvar.classList.replace('shadow-[0_0_15px_rgba(245,158,11,0.3)]', 'shadow-[0_0_15px_rgba(6,182,212,0.3)]');
            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.remove('has-value'));
            document.getElementById('secao-pecas')?.classList.add('hidden');
            this.fecharPartSurfer();
            this.equipAtual = null;
            this.pecas = [];
            this.marcarSujo(false);
        }
        // ==========================================
        // PEÇAS DO MODELO (lista editável; só grava em "Salvar peças")
        // ==========================================
        iniciarEventosPecas() {
            document.getElementById('btn-importar-planilha')?.addEventListener('click', () => this.importarPlanilha());
            document.getElementById('importacao-arquivo')?.addEventListener('change', (e) => {
                const arquivo = e.target.files?.[0];
                if (!arquivo)
                    return;
                const leitor = new FileReader();
                leitor.onload = () => { document.getElementById('importacao-texto').value = String(leitor.result || ''); };
                leitor.readAsText(arquivo, 'utf-8');
            });
            document.getElementById('btn-add-peca')?.addEventListener('click', () => this.adicionarPecaDoFormulario());
            document.getElementById('peca-pn')?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.adicionarPecaDoFormulario();
                }
            });
            document.getElementById('peca-completo')?.addEventListener('change', (e) => this.preencherEquipamentoCompleto(e.target.checked));
            document.getElementById('btn-importar-pecas')?.addEventListener('click', () => this.importarLista());
            document.getElementById('btn-salvar-pecas')?.addEventListener('click', () => this.salvarPecas());
            document.getElementById('btn-partsurfer')?.addEventListener('click', () => this.buscarPartSurfer());
            document.getElementById('ps-fechar')?.addEventListener('click', () => this.fecharPartSurfer());
            document.getElementById('ps-aplicar')?.addEventListener('click', () => this.aplicarPartSurfer());
            document.getElementById('ps-marcar-todas')?.addEventListener('click', () => this.marcarCandidatas(true));
            document.getElementById('ps-desmarcar')?.addEventListener('click', () => this.marcarCandidatas(false));
            document.getElementById('ps-filtro')?.addEventListener('input', () => this.desenharCandidatas());
            // Evita perder peças editadas e não salvas ao fechar a aba
            window.addEventListener('beforeunload', (e) => {
                if (this.sujo) {
                    e.preventDefault();
                    e.returnValue = '';
                }
            });
        }
        marcarSujo(valor) {
            this.sujo = valor;
            this.atualizarStatusPecas();
        }
        atualizarStatusPecas() {
            const el = document.getElementById('pecas-status');
            if (!el)
                return;
            if (this.sujo) {
                el.className = 'text-[10px] text-amber-400 font-semibold mb-4';
                el.innerText = 'Alterações não salvas: clique em "Salvar peças" para gravar.';
                return;
            }
            el.className = 'text-[10px] text-slate-500 mb-4';
            const quando = this.equipAtual && this.equipAtual.pecas_sincronizadas_em
                ? new Date(this.equipAtual.pecas_sincronizadas_em).toLocaleString('pt-BR') : 'nunca consultado';
            el.innerText = `Última consulta ao PartSurfer: ${quando}`;
        }
        mapearPecas(dados) {
            return dados.map((p) => ({
                id: p.id, part_number: p.part_number, descricao: p.descricao || '',
                equipamento_completo: !!p.equipamento_completo, cotacao_atual: p.cotacao_atual || null
            }));
        }
        async abrirPecas(equip) {
            this.equipAtual = equip;
            document.getElementById('pecas-modelo-nome').innerText = equip.modelo;
            document.getElementById('secao-pecas')?.classList.remove('hidden');
            this.pecas = [];
            this.fecharPartSurfer();
            this.marcarSujo(false);
            this.desenharPecas();
            try {
                const res = await (await fetch(`/api/modelo-equipamento/${equip.id}/pecas/`)).json();
                if (this.idAtual !== equip.id)
                    return; // o usuário já abriu outro modelo
                if (res.status === 'sucesso') {
                    this.pecas = this.mapearPecas(res.dados);
                    this.desenharPecas();
                }
                else {
                    Mensagem.erro(res.mensagem);
                }
            }
            catch (e) {
                Mensagem.erro('Erro ao carregar as peças do modelo.');
            }
        }
        // ---------- consulta ao HP PartSurfer (lista marcável, sem modal) ----------
        async buscarPartSurfer() {
            if (!this.idAtual)
                return;
            const id = this.idAtual;
            const btn = document.getElementById('btn-partsurfer');
            const rotulo = btn.innerText;
            btn.disabled = true;
            btn.innerText = 'Consultando HP...';
            try {
                const res = await (await fetch(`/api/modelo-equipamento/${id}/partsurfer/`, { method: 'POST' })).json();
                if (res.status !== 'sucesso') {
                    Mensagem.erro(res.mensagem);
                    return;
                }
                if (this.idAtual !== id)
                    return;
                if (this.equipAtual)
                    this.equipAtual.pecas_sincronizadas_em = new Date().toISOString();
                this.atualizarStatusPecas();
                // O que já está na lista local (mesmo sem salvar) vem marcado
                const locais = new Set(this.pecas.map(p => p.part_number));
                this.candidatas = res.dados.map((c) => ({ ...c, selecionada: c.selecionada || locais.has(c.part_number) }));
                this.pecas.forEach(p => {
                    if (!this.candidatas.some(c => c.part_number === p.part_number)) {
                        this.candidatas.push({ part_number: p.part_number, descricao: p.descricao, selecionada: true, somente_local: true });
                    }
                });
                document.getElementById('partsurfer-msg').innerText =
                    `${this.candidatas.length} peça(s) listada(s). Marque as que este modelo usa.`;
                document.getElementById('ps-filtro').value = '';
                document.getElementById('painel-partsurfer')?.classList.remove('hidden');
                this.desenharCandidatas();
            }
            catch (e) {
                Mensagem.erro('Erro ao comunicar com o servidor.');
            }
            finally {
                btn.disabled = false;
                btn.innerText = rotulo;
            }
        }
        candidatasVisiveis() {
            const filtro = document.getElementById('ps-filtro').value.trim().toLowerCase();
            return this.candidatas.filter(c => !filtro || c.part_number.toLowerCase().includes(filtro) || c.descricao.toLowerCase().includes(filtro));
        }
        desenharCandidatas() {
            const ul = document.getElementById('ps-lista');
            ul.innerHTML = '';
            this.candidatasVisiveis().forEach(c => {
                const li = document.createElement('li');
                li.className = 'py-1.5';
                li.innerHTML = `<label class="flex items-center gap-3 cursor-pointer">
                    <input type="checkbox" class="accent-cyan-500" ${c.selecionada ? 'checked' : ''}>
                    <span class="font-mono text-cyan-400">${escapeHtml(c.part_number)}</span>
                    <span class="text-slate-300">${escapeHtml(c.descricao)}</span>
                    ${c.somente_local ? '<span class="text-[10px] text-amber-400">(não veio do PartSurfer)</span>' : ''}
                </label>`;
                li.querySelector('input')?.addEventListener('change', (e) => {
                    c.selecionada = e.target.checked;
                });
                ul.appendChild(li);
            });
        }
        marcarCandidatas(valor) {
            this.candidatasVisiveis().forEach(c => { c.selecionada = valor; });
            this.desenharCandidatas();
        }
        aplicarPartSurfer() {
            // Quem já está na lista mantém descrição, marcação de equipamento completo e cotação
            const atuais = new Map(this.pecas.map(p => [p.part_number, p]));
            const novas = this.candidatas.filter(c => c.selecionada).map(c => atuais.get(c.part_number) || { part_number: c.part_number, descricao: c.descricao, equipamento_completo: false });
            const antes = this.pecas.map(p => p.part_number).sort().join('|');
            const depois = novas.map(p => p.part_number).sort().join('|');
            this.pecas = novas;
            if (antes !== depois)
                this.marcarSujo(true);
            this.desenharPecas();
            this.fecharPartSurfer();
        }
        fecharPartSurfer() {
            document.getElementById('painel-partsurfer')?.classList.add('hidden');
            this.candidatas = [];
        }
        // ---------- importação de planilha (vários modelos de uma vez; grava direto no servidor) ----------
        async importarPlanilha() {
            const texto = document.getElementById('importacao-texto').value;
            const btn = document.getElementById('btn-importar-planilha');
            const saida = document.getElementById('importacao-resultado');
            if (!texto.trim()) {
                Mensagem.aviso('Cole a planilha ou escolha um arquivo CSV.');
                return;
            }
            if (this.sujo && !(await this.confirmarDescarte()))
                return; // a importação pode mudar as peças do modelo aberto
            btn.disabled = true;
            try {
                const res = await (await fetch('/api/modelo-equipamento/importar-pecas/', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texto })
                })).json();
                if (res.status !== 'sucesso') {
                    Mensagem.erro(res.mensagem);
                    return;
                }
                const d = res.dado;
                saida.innerHTML = `<p class="text-emerald-400 font-semibold">${d.linhas} linha(s) lida(s): ${d.criadas} peça(s) nova(s), ${d.vinculadas} vínculo(s) novo(s), ${d.atualizadas} peça(s) atualizada(s).</p>`
                    + (d.erros.length ? `<ul class="mt-2 list-disc ml-5 text-amber-400">${d.erros.map((e) => `<li>${escapeHtml(e)}</li>`).join('')}</ul>` : '');
                saida.classList.remove('hidden');
                this.carregarModelos();
                if (this.equipAtual) {
                    this.marcarSujo(false);
                    this.abrirPecas(this.equipAtual);
                } // recarrega o modelo aberto
            }
            catch (e) {
                Mensagem.erro('Erro ao comunicar com o servidor.');
            }
            finally {
                btn.disabled = false;
            }
        }
        // ---------- adicionar / importar ----------
        adicionarPeca(pn, descricao, completo) {
            const chave = pn.trim().toUpperCase();
            if (!chave)
                return false;
            const existente = this.pecas.find(p => p.part_number === chave);
            if (existente) {
                if (descricao.trim())
                    existente.descricao = descricao.trim();
                if (completo !== undefined)
                    existente.equipamento_completo = completo;
            }
            else {
                this.pecas.push({ part_number: chave, descricao: descricao.trim(), equipamento_completo: !!completo });
            }
            this.marcarSujo(true);
            return true;
        }
        preencherEquipamentoCompleto(marcado) {
            if (!marcado || !this.equipAtual)
                return;
            const pn = document.getElementById('peca-pn');
            const desc = document.getElementById('peca-descricao');
            if (!pn.value.trim())
                pn.value = this.equipAtual.pn || '';
            if (!desc.value.trim())
                desc.value = `Equipamento completo — ${this.equipAtual.modelo}`;
            pn.classList.add('has-value');
            desc.classList.add('has-value');
        }
        adicionarPecaDoFormulario() {
            const pn = document.getElementById('peca-pn');
            const desc = document.getElementById('peca-descricao');
            const completo = document.getElementById('peca-completo');
            if (!this.adicionarPeca(pn.value, desc.value, completo.checked ? true : undefined)) {
                Mensagem.aviso('Informe o Part Number da peça.');
                return;
            }
            pn.value = '';
            desc.value = '';
            completo.checked = false;
            pn.classList.remove('has-value');
            desc.classList.remove('has-value');
            pn.focus();
            this.desenharPecas();
        }
        importarLista() {
            const area = document.getElementById('peca-colar');
            let qtd = 0;
            area.value.split(/\r?\n/).forEach(linha => {
                const [pn, ...resto] = linha.split(/[;\t]/);
                if (this.adicionarPeca(pn || '', resto.join(' ').trim()))
                    qtd++;
            });
            area.value = '';
            this.desenharPecas();
            if (qtd === 0)
                Mensagem.aviso('Nenhuma linha válida encontrada.');
        }
        // ---------- lista ----------
        desenharPecas() {
            const ul = document.getElementById('lista-pecas');
            ul.innerHTML = '';
            document.getElementById('pecas-vazio')?.classList.toggle('hidden', this.pecas.length > 0);
            this.pecas.slice().sort((a, b) => a.part_number.localeCompare(b.part_number)).forEach(p => {
                const c = p.cotacao_atual;
                const cotacao = c
                    ? `<span class="text-emerald-400 font-semibold text-xs">${escapeHtml(formatarMoeda(c.valor))}</span>
                       <span class="block text-[10px] text-slate-500">${escapeHtml(c.fornecedor)} · ${escapeHtml(formatarDataBr(c.data_cotacao))}</span>`
                    : '<span class="text-[10px] text-slate-500">Sem cotação</span>';
                const acaoCotacao = p.id
                    ? `<button type="button" class="btn-cotacoes px-2 py-1 rounded-md text-[11px] font-semibold text-cyan-300 bg-slate-800 hover:bg-slate-700 transition-colors">Cotações</button>`
                    : '<span class="text-[10px] text-amber-400/80">salve para cotar</span>';
                const li = document.createElement('li');
                li.className = 'flex items-center justify-between py-2 gap-3';
                li.innerHTML = `<div class="min-w-0"><span class="font-mono text-cyan-400 text-xs">${escapeHtml(p.part_number)}</span>
                    <span class="text-slate-300 text-xs ml-3">${escapeHtml(p.descricao)}</span>
                    ${p.equipamento_completo ? '<span class="ml-2 px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px] font-bold">Equipamento completo</span>' : ''}</div>
                    <div class="flex items-center gap-3 shrink-0"><div class="text-right">${cotacao}</div>${acaoCotacao}
                    <button type="button" class="btn-remover text-[10px] font-bold uppercase text-rose-400 hover:text-rose-300">Remover</button></div>`;
                li.querySelector('.btn-remover')?.addEventListener('click', () => {
                    this.pecas = this.pecas.filter(x => x.part_number !== p.part_number);
                    this.marcarSujo(true);
                    this.desenharPecas();
                });
                li.querySelector('.btn-cotacoes')?.addEventListener('click', () => {
                    if (p.id)
                        this.abrirModalCotacoes(p.id, p.part_number);
                });
                ul.appendChild(li);
            });
        }
        async salvarPecas() {
            if (!this.idAtual)
                return;
            const btn = document.getElementById('btn-salvar-pecas');
            btn.disabled = true;
            try {
                const res = await (await fetch(`/api/modelo-equipamento/${this.idAtual}/pecas/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pecas: this.pecas.map(p => ({ part_number: p.part_number, descricao: p.descricao, equipamento_completo: p.equipamento_completo })) })
                })).json();
                if (res.status === 'sucesso') {
                    this.pecas = this.mapearPecas(res.dados);
                    this.marcarSujo(false);
                    this.desenharPecas();
                    this.carregarModelos();
                    Mensagem.sucesso(res.mensagem);
                }
                else {
                    Mensagem.erro(res.mensagem);
                }
            }
            catch (e) {
                Mensagem.erro('Erro ao comunicar com o servidor.');
            }
            finally {
                btn.disabled = false;
            }
        }
        // Depois de lançar/excluir uma cotação: atualiza só a cotação das peças, sem mexer nas alterações não salvas
        async atualizarCotacoes() {
            if (!this.idAtual)
                return;
            try {
                const res = await (await fetch(`/api/modelo-equipamento/${this.idAtual}/pecas/`)).json();
                if (res.status !== 'sucesso')
                    return;
                const porPn = new Map(res.dados.map((p) => [p.part_number, p]));
                this.pecas.forEach(p => {
                    const salva = porPn.get(p.part_number);
                    if (salva) {
                        p.id = salva.id;
                        p.cotacao_atual = salva.cotacao_atual || null;
                    }
                });
                this.desenharPecas();
            }
            catch (e) { /* a lista continua como estava */ }
        }
    }
    window.addEventListener('DOMContentLoaded', () => {
        new G_modeloEquipamento();
    });
})();
