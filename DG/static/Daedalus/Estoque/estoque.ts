/// <reference path="../BaseUI.ts" />
(() => {
    type ItemEstoque = {
        id_peca: number; part_number: string; descricao: string; equipamento_completo: boolean; saldo: number;
        minimo: number; local: string; custo_medio: number; valor_total: number; situacao: string;
    };

    const ROTULOS: Record<string, string> = { entrada: 'Entrada', saida: 'Saída', contagem: 'Contagem' };

    class Estoque {
        private itens: ItemEstoque[] = [];
        private temporizador: number | undefined;

        constructor() {
            const params = new URLSearchParams(window.location.search);
            const situacao = document.getElementById('estoque-situacao') as HTMLSelectElement;
            if (['abaixo', 'sem_saldo'].includes(params.get('situacao') || '')) situacao.value = params.get('situacao') as string;

            const busca = document.getElementById('estoque-busca') as HTMLInputElement;
            busca.addEventListener('input', () => {
                window.clearTimeout(this.temporizador);
                this.temporizador = window.setTimeout(() => this.carregar(), 300);
            });
            situacao.addEventListener('change', () => this.carregar());
            document.getElementById('card-abaixo')!.addEventListener('click', () => { situacao.value = 'abaixo'; this.carregar(); });
            document.getElementById('card-sem-saldo')!.addEventListener('click', () => { situacao.value = 'sem_saldo'; this.carregar(); });
            document.getElementById('btn-nova-entrada')!.addEventListener('click', () => this.novaEntrada());
            document.getElementById('estoque-linhas')!.addEventListener('click', (e) => this.aoClicarNaTabela(e));
            this.carregar();
        }

        private async carregar(): Promise<void> {
            const q = (document.getElementById('estoque-busca') as HTMLInputElement).value.trim();
            const situacao = (document.getElementById('estoque-situacao') as HTMLSelectElement).value;
            try {
                const res = await (await fetch(`/api/estoque/?q=${encodeURIComponent(q)}&situacao=${situacao}`)).json();
                if (res.status !== 'sucesso') { await Mensagem.erro(res.mensagem); return; }
                this.itens = res.dados;
                const r = res.resumo;
                (document.getElementById('res-itens') as HTMLElement).innerText = String(r.itens);
                (document.getElementById('res-valor') as HTMLElement).innerText = formatarMoeda(r.valor_total);
                (document.getElementById('res-abaixo') as HTMLElement).innerText = String(r.abaixo_minimo);
                (document.getElementById('res-sem-saldo') as HTMLElement).innerText = String(r.sem_saldo);
                this.desenhar();
            } catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }

        private desenhar(): void {
            document.getElementById('estoque-vazio')!.classList.toggle('hidden', this.itens.length > 0);
            const cor = (s: string) => s === 'sem_saldo' ? 'text-rose-400' : s === 'abaixo' ? 'text-amber-400' : 'text-emerald-400';
            (document.getElementById('estoque-linhas') as HTMLElement).innerHTML = this.itens.map((i) => `
                <tr>
                    <td class="px-4 py-2.5"><span class="font-mono text-cyan-300">${escapeHtml(i.part_number)}</span>
                        <span class="block text-[11px] text-slate-400">${escapeHtml(i.descricao || '')}${i.equipamento_completo ? ' (equipamento completo)' : ''}</span></td>
                    <td class="px-4 py-2.5 text-right font-bold ${cor(i.situacao)}">${i.saldo}</td>
                    <td class="px-4 py-2.5 text-right text-slate-400">${i.minimo || '—'}</td>
                    <td class="px-4 py-2.5 text-slate-300">${escapeHtml(i.local || '—')}</td>
                    <td class="px-4 py-2.5 text-right">${i.custo_medio ? escapeHtml(formatarMoeda(i.custo_medio)) : '—'}</td>
                    <td class="px-4 py-2.5 text-right">${i.valor_total ? escapeHtml(formatarMoeda(i.valor_total)) : '—'}</td>
                    <td class="px-4 py-2.5 text-right whitespace-nowrap">
                        <button class="acao px-2 py-1 rounded bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/40" data-acao="entrada" data-id="${i.id_peca}">Entrada</button>
                        <button class="acao px-2 py-1 rounded bg-rose-600/20 text-rose-300 hover:bg-rose-600/40" data-acao="saida" data-id="${i.id_peca}">Saída</button>
                        <button class="acao px-2 py-1 rounded bg-slate-700 text-slate-200 hover:bg-slate-600" data-acao="contagem" data-id="${i.id_peca}">Contagem</button>
                        <button class="acao px-2 py-1 rounded bg-slate-700 text-slate-200 hover:bg-slate-600" data-acao="config" data-id="${i.id_peca}">Mínimo/local</button>
                        <button class="acao px-2 py-1 rounded bg-slate-700 text-slate-200 hover:bg-slate-600" data-acao="historico" data-id="${i.id_peca}">Histórico</button>
                    </td>
                </tr>`).join('');
        }

        private aoClicarNaTabela(e: Event): void {
            const botao = (e.target as HTMLElement).closest('.acao') as HTMLElement | null;
            if (!botao) return;
            const item = this.itens.find((i) => i.id_peca === Number(botao.dataset.id));
            if (!item) return;
            const acao = botao.dataset.acao;
            if (acao === 'historico') this.historico(item);
            else if (acao === 'config') this.configurar(item);
            else this.movimento(acao as string, item);
        }

        // ---------------------------------------------------------------- movimento (entrada, saída, contagem)
        private campo(id: string): HTMLInputElement { return document.getElementById(id) as HTMLInputElement; }

        private htmlCampos(tipo: string): string {
            const rotuloQtd = tipo === 'contagem' ? 'Quantidade contada (saldo real)' : 'Quantidade';
            const placeholderMotivo = tipo === 'entrada' ? 'Nota fiscal ou origem (opcional)'
                : tipo === 'saida' ? 'Para quê saiu (ticket, laudo, perda...)' : 'Motivo do ajuste (obrigatório)';
            return `
                <label style="display:block;text-align:left;font-size:12px;opacity:.75">${rotuloQtd}</label>
                <input id="mv-qtd" type="number" min="${tipo === 'contagem' ? 0 : 1}" step="1" class="swal2-input" style="margin:4px 0 10px;width:100%">
                ${tipo === 'entrada' ? `<label style="display:block;text-align:left;font-size:12px;opacity:.75">Custo unitário (opcional)</label>
                <input id="mv-custo" type="text" inputmode="decimal" placeholder="0,00" class="swal2-input" style="margin:4px 0 10px;width:100%">` : ''}
                <label style="display:block;text-align:left;font-size:12px;opacity:.75">Motivo</label>
                <input id="mv-motivo" type="text" maxlength="300" placeholder="${placeholderMotivo}" class="swal2-input" style="margin:4px 0 10px;width:100%">`;
        }

        private lerMovimento(tipo: string): any {
            const qtd = this.campo('mv-qtd').value.trim();
            const motivo = this.campo('mv-motivo').value.trim();
            if (qtd === '') { Swal.showValidationMessage('Informe a quantidade.'); return false; }
            if (tipo !== 'entrada' && !motivo) { Swal.showValidationMessage('Informe o motivo.'); return false; }
            return { tipo, quantidade: qtd, motivo, custo: tipo === 'entrada' ? this.campo('mv-custo').value.trim() : '' };
        }

        private async movimento(tipo: string, item: ItemEstoque): Promise<void> {
            const r = await Swal.fire({
                title: `${ROTULOS[tipo]}: ${item.part_number}`,
                html: `<p style="margin-bottom:8px;font-size:12px;opacity:.7">Saldo atual: ${item.saldo}</p>${this.htmlCampos(tipo)}`,
                showCancelButton: true, confirmButtonText: 'Registrar', cancelButtonText: 'Cancelar', confirmButtonColor: '#0891b2',
                preConfirm: () => this.lerMovimento(tipo)
            });
            if (r.isConfirmed) await this.enviar({ id_peca: item.id_peca, ...r.value });
        }

        private async enviar(corpo: any): Promise<void> {
            try {
                const res = await (await fetch('/api/estoque/movimentar/', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo)
                })).json();
                if (res.status === 'sucesso') { this.carregar(); Mensagem.sucesso(res.mensagem); }
                else await Mensagem.erro(res.mensagem);
            } catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }

        // ---------------------------------------------------------------- nova entrada (escolhe a peça do catálogo)
        private async novaEntrada(): Promise<void> {
            let escolhida: number | null = null;
            const r = await Swal.fire({
                title: 'Nova entrada',
                html: `<label style="display:block;text-align:left;font-size:12px;opacity:.75">Peça do catálogo (PN ou descrição)</label>
                    <input id="mv-busca" type="text" placeholder="Digite ao menos 2 letras" class="swal2-input" style="margin:4px 0 6px;width:100%">
                    <select id="mv-peca" size="5" class="swal2-select" style="width:100%;margin:0 0 10px;height:auto"></select>
                    ${this.htmlCampos('entrada')}`,
                showCancelButton: true, confirmButtonText: 'Registrar entrada', cancelButtonText: 'Cancelar', confirmButtonColor: '#0891b2',
                didOpen: () => {
                    const caixa = this.campo('mv-busca');
                    const lista = document.getElementById('mv-peca') as HTMLSelectElement;
                    let espera: number | undefined;
                    caixa.addEventListener('input', () => {
                        window.clearTimeout(espera);
                        espera = window.setTimeout(async () => {
                            const termo = caixa.value.trim();
                            if (termo.length < 2) { lista.innerHTML = ''; return; }
                            const res = await (await fetch(`/api/estoque/catalogo/?q=${encodeURIComponent(termo)}`)).json();
                            lista.innerHTML = '';
                            (res.dados || []).forEach((p: any) => lista.add(new Option(
                                `${p.part_number} - ${(p.descricao || '').slice(0, 60)}${p.controlada ? ' (já controlada)' : ''}`, String(p.id_peca))));
                        }, 300);
                    });
                    lista.addEventListener('change', () => { escolhida = Number(lista.value) || null; });
                },
                preConfirm: () => {
                    if (!escolhida) { Swal.showValidationMessage('Escolha a peça na lista.'); return false; }
                    const mov = this.lerMovimento('entrada');
                    return mov ? { id_peca: escolhida, ...mov } : false;
                }
            });
            if (r.isConfirmed) await this.enviar(r.value);
        }

        // ---------------------------------------------------------------- mínimo e local
        private async configurar(item: ItemEstoque): Promise<void> {
            const r = await Swal.fire({
                title: `Mínimo e local: ${item.part_number}`,
                html: `<label style="display:block;text-align:left;font-size:12px;opacity:.75">Estoque mínimo (0 = sem alerta)</label>
                    <input id="cf-min" type="number" min="0" step="1" value="${item.minimo}" class="swal2-input" style="margin:4px 0 10px;width:100%">
                    <label style="display:block;text-align:left;font-size:12px;opacity:.75">Local (prateleira, caixa...)</label>
                    <input id="cf-local" type="text" maxlength="100" value="${escapeHtml(item.local)}" class="swal2-input" style="margin:4px 0 10px;width:100%">`,
                showCancelButton: true, confirmButtonText: 'Salvar', cancelButtonText: 'Cancelar', confirmButtonColor: '#0891b2',
                preConfirm: () => ({ id_peca: item.id_peca, minimo: this.campo('cf-min').value.trim(), local: this.campo('cf-local').value.trim() })
            });
            if (!r.isConfirmed) return;
            try {
                const res = await (await fetch('/api/estoque/config/', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(r.value)
                })).json();
                if (res.status === 'sucesso') { this.carregar(); Mensagem.sucesso(res.mensagem); }
                else await Mensagem.erro(res.mensagem);
            } catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }

        // ---------------------------------------------------------------- histórico
        private async historico(item: ItemEstoque): Promise<void> {
            try {
                const res = await (await fetch(`/api/estoque/${item.id_peca}/movimentos/`)).json();
                if (res.status !== 'sucesso') { await Mensagem.erro(res.mensagem); return; }
                const linhas = res.dados.map((m: any) => `
                    <tr style="border-top:1px solid #33415566">
                        <td style="padding:6px;white-space:nowrap">${escapeHtml(new Date(m.quando).toLocaleString('pt-BR'))}</td>
                        <td style="padding:6px">${escapeHtml(m.tipo)}</td>
                        <td style="padding:6px;text-align:right;font-weight:bold;color:${m.quantidade > 0 ? '#34d399' : '#fb7185'}">${m.quantidade > 0 ? '+' : ''}${m.quantidade}</td>
                        <td style="padding:6px;text-align:right">${m.saldo_apos}</td>
                        <td style="padding:6px;text-align:left">${escapeHtml(m.usuario)}${m.motivo ? ': ' + escapeHtml(m.motivo) : ''}</td>
                    </tr>`).join('');
                await Swal.fire({
                    title: `Histórico: ${item.part_number}`, width: 760,
                    html: res.dados.length === 0 ? '<p style="opacity:.7">Nenhum movimento ainda.</p>'
                        : `<div style="max-height:360px;overflow:auto;font-size:12px"><table style="width:100%"><thead><tr style="opacity:.6"><th style="padding:6px">Quando</th><th>Tipo</th><th>Qtde</th><th>Saldo</th><th style="text-align:left">Quem e por quê</th></tr></thead><tbody>${linhas}</tbody></table></div>`,
                    confirmButtonText: 'Fechar', confirmButtonColor: '#64748b'
                });
            } catch (e) {
                await Mensagem.erro('Erro ao conectar com o servidor.');
            }
        }
    }

    window.addEventListener('DOMContentLoaded', () => { new Estoque(); });
})();
