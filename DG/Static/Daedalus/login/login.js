"use strict";
(() => {
    class LoginUI {
        constructor() {
            this.form = document.getElementById('form-login');
            this.btnEntrar = document.getElementById('btn-entrar');
            this.erroMsg = document.getElementById('msg-erro');
            this.iniciarEventos();
        }
        iniciarEventos() {
            this.form.addEventListener('submit', (e) => {
                e.preventDefault(); // Impede a página de recarregar
                this.realizarLogin();
            });
        }
        async realizarLogin() {
            const loginInput = document.getElementById('login').value;
            const senhaInput = document.getElementById('senha').value;
            if (!loginInput || !senhaInput) {
                this.mostrarErro("Preencha a matrícula e a senha.");
                return;
            }
            // UI Feedback: Desabilita botão enquanto carrega
            this.btnEntrar.disabled = true;
            this.btnEntrar.innerText = "AUTENTICANDO...";
            this.erroMsg.classList.add('hidden');
            try {
                const resposta = await fetch('/api/login/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        login: parseInt(loginInput),
                        senha: senhaInput
                    })
                });
                const resultado = await resposta.json();
                if (resultado.status === 'sucesso') {
                    // Login com sucesso! Redireciona para o Dashboard (ou Home)
                    window.location.href = '/principal/';
                }
                else {
                    this.mostrarErro(resultado.mensagem);
                    this.resetarBotao();
                }
            }
            catch (error) {
                console.error(error);
                this.mostrarErro("Erro de conexão com o servidor.");
                this.resetarBotao();
            }
        }
        mostrarErro(msg) {
            this.erroMsg.innerText = msg;
            this.erroMsg.classList.remove('hidden');
        }
        resetarBotao() {
            this.btnEntrar.disabled = false;
            this.btnEntrar.innerText = "ACESSAR SISTEMA";
        }
    }
    window.addEventListener('DOMContentLoaded', () => new LoginUI());
})();
