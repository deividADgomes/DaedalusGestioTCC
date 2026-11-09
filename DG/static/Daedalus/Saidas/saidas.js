"use strict";
/// <reference path="../BaseUI.ts" />
(() => {
    const COR = {
        rascunho: 'bg-slate-600/30 text-slate-300', enviada: 'bg-amber-500/20 text-amber-300',
        nota_emitida: 'bg-emerald-500/20 text-emerald-300', cancelada: 'bg-rose-500/20 text-rose-300',
    };
    // Ordem das colunas da planilha da operação, usada para colar linhas do Excel.
    const CAMPOS_PLANILHA = ['ticket', 'cliente', 'equipamento', 'descricao', 'quantidade', 'part_number', 'destinatario', 'telefone',
        'cidade', 'estado', 'data_solicitacao', 'numero_nf', 'rastreio', 'observacao'];
    const el = (id) => document.getElementById(id);
    const valor = (id) => (el(id).value || '').trim();
    const dataBr = (d) => /^\d{4}-\d{2}-\d{2}$/.test(d) ? d.split('-').reverse().join('/') : d;
    class Saidas {
        constructor() {
            this.atual = this.vazia();
            this.config = { fiscal_email: '', email_ativo: false };
            this.catalogo = {};
            const params = new URLSearchParams(window.location.search);
            if (params.get('status'))
                el('lista-status').value = params.get('status');
            el('lista-busca').addEventListener('input', () => { window.clearTimeout(this.temporizador); this.temporizador = window.setTimeout(() => this.carregarLista(), 300); });
            el('lista-status').addEventListener('change', () => this.carregarLista());
            el('btn-nova-saida').addEventListener('click', () => this.abrirEditor(this.vazia()));
            el('btn-voltar').addEventListener('click', () => this.voltar());
            el('btn-add-item').addEventListener('click', () => this.adicionarDoFormulario());
            el('btn-limpar-destino').addEventListener('click', () => this.limparDestino());
            el('btn-colar').addEventListener('click', () => this.colarPlanilha());
            el('i-pn').addEventListener('input', () => this.sugerirPecas());
            el('i-pn').addEventListener('change', () => this.aoEscolherPn());
            el('lista-linhas').addEventListener('click', (e) => {
                const linha = e.target.closest('[data-id]');
                if (linha)
                    this.abrir(Number(linha.dataset.id));
            });
            el('itens-linhas').addEventListener('click', (e) => this.aoClicarNosItens(e));
            this.carregarLista().then(() => { const id = Number(params.get('id')); if (id)
                this.abrir(id); });
        }
        vazia() { return { status: 'rascunho', observacao: '', itens: [] }; }
        // ---------------------------------------------------------------- lista
        async carregarLista() {
            const q = encodeURIComponent(valor('lista-busca'));
            const status = el('lista-status').value;
            try {
                const res = await (await fetch(`/api/saidas/?q=${q}&status=${status}`)).json();
                if (res.status !== 'sucesso') {
                    await Mensagem.erro(res.mensagem);
                    return;
                }
                this.config = res.config;
                el('lista-vazia').classList.toggle('hidden', res.dados.length > 0);
                const resumo = (v, max) => v.length === 0 ? '—' : v.slice(0, max).join(', ') + (v.length > max ? ` +${v.length - max}` : '');
                el('lista-linhas').innerHTML = res.dados.map((s) => `
                    <tr data-id="${s.id}" class="cursor-pointer hover:bg-[#0f172a]">
                        <td class="px-4 py-2.5 font-mono text-cyan-300">${escapeHtml(s.numero)}</td>
                        <td class="px-4 py-2.5 text-slate-400">${escapeHtml(new Date(s.criado_em).toLocaleDateString('pt-BR'))}</td>
                        <td class="px-4 py-2.5">${escapeHtml(resumo(s.tickets, 3))}</td>
                        <td class="px-4 py-2.5 text-slate-300">${escapeHtml(resumo(s.destinatarios, 2))}</td>
                        <td class="px-4 py-2.5 text-right">${Number(s.total_itens)}</td>
                        <td class="px-4 py-2.5 text-right">${Number(s.com_nf)}/${Number(s.total_itens)}</td>
                        <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${COR[s.status] || ''}">${escapeHtml(s.status_nome)}</span></td>
                        <td class="px-4 py-2.5 text-right text-cyan-300">Abrir</td>
                    </tr>`).join('');
            }
            catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }
        async abrir(id) {
            try {
                const res = await (await fetch(`/api/saidas/${id}/`)).json();
                if (res.status !== 'sucesso') {
                    await Mensagem.erro(res.mensagem);
                    return;
                }
                this.abrirEditor(res.dado);
            }
            catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }
        voltar() {
            el('vista-editor').classList.add('hidden');
            el('vista-lista').classList.remove('hidden');
            this.carregarLista();
        }
        // ---------------------------------------------------------------- editor
        abrirEditor(s) {
            this.atual = s;
            el('vista-lista').classList.add('hidden');
            el('vista-editor').classList.remove('hidden');
            el('editor-titulo').innerText = s.id ? `Lista ${s.numero}` : 'Nova lista';
            el('s-observacao').value = s.observacao;
            el('s-observacao').disabled = s.status !== 'rascunho';
            el('bloco-adicionar').classList.toggle('hidden', s.status !== 'rascunho');
            if (!el('i-data').value)
                el('i-data').value = new Date().toISOString().slice(0, 10);
            this.desenharBanner();
            this.desenharItens();
            this.desenharAcoes();
        }
        desenharBanner() {
            const s = this.atual, b = el('editor-banner');
            const f = (d) => d ? new Date(d).toLocaleString('pt-BR') : '';
            let html = '', classe = '';
            if (s.status === 'enviada' || s.status === 'nota_emitida') {
                const cheia = s.status === 'nota_emitida';
                classe = cheia ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200' : 'border-amber-500/40 bg-amber-500/10 text-amber-200';
                html = `Enviada ao fiscal em ${escapeHtml(f(s.enviado_em))} por ${escapeHtml(s.enviado_por || '—')}${s.emails_fiscal ? ' (e-mail para ' + escapeHtml(s.emails_fiscal) + ')' : ''}.
                    Os itens do nosso estoque já foram baixados. ${cheia ? 'Todas as linhas têm NF.' : 'Preencha a NF e o rastreio de cada linha conforme o fiscal for emitindo.'}`;
            }
            else if (s.status === 'cancelada') {
                classe = 'border-rose-500/40 bg-rose-500/10 text-rose-200';
                html = `Cancelada em ${escapeHtml(f(s.cancelado_em))}${s.motivo_cancelamento ? ': ' + escapeHtml(s.motivo_cancelamento) : ''}.`;
            }
            b.className = `${html ? '' : 'hidden '}rounded-xl border px-5 py-3 text-xs ${classe}`;
            b.innerHTML = html;
        }
        desenharItens() {
            const s = this.atual;
            const rascunho = s.status === 'rascunho';
            const retorno = s.status === 'enviada' || s.status === 'nota_emitida'; // NF e rastreio são preenchidos agora
            el('itens-vazio').classList.toggle('hidden', s.itens.length > 0);
            const caixa = el('itens-avisos');
            const avisos = s.avisos || [];
            caixa.classList.toggle('hidden', avisos.length === 0);
            caixa.innerHTML = avisos.length ? `<strong>Atenção:</strong> ${avisos.map((a) => escapeHtml(a)).join(' ')}` : '';
            const campoRetorno = (i, campo, v) => retorno
                ? `<input class="cx-tabela" data-id="${i.id}" data-campo="${campo}" value="${escapeHtml(v)}" maxlength="${campo === 'rastreio' ? 100 : campo === 'observacao' ? 500 : 30}">`
                : escapeHtml(v || '—');
            el('itens-linhas').innerHTML = s.itens.map((i, n) => `
                <tr>
                    <td class="px-2 py-2">${escapeHtml(i.ticket || '—')}</td>
                    <td class="px-2 py-2">${escapeHtml(i.cliente || '—')}</td>
                    <td class="px-2 py-2">${escapeHtml(i.equipamento || '—')}</td>
                    <td class="px-2 py-2 text-slate-300">${escapeHtml(i.descricao || '—')}</td>
                    <td class="px-2 py-2 text-right font-bold">${i.quantidade}</td>
                    <td class="px-2 py-2 font-mono text-cyan-300">${escapeHtml(i.part_number)}${i.origem === 'externa' ? '<span class="block text-[10px] text-amber-300 font-sans">fora do estoque</span>' : ''}</td>
                    <td class="px-2 py-2">${escapeHtml(i.destinatario)}</td>
                    <td class="px-2 py-2">${escapeHtml(i.telefone || '—')}</td>
                    <td class="px-2 py-2">${escapeHtml(i.cidade)}/${escapeHtml(i.estado)}</td>
                    <td class="px-2 py-2">${escapeHtml(dataBr(i.data_solicitacao))}</td>
                    <td class="px-2 py-2">${campoRetorno(i, 'numero_nf', i.numero_nf)}</td>
                    <td class="px-2 py-2">${campoRetorno(i, 'rastreio', i.rastreio)}</td>
                    <td class="px-2 py-2">${campoRetorno(i, 'observacao', i.observacao)}</td>
                    <td class="px-2 py-2 text-right">${rascunho ? `<button type="button" data-editar="${n}" class="text-[10px] font-bold uppercase text-cyan-300 hover:text-cyan-200 mr-2">Editar</button><button type="button" data-remover="${n}" class="text-[10px] font-bold uppercase text-rose-400 hover:text-rose-300">Remover</button>` : ''}</td>
                </tr>`).join('');
        }
        aoClicarNosItens(e) {
            const alvo = e.target;
            const remover = alvo.closest('[data-remover]');
            const editar = alvo.closest('[data-editar]');
            if (remover) {
                this.atual.itens.splice(Number(remover.dataset.remover), 1);
                this.desenharItens();
            }
            if (editar) { // volta a linha para o formulário para ajustar e adicionar de novo
                const [i] = this.atual.itens.splice(Number(editar.dataset.editar), 1);
                this.preencherFormulario(i);
                this.desenharItens();
            }
        }
        // ---------------------------------------------------------------- formulário de uma linha
        preencherFormulario(i) {
            const m = {
                'i-ticket': i.ticket, 'i-cliente': i.cliente, 'i-equip': i.equipamento, 'i-pn': i.part_number, 'i-desc': i.descricao,
                'i-qtd': String(i.quantidade), 'i-dest': i.destinatario, 'i-tel': i.telefone, 'i-cidade': i.cidade, 'i-uf': i.estado, 'i-obs': i.observacao
            };
            Object.keys(m).forEach((id) => { el(id).value = m[id]; });
            el('i-origem').value = i.origem === 'estoque' || i.origem === 'externa' ? i.origem : 'auto';
            const iso = /^\d{4}-\d{2}-\d{2}$/.test(i.data_solicitacao) ? i.data_solicitacao : '';
            if (iso)
                el('i-data').value = iso;
            el('i-dica').innerText = '';
        }
        adicionarDoFormulario() {
            const pn = valor('i-pn').replace(/\s+/g, '').toUpperCase();
            const qtd = parseInt(valor('i-qtd'), 10);
            const uf = valor('i-uf').toUpperCase();
            if (!pn) {
                Mensagem.aviso('Informe o PN.');
                return;
            }
            if (!qtd || qtd < 1) {
                Mensagem.aviso('Informe a quantidade.');
                return;
            }
            if (!valor('i-dest') || !valor('i-cidade') || uf.length !== 2) {
                Mensagem.aviso('Informe o destinatário, a cidade e a UF (2 letras): o fiscal precisa deles para a nota.');
                return;
            }
            this.atual.itens.push({
                ticket: valor('i-ticket'), cliente: valor('i-cliente'), equipamento: valor('i-equip'), descricao: valor('i-desc'), quantidade: qtd,
                part_number: pn, origem: el('i-origem').value, destinatario: valor('i-dest'), telefone: valor('i-tel'),
                cidade: valor('i-cidade'), estado: uf, data_solicitacao: valor('i-data'), numero_nf: '', rastreio: '', observacao: valor('i-obs')
            });
            // Mantém ticket, cliente, equipamento e destino: o mais comum é lançar várias peças do mesmo chamado.
            ['i-pn', 'i-desc', 'i-obs'].forEach((id) => { el(id).value = ''; });
            el('i-qtd').value = '1';
            el('i-origem').value = 'auto';
            el('i-dica').innerText = '';
            this.desenharItens();
            el('i-pn').focus();
        }
        limparDestino() {
            ['i-ticket', 'i-cliente', 'i-equip', 'i-dest', 'i-tel', 'i-cidade', 'i-uf'].forEach((id) => { el(id).value = ''; });
            el('i-ticket').focus();
        }
        sugerirPecas() {
            window.clearTimeout(this.temporizadorPn);
            this.temporizadorPn = window.setTimeout(async () => {
                const termo = valor('i-pn');
                if (termo.length < 2)
                    return;
                try {
                    const res = await (await fetch(`/api/estoque/catalogo/?q=${encodeURIComponent(termo)}`)).json();
                    (res.dados || []).forEach((p) => { this.catalogo[p.part_number] = { descricao: p.descricao || '', saldo: p.saldo, controlada: p.controlada }; });
                    el('dl-pecas').innerHTML = (res.dados || []).map((p) => `<option value="${escapeHtml(p.part_number)}">${escapeHtml((p.descricao || '').slice(0, 60))}</option>`).join('');
                }
                catch (e) { /* sem sugestões: o PN pode ser digitado */ }
            }, 250);
        }
        aoEscolherPn() {
            const pn = valor('i-pn').replace(/\s+/g, '').toUpperCase();
            el('i-pn').value = pn;
            const peca = this.catalogo[pn];
            if (peca) {
                if (!valor('i-desc'))
                    el('i-desc').value = peca.descricao;
                el('i-dica').innerText = peca.controlada ? `Peça do catálogo. Saldo em estoque: ${peca.saldo}.` : 'Peça do catálogo, ainda sem controle de estoque (saldo 0).';
            }
            else if (pn) {
                el('i-dica').innerText = 'PN fora do catálogo: a linha consta na lista para o fiscal, mas não dá baixa no nosso estoque.';
            }
        }
        // ---------------------------------------------------------------- colar da planilha
        colarPlanilha() {
            const texto = el('colar-planilha').value;
            const linhas = texto.split(/\r?\n/).filter((l) => l.trim() !== '');
            if (linhas.length === 0) {
                Mensagem.aviso('Cole as linhas copiadas da planilha.');
                return;
            }
            const separador = linhas[0].includes('\t') ? '\t' : ';';
            let novas = 0;
            linhas.forEach((linha, n) => {
                const c = linha.split(separador).map((x) => x.trim());
                if (n === 0 && c[0].toLowerCase() === 'ticket')
                    return; // cabeçalho
                const item = { origem: 'auto', id: undefined };
                CAMPOS_PLANILHA.forEach((campo, k) => { item[campo] = c[k] ?? ''; });
                item.quantidade = parseInt(item.quantidade, 10) || 0; // vazia/inválida: o servidor aponta a linha
                item.part_number = String(item.part_number).replace(/\s+/g, '').toUpperCase();
                this.atual.itens.push(item);
                novas++;
            });
            el('colar-planilha').value = '';
            this.desenharItens();
            Mensagem.sucesso(`${novas} linha(s) importada(s). Confira e use "Salvar rascunho": o sistema valida cada linha.`);
        }
        // ---------------------------------------------------------------- ações
        desenharAcoes() {
            const s = this.atual;
            const botao = (id, texto, cor) => `<button type="button" id="${id}" class="px-5 py-2.5 rounded-lg text-sm font-semibold text-white ${cor} transition-colors">${texto}</button>`;
            let html = '';
            if (s.status === 'rascunho') {
                html += botao('ac-salvar', 'Salvar rascunho', 'bg-slate-600 hover:bg-slate-500');
                html += botao('ac-enviar', 'Enviar ao fiscal', 'bg-cyan-600 hover:bg-cyan-500');
                if (s.id)
                    html += botao('ac-cancelar', 'Cancelar lista', 'bg-rose-700 hover:bg-rose-600');
            }
            else if (s.status === 'enviada' || s.status === 'nota_emitida') {
                html += botao('ac-retorno', 'Salvar NF e rastreio', 'bg-emerald-600 hover:bg-emerald-500');
                html += botao('ac-nf-geral', 'Mesma NF para as linhas sem NF', 'bg-slate-600 hover:bg-slate-500');
                if (s.status === 'enviada')
                    html += botao('ac-cancelar', 'Cancelar e devolver ao estoque', 'bg-rose-700 hover:bg-rose-600');
            }
            if (s.id)
                html += botao('ac-csv', 'Baixar lista (CSV)', 'bg-slate-700 hover:bg-slate-600');
            el('editor-acoes').innerHTML = html;
            const ligar = (id, fn) => document.getElementById(id)?.addEventListener('click', fn);
            ligar('ac-salvar', () => this.salvar(true));
            ligar('ac-enviar', () => this.enviar());
            ligar('ac-retorno', () => this.salvarRetorno());
            ligar('ac-nf-geral', () => this.nfGeral());
            ligar('ac-cancelar', () => this.cancelar());
            ligar('ac-csv', () => { window.location.href = `/api/saidas/${s.id}/csv/`; });
        }
        corpo() {
            return {
                id: this.atual.id, observacao: valor('s-observacao'),
                itens: this.atual.itens.map((i) => ({
                    ticket: i.ticket, cliente: i.cliente, equipamento: i.equipamento, descricao: i.descricao, quantidade: i.quantidade, part_number: i.part_number,
                    origem: i.origem, destinatario: i.destinatario, telefone: i.telefone, cidade: i.cidade, estado: i.estado,
                    data_solicitacao: i.data_solicitacao, numero_nf: i.numero_nf, rastreio: i.rastreio, observacao: i.observacao
                }))
            };
        }
        async requisitar(url, corpo) {
            try {
                return await (await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) })).json();
            }
            catch (e) {
                return { status: 'erro', mensagem: 'Erro ao conectar com o servidor.' };
            }
        }
        async salvar(avisar) {
            const res = await this.requisitar('/api/saidas/', this.corpo());
            if (res.status !== 'sucesso') {
                await Mensagem.erro(res.mensagem);
                return false;
            }
            this.abrirEditor(res.dado);
            if (avisar)
                Mensagem.sucesso(res.mensagem);
            return true;
        }
        async enviar() {
            if (!(await this.salvar(false)))
                return;
            const s = this.atual;
            const doEstoque = s.itens.filter((i) => i.origem === 'estoque').reduce((t, i) => t + i.quantidade, 0);
            const r = await Swal.fire({
                title: `Enviar ${s.numero} ao fiscal?`,
                html: `<p style="font-size:13px;margin-bottom:10px">${s.itens.length} linha(s). ${doEstoque ? `Vão sair do nosso estoque ${doEstoque} unidade(s). ` : 'Nenhum item sai do nosso estoque. '}Depois de enviada, as linhas não podem mais ser alteradas (só NF, rastreio e observação).</p>
                    <label style="display:flex;gap:8px;align-items:center;font-size:13px;margin-bottom:8px"><input type="checkbox" id="en-email" ${this.config.email_ativo ? 'checked' : 'disabled'}> Enviar a lista por e-mail ao fiscal${this.config.email_ativo ? '' : ' (e-mail não configurado)'}</label>
                    <input id="en-dest" class="swal2-input" style="width:100%;margin:4px 0" placeholder="E-mail(s) do fiscal, separados por vírgula" value="${escapeHtml(this.config.fiscal_email)}">
                    <textarea id="en-msg" class="swal2-textarea" style="width:100%;margin:4px 0" placeholder="Mensagem ao fiscal (opcional)"></textarea>`,
                showCancelButton: true, confirmButtonText: 'Enviar', cancelButtonText: 'Voltar', confirmButtonColor: '#0891b2',
                preConfirm: () => ({ enviar_email: document.getElementById('en-email').checked,
                    destinatarios: document.getElementById('en-dest').value.trim(), mensagem: document.getElementById('en-msg').value })
            });
            if (!r.isConfirmed)
                return;
            const res = await this.requisitar(`/api/saidas/${s.id}/enviar/`, r.value);
            if (res.status !== 'sucesso') {
                await Mensagem.erro(res.mensagem);
                return;
            }
            this.abrirEditor(res.dado);
            Mensagem.sucesso(res.mensagem);
        }
        async salvarRetorno() {
            const porId = {};
            document.querySelectorAll('#itens-linhas input[data-id]').forEach((campo) => {
                const c = campo;
                const id = Number(c.dataset.id);
                (porId[id] = porId[id] || { id })[c.dataset.campo] = c.value;
            });
            const res = await this.requisitar(`/api/saidas/${this.atual.id}/retorno/`, { linhas: Object.values(porId) });
            if (res.status !== 'sucesso') {
                await Mensagem.erro(res.mensagem);
                return;
            }
            this.abrirEditor(res.dado);
            Mensagem.sucesso(res.mensagem);
        }
        async nfGeral() {
            const r = await Swal.fire({
                title: 'Mesma NF para as linhas sem NF', input: 'text', inputPlaceholder: 'Número da nota fiscal',
                inputValidator: (v) => v.trim() ? undefined : 'Informe o número da nota.',
                showCancelButton: true, confirmButtonText: 'Aplicar', cancelButtonText: 'Voltar', confirmButtonColor: '#059669'
            });
            if (!r.isConfirmed)
                return;
            const res = await this.requisitar(`/api/saidas/${this.atual.id}/nota/`, { numero_nf: r.value });
            if (res.status !== 'sucesso') {
                await Mensagem.erro(res.mensagem);
                return;
            }
            this.abrirEditor(res.dado);
            Mensagem.sucesso(res.mensagem);
        }
        async cancelar() {
            const enviada = this.atual.status === 'enviada';
            const r = await Swal.fire({
                title: `Cancelar ${this.atual.numero || 'a lista'}?`,
                text: enviada ? 'As peças que saíram do nosso estoque voltam ao saldo. Informe o motivo.' : 'O rascunho será marcado como cancelado.',
                input: 'text', inputPlaceholder: enviada ? 'Motivo (obrigatório)' : 'Motivo (opcional)',
                inputValidator: (v) => (enviada && !v.trim()) ? 'Informe o motivo.' : undefined,
                showCancelButton: true, confirmButtonText: 'Cancelar lista', cancelButtonText: 'Voltar', confirmButtonColor: '#e11d48'
            });
            if (!r.isConfirmed)
                return;
            const res = await this.requisitar(`/api/saidas/${this.atual.id}/cancelar/`, { motivo: r.value || '' });
            if (res.status !== 'sucesso') {
                await Mensagem.erro(res.mensagem);
                return;
            }
            this.abrirEditor(res.dado);
            Mensagem.sucesso(res.mensagem);
        }
    }
    window.addEventListener('DOMContentLoaded', () => { new Saidas(); });
})();
