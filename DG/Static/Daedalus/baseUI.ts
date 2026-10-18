class BaseUI {
    constructor() {
        this.subMenuGerenciar();
        this.iniciarMenuPerfil();
    }

    protected subMenuGerenciar(): void {
        const configurarMenu = (idBotao: string, idSubmenu: string, idSeta: string) => {
            const btn = document.getElementById(idBotao);
            const submenu = document.getElementById(idSubmenu);
            const seta = document.getElementById(idSeta);

            if (btn && submenu) {
                btn.addEventListener('click', (e) => {
                    e.preventDefault(); 
                    submenu.classList.toggle('hidden');
                    submenu.classList.toggle('flex');
                    if (seta) seta.classList.toggle('rotate-180');
                    btn.classList.toggle('text-cyan-400');
                });
            }
        };
        configurarMenu('btn-menu-gerenciar', 'submenu-gerenciar', 'seta-gerenciar');
    }

    protected iniciarMenuPerfil(): void {
        // Elementos do Perfil
        const btnPerfil = document.getElementById("btn-perfil");
        const dropdownPerfil = document.getElementById("dropdown-perfil");
        
        // Elementos do Modal de Senha
        const btnAbrirSenha = document.getElementById("btn-abrir-senha");
        const modalSenha = document.getElementById("modal-senha");
        const btnFecharSenha = document.getElementById("btn-fechar-senha");
        const formSenha = document.getElementById("form-alterar-senha") as HTMLFormElement;
        const msgErro = document.getElementById("msg-senha-erro");

        // Lógica de Abrir/Fechar o Dropdown do Perfil
        if (btnPerfil && dropdownPerfil) {
            btnPerfil.addEventListener("click", (e) => {
                e.stopPropagation();
                if (dropdownPerfil.classList.contains("hidden")) {
                    dropdownPerfil.classList.remove("hidden");
                    setTimeout(() => {
                        dropdownPerfil.classList.remove("opacity-0", "scale-95");
                    }, 10);
                } else {
                    dropdownPerfil.classList.add("opacity-0", "scale-95");
                    setTimeout(() => dropdownPerfil.classList.add("hidden"), 200);
                }
            });

            // Fechar dropdown se clicar fora dele
            document.addEventListener("click", (e) => {
                const targetNode = e.target as Node;
                if (!dropdownPerfil.contains(targetNode) && !btnPerfil.contains(targetNode)) {
                    dropdownPerfil.classList.add("opacity-0", "scale-95");
                    setTimeout(() => dropdownPerfil.classList.add("hidden"), 200);
                }
            });
        }

        // Lógica de Abrir o Modal de Senha
        if (btnAbrirSenha && modalSenha && dropdownPerfil) {
            btnAbrirSenha.addEventListener("click", () => {
                modalSenha.classList.remove("hidden");
                dropdownPerfil.classList.add("opacity-0", "scale-95", "hidden"); 
            });
        }

        // Lógica de Fechar o Modal de Senha
        if (btnFecharSenha && modalSenha && formSenha && msgErro) {
            btnFecharSenha.addEventListener("click", () => {
                modalSenha.classList.add("hidden");
                formSenha.reset();
                msgErro.classList.add("hidden");
            });
        }

        // Validação do Formulário de Senha (Preparado para API)
        if (formSenha && msgErro && modalSenha) {
            formSenha.addEventListener("submit", async (e) => {
                e.preventDefault();
                const atual = (document.getElementById("senha-atual") as HTMLInputElement).value;
                const s1 = (document.getElementById("nova-senha") as HTMLInputElement).value;
                const s2 = (document.getElementById("confirma-senha") as HTMLInputElement).value;

                if (s1 !== s2) {
                    msgErro.textContent = "As senhas não coincidem!";
                    msgErro.classList.remove("hidden");
                    return;
                }

                if (s1.length < 4) {
                    msgErro.textContent = "A senha deve ter pelo menos 4 caracteres.";
                    msgErro.classList.remove("hidden");
                    return;
                }

                try {
                    const resposta = await fetch('/api/alterar-senha/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ senha_atual: atual, nova_senha: s1 })
                    });
                    const resultado = await resposta.json();

                    if (resultado.status === 'sucesso') {
                        alert("Senha alterada com sucesso.");
                        modalSenha.classList.add("hidden");
                        formSenha.reset();
                        msgErro.classList.add("hidden");
                    } else {
                        msgErro.textContent = resultado.mensagem;
                        msgErro.classList.remove("hidden");
                    }
                } catch (erro) {
                    console.error(erro);
                    msgErro.textContent = "Erro de conexão com o servidor.";
                    msgErro.classList.remove("hidden");
                }
            });
        }
    }
}