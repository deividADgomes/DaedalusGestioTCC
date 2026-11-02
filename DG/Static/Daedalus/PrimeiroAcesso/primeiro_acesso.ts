/// <reference path="../utilitarios.ts" />

(() => {
    class PrimeiroAcessoUI {
        private form = obterElemento<HTMLFormElement>('form-primeiro-acesso');
        private botaoSalvar = obterElemento<HTMLButtonElement>('btn-salvar');
        private mensagemErro = obterElemento<HTMLParagraphElement>('msg-erro');

        constructor() {
            this.form.addEventListener('submit', (evento) => {
                evento.preventDefault();
                this.salvar();
            });
        }

        private async salvar(): Promise<void> {
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
            } catch (erro) {
                console.error(erro);
                this.mostrarErro('Erro de conexão com o servidor.');
            }
            this.botaoSalvar.disabled = false;
        }

        private mostrarErro(texto: string): void {
            this.mensagemErro.innerText = texto;
            this.mensagemErro.classList.remove('hidden');
        }
    }

    window.addEventListener('DOMContentLoaded', () => new PrimeiroAcessoUI());
})();
