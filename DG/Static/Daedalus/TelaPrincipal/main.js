"use strict";
/// <reference path="../baseUI.ts" />
(() => {
    class G_triagemUI extends BaseUI {
        constructor() {
            super();
            this.idAtual = null;
            this.fotosPendentes = [];
            // IDs ALINHADOS COM O SEU HTML:
            this.btnSalvar = document.getElementById('btn-salvar');
            this.btnLimpar = document.getElementById('btn-limpar');
            this.form = document.getElementById('form-triagem');
            this.toggleStatus = document.getElementById('funcional');
            this.statusTexto = document.getElementById('status-texto');
            this.iniciarEventos();
            this.preencherDataHoje();
            this.carregarDropdowns();
        }
        iniciarEventos() {
            this.btnSalvar.addEventListener('click', () => this.salvarTriagem());
            this.btnLimpar.addEventListener('click', () => this.limparFormulario());
            document.getElementById('equipamento')
                .addEventListener('change', () => this.carregarPecasDoModelo());
            document.getElementById('input-fotos')
                .addEventListener('change', (e) => this.selecionarFotos(e));
            // Lógica do seu Toggle Switch bonito
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
        // ==========================================
        // PEÇAS DO MODELO
        // ==========================================
        async carregarPecasDoModelo() {
            const select = document.getElementById('peca-trocada');
            const idEquip = document.getElementById('equipamento').value;
            select.innerHTML = '<option value="">Carregando...</option>';
            try {
                const res = await fetch(`/api/modelo-equipamento/pecas/?id_equipamento=${idEquip}`).then(r => r.json());
                const pecas = res.status === 'sucesso' ? res.dados : [];
                select.innerHTML = pecas.length
                    ? '<option value="">Nenhuma / outra (descrever ao lado)</option>'
                    : '<option value="">Este modelo não tem peças cadastradas</option>';
                pecas.forEach(p => select.add(new Option(p.descricao ? `${p.part_number} - ${p.descricao}` : p.part_number, p.id)));
            }
            catch (e) {
                select.innerHTML = '<option value="">Não foi possível carregar as peças</option>';
            }
        }
        // ==========================================
        // FOTOS (enviadas depois que a triagem é salva)
        // ==========================================
        selecionarFotos(e) {
            const input = e.target;
            Array.from(input.files || []).forEach(arq => {
                if (!['image/jpeg', 'image/png', 'image/webp'].includes(arq.type)) {
                    alert(`"${arq.name}": use JPG, PNG ou WEBP.`);
                }
                else if (arq.size > G_triagemUI.MAX_BYTES) {
                    alert(`"${arq.name}" excede 10 MB.`);
                }
                else if (this.fotosPendentes.length >= G_triagemUI.MAX_FOTOS) {
                    alert(`Limite de ${G_triagemUI.MAX_FOTOS} fotos por triagem.`);
                }
                else {
                    this.fotosPendentes.push(arq);
                }
            });
            input.value = '';
            this.desenharPrevia();
        }
        desenharPrevia() {
            const area = document.getElementById('previa-fotos');
            area.querySelectorAll('img').forEach(img => URL.revokeObjectURL(img.src));
            area.innerHTML = '';
            this.fotosPendentes.forEach((arq, i) => {
                const item = document.createElement('div');
                item.className = 'relative group aspect-square rounded-lg overflow-hidden border border-[#334155] bg-slate-900';
                const img = document.createElement('img');
                img.src = URL.createObjectURL(arq);
                img.alt = arq.name;
                img.className = 'w-full h-full object-cover';
                const rem = document.createElement('button');
                rem.type = 'button';
                rem.textContent = '✕';
                rem.title = 'Remover';
                rem.className = 'absolute top-1 right-1 w-6 h-6 rounded-full bg-black/70 text-rose-300 text-xs hover:bg-rose-600 hover:text-white';
                rem.addEventListener('click', () => { this.fotosPendentes.splice(i, 1); this.desenharPrevia(); });
                item.append(img, rem);
                area.appendChild(item);
            });
        }
        async enviarFotos(idTriagem) {
            const falhas = [];
            for (const arq of this.fotosPendentes) {
                const fd = new FormData();
                fd.append('id_triagem', String(idTriagem));
                fd.append('arquivo', arq);
                try {
                    const res = await fetch('/api/triagem/fotos/', { method: 'POST', body: fd }).then(r => r.json());
                    if (res.status !== 'sucesso') {
                        falhas.push(`${arq.name}: ${res.mensagem}`);
                    }
                }
                catch (e) {
                    falhas.push(`${arq.name}: falha de comunicação`);
                }
            }
            return falhas;
        }
        preencherDataHoje() {
            const dataInput = document.getElementById('data');
            const hoje = new Date();
            dataInput.value = hoje.toLocaleDateString('pt-BR');
        }
        async carregarDropdowns() {
            try {
                const [respClientes, respEquips, respTecnicos, respAnalistas] = await Promise.all([
                    // FILTRO APLICADO AQUI: ?tipo=2 traz apenas os clientes finais!
                    fetch('/api/empresa/?tipo=2').then(r => r.json()),
                    fetch('/api/modelo-equipamento/').then(r => r.json()),
                    fetch('/api/tecnico/').then(r => r.json()),
                    fetch('/api/funcionario/').then(r => r.json())
                ]);
                // IDs ALINHADOS COM O SEU HTML:
                const selectCliente = document.getElementById('cliente');
                selectCliente.innerHTML = '<option value="" disabled selected>Selecione...</option>';
                if (respClientes.status === 'sucesso') {
                    respClientes.dados.forEach((cli) => selectCliente.add(new Option(cli.razao_social || cli.nome, cli.id)));
                }
                const selectEquip = document.getElementById('equipamento');
                selectEquip.innerHTML = '<option value="" disabled selected>Selecione...</option>';
                if (respEquips.status === 'sucesso') {
                    respEquips.dados.forEach((eq) => selectEquip.add(new Option(`${eq.pn} - ${eq.modelo}`, eq.id)));
                }
                const selectTecnico = document.getElementById('tecnico');
                selectTecnico.innerHTML = '<option value="" disabled selected>Selecione...</option>';
                if (respTecnicos.status === 'sucesso') {
                    respTecnicos.dados.forEach((tec) => {
                        // Concatenando o Nome do Técnico + Nome da Empresa
                        const textoOpcao = `${tec.nome} (${tec.nome_empresa})`;
                        selectTecnico.add(new Option(textoOpcao, tec.id));
                    });
                }
                const selectAnalista = document.getElementById('analista');
                selectAnalista.innerHTML = '<option value="" disabled selected>Selecione...</option>';
                if (respAnalistas.status === 'sucesso') {
                    respAnalistas.dados.forEach((func) => {
                        // A trava de segurança: Só adiciona se o cargo existir e for diferente de Administrador
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
        async salvarTriagem() {
            // IDs ALINHADOS COM O SEU HTML:
            const n_ticket = document.getElementById('ticket').value;
            const sn = document.getElementById('nserie').value;
            const id_cliente = document.getElementById('cliente').value;
            const id_equipamento = document.getElementById('equipamento').value;
            const id_tecnico = document.getElementById('tecnico').value;
            const id_analista = document.getElementById('analista').value;
            // Lê o Toggle Switch para saber se é Funcional (1) ou Nao Funcional (2)
            const status_peca = this.toggleStatus.checked ? 1 : 2;
            if (!n_ticket || !sn || !id_cliente || !id_equipamento || !id_tecnico || !id_analista) {
                alert("Preencha todos os campos obrigatórios e selecione as listas!");
                return;
            }
            const dados = {
                id: this.idAtual,
                n_ticket: parseInt(n_ticket),
                nf: parseInt(document.getElementById('nf').value) || 0,
                cidade: document.getElementById('Cidade').value,
                estado: document.getElementById('Estado').value,
                id_cliente: parseInt(id_cliente),
                id_equipamento: parseInt(id_equipamento),
                id_tecnico: parseInt(id_tecnico),
                id_analista: parseInt(id_analista), // O Back-end vai ler isto como o Analista do Chamado
                sn: sn,
                status_peca: status_peca,
                troca: document.getElementById('troca').value,
                id_peca_trocada: document.getElementById('peca-trocada').value || null,
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
                    let aviso = resultado.mensagem || "Triagem salva com sucesso!";
                    if (this.fotosPendentes.length && resultado.id_gerado) {
                        const falhas = await this.enviarFotos(resultado.id_gerado);
                        aviso += falhas.length
                            ? `\n\nAlgumas fotos não foram enviadas (anexe-as depois na tela de visualização):\n- ${falhas.join('\n- ')}`
                            : `\n${this.fotosPendentes.length} foto(s) anexada(s).`;
                    }
                    alert(aviso);
                    this.limparFormulario();
                }
                else {
                    alert("Erro do Servidor: " + resultado.mensagem);
                }
            }
            catch (error) {
                console.error("Falha na requisição:", error);
                alert("Erro ao comunicar com o servidor.");
            }
        }
        limparFormulario() {
            this.form.reset();
            this.idAtual = null;
            // Reseta o interruptor
            this.statusTexto.innerText = "Defeito";
            this.statusTexto.classList.replace("text-emerald-400", "text-rose-400");
            this.fotosPendentes = [];
            this.desenharPrevia();
            document.getElementById('peca-trocada').innerHTML =
                '<option value="">Selecione o modelo primeiro</option>';
            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.remove('has-value'));
            this.preencherDataHoje(); // Mantém a data
        }
    }
    G_triagemUI.MAX_FOTOS = 10;
    G_triagemUI.MAX_BYTES = 10 * 1024 * 1024;
    window.addEventListener('DOMContentLoaded', () => new G_triagemUI());
})();
