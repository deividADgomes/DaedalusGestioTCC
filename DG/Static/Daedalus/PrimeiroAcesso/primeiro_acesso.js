"use strict";
(() => {
    class PrimeiroAcessoUI {
        constructor() {
            this.form = document.getElementById('form-primeiro-acesso');
            this.btnSalvar = document.getElementById('btn-salvar');
            this.erroMsg = document.getElementById('msg-erro');
            this.form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.salvar();
            });
        }
        async salvar() {
            const atual = document.getElementById('senha-atual').value;
            const nova = document.getElementById('nova-senha').value;
            const confirma = document.getElementById('confirma-senha').value;
            if (nova !== confirma) {
                this.mostrarErro('As senhas não coincidem!');
                return;
            }
            if (nova.length < 4) {
                this.mostrarErro('A senha deve ter pelo menos 4 caracteres.');
                return;
            }
            this.btnSalvar.disabled = true;
            this.erroMsg.classList.add('hidden');
            try {
                const resposta = await fetch('/api/alterar-senha/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ senha_atual: atual, nova_senha: nova })
                });
                const resultado = await resposta.json();
                if (resultado.status === 'sucesso') {
                    window.location.href = '/principal/';
                }
                else {
                    this.mostrarErro(resultado.mensagem);
                    this.btnSalvar.disabled = false;
                }
            }
            catch (error) {
                console.error(error);
                this.mostrarErro('Erro de conexão com o servidor.');
                this.btnSalvar.disabled = false;
            }
        }
        mostrarErro(msg) {
            this.erroMsg.innerText = msg;
            this.erroMsg.classList.remove('hidden');
        }
    }
    window.addEventListener('DOMContentLoaded', () => new PrimeiroAcessoUI());
})();
