/// <reference path="../utilitarios.ts" />

(() => {
    class LoginUI {
        private form = obterElemento<HTMLFormElement>('form-login');
        private botaoEntrar = obterElemento<HTMLButtonElement>('btn-entrar');
        private mensagemErro = obterElemento<HTMLParagraphElement>('msg-erro');

        constructor() {
            this.iniciarEventos();
        }

        private iniciarEventos(): void {
            const formularioRecuperacao = obterElemento<HTMLFormElement>('form-recuperar');

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

        private async solicitarRecuperacao(): Promise<void> {
            const mensagem = obterElemento<HTMLParagraphElement>('msg-recuperar');
            try {
                const resultado = await enviarJson('/api/recuperar-senha/', {
                    login: parseInt(valorDoCampo('login-recuperar')),
                    email: valorDoCampo('email-recuperar').trim(),
                });
                mensagem.innerText = resultado.mensagem;
            } catch (erro) {
                console.error(erro);
                mensagem.innerText = 'Erro de conexão com o servidor.';
            }
            mensagem.classList.remove('hidden');
        }

        private async realizarLogin(): Promise<void> {
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
            } catch (erro) {
                console.error(erro);
                this.mostrarErro('Erro de conexão com o servidor.');
            }
            this.resetarBotao();
        }

        private mostrarErro(texto: string): void {
            this.mensagemErro.innerText = texto;
            this.mensagemErro.classList.remove('hidden');
        }

        private resetarBotao(): void {
            this.botaoEntrar.disabled = false;
            this.botaoEntrar.innerText = 'ACESSAR SISTEMA';
        }
    }

    window.addEventListener('DOMContentLoaded', () => new LoginUI());
})();
