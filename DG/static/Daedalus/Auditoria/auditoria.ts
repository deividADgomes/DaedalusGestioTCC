/// <reference path="../BaseUI.ts" />
(() => {
    class Auditoria {
        private temporizador: number | undefined;

        constructor() {
            const campo = document.getElementById('auditoria-busca') as HTMLInputElement;
            campo.addEventListener('input', () => {
                window.clearTimeout(this.temporizador);
                this.temporizador = window.setTimeout(() => this.carregar(campo.value), 300);
            });
            this.carregar('');
        }

        private async carregar(busca: string): Promise<void> {
            const corpo = document.getElementById('auditoria-linhas') as HTMLElement;
            const vazio = document.getElementById('auditoria-vazio') as HTMLElement;
            try {
                const res = await (await fetch(`/api/auditoria/?q=${encodeURIComponent(busca.trim())}`)).json();
                if (res.status !== 'sucesso') { await Mensagem.erro(res.mensagem); return; }
                vazio.classList.toggle('hidden', res.dados.length > 0);
                corpo.innerHTML = res.dados.map((l: any) => `
                    <tr>
                        <td class="px-4 py-2.5 whitespace-nowrap text-slate-400">${escapeHtml(new Date(l.quando).toLocaleString('pt-BR'))}</td>
                        <td class="px-4 py-2.5 font-semibold">${escapeHtml(l.usuario)}</td>
                        <td class="px-4 py-2.5">${escapeHtml(l.acao)}</td>
                        <td class="px-4 py-2.5">${escapeHtml(l.entidade)}${l.entidade_id ? ` <span class="text-slate-500">#${Number(l.entidade_id)}</span>` : ''}</td>
                        <td class="px-4 py-2.5 text-slate-400">${escapeHtml(l.descricao)}</td>
                    </tr>`).join('');
            } catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }
    }

    window.addEventListener('DOMContentLoaded', () => { new Auditoria(); });
})();
