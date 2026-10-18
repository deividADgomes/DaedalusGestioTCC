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
            // UC09: "Esqueci minha senha" envia e-mail ao administrador, que redefine pela tela de funcionários
            const formRecuperar = document.getElementById('form-recuperar');
            document.getElementById('btn-esqueci').addEventListener('click', () => {
                formRecuperar.classList.toggle('hidden');
            });
            formRecuperar.addEventListener('submit', (e) => {
                e.preventDefault();
                this.solicitarRecuperacao();
            });
        }
        async solicitarRecuperacao() {
            const msg = document.getElementById('msg-recuperar');
            const matricula = document.getElementById('login-recuperar').value;
            const email = document.getElementById('email-recuperar').value.trim();
            try {
                const resposta = await fetch('/api/recuperar-senha/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ login: parseInt(matricula), email: email })
                });
                const resultado = await resposta.json();
                msg.innerText = resultado.mensagem;
            }
            catch (error) {
                console.error(error);
                msg.innerText = 'Erro de conexão com o servidor.';
            }
            msg.classList.remove('hidden');
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
                    // Primeiro acesso: força a troca da senha provisória (RF14)
                    window.location.href = resultado.primeiro_acesso ? '/primeiro-acesso/' : '/principal/';
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
