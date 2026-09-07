"use strict";
/// <reference path="../baseUI.ts" />
(() => {
    class G_modeloEquipamento extends BaseUI {
        constructor() {
            super();
            this.idAtual = null;
            this.btnSalvar = document.getElementById('btn-salvar-modelo');
            this.btnLimpar = document.getElementById('btn-limpar');
            this.form = document.getElementById('form-cadastro-modelo');
            this.listaModeloEquip = document.getElementById('lista-modelos');
            this.iniciarEventos();
            this.carregarModelos(); // Busca os dados do servidor ao abrir a tela
        }
        iniciarEventos() {
            this.btnSalvar.addEventListener('click', () => this.salvarModelo());
            this.btnLimpar.addEventListener('click', () => this.limparFormulario());
        }
        // ==========================================
        // LÓGICA DE SALVAR / ALTERAR (POST)
        // ==========================================
        async salvarModelo() {
            // Presumindo que os IDs dos inputs no seu HTML sejam 'pn' e 'modelo'
            const pn = document.getElementById('pn').value;
            const modelo = document.getElementById('modelo').value;
            if (!pn || !modelo) {
                alert("Preencha todos os campos obrigatórios (PN e Modelo)!");
                return;
            }
            // O pacote de dados alinhado com o EquipamentoDTO
            const dados = {
                id: this.idAtual,
                pn: pn,
                modelo: modelo
            };
            try {
                const resposta = await fetch('/api/modelo-equipamento/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });
                const resultado = await resposta.json();
                if (resultado.status === 'sucesso') {
                    alert(resultado.mensagem);
                    this.limparFormulario();
                    this.carregarModelos(); // Atualiza a grid
                }
                else {
                    alert("Erro: " + resultado.mensagem);
                }
            }
            catch (error) {
                console.error("Falha na requisição:", error);
                alert("Erro ao comunicar com o servidor.");
            }
        }
        // ==========================================
        // LÓGICA DE LISTAGEM (GET)
        // ==========================================
        async carregarModelos() {
            this.listaModeloEquip.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Carregando dados do servidor...</p>';
            try {
                const resposta = await fetch('/api/modelo-equipamento/');
                const resultado = await resposta.json();
                if (resultado.status === 'sucesso') {
                    this.listaModeloEquip.innerHTML = '';
                    if (resultado.dados.length === 0) {
                        this.listaModeloEquip.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Nenhum equipamento cadastrado.</p>';
                        return;
                    }
                    resultado.dados.forEach((equip) => {
                        const card = document.createElement('div');
                        card.className = "bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group";
                        card.innerHTML = `
                            <div class="flex justify-between items-start mb-2">
                                <span class="text-xs font-bold text-cyan-400 uppercase tracking-wider">Equipamento</span>
                                <span class="text-[10px] text-slate-500 font-mono">ID: ${equip.id}</span>
                            </div>
                            <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${equip.modelo}</h3>
                            <p class="text-xs text-slate-400 mt-1 font-mono">PN: ${equip.pn}</p>
                            <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-end">
                                <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                            </div>
                        `;
                        // Duplo clique aciona a edição
                        card.addEventListener('dblclick', () => {
                            this.prepararEdicao(equip.id, equip.pn, equip.modelo);
                        });
                        this.listaModeloEquip.appendChild(card);
                    });
                }
                else {
                    this.listaModeloEquip.innerHTML = `<p class="text-sm font-bold text-red-500 col-span-full text-center py-10">Erro do Servidor: ${resultado.mensagem}</p>`;
                }
            }
            catch (error) {
                this.listaModeloEquip.innerHTML = '<p class="text-sm font-bold text-red-500 col-span-full text-center py-10">Erro crítico ao tentar conectar com o servidor.</p>';
            }
        }
        // ==========================================
        // MANIPULAÇÃO DA INTERFACE DÚPLICE
        // ==========================================
        prepararEdicao(id, pn, modelo) {
            this.idAtual = id;
            document.getElementById('pn').value = pn;
            document.getElementById('modelo').value = modelo;
            // Sinais visuais de modo de Alteração
            this.btnSalvar.innerText = "Alterar Registro";
            this.btnSalvar.classList.replace('bg-cyan-600', 'bg-amber-600');
            this.btnSalvar.classList.replace('hover:bg-cyan-500', 'hover:bg-amber-500');
            this.btnSalvar.classList.replace('shadow-[0_0_15px_rgba(6,182,212,0.3)]', 'shadow-[0_0_15px_rgba(245,158,11,0.3)]');
            // Ativa o Floating Label
            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.add('has-value'));
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
        }
    }
    window.addEventListener('DOMContentLoaded', () => {
        new G_modeloEquipamento();
    });
})();
