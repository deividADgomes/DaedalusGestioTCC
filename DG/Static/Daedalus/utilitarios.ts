type CampoDeFormulario = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

const SENHA_MINIMA = 4;

const CARACTERES_ESCAPADOS: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
};

const CLASSES_BOTAO_INSERCAO = ['bg-cyan-600', 'hover:bg-cyan-500', 'shadow-[0_0_15px_rgba(6,182,212,0.3)]'];
const CLASSES_BOTAO_EDICAO = ['bg-amber-600', 'hover:bg-amber-500', 'shadow-[0_0_15px_rgba(245,158,11,0.3)]'];

const CLASSE_MENSAGEM_NEUTRA = 'text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10';
const CLASSE_MENSAGEM_ERRO = 'text-sm font-bold text-red-500 col-span-full text-center py-10';

function escapeHtml(valor: unknown): string {
    return String(valor ?? '').replace(/[&<>"']/g, (caractere) => CARACTERES_ESCAPADOS[caractere]);
}

function obterElemento<T extends HTMLElement = HTMLElement>(id: string): T {
    return document.getElementById(id) as T;
}

function valorDoCampo(id: string): string {
    return obterElemento<CampoDeFormulario>(id).value;
}

function definirValorDoCampo(id: string, valor: string): void {
    obterElemento<CampoDeFormulario>(id).value = valor;
}

async function requisitarJson(url: string, opcoes: RequestInit = {}): Promise<any> {
    const resposta = await fetch(url, opcoes);
    return resposta.json();
}

function buscarJson(url: string): Promise<any> {
    return requisitarJson(url);
}

function enviarJson(url: string, dados: unknown, metodo = 'POST'): Promise<any> {
    return requisitarJson(url, {
        method: metodo,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dados),
    });
}

function htmlMensagemNeutra(texto: string): string {
    return `<p class="${CLASSE_MENSAGEM_NEUTRA}">${texto}</p>`;
}

function htmlMensagemErro(texto: string): string {
    return `<p class="${CLASSE_MENSAGEM_ERRO}">${texto}</p>`;
}

function trocarClasses(elemento: HTMLElement, de: string[], para: string[]): void {
    de.forEach((classe, indice) => elemento.classList.replace(classe, para[indice]));
}

function aplicarModoEdicao(botao: HTMLButtonElement, rotulo: string): void {
    botao.innerText = rotulo;
    trocarClasses(botao, CLASSES_BOTAO_INSERCAO, CLASSES_BOTAO_EDICAO);
}

function aplicarModoInsercao(botao: HTMLButtonElement, rotulo: string): void {
    botao.innerText = rotulo;
    trocarClasses(botao, CLASSES_BOTAO_EDICAO, CLASSES_BOTAO_INSERCAO);
}

function marcarRotulosFlutuantes(preenchidos: boolean): void {
    document.querySelectorAll('.input-dynamic').forEach((campo) => campo.classList.toggle('has-value', preenchidos));
}

function formatarCnpj(valor: string): string {
    if (!valor) return '';
    return valor
        .replace(/\D/g, '')
        .substring(0, 14)
        .replace(/^(\d{2})(\d)/, '$1.$2')
        .replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
        .replace(/\.(\d{3})(\d)/, '.$1/$2')
        .replace(/(\d{4})(\d)/, '$1-$2');
}
