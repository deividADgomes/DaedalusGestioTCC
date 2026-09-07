"use strict";
/// <reference path="../baseUI.ts" />
(() => {
    class G_triagemUI extends BaseUI {
        constructor() {
            super();
            this.idAtual = null;
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
                    alert(resultado.mensagem || "Triagem salva com sucesso!");
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
            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.remove('has-value'));
            this.preencherDataHoje(); // Mantém a data
        }
    }
    window.addEventListener('DOMContentLoaded', () => new G_triagemUI());
})();
