"use strict";
/**
 * Caixas de mensagem do sistema (SweetAlert2), no mesmo padrão da tela de Gestão RFB:
 *  - erro / aviso / info: janela com título e botão OK;
 *  - sucesso: aviso rápido no canto (toast);
 *  - confirmar: pergunta Sim/Cancelar (devolve true/false);
 *  - pedirTexto: pergunta um texto (devolve o texto ou null se cancelar).
 * Use estas funções em vez de alert() e confirm().
 */
const Mensagem = {
    erro(texto, titulo = 'Erro') {
        return Swal.fire(titulo, String(texto ?? ''), 'error');
    },
    aviso(texto, titulo = 'Aviso') {
        return Swal.fire(titulo, String(texto ?? ''), 'warning');
    },
    info(texto, titulo = 'Aviso') {
        return Swal.fire(titulo, String(texto ?? ''), 'info');
    },
    sucesso(texto) {
        return Swal.fire({ title: String(texto ?? ''), icon: 'success', toast: true, position: 'top-end', showConfirmButton: false, timer: 3000 });
    },
    async confirmar(texto, titulo = 'Confirmação', botao = 'Sim, continuar') {
        const r = await Swal.fire({
            title: titulo,
            text: texto,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#0891b2',
            cancelButtonColor: '#64748b',
            confirmButtonText: botao,
            cancelButtonText: 'Cancelar'
        });
        return !!r.isConfirmed;
    },
    /** Pede o destinatário e uma mensagem opcional para enviar o laudo por e-mail. Devolve null se cancelar. */
    async pedirEmail(padrao) {
        const r = await Swal.fire({
            title: 'Enviar laudo por e-mail',
            html: `<input id="swal-dest" type="email" class="swal2-input" placeholder="E-mail do cliente" value="${escapeHtml(padrao)}">
                   <textarea id="swal-msg" class="swal2-textarea" placeholder="Mensagem (opcional: se vazio, vai um texto padrão)"></textarea>`,
            focusConfirm: false,
            showCancelButton: true,
            confirmButtonColor: '#0891b2',
            cancelButtonColor: '#64748b',
            confirmButtonText: 'Enviar com o Word anexo',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                const destinatario = document.getElementById('swal-dest').value.trim();
                if (!destinatario) {
                    Swal.showValidationMessage('Informe o e-mail do destinatário.');
                    return false;
                }
                return { destinatario, mensagem: document.getElementById('swal-msg').value };
            }
        });
        return r.isConfirmed ? r.value : null;
    },
    /** Pergunta por que o cliente não aprovou o orçamento. Devolve o motivo ou null se cancelar. */
    async motivoRecusa(numero) {
        const opcoes = {
            'Preço': 'Preço', 'Prazo': 'Prazo', 'Cliente desistiu': 'Cliente desistiu',
            'Sem resposta do cliente': 'Sem resposta do cliente', 'Outro': 'Outro',
        };
        const r = await Swal.fire({
            title: 'Por que não foi aprovado?',
            text: `Orçamento ${numero}`,
            input: 'select',
            inputOptions: opcoes,
            inputPlaceholder: 'Escolha o motivo',
            inputValidator: (v) => v ? undefined : 'Escolha um motivo.',
            showCancelButton: true,
            confirmButtonColor: '#e11d48',
            cancelButtonColor: '#64748b',
            confirmButtonText: 'Registrar como não aprovado',
            cancelButtonText: 'Cancelar'
        });
        return r.isConfirmed ? String(r.value) : null;
    },
    async pedirMotivo(titulo, texto, botao = 'Salvar alterações') {
        const r = await Swal.fire({
            title: titulo,
            text: texto,
            input: 'textarea',
            inputPlaceholder: 'Ex.: correção do valor da peça a pedido do cliente',
            inputAttributes: { maxlength: '500' },
            showCancelButton: true,
            confirmButtonColor: '#0891b2',
            cancelButtonColor: '#64748b',
            confirmButtonText: botao,
            cancelButtonText: 'Cancelar',
            inputValidator: (v) => (String(v || '').trim().length < 5 ? 'Descreva o motivo (mínimo de 5 caracteres).' : undefined)
        });
        return r.isConfirmed ? String(r.value).trim() : null;
    },
    async pedirTexto(titulo, texto, valorInicial, botao = 'Confirmar') {
        const r = await Swal.fire({
            title: titulo,
            text: texto,
            input: 'text',
            inputValue: valorInicial,
            showCancelButton: true,
            confirmButtonColor: '#0891b2',
            cancelButtonColor: '#64748b',
            confirmButtonText: botao,
            cancelButtonText: 'Cancelar',
            inputValidator: (v) => (!String(v || '').trim() ? 'Informe um nome para o arquivo.' : undefined)
        });
        return r.isConfirmed ? String(r.value).trim() : null;
    }
};
/**
 * Pergunta como nomear o arquivo e baixa o documento (Word) do endereço informado.
 * O nome sugerido já vem preenchido; o servidor remove caracteres inválidos e acrescenta ".docx".
 */
async function baixarDocumento(url, nomeSugerido) {
    const nome = await Mensagem.pedirTexto('Nome do arquivo', 'Escolha o nome com que o documento será salvo:', nomeSugerido.replace(/\.docx$/i, ''), 'Baixar');
    if (nome === null)
        return;
    try {
        const separador = url.includes('?') ? '&' : '?';
        const resposta = await fetch(`${url}${separador}nome=${encodeURIComponent(nome)}`);
        if (!resposta.ok) {
            let mensagem = 'Não foi possível gerar o documento.';
            try {
                mensagem = (await resposta.json()).mensagem || mensagem;
            }
            catch (e) { /* resposta sem JSON */ }
            await Mensagem.erro(mensagem);
            return;
        }
        const blob = await resposta.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = (nome.replace(/[\\/:*?"<>|]+/g, '').trim() || 'documento') + '.docx';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
        Mensagem.sucesso('Documento baixado.');
    }
    catch (e) {
        Mensagem.erro('Erro ao comunicar com o servidor.');
    }
}
/**
 * Escapa texto para uso seguro dentro de innerHTML (evita XSS com dados vindos do servidor).
 * Use SEMPRE em valores digitados por pessoas: nomes, descrições, observações, etc.
 */
function escapeHtml(valor) {
    return String(valor ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
/** Formata número como moeda brasileira (R$ 1.234,56). */
function formatarMoeda(valor) {
    return (valor ?? 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
/** Converte AAAA-MM-DD em DD/MM/AAAA sem passar por fuso horário. */
function formatarDataBr(iso) {
    if (!iso)
        return '';
    const [a, m, d] = iso.substring(0, 10).split('-');
    return `${d}/${m}/${a}`;
}
class BaseUI {
    constructor() {
        this.subMenuGerenciar();
        this.iniciarMenuLateral();
        this.iniciarMenuPerfil();
        this.iniciarControleInatividade(); // <--- Gatilho adicionado aqui[cite: 12]
    }
    subMenuGerenciar() {
        const configurarMenu = (idBotao, idSubmenu, idSeta) => {
            const btn = document.getElementById(idBotao);
            const submenu = document.getElementById(idSubmenu);
            const seta = document.getElementById(idSeta);
            if (btn && submenu) {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    submenu.classList.toggle('hidden');
                    submenu.classList.toggle('flex');
                    if (seta)
                        seta.classList.toggle('rotate-180');
                    btn.classList.toggle('text-cyan-400');
                });
            }
        };
        configurarMenu('btn-menu-gerenciar', 'submenu-gerenciar', 'seta-gerenciar');
        configurarMenu('btn-menu-orcamentos', 'submenu-orcamentos', 'seta-orcamentos');
    }
    /**
     * Menu lateral recolhível: fica fechado e abre/fecha pelo botão do cabeçalho.
     * Fecha ao clicar no fundo escuro, no "×" ou ao apertar Esc. Fechado, não recebe foco do teclado.
     */
    iniciarMenuLateral() {
        const menu = document.getElementById('sidebar');
        const fundo = document.getElementById('sidebar-backdrop');
        const btnAbrir = document.getElementById('btn-menu-abrir');
        const btnFechar = document.getElementById('btn-menu-fechar');
        if (!menu || !fundo || !btnAbrir)
            return;
        const aberto = () => !menu.classList.contains('-translate-x-full');
        const definir = (abrir) => {
            menu.classList.toggle('-translate-x-full', !abrir);
            menu.setAttribute('aria-hidden', String(!abrir));
            menu.inert = !abrir;
            fundo.classList.toggle('hidden', !abrir);
            btnAbrir.setAttribute('aria-expanded', String(abrir));
            if (abrir) {
                const alvo = menu.querySelector('a[aria-current="page"]') || menu.querySelector('nav a');
                alvo?.focus();
            }
            else {
                btnAbrir.focus();
            }
        };
        menu.inert = true; // começa recolhido
        btnAbrir.addEventListener('click', () => definir(!aberto()));
        btnFechar?.addEventListener('click', () => definir(false));
        fundo.addEventListener('click', () => definir(false));
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && aberto())
            definir(false); });
    }
    iniciarMenuPerfil() {
        // Elementos do Perfil
        const btnPerfil = document.getElementById("btn-perfil");
        const dropdownPerfil = document.getElementById("dropdown-perfil");
        // Elementos do Modal de Senha
        const btnAbrirSenha = document.getElementById("btn-abrir-senha");
        const modalSenha = document.getElementById("modal-senha");
        const btnFecharSenha = document.getElementById("btn-fechar-senha");
        const formSenha = document.getElementById("form-alterar-senha");
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
                }
                else {
                    dropdownPerfil.classList.add("opacity-0", "scale-95");
                    setTimeout(() => dropdownPerfil.classList.add("hidden"), 200);
                }
            });
            // Fechar dropdown se clicar fora dele
            document.addEventListener("click", (e) => {
                const targetNode = e.target;
                if (!dropdownPerfil.contains(targetNode) && !btnPerfil.contains(targetNode)) {
                    dropdownPerfil.classList.add("opacity-0", "scale-95");
                    setTimeout(() => dropdownPerfil.classList.add("hidden"), 200);
                }
            });
        }
        // Primeiro acesso (ou servidor exigindo troca): o modal abre sozinho e não pode ser fechado.
        let senhaObrigatoria = false;
        const abrirModalSenha = (obrigatoria) => {
            if (!modalSenha)
                return;
            senhaObrigatoria = obrigatoria;
            modalSenha.classList.remove("hidden");
            if (btnFecharSenha)
                btnFecharSenha.classList.toggle("hidden", obrigatoria);
            const aviso = document.getElementById("aviso-senha-obrigatoria");
            if (aviso)
                aviso.classList.toggle("hidden", !obrigatoria);
        };
        // Lógica de Abrir o Modal de Senha
        if (btnAbrirSenha && modalSenha && dropdownPerfil) {
            btnAbrirSenha.addEventListener("click", () => {
                abrirModalSenha(false);
                dropdownPerfil.classList.add("opacity-0", "scale-95", "hidden");
            });
        }
        if (window.PRIMEIRO_ACESSO === true)
            abrirModalSenha(true);
        window.addEventListener("trocar-senha-obrigatoria", () => abrirModalSenha(true));
        // Lógica de Fechar o Modal de Senha
        if (btnFecharSenha && modalSenha && formSenha && msgErro) {
            btnFecharSenha.addEventListener("click", () => {
                if (senhaObrigatoria)
                    return;
                modalSenha.classList.add("hidden");
                formSenha.reset();
                msgErro.classList.add("hidden");
            });
        }
        // Validação e envio do formulário de senha
        if (formSenha && msgErro && modalSenha) {
            formSenha.addEventListener("submit", async (e) => {
                e.preventDefault();
                const atual = document.getElementById("senha-atual").value;
                const s1 = document.getElementById("nova-senha").value;
                const s2 = document.getElementById("confirma-senha").value;
                const mostrarErro = (texto) => {
                    msgErro.textContent = texto;
                    msgErro.classList.remove("hidden");
                };
                if (s1 !== s2)
                    return mostrarErro("As senhas não coincidem!");
                if (s1.length < 8)
                    return mostrarErro("A senha deve ter pelo menos 8 caracteres.");
                try {
                    const resposta = await fetch('/api/alterar-senha/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ senha_atual: atual, nova_senha: s1 })
                    });
                    const resultado = await resposta.json();
                    if (resultado.status !== 'sucesso')
                        return mostrarErro(resultado.mensagem || "Não foi possível alterar a senha.");
                    formSenha.reset();
                    msgErro.classList.add("hidden");
                    modalSenha.classList.add("hidden");
                    if (senhaObrigatoria)
                        window.location.reload();
                    else
                        Mensagem.sucesso("Senha alterada com sucesso!");
                }
                catch (erro) {
                    console.error(erro);
                    mostrarErro("Erro de conexão com o servidor.");
                }
            });
        }
    }
    // ==========================================
    // CONTROLE DE SESSÃO E INATIVIDADE
    // ==========================================
    iniciarControleInatividade() {
        let timeoutDeInatividade;
        // Define o tempo limite em milissegundos (ex: 30 minutos = 30 * 60 * 1000)
        const TEMPO_LIMITE_MS = 30 * 60 * 1000;
        const resetarCronometro = () => {
            clearTimeout(timeoutDeInatividade);
            timeoutDeInatividade = window.setTimeout(this.deslogarUsuario, TEMPO_LIMITE_MS);
        };
        // Redireciona para a rota de logout do Django
        this.deslogarUsuario = () => {
            Mensagem.aviso("Sua sessão expirou por inatividade. Por favor, faça login novamente.", "Sessão expirada")
                .then(() => { window.location.href = '/logout/'; });
        };
        // Escuta as ações do usuário (mouse, teclado e scroll) para provar que ele está ativo
        window.addEventListener('mousemove', resetarCronometro);
        window.addEventListener('keydown', resetarCronometro);
        window.addEventListener('scroll', resetarCronometro);
        window.addEventListener('click', resetarCronometro);
        // Inicia o cronômetro no primeiro carregamento
        resetarCronometro();
    }
}
