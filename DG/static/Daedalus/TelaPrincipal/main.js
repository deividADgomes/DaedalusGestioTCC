"use strict";
/// <reference path="../BaseUI.ts" />
(() => {
    // System board = PN terminado em -601. Nesses casos a triagem pede o CT (o número de série da placa).
    const ehSystem = (pn, texto) => /-601$/i.test((pn || '').trim()) || /-601\b/i.test(texto || '');
    class G_triagemUI extends BaseUI {
        constructor() {
            super();
            this.idAtual = null;
            // Motivos possíveis para uma troca indevida (a lista vem do servidor, para ser ampliada num lugar só).
            this.motivoOutro = 'Outro';
            // IDs ALINHADOS COM O SEU HTML:
            this.btnSalvar = document.getElementById('btn-salvar');
            this.btnLimpar = document.getElementById('btn-limpar');
            this.form = document.getElementById('form-triagem');
            this.selectEstado = document.getElementById('Estado');
            this.selectCidade = document.getElementById('Cidade');
            this.toggleStatus = document.getElementById('funcional');
            this.statusTexto = document.getElementById('status-texto');
            this.iniciarEventos();
            this.preencherDataHoje();
            // Com ?id= na URL a tela abre em modo de edição (vem do botão "Editar" da visualização do laudo)
            this.carregarDropdowns().then(() => this.iniciarEdicaoSeHouver());
        }
        async carregarMotivosIndevida() {
            try {
                const r = await (await fetch('/api/triagem/opcoes/')).json();
                if (r.status !== 'sucesso')
                    return;
                this.motivoOutro = r.dados.motivo_outro;
                const select = document.getElementById('motivo-indevida');
                const atual = select.value;
                select.innerHTML = '<option value="">Selecione o motivo...</option>';
                r.dados.motivos_troca_indevida.forEach((m) => select.add(new Option(m, m)));
                select.value = atual;
            }
            catch (e) { /* sem a lista, o formulário avisa na hora de salvar */ }
        }
        // Só pede o motivo quando a troca foi indevida; "Outro" exige a explicação.
        atualizarMotivoIndevida() {
            const indevida = document.getElementById('troca-indevida').value === 'sim';
            const motivo = document.getElementById('motivo-indevida');
            const just = document.getElementById('justificativa-indevida');
            document.getElementById('grupo-motivo-indevida').classList.toggle('hidden', !indevida);
            document.getElementById('grupo-justificativa-indevida').classList.toggle('hidden', !indevida);
            if (!indevida) {
                motivo.value = '';
                just.value = '';
                just.classList.remove('has-value');
                return;
            }
            document.getElementById('rotulo-justificativa-indevida').innerText =
                motivo.value === this.motivoOutro ? 'Descreva o motivo (obrigatório)' : 'Explicação (opcional)';
        }
        iniciarEventos() {
            this.carregarMotivosIndevida();
            document.getElementById('troca-indevida').addEventListener('change', () => this.atualizarMotivoIndevida());
            document.getElementById('motivo-indevida').addEventListener('change', () => this.atualizarMotivoIndevida());
            this.btnSalvar.addEventListener('click', () => this.salvarTriagem());
            this.btnLimpar.addEventListener('click', () => {
                if (this.idAtual) {
                    window.location.href = `/visualizar/?id=${this.idAtual}`;
                    return;
                } // em edição, vira "Cancelar"
                this.limparFormulario();
            });
            // Reincidência: avisa se este número de série já passou pela triagem antes
            document.getElementById('nserie').addEventListener('change', () => this.verificarReincidencia());
            // Peça trocada: a lista vem das peças cadastradas no modelo escolhido
            document.getElementById('equipamento').addEventListener('change', (e) => {
                this.carregarPecasDoModelo(parseInt(e.target.value, 10) || 0);
            });
            document.getElementById('peca-trocada').addEventListener('change', () => this.atualizarCampoTroca());
            document.getElementById('troca').addEventListener('input', () => this.atualizarCampoCt());
            document.getElementById('ct').addEventListener('input', (e) => { e.target.value = e.target.value.toUpperCase(); });
            // Lógica IBGE: Ao trocar o estado, puxa as cidades
            this.selectEstado.addEventListener('change', () => {
                const uf = this.selectEstado.value;
                if (uf) {
                    this.carregarCidadesIBGE(uf);
                    this.selectEstado.classList.add('has-value');
                }
                else {
                    this.selectCidade.innerHTML = '<option value="" disabled selected></option>';
                    this.selectCidade.disabled = true;
                    this.selectCidade.classList.remove('has-value');
                }
            });
            this.selectCidade.addEventListener('change', () => {
                this.selectCidade.classList.add('has-value');
            });
            // Lógica do Toggle Switch
            this.toggleStatus.addEventListener('change', () => {
                if (this.toggleStatus.checked) {
                    this.statusTexto.innerText = "Funcional";
                    this.statusTexto.classList.replace("text-rose-400", "text-emerald-400");
                }
                else {
                    this.statusTexto.innerText = "Defeito";
                    this.statusTexto.classList.replace("text-emerald-400", "text-rose-400");
                }
            });
        }
        preencherDataHoje() {
            const dataInput = document.getElementById('data');
            const hoje = new Date();
            dataInput.value = hoje.toLocaleDateString('pt-BR');
        }
        async carregarCidadesIBGE(uf, cidadePreSelecionada) {
            this.selectCidade.innerHTML = '<option value="" disabled selected>Buscando...</option>';
            this.selectCidade.disabled = true;
            try {
                const req = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${uf}/municipios`);
                if (!req.ok)
                    throw new Error("UF inválida");
                const cidades = await req.json();
                this.selectCidade.innerHTML = '<option value="" disabled selected></option>';
                cidades.forEach((cidade) => {
                    this.selectCidade.appendChild(new Option(cidade.nome, cidade.nome));
                });
                this.selectCidade.disabled = false;
                if (cidadePreSelecionada) {
                    this.selectCidade.value = cidadePreSelecionada;
                    this.selectCidade.classList.add('has-value');
                }
            }
            catch (error) {
                this.selectCidade.innerHTML = '<option value="" disabled selected></option>';
            }
        }
        async carregarDropdowns() {
            try {
                const [respClientes, respEquips, respTecnicos, respAnalistas] = await Promise.all([
                    fetch('/api/empresa/?tipo=2').then(r => r.json()),
                    fetch('/api/modelo-equipamento/').then(r => r.json()),
                    fetch('/api/tecnico/').then(r => r.json()),
                    fetch('/api/funcionario/').then(r => r.json())
                ]);
                const selectCliente = document.getElementById('cliente');
                selectCliente.innerHTML = '<option value="" disabled selected>Selecione...</option>';
                if (respClientes.status === 'sucesso') {
                    respClientes.dados.forEach((cli) => selectCliente.add(new Option(cli.razao_social || cli.nome, cli.id)));
                }
                const selectEquip = document.getElementById('equipamento');
                selectEquip.innerHTML = '<option value="" disabled selected>Selecione...</option>';
                if (respEquips.status === 'sucesso') {
                    respEquips.dados.forEach((eq) => selectEquip.add(new Option(`${eq.pn} - ${escapeHtml(eq.modelo)}`, eq.id)));
                }
                const selectTecnico = document.getElementById('tecnico');
                selectTecnico.innerHTML = '<option value="" disabled selected>Selecione...</option>';
                if (respTecnicos.status === 'sucesso') {
                    respTecnicos.dados.forEach((tec) => {
                        const textoOpcao = `${escapeHtml(tec.nome)} (${escapeHtml(tec.nome_empresa)})`;
                        selectTecnico.add(new Option(textoOpcao, tec.id));
                    });
                }
                const selectAnalista = document.getElementById('analista');
                selectAnalista.innerHTML = '<option value="" disabled selected>Selecione...</option>';
                if (respAnalistas.status === 'sucesso') {
                    respAnalistas.dados.forEach((func) => {
                        if (func.cargo && func.cargo !== 'Administrador') {
                            selectAnalista.add(new Option(func.nome + ' - ' + func.cargo, func.id));
                        }
                    });
                }
            }
            catch (error) {
                console.error("Erro ao carregar selects:", error);
            }
        }
        async verificarReincidencia() {
            const aviso = document.getElementById('aviso-serie');
            const sn = document.getElementById('nserie').value.trim();
            aviso.classList.add('hidden');
            if (!sn)
                return;
            try {
                const r = await (await fetch(`/api/triagem/por-serie/?sn=${encodeURIComponent(sn)}&excluir=${this.idAtual || ''}`)).json();
                if (r.status !== 'sucesso' || r.dados.length === 0)
                    return;
                const itens = r.dados.slice(0, 3).map((t) => {
                    const data = t.criado_em ? new Date(t.criado_em).toLocaleDateString('pt-BR') : 'sem data';
                    return `<li>Ticket <a class="underline" href="/visualizar/?id=${Number(t.id)}">#${escapeHtml(String(t.n_ticket))}</a> em ${escapeHtml(data)}: ${escapeHtml(t.status)}${t.cliente ? ' (' + escapeHtml(t.cliente) + ')' : ''}</li>`;
                }).join('');
                const mais = r.dados.length > 3 ? ` e mais ${r.dados.length - 3}` : '';
                aviso.innerHTML = `<strong>Reincidência:</strong> este número de série já foi triado ${r.dados.length} vez(es)${mais}.
                    <ul class="list-disc ml-5 mt-1">${itens}</ul>
                    <a class="underline mt-1 inline-block" href="/serie/?sn=${encodeURIComponent(sn)}">Ver a linha do tempo completa</a>`;
                aviso.classList.remove('hidden');
            }
            catch (e) { /* o aviso é um extra: se falhar, a triagem segue normal */ }
        }
        // Monta a lista "Peça / Equipamento Trocado" com as peças do modelo (mais "nenhuma" e "outra, digitar").
        montarOpcoesPeca(pecas) {
            const select = document.getElementById('peca-trocada');
            select.innerHTML = '';
            select.add(new Option('Nenhuma peça trocada', ''));
            pecas.forEach((p) => {
                const descricao = String(p.descricao || '').replace(/\s+/g, ' ').trim();
                const texto = `${p.part_number}${descricao ? ' - ' + descricao.slice(0, 70) : ''}${p.equipamento_completo ? ' (equipamento completo)' : ''}`;
                const opcao = new Option(texto, String(p.id));
                opcao.dataset.pn = p.part_number;
                opcao.dataset.system = ehSystem(p.part_number, '') ? '1' : '0';
                select.add(opcao);
            });
            select.add(new Option('Outra peça (digitar)', 'outro'));
            select.classList.add('has-value');
            this.atualizarCampoTroca();
        }
        async carregarPecasDoModelo(idEquipamento) {
            if (!idEquipamento) {
                this.montarOpcoesPeca([]);
                return;
            }
            try {
                const r = await (await fetch(`/api/modelo-equipamento/${idEquipamento}/pecas/`)).json();
                this.montarOpcoesPeca(r.status === 'sucesso' ? r.dados : []);
            }
            catch (e) {
                this.montarOpcoesPeca([]); // sem a lista, o usuário ainda pode digitar a peça
            }
        }
        // O CT (PN terminado em -601) aparece quando a peça trocada é um "System".
        atualizarCampoCt() {
            const select = document.getElementById('peca-trocada');
            const grupo = document.getElementById('grupo-ct');
            const campo = document.getElementById('ct');
            const opcao = select.selectedOptions[0];
            const livre = document.getElementById('troca').value;
            const system = select.value === 'outro' ? ehSystem('', livre) : (!!opcao && opcao.dataset.system === '1');
            grupo.classList.toggle('hidden', !system);
            if (!system) {
                campo.value = '';
                campo.classList.remove('has-value');
                return;
            }
            if (campo.value)
                campo.classList.add('has-value');
        }
        // O campo de texto só aparece quando a opção "Outra peça (digitar)" está escolhida.
        atualizarCampoTroca() {
            const escolha = document.getElementById('peca-trocada').value;
            this.atualizarCampoCt();
            const grupo = document.getElementById('grupo-troca-texto');
            const campo = document.getElementById('troca');
            if (escolha === 'outro') {
                grupo.classList.remove('hidden');
            }
            else {
                grupo.classList.add('hidden');
                campo.value = '';
                campo.classList.remove('has-value');
            }
        }
        // ==========================================
        // EDIÇÃO DE UMA TRIAGEM JÁ SALVA
        // ==========================================
        async iniciarEdicaoSeHouver() {
            const id = parseInt(new URLSearchParams(window.location.search).get('id') || '', 10);
            if (!id)
                return;
            try {
                const res = await (await fetch(`/api/triagem/?id=${id}`)).json();
                if (res.status !== 'sucesso') {
                    await Mensagem.erro(res.mensagem || 'Triagem não encontrada.');
                    window.location.href = '/pesquisa/';
                    return;
                }
                const d = res.dado;
                this.idAtual = d.id;
                const texto = (campo, valor) => { document.getElementById(campo).value = valor ?? ''; };
                texto('ticket', d.n_ticket);
                texto('nf', d.nf);
                texto('nserie', d.sn);
                texto('defeitoAlegado', d.defeito_usuario);
                texto('constatacao', d.defeito_tecnico);
                texto('defeitoResumo', d.defeito_constatado);
                texto('testes', d.testes);
                texto('analise', d.analise);
                texto('conclusao', d.conclusao);
                const escolher = (campo, valor, rotulo) => {
                    const sel = document.getElementById(campo);
                    // O analista do chamado pode ser um Administrador, que não está na lista: acrescenta a opção
                    if (![...sel.options].some(o => o.value === String(valor)))
                        sel.add(new Option(rotulo || String(valor), String(valor)));
                    sel.value = String(valor);
                };
                escolher('cliente', d.id_cliente, d.nome_cliente);
                escolher('equipamento', d.id_equipamento, d.nome_equipamento);
                escolher('tecnico', d.id_tecnico, d.nome_tecnico);
                escolher('analista', d.id_analista_chamado, d.nome_analista_chamado);
                this.selectEstado.value = d.estado;
                await this.carregarCidadesIBGE(d.estado, d.cidade);
                this.toggleStatus.checked = d.status_peca === 1;
                this.toggleStatus.dispatchEvent(new Event('change'));
                // Peça trocada: a lista depende do modelo; sem peça vinculada, o texto livre vai em "Outra peça"
                await this.carregarPecasDoModelo(d.id_equipamento);
                const selPeca = document.getElementById('peca-trocada');
                if (d.id_peca_trocada && [...selPeca.options].some(o => o.value === String(d.id_peca_trocada))) {
                    selPeca.value = String(d.id_peca_trocada);
                }
                else if (d.troca) {
                    selPeca.value = 'outro';
                    document.getElementById('troca').value = d.troca;
                }
                document.getElementById('ct').value = d.ct || '';
                await this.carregarMotivosIndevida();
                document.getElementById('troca-indevida').value = d.troca_indevida === true ? 'sim' : d.troca_indevida === false ? 'nao' : '';
                document.getElementById('motivo-indevida').value = d.motivo_troca_indevida || '';
                document.getElementById('justificativa-indevida').value = d.justificativa_troca_indevida || '';
                this.atualizarMotivoIndevida();
                this.atualizarCampoTroca();
                if (selPeca.value === 'outro')
                    document.getElementById('troca').value = d.troca || '';
                if (d.criado_em)
                    document.getElementById('data').value = new Date(d.criado_em).toLocaleDateString('pt-BR');
                document.querySelectorAll('.input-dynamic').forEach(el => { if (el.value)
                    el.classList.add('has-value'); });
                document.getElementById('titulo-tela').innerText = 'Editar Triagem';
                document.getElementById('subtitulo-tela').innerText = `Ticket #${d.n_ticket}: analisado por ${d.nome_analista}`;
                this.btnSalvar.innerText = 'Salvar alterações';
                this.btnLimpar.innerText = 'Cancelar';
            }
            catch (e) {
                await Mensagem.erro('Erro ao carregar a triagem para edição.');
            }
        }
        async salvarTriagem() {
            const n_ticket = document.getElementById('ticket').value;
            const sn = document.getElementById('nserie').value;
            const id_cliente = document.getElementById('cliente').value;
            const id_equipamento = document.getElementById('equipamento').value;
            const id_tecnico = document.getElementById('tecnico').value;
            const id_analista = document.getElementById('analista').value;
            const cidadeVal = this.selectCidade.value;
            const estadoVal = this.selectEstado.value;
            const status_peca = this.toggleStatus.checked ? 1 : 2;
            const ctVisivel = !document.getElementById('grupo-ct').classList.contains('hidden');
            const ct = document.getElementById('ct').value.trim().toUpperCase();
            if (ctVisivel && !ct) {
                Mensagem.aviso('A peça trocada é uma System board (PN terminado em -601): informe o CT, o número de série da placa.');
                return;
            }
            const trocaIndevida = document.getElementById('troca-indevida').value;
            if (!trocaIndevida) {
                Mensagem.aviso('Informe se a troca foi indevida (Sim ou Não).');
                return;
            }
            const motivoIndevida = document.getElementById('motivo-indevida').value;
            const justificativaIndevida = document.getElementById('justificativa-indevida').value.trim();
            if (trocaIndevida === 'sim' && !motivoIndevida) {
                Mensagem.aviso('Informe o motivo da troca indevida.');
                return;
            }
            if (trocaIndevida === 'sim' && motivoIndevida === this.motivoOutro && justificativaIndevida.length < 3) {
                Mensagem.aviso('Descreva o motivo da troca indevida.');
                return;
            }
            if (!n_ticket || !sn || !id_cliente || !id_equipamento || !id_tecnico || !id_analista || !cidadeVal || !estadoVal) {
                Mensagem.aviso("Preencha todos os campos obrigatórios (incluindo Cidade e Estado) e selecione as listas!");
                return;
            }
            const dados = {
                id: this.idAtual,
                n_ticket: parseInt(n_ticket) || 0,
                nf: parseInt(document.getElementById('nf').value) || 0,
                cidade: cidadeVal,
                estado: estadoVal,
                id_cliente: parseInt(id_cliente) || 0,
                id_equipamento: parseInt(id_equipamento) || 0,
                id_tecnico: parseInt(id_tecnico) || 0,
                id_analista: parseInt(id_analista) || 0,
                sn: sn,
                status_peca: status_peca,
                troca_indevida: trocaIndevida === 'sim',
                motivo_troca_indevida: trocaIndevida === 'sim' ? motivoIndevida : '',
                justificativa_troca_indevida: trocaIndevida === 'sim' ? justificativaIndevida : '',
                ct: ctVisivel ? ct : '',
                id_peca_trocada: parseInt(document.getElementById('peca-trocada').value, 10) || null,
                troca: document.getElementById('peca-trocada').value === 'outro'
                    ? document.getElementById('troca').value : '',
                defeito_usuario: document.getElementById('defeitoAlegado').value,
                defeito_tecnico: document.getElementById('constatacao').value,
                defeito_constatado: document.getElementById('defeitoResumo').value,
                testes: document.getElementById('testes').value,
                analise: document.getElementById('analise').value,
                conclusao: document.getElementById('conclusao').value
            };
            try {
                const resposta = await fetch('/api/triagem/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });
                const resultado = await resposta.json();
                if (resultado.status === 'sucesso') {
                    // Busca o ID gerado (suportando vários formatos de retorno da sua API)
                    const idSalvo = resultado.id || (resultado.dado && resultado.dado.id_triagem) || this.idAtual;
                    if (this.idAtual) { // edição: volta para o laudo, onde aparece o histórico da correção
                        await Mensagem.sucesso('Alterações salvas. A correção ficou registrada no histórico do laudo.');
                        window.location.href = `/visualizar/?id=${this.idAtual}`;
                        return;
                    }
                    // Substitui o alert por um confirm
                    const desejaBaixar = await Mensagem.confirmar("Deseja gerar e baixar o documento Word (.docx) agora?", "Triagem salva com sucesso!", "Sim, baixar");
                    if (desejaBaixar) {
                        if (idSalvo) {
                            window.location.href = `/api/triagem/exportar-docx/?id=${idSalvo}`;
                        }
                        else {
                            Mensagem.aviso("Não foi possível obter o ID da triagem para download imediato. Você pode baixá-lo na tela de pesquisa.");
                        }
                    }
                    this.limparFormulario();
                }
                else {
                    Mensagem.erro(resultado.mensagem, "Erro do Servidor");
                }
            }
            catch (error) {
                console.error("Falha na requisição:", error);
                Mensagem.erro("Erro ao comunicar com o servidor.");
            }
        }
        limparFormulario() {
            this.form.reset();
            this.idAtual = null;
            // Reseta a lógica IBGE
            this.selectCidade.innerHTML = '<option value="" disabled selected></option>';
            this.selectCidade.disabled = true;
            // Reseta o interruptor
            this.statusTexto.innerText = "Defeito";
            this.statusTexto.classList.replace("text-emerald-400", "text-rose-400");
            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.remove('has-value'));
            document.getElementById('troca-indevida')?.classList.add('has-value');
            document.getElementById('motivo-indevida')?.classList.add('has-value');
            document.getElementById('grupo-motivo-indevida')?.classList.add('hidden');
            document.getElementById('grupo-justificativa-indevida')?.classList.add('hidden');
            document.getElementById('grupo-ct')?.classList.add('hidden');
            this.montarOpcoesPeca([]); // volta a lista de peças ao estado inicial (e reaplica o has-value dela)
            this.preencherDataHoje(); // Mantém a data
        }
    }
    window.addEventListener('DOMContentLoaded', () => new G_triagemUI());
})();
