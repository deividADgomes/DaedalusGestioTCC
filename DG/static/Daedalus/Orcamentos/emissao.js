"use strict";
/// <reference path="../BaseUI.ts" />
(() => {
    class EmissaoLaudosUI extends BaseUI {
        constructor() {
            super();
            this.form = document.getElementById('form-laudo');
            this.selectUf = document.getElementById('cliente_uf');
            this.selectCidade = document.getElementById('cliente_cidade');
            this.itens = [];
            this.idOrcamento = null;
            this.numero = '';
            this.status = 'rascunho';
            this.triagemId = null;
            this.equipamentoId = null;
            this.pecasModelo = [];
            this.aplicarRegra = true; // false: o valor digitado é o valor cheio
            this.tecnicosProntos = Promise.resolve();
            this.modoAlteracao = false; // editando um laudo já emitido
            this.alteravel = false; // o status permite alterar depois de emitido
            // Regras de preço vindas do servidor (settings.ORCAMENTO_PRECIFICACAO). Aqui é só prévia:
            // o valor que vale é recalculado e gravado pelo servidor ao salvar.
            const bruto = document.getElementById('precificacao-data');
            this.preco = bruto ? JSON.parse(bruto.textContent || '{}') : { margem: 1, adicionais: [], validade_dias: 15 };
            this.mostrarRegraDePreco();
            this.ligarRegraDePreco();
            this.ligarTecnico();
            this.tecnicosProntos = this.carregarTecnicos();
            document.getElementById('aviso-sem-email')
                .classList.toggle('hidden', !!this.campo('analista_email').value);
            this.carregarModelos();
            this.selectUf.addEventListener('change', () => {
                if (this.selectUf.value)
                    this.carregarCidades(this.selectUf.value);
                else
                    this.limparCidades();
            });
            this.form.addEventListener('submit', (e) => { e.preventDefault(); this.salvar(); });
            document.getElementById('btn-emitir').addEventListener('click', () => this.emitir());
            document.getElementById('btn-baixar').addEventListener('click', () => this.baixar());
            document.getElementById('btn-enviar-email').addEventListener('click', () => this.enviarPorEmail());
            document.getElementById('btn-alterar').addEventListener('click', () => this.iniciarAlteracao());
            document.getElementById('btn-salvar-alt').addEventListener('click', () => this.salvarAlteracoes());
            document.getElementById('btn-cancelar-alt').addEventListener('click', () => this.cancelarAlteracao());
            document.getElementById('btn-ticket').addEventListener('click', () => this.preencherPorTicket());
            document.getElementById('btn-copiar').addEventListener('click', () => this.copiarDeLaudo());
            document.getElementById('copia-numero').addEventListener('keydown', (e) => { if (e.key === 'Enter') {
                e.preventDefault();
                this.copiarDeLaudo();
            } });
            document.getElementById('sel-modelo').addEventListener('change', () => this.escolherModelo());
            document.getElementById('btn-add-peca').addEventListener('click', () => this.adicionarPecaDoModelo());
            document.getElementById('btn-add-avulso').addEventListener('click', () => {
                this.itens.push({ peca_id: null, cotacao_id: null, nome: '', descricao: '', part_number: '', quantidade: 1, valor_base: null });
                this.desenharItens();
            });
            document.querySelectorAll('.btn-status').forEach((b) => {
                b.addEventListener('click', () => this.mudarStatus(b.dataset.status));
            });
            const params = new URLSearchParams(window.location.search);
            const id = params.get('id');
            const copiar = params.get('copiar');
            if (id)
                this.abrir(Number(id));
            else {
                this.desenharItens();
                if (copiar) { // vem de "Criar cópia" na tela de um laudo ou na pesquisa
                    document.getElementById('copia-numero').value = copiar;
                    this.copiarDeLaudo(true);
                }
            }
        }
        // ---------- utilidades ----------
        campo(nome) {
            return this.form.elements.namedItem(nome);
        }
        get editavel() { return this.status === 'rascunho' || this.modoAlteracao; }
        lerNumero(texto) {
            const t = texto.trim();
            if (!t)
                return null;
            const n = Number(t.includes(',') ? t.replace(/\./g, '').replace(',', '.') : t);
            return isFinite(n) ? n : null;
        }
        arredondar(valor) {
            return Math.round((valor + Number.EPSILON) * 100) / 100;
        }
        // ---------- preço (prévia) ----------
        get totalAdicionais() {
            return this.preco.adicionais.reduce((a, b) => a + b, 0);
        }
        mostrarRegraDePreco() {
            const margem = String(this.preco.margem).replace('.', ',');
            const adicionais = this.preco.adicionais.map((v) => formatarMoeda(v)).join(' + ');
            document.getElementById('regra-preco').textContent = this.aplicarRegra
                ? `Cada peça é cobrada pelo valor da peça × ${margem}. A primeira peça do orçamento soma ainda ${adicionais} (${formatarMoeda(this.totalAdicionais)}), uma única vez.`
                : 'Regra de preço desligada: o valor digitado em cada peça é o valor cheio cobrado, sem margem e sem adicionais.';
            document.getElementById('th-base').textContent = this.aplicarRegra ? 'Valor da peça (R$)' : 'Valor cheio (R$)';
            document.getElementById('th-cobrado').textContent = this.aplicarRegra ? 'Valor c/ margem' : 'Valor cobrado';
            document.getElementById('validade-dias').textContent = String(this.preco.validade_dias);
        }
        ligarRegraDePreco() {
            const chk = document.getElementById('chk-regra');
            chk.addEventListener('change', () => {
                this.aplicarRegra = chk.checked;
                this.mostrarRegraDePreco();
                this.desenharItens();
                if (!this.aplicarRegra) {
                    Mensagem.info('Sem a regra, o valor digitado em cada peça é o valor cheio cobrado (sem margem e sem os adicionais). Confira os valores.', 'Valor cheio');
                }
            });
        }
        // ---------- técnico responsável: lista do banco ou digitado ----------
        async carregarTecnicos() {
            try {
                const r = await (await fetch('/api/tecnico/')).json();
                if (r.status !== 'sucesso')
                    return;
                const sel = document.getElementById('sel-tecnico');
                sel.innerHTML = '<option value="">Selecione o técnico...</option>' + r.dados.map((x) => `<option value="${escapeHtml(x.nome)}">${escapeHtml(x.nome)}${x.nome_empresa ? ' — ' + escapeHtml(x.nome_empresa) : ''}</option>`).join('')
                    + '<option value="__outro__">Outro (digitar manualmente)</option>';
            }
            catch (e) { /* sem a lista, ainda dá para digitar o nome em "Outro" */ }
        }
        ligarTecnico() {
            const sel = document.getElementById('sel-tecnico');
            const campo = document.getElementById('tecnico_manual');
            sel.addEventListener('change', () => {
                if (sel.value === '__outro__') {
                    campo.classList.remove('hidden');
                    campo.value = '';
                    campo.focus();
                }
                else {
                    campo.classList.add('hidden');
                    campo.value = sel.value;
                }
            });
        }
        definirTecnico(nome) {
            const sel = document.getElementById('sel-tecnico');
            const campo = document.getElementById('tecnico_manual');
            if (!nome) {
                sel.value = '';
                campo.value = '';
                campo.classList.add('hidden');
                return;
            }
            const existe = [...sel.options].some((o) => o.value === nome && o.value !== '__outro__');
            sel.value = existe ? nome : '__outro__';
            campo.value = nome;
            campo.classList.toggle('hidden', existe);
        }
        valoresDoItem(i, indice) {
            const base = i.valor_base || 0;
            const unitario = this.aplicarRegra ? this.arredondar(base * this.preco.margem) : this.arredondar(base);
            const adicional = this.aplicarRegra && indice === 0 ? this.totalAdicionais : 0;
            return { unitario, adicional, subtotal: this.arredondar(unitario * i.quantidade + adicional) };
        }
        // ---------- UF e cidades (IBGE, igual à Gestão RFB) ----------
        limparCidades() {
            this.selectCidade.innerHTML = '<option value="">Selecione a UF primeiro</option>';
            this.selectCidade.disabled = true;
        }
        async carregarCidades(uf, cidadePreSelecionada) {
            this.selectCidade.innerHTML = '<option value="">Buscando...</option>';
            this.selectCidade.disabled = true;
            try {
                const req = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${encodeURIComponent(uf)}/municipios`);
                if (!req.ok)
                    throw new Error('UF inválida');
                const cidades = await req.json();
                this.selectCidade.innerHTML = '<option value="">Selecione a cidade</option>';
                cidades.forEach((c) => this.selectCidade.appendChild(new Option(c.nome, c.nome)));
                if (cidadePreSelecionada && !cidades.some((c) => c.nome === cidadePreSelecionada)) {
                    this.selectCidade.appendChild(new Option(cidadePreSelecionada, cidadePreSelecionada));
                }
                this.selectCidade.disabled = !this.editavel;
                if (cidadePreSelecionada)
                    this.selectCidade.value = cidadePreSelecionada;
            }
            catch (e) {
                // IBGE fora do ar: mantém ao menos a cidade já salva, para não perder o dado
                this.selectCidade.innerHTML = '<option value="">Não foi possível carregar as cidades</option>';
                if (cidadePreSelecionada) {
                    this.selectCidade.appendChild(new Option(cidadePreSelecionada, cidadePreSelecionada));
                    this.selectCidade.value = cidadePreSelecionada;
                }
                this.selectCidade.disabled = !this.editavel;
                Mensagem.aviso('Não foi possível carregar a lista de cidades agora. Tente escolher a UF novamente em instantes.');
            }
        }
        async definirUfCidade(uf, cidade) {
            this.selectUf.value = uf || '';
            if (uf)
                await this.carregarCidades(uf, cidade);
            else
                this.limparCidades();
        }
        // ---------- modelos e peças ----------
        async carregarModelos() {
            try {
                const r = await (await fetch('/api/modelo-equipamento/')).json();
                if (r.status !== 'sucesso')
                    return;
                const sel = document.getElementById('sel-modelo');
                sel.innerHTML = '<option value="">— Escolher modelo —</option>' + r.dados.map((m) => `<option value="${Number(m.id)}" data-modelo="${escapeHtml(m.modelo)}" data-tipo="${escapeHtml(m.tipo || '')}" data-marca="${escapeHtml(m.marca || '')}">${escapeHtml(m.modelo)} (${escapeHtml(m.pn)})</option>`).join('');
                if (this.equipamentoId)
                    sel.value = String(this.equipamentoId);
            }
            catch (e) { /* o formulário continua utilizável sem a lista */ }
        }
        async escolherModelo() {
            const sel = document.getElementById('sel-modelo');
            this.equipamentoId = sel.value ? Number(sel.value) : null;
            if (this.equipamentoId) {
                // Ao escolher o modelo, tipo, marca e modelo são preenchidos automaticamente.
                const opcao = sel.selectedOptions[0];
                this.campo('equip_modelo').value = opcao.dataset.modelo || '';
                this.campo('equip_tipo').value = opcao.dataset.tipo || '';
                this.campo('equip_marca').value = opcao.dataset.marca || '';
                await this.carregarPecasDoModelo();
            }
            else {
                this.pecasModelo = [];
                this.desenharSeletorPecas();
            }
        }
        async carregarPecasDoModelo() {
            this.pecasModelo = [];
            if (this.equipamentoId) {
                try {
                    const r = await (await fetch(`/api/modelo-equipamento/${this.equipamentoId}/pecas/`)).json();
                    if (r.status === 'sucesso')
                        this.pecasModelo = r.dados;
                }
                catch (e) { /* segue sem peças do modelo */ }
            }
            this.desenharSeletorPecas();
        }
        desenharSeletorPecas() {
            const sel = document.getElementById('sel-peca');
            sel.innerHTML = '<option value="">Peça do modelo...</option>' + this.pecasModelo.map((p) => {
                const preco = p.cotacao_atual ? ` — ${formatarMoeda(p.cotacao_atual.valor)}` : ' — sem cotação';
                return `<option value="${Number(p.id)}">${escapeHtml(p.part_number)} · ${escapeHtml((p.descricao || '').slice(0, 40))}${p.equipamento_completo ? ' [equipamento completo]' : ''}${escapeHtml(preco)}</option>`;
            }).join('');
        }
        adicionarPecaDoModelo() {
            const sel = document.getElementById('sel-peca');
            const peca = this.pecasModelo.find((p) => String(p.id) === sel.value);
            if (!peca) {
                Mensagem.aviso('Escolha uma peça do modelo (ou use "+ Item avulso").');
                return;
            }
            this.itens.push({
                peca_id: peca.id, cotacao_id: peca.cotacao_atual ? peca.cotacao_atual.id : null,
                nome: peca.part_number, descricao: peca.descricao || '', part_number: peca.part_number, quantidade: 1,
                valor_base: peca.cotacao_atual ? peca.cotacao_atual.valor : null,
            });
            sel.value = '';
            this.desenharItens();
        }
        // ---------- tabela de itens ----------
        desenharItens() {
            const corpo = document.getElementById('itens-laudo');
            const dis = this.editavel ? '' : 'disabled';
            if (!this.itens.length) {
                corpo.innerHTML = '<tr><td colspan="8" class="px-2 py-6 text-center text-slate-500">Nenhuma peça no orçamento.</td></tr>';
            }
            else {
                corpo.innerHTML = this.itens.map((i, idx) => {
                    const v = this.valoresDoItem(i, idx);
                    return `
                    <tr class="border-t border-[#334155]/50">
                        <td class="px-2 py-1.5"><input data-idx="${idx}" data-f="nome" value="${escapeHtml(i.nome)}" maxlength="150" ${dis}></td>
                        <td class="px-2 py-1.5"><input data-idx="${idx}" data-f="descricao" value="${escapeHtml(i.descricao)}" maxlength="255" ${dis}></td>
                        <td class="px-2 py-1.5"><input data-idx="${idx}" data-f="part_number" value="${escapeHtml(i.part_number)}" maxlength="100" ${dis}></td>
                        <td class="px-2 py-1.5"><input data-idx="${idx}" data-f="quantidade" type="number" min="1" max="999" value="${Number(i.quantidade)}" ${dis}></td>
                        <td class="px-2 py-1.5"><input data-idx="${idx}" data-f="valor_base" inputmode="decimal" value="${i.valor_base === null ? '' : String(i.valor_base).replace('.', ',')}" ${dis}></td>
                        <td class="px-2 py-1.5 text-right text-slate-300 whitespace-nowrap" id="un-${idx}">${escapeHtml(formatarMoeda(v.unitario))}</td>
                        <td class="px-2 py-1.5 text-right text-slate-200 whitespace-nowrap">
                            <span id="sub-${idx}">${escapeHtml(formatarMoeda(v.subtotal))}</span>
                            <span id="ad-${idx}" class="block text-[10px] text-cyan-400">${idx === 0 && this.aplicarRegra ? escapeHtml('inclui + ' + formatarMoeda(v.adicional)) : ''}</span>
                        </td>
                        <td class="px-2 py-1.5 text-right">${this.editavel ? `<button type="button" data-rm="${idx}" class="text-rose-400 hover:text-rose-300 text-xs">Remover</button>` : ''}</td>
                    </tr>`;
                }).join('');
                corpo.querySelectorAll('input').forEach((inp) => {
                    inp.addEventListener('input', () => {
                        const el = inp;
                        const idx = Number(el.dataset.idx);
                        const item = this.itens[idx];
                        const f = el.dataset.f;
                        if (f === 'quantidade')
                            item.quantidade = Math.max(1, parseInt(el.value, 10) || 1);
                        else if (f === 'valor_base') {
                            item.valor_base = this.lerNumero(el.value);
                            item.cotacao_id = null;
                        }
                        else
                            item[f] = el.value;
                        const v = this.valoresDoItem(item, idx);
                        document.getElementById('un-' + idx).textContent = formatarMoeda(v.unitario);
                        document.getElementById('sub-' + idx).textContent = formatarMoeda(v.subtotal);
                        this.atualizarTotal();
                    });
                });
                corpo.querySelectorAll('[data-rm]').forEach((b) => {
                    b.addEventListener('click', () => {
                        // Ao remover a primeira peça, a seguinte passa a ser a "primeira" e recebe os adicionais.
                        this.itens.splice(Number(b.dataset.rm), 1);
                        this.desenharItens();
                    });
                });
            }
            this.atualizarTotal();
        }
        atualizarTotal() {
            const total = this.itens.reduce((s, i, idx) => s + this.valoresDoItem(i, idx).subtotal, 0);
            document.getElementById('total-laudo').textContent = formatarMoeda(this.arredondar(total));
        }
        // ---------- carregar / preencher ----------
        async preencherFormulario(d) {
            Array.from(this.form.elements).forEach((el) => {
                const nome = el.name;
                if (!nome || nome === 'cliente_uf' || nome === 'cliente_cidade' || nome === 'aplicar_regra')
                    return;
                if (d[nome] !== undefined && d[nome] !== null)
                    el.value = d[nome];
            });
            if (d.aplicar_regra !== undefined) {
                this.aplicarRegra = d.aplicar_regra !== false;
                document.getElementById('chk-regra').checked = this.aplicarRegra;
                this.mostrarRegraDePreco();
            }
            if (d.tecnico_responsavel !== undefined) {
                await this.tecnicosProntos;
                this.definirTecnico(d.tecnico_responsavel || '');
            }
            this.triagemId = d.triagem_id || null;
            this.equipamentoId = d.equipamento_id || null;
            await this.definirUfCidade(d.cliente_uf || '', d.cliente_cidade || '');
        }
        async preencherPorTicket() {
            const ticket = document.getElementById('ticket-busca').value.trim();
            if (!ticket) {
                Mensagem.aviso('Informe o número do ticket.');
                return;
            }
            try {
                const r = await (await fetch('/api/orcamentos/pre-preenchimento/?ticket=' + encodeURIComponent(ticket))).json();
                if (r.status !== 'sucesso') {
                    Mensagem.aviso(r.mensagem, 'Ticket não encontrado');
                    return;
                }
                await this.preencherFormulario(r.dado);
                document.getElementById('sel-modelo').value = this.equipamentoId ? String(this.equipamentoId) : '';
                await this.carregarPecasDoModelo();
                Mensagem.sucesso('Dados da triagem carregados.');
            }
            catch (e) {
                Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }
        // Preenche este laudo (novo) com os dados de um laudo existente.
        async copiarDeLaudo(semConfirmar = false) {
            const numero = document.getElementById('copia-numero').value.trim();
            if (!numero) {
                Mensagem.aviso('Informe o número do laudo que será copiado.');
                return;
            }
            const jaTemDados = this.itens.length > 0 || !!this.campo('cliente_nome').value.trim();
            if (jaTemDados && !semConfirmar && !(await Mensagem.confirmar('O que já foi preenchido neste laudo será substituído pelos dados do laudo copiado.', 'Substituir os dados?', 'Sim, copiar')))
                return;
            const atualizar = document.getElementById('copia-atualizar').checked;
            try {
                const r = await (await fetch(`/api/orcamentos/copiar/?numero=${encodeURIComponent(numero)}${atualizar ? '&atualizar_valores=1' : ''}`)).json();
                if (r.status !== 'sucesso') {
                    Mensagem.aviso(r.mensagem, 'Laudo não encontrado');
                    return;
                }
                const d = r.dado;
                await this.preencherFormulario(d);
                document.getElementById('sel-modelo').value = this.equipamentoId ? String(this.equipamentoId) : '';
                this.itens = d.itens.map((i) => ({
                    peca_id: i.peca_id, cotacao_id: i.cotacao_id, nome: i.nome, descricao: i.descricao,
                    part_number: i.part_number, quantidade: i.quantidade, valor_base: i.valor_base,
                }));
                await this.carregarPecasDoModelo();
                this.desenharItens();
                const aviso = document.getElementById('aviso-copia');
                aviso.innerHTML = `<strong>Copiado do laudo ${escapeHtml(d.origem.numero)}</strong> (${escapeHtml(d.origem.status_nome)}, emitido em ${escapeHtml(formatarDataBr(d.origem.data_emissao))}).
                    Revise os dados, ajuste o que mudou e clique em "Salvar rascunho".`
                    + (d.mudancas_preco.length ? `<ul class="list-disc ml-5 mt-1">${d.mudancas_preco.map((m) => `<li>${escapeHtml(m)}</li>`).join('')}</ul>` : (atualizar ? ' As cotações das peças não mudaram.' : ''));
                aviso.classList.remove('hidden');
            }
            catch (e) {
                Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }
        async abrir(id) {
            try {
                const r = await (await fetch(`/api/orcamentos/${id}/`)).json();
                if (r.status !== 'sucesso') {
                    await Mensagem.erro(r.mensagem);
                    this.desenharItens();
                    return;
                }
                await this.aplicarDado(r.dado);
                await this.carregarPecasDoModelo();
            }
            catch (e) {
                Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }
        async aplicarDado(d) {
            const aviso = document.getElementById('aviso-cotacoes');
            const avisos = d.avisos_cotacao || [];
            aviso.innerHTML = avisos.length
                ? `<strong>Confira antes de emitir:</strong><ul class="list-disc ml-5 mt-1">${avisos.map((a) => `<li>${escapeHtml(a)}</li>`).join('')}</ul>` : '';
            aviso.classList.toggle('hidden', avisos.length === 0);
            this.idOrcamento = d.id;
            this.numero = d.numero;
            this.status = d.status;
            this.alteravel = !!d.alteravel;
            this.modoAlteracao = false;
            await this.preencherFormulario(d);
            document.getElementById('sel-modelo').value = this.equipamentoId ? String(this.equipamentoId) : '';
            this.itens = d.itens.map((i) => ({
                peca_id: i.peca_id, cotacao_id: i.cotacao_id, nome: i.nome, descricao: i.descricao,
                part_number: i.part_number, quantidade: i.quantidade, valor_base: i.valor_base,
            }));
            document.getElementById('sub-emissao').textContent = `${d.numero} · ${d.status_nome}`;
            const info = document.getElementById('info-datas');
            info.textContent = `Emissão: ${formatarDataBr(d.data_emissao)} · Válido até: ${formatarDataBr(d.validade_ate)}`;
            info.classList.remove('hidden');
            this.atualizarEstado();
            this.desenharItens();
            this.carregarHistorico();
        }
        atualizarEstado() {
            const dis = !this.editavel;
            Array.from(this.form.elements).forEach((el) => {
                if (el.tagName !== 'BUTTON')
                    el.disabled = dis;
            });
            ['btn-ticket', 'btn-add-peca', 'btn-add-avulso', 'sel-peca'].forEach((id) => (document.getElementById(id).disabled = dis));
            document.getElementById('ticket-busca').disabled = dis;
            const rascunho = this.status === 'rascunho';
            document.getElementById('btn-salvar').classList.toggle('hidden', !rascunho);
            document.getElementById('btn-emitir').classList.toggle('hidden', !rascunho);
            document.getElementById('btn-alterar').classList.toggle('hidden', rascunho || !this.alteravel || this.modoAlteracao);
            document.getElementById('btn-salvar-alt').classList.toggle('hidden', !this.modoAlteracao);
            document.getElementById('btn-cancelar-alt').classList.toggle('hidden', !this.modoAlteracao);
            document.getElementById('btn-baixar').classList.toggle('hidden', !this.idOrcamento);
            const criarCopia = document.getElementById('btn-criar-copia');
            criarCopia.href = `/orcamentos/emissao/?copiar=${encodeURIComponent(this.numero)}`;
            criarCopia.classList.toggle('hidden', !this.idOrcamento || this.status === 'rascunho' || this.modoAlteracao);
            const enviavel = ['emitido', 'aprovado', 'recusado'].includes(this.status) && !this.modoAlteracao;
            document.getElementById('btn-enviar-email').classList.toggle('hidden', !this.idOrcamento || !enviavel);
            const acoes = document.getElementById('acoes-status');
            const mostrar = (this.status === 'emitido' || this.status === 'recusado' || this.status === 'aprovado') && !this.modoAlteracao;
            acoes.classList.toggle('hidden', !mostrar);
            acoes.classList.toggle('flex', mostrar);
            acoes.querySelectorAll('.btn-status').forEach((b) => {
                const alvo = b.dataset.status;
                const permitido = (this.status === 'emitido' && ['aprovado', 'recusado', 'cancelado'].includes(alvo))
                    || (this.status === 'aprovado' && alvo === 'cancelado')
                    || (this.status === 'recusado' && alvo === 'cancelado');
                b.classList.toggle('hidden', !permitido);
            });
            const aviso = document.getElementById('aviso-status');
            const mensagem = this.modoAlteracao
                ? 'Modo de alteração: ao salvar, você informará o motivo, que fica registrado no histórico do laudo.'
                : dis
                    ? (this.alteravel
                        ? 'Este laudo já foi emitido. Para corrigir algum dado, use "Editar laudo": o motivo e o que mudou ficam registrados no histórico.'
                        : 'Este laudo está cancelado e não pode mais ser alterado.')
                    : '';
            aviso.classList.toggle('hidden', !mensagem);
            aviso.textContent = mensagem;
        }
        // ---------- alterar um laudo já emitido ----------
        iniciarAlteracao() {
            this.modoAlteracao = true;
            this.atualizarEstado();
            this.desenharItens();
            Mensagem.info('Faça as correções e clique em "Salvar alterações". O preço é recalculado automaticamente.', 'Modo de alteração');
        }
        async cancelarAlteracao() {
            if (this.idOrcamento)
                await this.abrir(this.idOrcamento); // recarrega o que está gravado
        }
        async salvarAlteracoes() {
            if (!this.form.reportValidity())
                return;
            const motivo = await Mensagem.pedirMotivo('Motivo da alteração', `Este motivo ficará registrado no histórico do laudo ${this.numero}.`);
            if (motivo === null)
                return;
            const btn = document.getElementById('btn-salvar-alt');
            btn.disabled = true;
            try {
                const r = await (await fetch('/api/orcamentos/', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ...this.coletar(), motivo_alteracao: motivo }),
                })).json();
                if (r.status !== 'sucesso') {
                    Mensagem.aviso(r.mensagem, 'Não foi possível alterar o laudo');
                    return;
                }
                await this.aplicarDado(r.dado);
                Mensagem.sucesso('Alterações salvas e registradas no histórico.');
                if (await Mensagem.confirmar('Deseja baixar o Word atualizado agora?', 'Laudo atualizado', 'Sim, baixar'))
                    await this.baixar();
            }
            catch (e) {
                Mensagem.erro('Erro ao conectar com o servidor.');
            }
            finally {
                btn.disabled = false;
            }
        }
        async carregarHistorico() {
            const card = document.getElementById('card-historico');
            const lista = document.getElementById('lista-historico');
            if (!this.idOrcamento) {
                card.classList.add('hidden');
                return;
            }
            try {
                const r = await (await fetch(`/api/orcamentos/${this.idOrcamento}/historico/`)).json();
                const itens = r.status === 'sucesso' ? r.dados : [];
                card.classList.toggle('hidden', itens.length === 0);
                lista.innerHTML = itens.map((h) => `
                    <div class="border border-[#334155] rounded-lg p-3 bg-[#0f172a]/40">
                        <div class="flex flex-wrap justify-between gap-2 text-xs">
                            <span class="font-semibold text-slate-200">${escapeHtml(h.motivo)}</span>
                            <span class="text-slate-500">${escapeHtml(new Date(h.quando).toLocaleString('pt-BR'))} · ${escapeHtml(h.usuario)}</span>
                        </div>
                        <ul class="mt-2 text-[11px] text-slate-400 list-disc pl-4">
                            ${(h.alteracoes || []).map((a) => `<li><span class="text-slate-300">${escapeHtml(a.campo)}:</span> ${escapeHtml(a.de)} → <span class="text-cyan-300">${escapeHtml(a.para)}</span></li>`).join('')}
                        </ul>
                    </div>`).join('');
            }
            catch (e) {
                card.classList.add('hidden');
            }
        }
        // ---------- salvar / emitir / baixar ----------
        coletar() {
            const dados = { id: this.idOrcamento, triagem_id: this.triagemId, equipamento_id: this.equipamentoId };
            Array.from(this.form.elements).forEach((el) => {
                const nome = el.name;
                if (nome)
                    dados[nome] = el.value;
            });
            // O servidor recalcula valor com margem e adicionais; envia só o valor da peça.
            dados.aplicar_regra = this.aplicarRegra;
            dados.itens = this.itens.map((i) => ({
                peca_id: i.peca_id, cotacao_id: i.cotacao_id, nome: i.nome, descricao: i.descricao,
                part_number: i.part_number, quantidade: i.quantidade, valor_base: i.valor_base === null ? '' : i.valor_base,
            }));
            return dados;
        }
        async salvar(silencioso = false) {
            const btn = document.getElementById('btn-salvar');
            btn.disabled = true;
            try {
                const r = await (await fetch('/api/orcamentos/', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.coletar()),
                })).json();
                if (r.status !== 'sucesso') {
                    Mensagem.erro(r.mensagem, 'Não foi possível salvar');
                    return false;
                }
                await this.aplicarDado(r.dado);
                window.history.replaceState(null, '', `?id=${r.dado.id}`);
                if (!silencioso)
                    Mensagem.sucesso('Laudo salvo como rascunho.');
                return true;
            }
            catch (e) {
                Mensagem.erro('Erro ao conectar com o servidor.');
                return false;
            }
            finally {
                btn.disabled = false;
            }
        }
        nomeSugerido() {
            const cliente = this.campo('cliente_nome').value.trim().replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_+|_+$/g, '');
            return `Laudo_${this.numero}${cliente ? '_' + cliente : ''}`;
        }
        async baixar() {
            if (!this.idOrcamento)
                return;
            await baixarDocumento(`/api/orcamentos/${this.idOrcamento}/docx/`, this.nomeSugerido());
        }
        async enviarPorEmail() {
            if (!this.idOrcamento)
                return;
            const dados = await Mensagem.pedirEmail(this.campo('cliente_email').value.trim());
            if (!dados)
                return;
            const btn = document.getElementById('btn-enviar-email');
            btn.disabled = true;
            try {
                const res = await (await fetch(`/api/orcamentos/${this.idOrcamento}/enviar-email/`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados)
                })).json();
                if (res.status === 'sucesso')
                    await Mensagem.sucesso(res.mensagem);
                else
                    await Mensagem.erro(res.mensagem);
            }
            catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
            finally {
                btn.disabled = false;
            }
        }
        async emitir() {
            if (!this.form.reportValidity())
                return;
            if (!(await Mensagem.confirmar('Depois de emitido, o laudo não poderá mais ser editado.', 'Emitir o laudo?', 'Sim, emitir')))
                return;
            if (!(await this.salvar(true)))
                return;
            if (await this.mudarStatus('emitido', false)) {
                await this.baixar(); // pergunta o nome do arquivo e baixa
            }
        }
        async mudarStatus(novo, confirmar = true) {
            if (!this.idOrcamento)
                return false;
            const nomes = { emitido: 'Emitido', aprovado: 'Aprovado', recusado: 'Recusado', cancelado: 'Cancelado' };
            let motivo = '';
            if (confirmar && novo === 'recusado') {
                const escolhido = await Mensagem.motivoRecusa(this.numero); // já serve de confirmação
                if (escolhido === null)
                    return false;
                motivo = escolhido;
            }
            else if (confirmar && !(await Mensagem.confirmar(`O laudo ${this.numero} será marcado como "${nomes[novo] || novo}".`, 'Mudar o status?', 'Sim, mudar')))
                return false;
            try {
                const r = await (await fetch(`/api/orcamentos/${this.idOrcamento}/status/`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: novo, motivo_recusa: motivo }),
                })).json();
                if (r.status !== 'sucesso') {
                    Mensagem.aviso(r.mensagem, 'Não foi possível mudar o status');
                    return false;
                }
                await this.aplicarDado(r.dado);
                if (confirmar)
                    Mensagem.sucesso(r.mensagem);
                return true;
            }
            catch (e) {
                Mensagem.erro('Erro ao conectar com o servidor.');
                return false;
            }
        }
    }
    document.addEventListener('DOMContentLoaded', () => new EmissaoLaudosUI());
})();
