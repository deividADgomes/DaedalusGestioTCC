"use strict";
class BaseUI {
    constructor() {
        this.iniciarSubmenuGerenciar();
        this.iniciarDropdownPerfil();
        this.iniciarModalAlterarSenha();
    }
    iniciarSubmenuGerenciar() {
        const botao = document.getElementById('btn-menu-gerenciar');
        const submenu = document.getElementById('submenu-gerenciar');
        const seta = document.getElementById('seta-gerenciar');
        if (!botao || !submenu)
            return;
        botao.addEventListener('click', (evento) => {
            evento.preventDefault();
            submenu.classList.toggle('hidden');
            submenu.classList.toggle('flex');
            seta?.classList.toggle('rotate-180');
            botao.classList.toggle('text-cyan-400');
        });
    }
    iniciarDropdownPerfil() {
        const botao = document.getElementById('btn-perfil');
        const dropdown = document.getElementById('dropdown-perfil');
        if (!botao || !dropdown)
            return;
        const ocultar = () => {
            dropdown.classList.add('opacity-0', 'scale-95');
            setTimeout(() => dropdown.classList.add('hidden'), 200);
        };
        botao.addEventListener('click', (evento) => {
            evento.stopPropagation();
            if (!dropdown.classList.contains('hidden')) {
                ocultar();
                return;
            }
            dropdown.classList.remove('hidden');
            setTimeout(() => dropdown.classList.remove('opacity-0', 'scale-95'), 10);
        });
        document.addEventListener('click', (evento) => {
            const alvo = evento.target;
            if (!dropdown.contains(alvo) && !botao.contains(alvo))
                ocultar();
        });
    }
    iniciarModalAlterarSenha() {
        const dropdown = document.getElementById('dropdown-perfil');
        const modal = document.getElementById('modal-senha');
        const formulario = document.getElementById('form-alterar-senha');
        const mensagemErro = document.getElementById('msg-senha-erro');
        if (!modal || !formulario || !mensagemErro)
            return;
        const exibirErro = (texto) => {
            mensagemErro.textContent = texto;
            mensagemErro.classList.remove('hidden');
        };
        const fechar = () => {
            modal.classList.add('hidden');
            formulario.reset();
            mensagemErro.classList.add('hidden');
        };
        document.getElementById('btn-abrir-senha')?.addEventListener('click', () => {
            modal.classList.remove('hidden');
            dropdown?.classList.add('opacity-0', 'scale-95', 'hidden');
        });
        document.getElementById('btn-fechar-senha')?.addEventListener('click', fechar);
        formulario.addEventListener('submit', async (evento) => {
            evento.preventDefault();
            const senhaAtual = valorDoCampo('senha-atual');
            const novaSenha = valorDoCampo('nova-senha');
            if (novaSenha !== valorDoCampo('confirma-senha')) {
                exibirErro('As senhas não coincidem!');
                return;
            }
            if (novaSenha.length < SENHA_MINIMA) {
                exibirErro(`A senha deve ter pelo menos ${SENHA_MINIMA} caracteres.`);
                return;
            }
            try {
                const resultado = await enviarJson('/api/alterar-senha/', {
                    senha_atual: senhaAtual,
                    nova_senha: novaSenha,
                });
                if (resultado.status !== 'sucesso') {
                    exibirErro(resultado.mensagem);
                    return;
                }
                alert('Senha alterada com sucesso.');
                fechar();
            }
            catch (erro) {
                console.error(erro);
                exibirErro('Erro de conexão com o servidor.');
            }
        });
    }
}
