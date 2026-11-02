"use strict";
(() => {
    class PrimeiroAcessoUI {
        constructor() {
            this.form = obterElemento('form-primeiro-acesso');
            this.botaoSalvar = obterElemento('btn-salvar');
            this.mensagemErro = obterElemento('msg-erro');
            this.form.addEventListener('submit', (evento) => {
                evento.preventDefault();
                this.salvar();
            });
        }
        async salvar() {
            const senhaAtual = valorDoCampo('senha-atual');
            const novaSenha = valorDoCampo('nova-senha');
            if (novaSenha !== valorDoCampo('confirma-senha')) {
                this.mostrarErro('As senhas não coincidem!');
                return;
            }
            if (novaSenha.length < SENHA_MINIMA) {
                this.mostrarErro(`A senha deve ter pelo menos ${SENHA_MINIMA} caracteres.`);
                return;
            }
            this.botaoSalvar.disabled = true;
            this.mensagemErro.classList.add('hidden');
            try {
                const resultado = await enviarJson('/api/alterar-senha/', {
                    senha_atual: senhaAtual,
                    nova_senha: novaSenha,
                });
                if (resultado.status === 'sucesso') {
                    window.location.href = '/principal/';
                    return;
                }
                this.mostrarErro(resultado.mensagem);
            }
            catch (erro) {
                console.error(erro);
                this.mostrarErro('Erro de conexão com o servidor.');
            }
            this.botaoSalvar.disabled = false;
        }
        mostrarErro(texto) {
            this.mensagemErro.innerText = texto;
            this.mensagemErro.classList.remove('hidden');
        }
    }
    window.addEventListener('DOMContentLoaded', () => new PrimeiroAcessoUI());
})();
