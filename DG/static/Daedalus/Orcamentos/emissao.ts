/// <reference path="../BaseUI.ts" />
(() => {
    interface ItemLaudo {
        peca_id: number | null; cotacao_id: number | null;
        nome: string; descricao: string; part_number: string; quantidade: number;
        valor_base: number | null;      // valor da peça (cotação ou digitado)
    }
    interface Precificacao { margem: number; adicionais: number[]; validade_dias: number; }

    class EmissaoLaudosUI extends BaseUI {
        private form = document.getElementById('form-laudo') as HTMLFormElement;
        private selectUf = document.getElementById('cliente_uf') as HTMLSelectElement;
        private selectCidade = document.getElementById('cliente_cidade') as HTMLSelectElement;
        private itens: ItemLaudo[] = [];
        private idOrcamento: number | null = null;
        private numero = '';
        private status = 'rascunho';
        private triagemId: number | null = null;
        private equipamentoId: number | null = null;
        private pecasModelo: any[] = [];
        private aplicarRegra = true;           // false: o valor digitado é o valor cheio
        private tecnicosProntos: Promise<void> = Promise.resolve();
        private modoAlteracao = false;   // editando um laudo já emitido
        private alteravel = false;       // o status permite alterar depois de emitido
        private preco: Precificacao;

        constructor() {
            super();
            // Regras de preço vindas do servidor (settings.ORCAMENTO_PRECIFICACAO). Aqui é só prévia:
            // o valor que vale é recalculado e gravado pelo servidor ao salvar.
            const bruto = document.getElementById('precificacao-data');
            this.preco = bruto ? JSON.parse(bruto.textContent || '{}') : { margem: 1, adicionais: [], validade_dias: 15 };
            this.mostrarRegraDePreco();
            this.ligarRegraDePreco();
            this.ligarTecnico();
            this.tecnicosProntos = this.carregarTecnicos();
            (document.getElementById('aviso-sem-email') as HTMLElement)
                .classList.toggle('hidden', !!this.campo('analista_email').value);

            this.carregarModelos();

            this.selectUf.addEventListener('change', () => {
                if (this.selectUf.value) this.carregarCidades(this.selectUf.value);
                else this.limparCidades();
            });
            this.form.addEventListener('submit', (e) => { e.preventDefault(); this.salvar(); });
            (document.getElementById('btn-emitir') as HTMLElement).addEventListener('click', () => this.emitir());
            (document.getElementById('btn-baixar') as HTMLElement).addEventListener('click', () => this.baixar());
            (document.getElementById('btn-enviar-email') as HTMLElement).addEventListener('click', () => this.enviarPorEmail());
            (document.getElementById('btn-alterar') as HTMLElement).addEventListener('click', () => this.iniciarAlteracao());
            (document.getElementById('btn-salvar-alt') as HTMLElement).addEventListener('click', () => this.salvarAlteracoes());
            (document.getElementById('btn-cancelar-alt') as HTMLElement).addEventListener('click', () => this.cancelarAlteracao());
            (document.getElementById('btn-ticket') as HTMLElement).addEventListener('click', () => this.preencherPorTicket());
            (document.getElementById('btn-copiar') as HTMLElement).addEventListener('click', () => this.copiarDeLaudo());
            (document.getElementById('copia-numero') as HTMLInputElement).addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); this.copiarDeLaudo(); } });
            (document.getElementById('sel-modelo') as HTMLElement).addEventListener('change', () => this.escolherModelo());
            (document.getElementById('btn-add-peca') as HTMLElement).addEventListener('click', () => this.adicionarPecaDoModelo());
            (document.getElementById('btn-add-avulso') as HTMLElement).addEventListener('click', () => {
                this.itens.push({ peca_id: null, cotacao_id: null, nome: '', descricao: '', part_number: '', quantidade: 1, valor_base: null });
                this.desenharItens();
            });
            document.querySelectorAll('.btn-status').forEach((b) => {
                b.addEventListener('click', () => this.mudarStatus((b as HTMLElement).dataset.status as string));
            });

            const params = new URLSearchParams(window.location.search);
            const id = params.get('id');
            const copiar = params.get('copiar');
            if (id) this.abrir(Number(id));
            else {
                this.desenharItens();
                if (copiar) {                       // vem de "Criar cópia" na tela de um laudo ou na pesquisa
                    (document.getElementById('copia-numero') as HTMLInputElement).value = copiar;
                    this.copiarDeLaudo(true);
                }
            }
        }

        // ---------- utilidades ----------
        private campo(nome: string): HTMLInputElement {
            return this.form.elements.namedItem(nome) as HTMLInputElement;
        }
        private get editavel(): boolean { return this.status === 'rascunho' || this.modoAlteracao; }

        private lerNumero(texto: string): number | null {
            const t = texto.trim();
            if (!t) return null;
            const n = Number(t.includes(',') ? t.replace(/\./g, '').replace(',', '.') : t);
            return isFinite(n) ? n : null;
        }

        private arredondar(valor: number): number {
            return Math.round((valor + Number.EPSILON) * 100) / 100;
        }

        // ---------- preço (prévia) ----------
        private get totalAdicionais(): number {
            return this.preco.adicionais.reduce((a, b) => a + b, 0);
        }

        private mostrarRegraDePreco(): void {
            const margem = String(this.preco.margem).replace('.', ',');
            const adicionais = this.preco.adicionais.map((v) => formatarMoeda(v)).join(' + ');
            (document.getElementById('regra-preco') as HTMLElement).textContent = this.aplicarRegra
                ? `Cada peça é cobrada pelo valor da peça × ${margem}. A primeira peça do orçamento soma ainda ${adicionais} (${formatarMoeda(this.totalAdicionais)}), uma única vez.`
                : 'Regra de preço desligada: o valor digitado em cada peça é o valor cheio cobrado, sem margem e sem adicionais.';
            (document.getElementById('th-base') as HTMLElement).textContent = this.aplicarRegra ? 'Valor da peça (R$)' : 'Valor cheio (R$)';
            (document.getElementById('th-cobrado') as HTMLElement).textContent = this.aplicarRegra ? 'Valor c/ margem' : 'Valor cobrado';
            (document.getElementById('validade-dias') as HTMLElement).textContent = String(this.preco.validade_dias);
        }

        private ligarRegraDePreco(): void {
            const chk = document.getElementById('chk-regra') as HTMLInputElement;
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
        private async carregarTecnicos(): Promise<void> {
            try {
                const r = await (await fetch('/api/tecnico/')).json();
                if (r.status !== 'sucesso') return;
                const sel = document.getElementById('sel-tecnico') as HTMLSelectElement;
                sel.innerHTML = '<option value="">Selecione o técnico...</option>' + r.dados.map((x: any) =>
                    `<option value="${escapeHtml(x.nome)}">${escapeHtml(x.nome)}${x.nome_empresa ? ' — ' + escapeHtml(x.nome_empresa) : ''}</option>`).join('')
                    + '<option value="__outro__">Outro (digitar manualmente)</option>';
            } catch (e) { /* sem a lista, ainda dá para digitar o nome em "Outro" */ }
        }

        private ligarTecnico(): void {
            const sel = document.getElementById('sel-tecnico') as HTMLSelectElement;
            const campo = document.getElementById('tecnico_manual') as HTMLInputElement;
            sel.addEventListener('change', () => {
                if (sel.value === '__outro__') { campo.classList.remove('hidden'); campo.value = ''; campo.focus(); }
                else { campo.classList.add('hidden'); campo.value = sel.value; }
            });
        }

        private definirTecnico(nome: string): void {
            const sel = document.getElementById('sel-tecnico') as HTMLSelectElement;
            const campo = document.getElementById('tecnico_manual') as HTMLInputElement;
            if (!nome) { sel.value = ''; campo.value = ''; campo.classList.add('hidden'); return; }
            const existe = [...sel.options].some((o) => o.value === nome && o.value !== '__outro__');
            sel.value = existe ? nome : '__outro__';
            campo.value = nome;
            campo.classList.toggle('hidden', existe);
        }

        private valoresDoItem(i: ItemLaudo, indice: number): { unitario: number; adicional: number; subtotal: number } {
            const base = i.valor_base || 0;
            const unitario = this.aplicarRegra ? this.arredondar(base * this.preco.margem) : this.arredondar(base);
            const adicional = this.aplicarRegra && indice === 0 ? this.totalAdicionais : 0;
            return { unitario, adicional, subtotal: this.arredondar(unitario * i.quantidade + adicional) };
        }

        // ---------- UF e cidades (IBGE, igual à Gestão RFB) ----------
        private limparCidades(): void {
            this.selectCidade.innerHTML = '<option value="">Selecione a UF primeiro</option>';
            this.selectCidade.disabled = true;
        }

        private async carregarCidades(uf: string, cidadePreSelecionada?: string): Promise<void> {
            this.selectCidade.innerHTML = '<option value="">Buscando...</option>';
            this.selectCidade.disabled = true;
            try {
                const req = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${encodeURIComponent(uf)}/municipios`);
                if (!req.ok) throw new Error('UF inválida');
                const cidades = await req.json();
                this.selectCidade.innerHTML = '<option value="">Selecione a cidade</option>';
                cidades.forEach((c: any) => this.selectCidade.appendChild(new Option(c.nome, c.nome)));
                if (cidadePreSelecionada && !cidades.some((c: any) => c.nome === cidadePreSelecionada)) {
                    this.selectCidade.appendChild(new Option(cidadePreSelecionada, cidadePreSelecionada));
                }
                this.selectCidade.disabled = !this.editavel;
                if (cidadePreSelecionada) this.selectCidade.value = cidadePreSelecionada;
            } catch (e) {
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

        private async definirUfCidade(uf: string, cidade: string): Promise<void> {
            this.selectUf.value = uf || '';
            if (uf) await this.carregarCidades(uf, cidade);
            else this.limparCidades();
        }

        // ---------- modelos e peças ----------
        private async carregarModelos(): Promise<void> {
            try {
                const r = await (await fetch('/api/modelo-equipamento/')).json();
                if (r.status !== 'sucesso') return;
                const sel = document.getElementById('sel-modelo') as HTMLSelectElement;
                sel.innerHTML = '<option value="">— Escolher modelo —</option>' + r.dados.map((m: any) =>
                    `<option value="${Number(m.id)}" data-modelo="${escapeHtml(m.modelo)}" data-tipo="${escapeHtml(m.tipo || '')}" data-marca="${escapeHtml(m.marca || '')}">${escapeHtml(m.modelo)} (${escapeHtml(m.pn)})</option>`).join('');
                if (this.equipamentoId) sel.value = String(this.equipamentoId);
            } catch (e) { /* o formulário continua utilizável sem a lista */ }
        }

        private async escolherModelo(): Promise<void> {
            const sel = document.getElementById('sel-modelo') as HTMLSelectElement;
            this.equipamentoId = sel.value ? Number(sel.value) : null;
            if (this.equipamentoId) {
                // Ao escolher o modelo, tipo, marca e modelo são preenchidos automaticamente.
                const opcao = sel.selectedOptions[0];
                this.campo('equip_modelo').value = opcao.dataset.modelo || '';
                this.campo('equip_tipo').value = opcao.dataset.tipo || '';
                this.campo('equip_marca').value = opcao.dataset.marca || '';
                await this.carregarPecasDoModelo();
            } else {
                this.pecasModelo = [];
                this.desenharSeletorPecas();
            }
        }

        private async carregarPecasDoModelo(): Promise<void> {
            this.pecasModelo = [];
            if (this.equipamentoId) {
                try {
                    const r = await (await fetch(`/api/modelo-equipamento/${this.equipamentoId}/pecas/`)).json();
                    if (r.status === 'sucesso') this.pecasModelo = r.dados;
                } catch (e) { /* segue sem peças do modelo */ }
            }
            this.desenharSeletorPecas();
        }

        private desenharSeletorPecas(): void {
            const sel = document.getElementById('sel-peca') as HTMLSelectElement;
            sel.innerHTML = '<option value="">Peça do modelo...</option>' + this.pecasModelo.map((p: any) => {
                const preco = p.cotacao_atual ? ` — ${formatarMoeda(p.cotacao_atual.valor)}` : ' — sem cotação';
                return `<option value="${Number(p.id)}">${escapeHtml(p.part_number)} · ${escapeHtml((p.descricao || '').slice(0, 40))}${p.equipamento_completo ? ' [equipamento completo]' : ''}${escapeHtml(preco)}</option>`;
            }).join('');
        }

        private adicionarPecaDoModelo(): void {
            const sel = document.getElementById('sel-peca') as HTMLSelectElement;
            const peca = this.pecasModelo.find((p: any) => String(p.id) === sel.value);
            if (!peca) { Mensagem.aviso('Escolha uma peça do modelo (ou use "+ Item avulso").'); return; }
            this.itens.push({
                peca_id: peca.id, cotacao_id: peca.cotacao_atual ? peca.cotacao_atual.id : null,
                nome: peca.part_number, descricao: peca.descricao || '', part_number: peca.part_number, quantidade: 1,
                valor_base: peca.cotacao_atual ? peca.cotacao_atual.valor : null,
            });
            sel.value = '';
            this.desenharItens();
        }

        // ---------- tabela de itens ----------
        private desenharItens(): void {
            const corpo = document.getElementById('itens-laudo') as HTMLElement;
            const dis = this.editavel ? '' : 'disabled';
            if (!this.itens.length) {
                corpo.innerHTML = '<tr><td colspan="8" class="px-2 py-6 text-center text-slate-500">Nenhuma peça no orçamento.</td></tr>';
            } else {
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
                        const el = inp as HTMLInputElement;
                        const idx = Number(el.dataset.idx);
                        const item = this.itens[idx];
                        const f = el.dataset.f as string;
                        if (f === 'quantidade') item.quantidade = Math.max(1, parseInt(el.value, 10) || 1);
                        else if (f === 'valor_base') { item.valor_base = this.lerNumero(el.value); item.cotacao_id = null; }
                        else (item as any)[f] = el.value;
                        const v = this.valoresDoItem(item, idx);
                        (document.getElementById('un-' + idx) as HTMLElement).textContent = formatarMoeda(v.unitario);
                        (document.getElementById('sub-' + idx) as HTMLElement).textContent = formatarMoeda(v.subtotal);
                        this.atualizarTotal();
                    });
                });
                corpo.querySelectorAll('[data-rm]').forEach((b) => {
                    b.addEventListener('click', () => {
                        // Ao remover a primeira peça, a seguinte passa a ser a "primeira" e recebe os adicionais.
                        this.itens.splice(Number((b as HTMLElement).dataset.rm), 1);
                        this.desenharItens();
                    });
                });
            }
            this.atualizarTotal();
        }

        private atualizarTotal(): void {
            const total = this.itens.reduce((s, i, idx) => s + this.valoresDoItem(i, idx).subtotal, 0);
            (document.getElementById('total-laudo') as HTMLElement).textContent = formatarMoeda(this.arredondar(total));
        }

        // ---------- carregar / preencher ----------
        private async preencherFormulario(d: any): Promise<void> {
            Array.from(this.form.elements).forEach((el) => {
                const nome = (el as HTMLInputElement).name;
                if (!nome || nome === 'cliente_uf' || nome === 'cliente_cidade' || nome === 'aplicar_regra') return;
                if (d[nome] !== undefined && d[nome] !== null) (el as HTMLInputElement).value = d[nome];
            });
            if (d.aplicar_regra !== undefined) {
                this.aplicarRegra = d.aplicar_regra !== false;
                (document.getElementById('chk-regra') as HTMLInputElement).checked = this.aplicarRegra;
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

        private async preencherPorTicket(): Promise<void> {
            const ticket = (document.getElementById('ticket-busca') as HTMLInputElement).value.trim();
            if (!ticket) { Mensagem.aviso('Informe o número do ticket.'); return; }
            try {
                const r = await (await fetch('/api/orcamentos/pre-preenchimento/?ticket=' + encodeURIComponent(ticket))).json();
                if (r.status !== 'sucesso') { Mensagem.aviso(r.mensagem, 'Ticket não encontrado'); return; }
                await this.preencherFormulario(r.dado);
                (document.getElementById('sel-modelo') as HTMLSelectElement).value = this.equipamentoId ? String(this.equipamentoId) : '';
                await this.carregarPecasDoModelo();
                Mensagem.sucesso('Dados da triagem carregados.');
            } catch (e) { Mensagem.erro('Erro ao conectar com o servidor.'); }
        }

        // Preenche este laudo (novo) com os dados de um laudo existente.
        private async copiarDeLaudo(semConfirmar = false): Promise<void> {
            const numero = (document.getElementById('copia-numero') as HTMLInputElement).value.trim();
            if (!numero) { Mensagem.aviso('Informe o número do laudo que será copiado.'); return; }
            const jaTemDados = this.itens.length > 0 || !!this.campo('cliente_nome').value.trim();
            if (jaTemDados && !semConfirmar && !(await Mensagem.confirmar('O que já foi preenchido neste laudo será substituído pelos dados do laudo copiado.', 'Substituir os dados?', 'Sim, copiar'))) return;
            const atualizar = (document.getElementById('copia-atualizar') as HTMLInputElement).checked;
            try {
                const r = await (await fetch(`/api/orcamentos/copiar/?numero=${encodeURIComponent(numero)}${atualizar ? '&atualizar_valores=1' : ''}`)).json();
                if (r.status !== 'sucesso') { Mensagem.aviso(r.mensagem, 'Laudo não encontrado'); return; }
                const d = r.dado;
                await this.preencherFormulario(d);
                (document.getElementById('sel-modelo') as HTMLSelectElement).value = this.equipamentoId ? String(this.equipamentoId) : '';
                this.itens = d.itens.map((i: any) => ({
                    peca_id: i.peca_id, cotacao_id: i.cotacao_id, nome: i.nome, descricao: i.descricao,
                    part_number: i.part_number, quantidade: i.quantidade, valor_base: i.valor_base,
                }));
                await this.carregarPecasDoModelo();
                this.desenharItens();
                const aviso = document.getElementById('aviso-copia') as HTMLElement;
                aviso.innerHTML = `<strong>Copiado do laudo ${escapeHtml(d.origem.numero)}</strong> (${escapeHtml(d.origem.status_nome)}, emitido em ${escapeHtml(formatarDataBr(d.origem.data_emissao))}).
                    Revise os dados, ajuste o que mudou e clique em "Salvar rascunho".`
                    + (d.mudancas_preco.length ? `<ul class="list-disc ml-5 mt-1">${d.mudancas_preco.map((m: string) => `<li>${escapeHtml(m)}</li>`).join('')}</ul>` : (atualizar ? ' As cotações das peças não mudaram.' : ''));
                aviso.classList.remove('hidden');
            } catch (e) { Mensagem.erro('Erro ao conectar com o servidor.'); }
        }

        private async abrir(id: number): Promise<void> {
            try {
                const r = await (await fetch(`/api/orcamentos/${id}/`)).json();
                if (r.status !== 'sucesso') { await Mensagem.erro(r.mensagem); this.desenharItens(); return; }
                await this.aplicarDado(r.dado);
                await this.carregarPecasDoModelo();
            } catch (e) { Mensagem.erro('Erro ao conectar com o servidor.'); }
        }

        private async aplicarDado(d: any): Promise<void> {
            const aviso = document.getElementById('aviso-cotacoes') as HTMLElement;
            const avisos: string[] = d.avisos_cotacao || [];
            aviso.innerHTML = avisos.length
                ? `<strong>Confira antes de emitir:</strong><ul class="list-disc ml-5 mt-1">${avisos.map((a) => `<li>${escapeHtml(a)}</li>`).join('')}</ul>` : '';
            aviso.classList.toggle('hidden', avisos.length === 0);
            this.idOrcamento = d.id;
            this.numero = d.numero;
            this.status = d.status;
            this.alteravel = !!d.alteravel;
            this.modoAlteracao = false;
            await this.preencherFormulario(d);
            (document.getElementById('sel-modelo') as HTMLSelectElement).value = this.equipamentoId ? String(this.equipamentoId) : '';
            this.itens = d.itens.map((i: any) => ({
                peca_id: i.peca_id, cotacao_id: i.cotacao_id, nome: i.nome, descricao: i.descricao,
                part_number: i.part_number, quantidade: i.quantidade, valor_base: i.valor_base,
            }));
            (document.getElementById('sub-emissao') as HTMLElement).textContent = `${d.numero} · ${d.status_nome}`;
            const info = document.getElementById('info-datas') as HTMLElement;
            info.textContent = `Emissão: ${formatarDataBr(d.data_emissao)} · Válido até: ${formatarDataBr(d.validade_ate)}`;
            info.classList.remove('hidden');
            this.atualizarEstado();
            this.desenharItens();
            this.carregarHistorico();
        }

        private atualizarEstado(): void {
            const dis = !this.editavel;
            Array.from(this.form.elements).forEach((el) => {
                if (el.tagName !== 'BUTTON') (el as HTMLInputElement).disabled = dis;
            });
            ['btn-ticket', 'btn-add-peca', 'btn-add-avulso', 'sel-peca'].forEach((id) => ((document.getElementById(id) as any).disabled = dis));
            (document.getElementById('ticket-busca') as HTMLInputElement).disabled = dis;
            const rascunho = this.status === 'rascunho';
            (document.getElementById('btn-salvar') as HTMLElement).classList.toggle('hidden', !rascunho);
            (document.getElementById('btn-emitir') as HTMLElement).classList.toggle('hidden', !rascunho);
            (document.getElementById('btn-alterar') as HTMLElement).classList.toggle('hidden', rascunho || !this.alteravel || this.modoAlteracao);
            (document.getElementById('btn-salvar-alt') as HTMLElement).classList.toggle('hidden', !this.modoAlteracao);
            (document.getElementById('btn-cancelar-alt') as HTMLElement).classList.toggle('hidden', !this.modoAlteracao);
            (document.getElementById('btn-baixar') as HTMLElement).classList.toggle('hidden', !this.idOrcamento);
            const criarCopia = document.getElementById('btn-criar-copia') as HTMLAnchorElement;
            criarCopia.href = `/orcamentos/emissao/?copiar=${encodeURIComponent(this.numero)}`;
            criarCopia.classList.toggle('hidden', !this.idOrcamento || this.status === 'rascunho' || this.modoAlteracao);
            const enviavel = ['emitido', 'aprovado', 'recusado'].includes(this.status) && !this.modoAlteracao;
            (document.getElementById('btn-enviar-email') as HTMLElement).classList.toggle('hidden', !this.idOrcamento || !enviavel);

            const acoes = document.getElementById('acoes-status') as HTMLElement;
            const mostrar = (this.status === 'emitido' || this.status === 'recusado' || this.status === 'aprovado') && !this.modoAlteracao;
            acoes.classList.toggle('hidden', !mostrar);
            acoes.classList.toggle('flex', mostrar);
            acoes.querySelectorAll('.btn-status').forEach((b) => {
                const alvo = (b as HTMLElement).dataset.status;
                const permitido = (this.status === 'emitido' && ['aprovado', 'recusado', 'cancelado'].includes(alvo as string))
                    || (this.status === 'aprovado' && alvo === 'cancelado')
                    || (this.status === 'recusado' && alvo === 'cancelado');
                (b as HTMLElement).classList.toggle('hidden', !permitido);
            });

            const aviso = document.getElementById('aviso-status') as HTMLElement;
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
        private iniciarAlteracao(): void {
            this.modoAlteracao = true;
            this.atualizarEstado();
            this.desenharItens();
            Mensagem.info('Faça as correções e clique em "Salvar alterações". O preço é recalculado automaticamente.', 'Modo de alteração');
        }

        private async cancelarAlteracao(): Promise<void> {
            if (this.idOrcamento) await this.abrir(this.idOrcamento);   // recarrega o que está gravado
        }

        private async salvarAlteracoes(): Promise<void> {
            if (!this.form.reportValidity()) return;
            const motivo = await Mensagem.pedirMotivo('Motivo da alteração', `Este motivo ficará registrado no histórico do laudo ${this.numero}.`);
            if (motivo === null) return;
            const btn = document.getElementById('btn-salvar-alt') as HTMLButtonElement;
            btn.disabled = true;
            try {
                const r = await (await fetch('/api/orcamentos/', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ...this.coletar(), motivo_alteracao: motivo }),
                })).json();
                if (r.status !== 'sucesso') { Mensagem.aviso(r.mensagem, 'Não foi possível alterar o laudo'); return; }
                await this.aplicarDado(r.dado);
                Mensagem.sucesso('Alterações salvas e registradas no histórico.');
                if (await Mensagem.confirmar('Deseja baixar o Word atualizado agora?', 'Laudo atualizado', 'Sim, baixar')) await this.baixar();
            } catch (e) {
                Mensagem.erro('Erro ao conectar com o servidor.');
            } finally {
                btn.disabled = false;
            }
        }

        private async carregarHistorico(): Promise<void> {
            const card = document.getElementById('card-historico') as HTMLElement;
            const lista = document.getElementById('lista-historico') as HTMLElement;
            if (!this.idOrcamento) { card.classList.add('hidden'); return; }
            try {
                const r = await (await fetch(`/api/orcamentos/${this.idOrcamento}/historico/`)).json();
                const itens: any[] = r.status === 'sucesso' ? r.dados : [];
                card.classList.toggle('hidden', itens.length === 0);
                lista.innerHTML = itens.map((h) => `
                    <div class="border border-[#334155] rounded-lg p-3 bg-[#0f172a]/40">
                        <div class="flex flex-wrap justify-between gap-2 text-xs">
                            <span class="font-semibold text-slate-200">${escapeHtml(h.motivo)}</span>
                            <span class="text-slate-500">${escapeHtml(new Date(h.quando).toLocaleString('pt-BR'))} · ${escapeHtml(h.usuario)}</span>
                        </div>
                        <ul class="mt-2 text-[11px] text-slate-400 list-disc pl-4">
                            ${(h.alteracoes || []).map((a: any) => `<li><span class="text-slate-300">${escapeHtml(a.campo)}:</span> ${escapeHtml(a.de)} → <span class="text-cyan-300">${escapeHtml(a.para)}</span></li>`).join('')}
                        </ul>
                    </div>`).join('');
            } catch (e) { card.classList.add('hidden'); }
        }

        // ---------- salvar / emitir / baixar ----------
        private coletar(): any {
            const dados: any = { id: this.idOrcamento, triagem_id: this.triagemId, equipamento_id: this.equipamentoId };
            Array.from(this.form.elements).forEach((el) => {
                const nome = (el as HTMLInputElement).name;
                if (nome) dados[nome] = (el as HTMLInputElement).value;
            });
            // O servidor recalcula valor com margem e adicionais; envia só o valor da peça.
            dados.aplicar_regra = this.aplicarRegra;
            dados.itens = this.itens.map((i) => ({
                peca_id: i.peca_id, cotacao_id: i.cotacao_id, nome: i.nome, descricao: i.descricao,
                part_number: i.part_number, quantidade: i.quantidade, valor_base: i.valor_base === null ? '' : i.valor_base,
            }));
            return dados;
        }

        private async salvar(silencioso = false): Promise<boolean> {
            const btn = document.getElementById('btn-salvar') as HTMLButtonElement;
            btn.disabled = true;
            try {
                const r = await (await fetch('/api/orcamentos/', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.coletar()),
                })).json();
                if (r.status !== 'sucesso') { Mensagem.erro(r.mensagem, 'Não foi possível salvar'); return false; }
                await this.aplicarDado(r.dado);
                window.history.replaceState(null, '', `?id=${r.dado.id}`);
                if (!silencioso) Mensagem.sucesso('Laudo salvo como rascunho.');
                return true;
            } catch (e) {
                Mensagem.erro('Erro ao conectar com o servidor.');
                return false;
            } finally {
                btn.disabled = false;
            }
        }

        private nomeSugerido(): string {
            const cliente = this.campo('cliente_nome').value.trim().replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_+|_+$/g, '');
            return `Laudo_${this.numero}${cliente ? '_' + cliente : ''}`;
        }

        private async baixar(): Promise<void> {
            if (!this.idOrcamento) return;
            await baixarDocumento(`/api/orcamentos/${this.idOrcamento}/docx/`, this.nomeSugerido());
        }

        private async enviarPorEmail(): Promise<void> {
            if (!this.idOrcamento) return;
            const dados = await Mensagem.pedirEmail(this.campo('cliente_email').value.trim());
            if (!dados) return;
            const btn = document.getElementById('btn-enviar-email') as HTMLButtonElement;
            btn.disabled = true;
            try {
                const res = await (await fetch(`/api/orcamentos/${this.idOrcamento}/enviar-email/`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados)
                })).json();
                if (res.status === 'sucesso') await Mensagem.sucesso(res.mensagem);
                else await Mensagem.erro(res.mensagem);
            } catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            } finally {
                btn.disabled = false;
            }
        }

        private async emitir(): Promise<void> {
            if (!this.form.reportValidity()) return;
            if (!(await Mensagem.confirmar('Depois de emitido, o laudo não poderá mais ser editado.', 'Emitir o laudo?', 'Sim, emitir'))) return;
            if (!(await this.salvar(true))) return;
            if (await this.mudarStatus('emitido', false)) {
                await this.baixar();   // pergunta o nome do arquivo e baixa
            }
        }

        private async mudarStatus(novo: string, confirmar = true): Promise<boolean> {
            if (!this.idOrcamento) return false;
            const nomes: Record<string, string> = { emitido: 'Emitido', aprovado: 'Aprovado', recusado: 'Recusado', cancelado: 'Cancelado' };
            let motivo = '';
            if (confirmar && novo === 'recusado') {
                const escolhido = await Mensagem.motivoRecusa(this.numero);   // já serve de confirmação
                if (escolhido === null) return false;
                motivo = escolhido;
            } else if (confirmar && !(await Mensagem.confirmar(`O laudo ${this.numero} será marcado como "${nomes[novo] || novo}".`, 'Mudar o status?', 'Sim, mudar'))) return false;
            try {
                const r = await (await fetch(`/api/orcamentos/${this.idOrcamento}/status/`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: novo, motivo_recusa: motivo }),
                })).json();
                if (r.status !== 'sucesso') { Mensagem.aviso(r.mensagem, 'Não foi possível mudar o status'); return false; }
                await this.aplicarDado(r.dado);
                if (confirmar) Mensagem.sucesso(r.mensagem);
                return true;
            } catch (e) {
                Mensagem.erro('Erro ao conectar com o servidor.');
                return false;
            }
        }
    }
    document.addEventListener('DOMContentLoaded', () => new EmissaoLaudosUI());
})();
