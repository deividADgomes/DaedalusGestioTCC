"use strict";
(() => {
    class LoginUI {
        constructor() {
            this.form = obterElemento('form-login');
            this.botaoEntrar = obterElemento('btn-entrar');
            this.mensagemErro = obterElemento('msg-erro');
            this.iniciarEventos();
        }
        iniciarEventos() {
            const formularioRecuperacao = obterElemento('form-recuperar');
            this.form.addEventListener('submit', (evento) => {
                evento.preventDefault();
                this.realizarLogin();
            });
            obterElemento('btn-esqueci').addEventListener('click', () => {
                formularioRecuperacao.classList.toggle('hidden');
            });
            formularioRecuperacao.addEventListener('submit', (evento) => {
                evento.preventDefault();
                this.solicitarRecuperacao();
            });
        }
        async solicitarRecuperacao() {
            const mensagem = obterElemento('msg-recuperar');
            try {
                const resultado = await enviarJson('/api/recuperar-senha/', {
                    login: parseInt(valorDoCampo('login-recuperar')),
                    email: valorDoCampo('email-recuperar').trim(),
                });
                mensagem.innerText = resultado.mensagem;
            }
            catch (erro) {
                console.error(erro);
                mensagem.innerText = 'Erro de conexão com o servidor.';
            }
            mensagem.classList.remove('hidden');
        }
        async realizarLogin() {
            const matricula = valorDoCampo('login');
            const senha = valorDoCampo('senha');
            if (!matricula || !senha) {
                this.mostrarErro('Preencha a matrícula e a senha.');
                return;
            }
            this.botaoEntrar.disabled = true;
            this.botaoEntrar.innerText = 'AUTENTICANDO...';
            this.mensagemErro.classList.add('hidden');
            try {
                const resultado = await enviarJson('/api/login/', { login: parseInt(matricula), senha });
                if (resultado.status === 'sucesso') {
                    window.location.href = resultado.primeiro_acesso ? '/primeiro-acesso/' : '/principal/';
                    return;
                }
                this.mostrarErro(resultado.mensagem);
            }
            catch (erro) {
                console.error(erro);
                this.mostrarErro('Erro de conexão com o servidor.');
            }
            this.resetarBotao();
        }
        mostrarErro(texto) {
            this.mensagemErro.innerText = texto;
            this.mensagemErro.classList.remove('hidden');
        }
        resetarBotao() {
            this.botaoEntrar.disabled = false;
            this.botaoEntrar.innerText = 'ACESSAR SISTEMA';
        }
    }
    window.addEventListener('DOMContentLoaded', () => new LoginUI());
})();
