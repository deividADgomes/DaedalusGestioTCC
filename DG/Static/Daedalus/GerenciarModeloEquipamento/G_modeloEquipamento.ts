/// <reference path="../baseUI.ts" />

(() => {
    class G_modeloEquipamento extends BaseUI {
        private btnSalvar: HTMLButtonElement;
        private btnLimpar: HTMLButtonElement;
        private form: HTMLFormElement;
        private listaModeloEquip: HTMLElement;
        private idAtual: number | null = null;
        private pecas: { part_number: string; descricao: string }[] = [];
        private candidatas: { part_number: string; descricao: string; selecionada: boolean; somente_local: boolean }[] = [];
        
        constructor() {
            super();
            this.btnSalvar = document.getElementById('btn-salvar-modelo') as HTMLButtonElement;
            this.btnLimpar = document.getElementById('btn-limpar') as HTMLButtonElement;
            this.form = document.getElementById('form-cadastro-modelo') as HTMLFormElement;
            this.listaModeloEquip = document.getElementById('lista-modelos') as HTMLElement;

            this.iniciarEventos();
            this.iniciarEventosPecas();
            this.carregarModelos(); // Busca os dados do servidor ao abrir a tela
        }

        private iniciarEventos(): void {
            this.btnSalvar.addEventListener('click', () => this.salvarModelo());
            this.btnLimpar.addEventListener('click', () => this.limparFormulario());
        }

        // ==========================================
        // LÓGICA DE SALVAR / ALTERAR (POST)
        // ==========================================
        private async salvarModelo(): Promise<void> {
            // Presumindo que os IDs dos inputs no seu HTML sejam 'pn' e 'modelo'
            const pn = (document.getElementById('pn') as HTMLInputElement).value;
            const modelo = (document.getElementById('modelo') as HTMLInputElement).value;

            if (!pn || !modelo) {
                alert("Preencha todos os campos obrigatórios (PN e Modelo)!");
                return;
            }

            // O pacote de dados alinhado com o EquipamentoDTO
            const dados = {
                id: this.idAtual,
                pn: pn,
                modelo: modelo
            };

            try {
                const resposta = await fetch('/api/modelo-equipamento/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dados)
                });

                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    alert(resultado.mensagem);
                    const idSalvo: number = resultado.id_gerado;
                    this.limparFormulario();
                    this.carregarModelos(); // Atualiza a grid
                    // Já abre o editor de peças do modelo recém-salvo
                    if (idSalvo) { this.prepararEdicao(idSalvo, pn, modelo); }
                } else {
                    alert("Erro: " + resultado.mensagem);
                }
            } catch (error) {
                console.error("Falha na requisição:", error);
                alert("Erro ao comunicar com o servidor.");
            }
        }

        // ==========================================
        // LÓGICA DE LISTAGEM (GET)
        // ==========================================
        private async carregarModelos(): Promise<void> {
            this.listaModeloEquip.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Carregando dados do servidor...</p>';

            try {
                const resposta = await fetch('/api/modelo-equipamento/');
                const resultado = await resposta.json();

                if (resultado.status === 'sucesso') {
                    this.listaModeloEquip.innerHTML = ''; 
                    
                    if (resultado.dados.length === 0) {
                        this.listaModeloEquip.innerHTML = '<p class="text-sm font-medium text-slate-500 uppercase col-span-full text-center py-10">Nenhum equipamento cadastrado.</p>';
                        return;
                    }

                    resultado.dados.forEach((equip: any) => {
                        const card = document.createElement('div');
                        card.className = "bg-[#1e293b] p-5 rounded-xl border border-[#334155] shadow-sm hover:border-cyan-500/50 transition-colors cursor-pointer group";
                        
                        card.innerHTML = `
                            <div class="flex justify-between items-start mb-2">
                                <span class="text-xs font-bold text-cyan-400 uppercase tracking-wider">Equipamento</span>
                                <span class="text-[10px] text-slate-500 font-mono">ID: ${equip.id}</span>
                            </div>
                            <h3 class="text-base font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">${escapeHtml(equip.modelo)}</h3>
                            <p class="text-xs text-slate-400 mt-1 font-mono">PN: ${escapeHtml(equip.pn)}</p>
                            <div class="mt-4 pt-3 border-t border-[#334155]/50 flex justify-between">
                                <span class="text-[10px] text-emerald-400 font-bold uppercase tracking-widest">${equip.total_pecas || 0} peça(s)</span>
                                <span class="text-[10px] text-slate-500 uppercase font-bold tracking-widest group-hover:text-cyan-500 transition-colors">Duplo clique para editar</span>
                            </div>
                        `;

                        // Duplo clique aciona a edição
                        card.addEventListener('dblclick', () => {
                            this.prepararEdicao(equip.id, equip.pn, equip.modelo);
                        });

                        this.listaModeloEquip.appendChild(card);
                    });
                } else {
                    this.listaModeloEquip.innerHTML = `<p class="text-sm font-bold text-red-500 col-span-full text-center py-10">Erro do Servidor: ${resultado.mensagem}</p>`;
                }
            } catch (error) {
                this.listaModeloEquip.innerHTML = '<p class="text-sm font-bold text-red-500 col-span-full text-center py-10">Erro crítico ao tentar conectar com o servidor.</p>';
            }
        }

        // ==========================================
        // MANIPULAÇÃO DA INTERFACE DÚPLICE
        // ==========================================
        private prepararEdicao(id: number, pn: string, modelo: string): void {
            this.idAtual = id;
            (document.getElementById('pn') as HTMLInputElement).value = pn;
            (document.getElementById('modelo') as HTMLInputElement).value = modelo;

            // Sinais visuais de modo de Alteração
            this.btnSalvar.innerText = "Alterar Registro";
            this.btnSalvar.classList.replace('bg-cyan-600', 'bg-amber-600');
            this.btnSalvar.classList.replace('hover:bg-cyan-500', 'hover:bg-amber-500');
            this.btnSalvar.classList.replace('shadow-[0_0_15px_rgba(6,182,212,0.3)]', 'shadow-[0_0_15px_rgba(245,158,11,0.3)]');
            
            // Ativa o Floating Label
            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.add('has-value'));

            this.form.scrollIntoView({ behavior: 'smooth', block: 'start' });
            this.abrirPecas(id, modelo);
        }

        private limparFormulario(): void {
            this.form.reset();
            this.idAtual = null;

            // Retorna ao visual padrão de Inserção
            this.btnSalvar.innerText = "Salvar Equipamento";
            this.btnSalvar.classList.replace('bg-amber-600', 'bg-cyan-600');
            this.btnSalvar.classList.replace('hover:bg-amber-500', 'hover:bg-cyan-500');
            this.btnSalvar.classList.replace('shadow-[0_0_15px_rgba(245,158,11,0.3)]', 'shadow-[0_0_15px_rgba(6,182,212,0.3)]');

            document.querySelectorAll('.input-dynamic').forEach(input => input.classList.remove('has-value'));
            document.getElementById('secao-pecas')?.classList.add('hidden');
            this.fecharPartSurfer();
            this.pecas = [];
        }

        // ==========================================
        // PEÇAS DO MODELO
        // ==========================================
        private iniciarEventosPecas(): void {
            document.getElementById('btn-add-peca')?.addEventListener('click', () => this.adicionarPecaDoFormulario());
            document.getElementById('peca-pn')?.addEventListener('keydown', (e) => {
                if ((e as KeyboardEvent).key === 'Enter') { e.preventDefault(); this.adicionarPecaDoFormulario(); }
            });
            document.getElementById('btn-importar-pecas')?.addEventListener('click', () => this.importarLista());
            document.getElementById('btn-salvar-pecas')?.addEventListener('click', () => this.salvarPecas());
            document.getElementById('btn-partsurfer')?.addEventListener('click', () => this.buscarPartSurfer());
            document.getElementById('ps-fechar')?.addEventListener('click', () => this.fecharPartSurfer());
            document.getElementById('ps-aplicar')?.addEventListener('click', () => this.aplicarPartSurfer());
            document.getElementById('ps-marcar-todas')?.addEventListener('click', () => this.marcarCandidatas(true));
            document.getElementById('ps-desmarcar')?.addEventListener('click', () => this.marcarCandidatas(false));
            document.getElementById('ps-filtro')?.addEventListener('input', () => this.desenharCandidatas());
        }

        // ==========================================
        // CONSULTA AUTOMÁTICA AO HP PARTSURFER
        // ==========================================
        private async buscarPartSurfer(): Promise<void> {
            if (!this.idAtual) { return; }
            const id = this.idAtual;
            const btn = document.getElementById('btn-partsurfer') as HTMLButtonElement;
            const rotulo = btn.innerText;
            btn.disabled = true;
            btn.innerText = 'Consultando...';
            try {
                const resp = await fetch(`/api/modelo-equipamento/${id}/partsurfer/`, { method: 'POST' });
                const res = await resp.json();
                if (res.status !== 'sucesso') { alert(res.mensagem); return; }
                if (this.idAtual !== id) { return; }
                // O que já está na lista local (mesmo sem salvar) vem marcado
                const locais = new Set(this.pecas.map(p => p.part_number));
                this.candidatas = res.dados.map((c: any) => ({ ...c, selecionada: c.selecionada || locais.has(c.part_number) }));
                this.pecas.forEach(p => {
                    if (!this.candidatas.some(c => c.part_number === p.part_number)) {
                        this.candidatas.push({ part_number: p.part_number, descricao: p.descricao, selecionada: true, somente_local: true });
                    }
                });
                (document.getElementById('partsurfer-msg') as HTMLElement).innerText = res.mensagem + ' Marque as que este modelo usa.';
                (document.getElementById('ps-filtro') as HTMLInputElement).value = '';
                document.getElementById('painel-partsurfer')?.classList.remove('hidden');
                this.desenharCandidatas();
            } catch (e) {
                alert('Erro ao comunicar com o servidor.');
            } finally {
                btn.disabled = false;
                btn.innerText = rotulo;
            }
        }

        private desenharCandidatas(): void {
            const filtro = (document.getElementById('ps-filtro') as HTMLInputElement).value.trim().toLowerCase();
            const ul = document.getElementById('ps-lista') as HTMLElement;
            ul.innerHTML = '';
            this.candidatas
                .filter(c => !filtro || c.part_number.toLowerCase().includes(filtro) || c.descricao.toLowerCase().includes(filtro))
                .forEach(c => {
                    const li = document.createElement('li');
                    li.className = 'py-1.5';
                    li.innerHTML = `<label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox" class="accent-cyan-500" ${c.selecionada ? 'checked' : ''}>
                        <span class="font-mono text-cyan-400">${escapeHtml(c.part_number)}</span>
                        <span class="text-slate-300">${escapeHtml(c.descricao)}</span>
                        ${c.somente_local ? '<span class="text-[10px] text-amber-400">(não veio do PartSurfer)</span>' : ''}
                    </label>`;
                    li.querySelector('input')?.addEventListener('change', (e) => {
                        c.selecionada = (e.target as HTMLInputElement).checked;
                    });
                    ul.appendChild(li);
                });
        }

        private marcarCandidatas(valor: boolean): void {
            this.candidatas.forEach(c => { c.selecionada = valor; });
            this.desenharCandidatas();
        }

        private aplicarPartSurfer(): void {
            this.pecas = this.candidatas
                .filter(c => c.selecionada)
                .map(c => ({ part_number: c.part_number, descricao: c.descricao }));
            this.desenharPecas();
            this.fecharPartSurfer();
        }

        private fecharPartSurfer(): void {
            document.getElementById('painel-partsurfer')?.classList.add('hidden');
            this.candidatas = [];
        }

        private async abrirPecas(id: number, modelo: string): Promise<void> {
            (document.getElementById('pecas-modelo-nome') as HTMLElement).innerText = modelo;
            document.getElementById('secao-pecas')?.classList.remove('hidden');
            this.pecas = [];
            this.fecharPartSurfer();
            this.desenharPecas();
            try {
                const resp = await fetch(`/api/modelo-equipamento/pecas/?id_equipamento=${id}`);
                const res = await resp.json();
                if (res.status === 'sucesso' && this.idAtual === id) {
                    this.pecas = res.dados.map((p: any) => ({ part_number: p.part_number, descricao: p.descricao || '' }));
                    this.desenharPecas();
                }
            } catch (e) {
                console.error('Falha ao carregar peças:', e);
            }
        }

        private adicionarPeca(pn: string, descricao: string): boolean {
            const chave = pn.trim().toUpperCase();
            if (!chave) { return false; }
            const existente = this.pecas.find(p => p.part_number === chave);
            if (existente) {
                if (descricao.trim()) { existente.descricao = descricao.trim(); }
            } else {
                this.pecas.push({ part_number: chave, descricao: descricao.trim() });
            }
            return true;
        }

        private adicionarPecaDoFormulario(): void {
            const pn = document.getElementById('peca-pn') as HTMLInputElement;
            const desc = document.getElementById('peca-descricao') as HTMLInputElement;
            if (!this.adicionarPeca(pn.value, desc.value)) {
                alert('Informe o Part Number da peça.');
                return;
            }
            pn.value = '';
            desc.value = '';
            pn.classList.remove('has-value');
            desc.classList.remove('has-value');
            pn.focus();
            this.desenharPecas();
        }

        private importarLista(): void {
            const area = document.getElementById('peca-colar') as HTMLTextAreaElement;
            let qtd = 0;
            area.value.split(/\r?\n/).forEach(linha => {
                const [pn, ...resto] = linha.split(/[;\t]/);
                if (this.adicionarPeca(pn || '', resto.join(' ').trim())) { qtd++; }
            });
            area.value = '';
            this.desenharPecas();
            if (qtd === 0) { alert('Nenhuma linha válida encontrada.'); }
        }

        private desenharPecas(): void {
            const ul = document.getElementById('lista-pecas') as HTMLElement;
            ul.innerHTML = '';
            document.getElementById('pecas-vazio')?.classList.toggle('hidden', this.pecas.length > 0);
            this.pecas.slice().sort((a, b) => a.part_number.localeCompare(b.part_number)).forEach(p => {
                const li = document.createElement('li');
                li.className = 'flex items-center justify-between py-2 gap-3';
                li.innerHTML = `<div class="min-w-0"><span class="font-mono text-cyan-400 text-xs">${escapeHtml(p.part_number)}</span>
                    <span class="text-slate-300 text-xs ml-3">${escapeHtml(p.descricao)}</span></div>
                    <button type="button" class="text-[10px] font-bold uppercase text-rose-400 hover:text-rose-300">Remover</button>`;
                li.querySelector('button')?.addEventListener('click', () => {
                    this.pecas = this.pecas.filter(x => x.part_number !== p.part_number);
                    this.desenharPecas();
                });
                ul.appendChild(li);
            });
        }

        private async salvarPecas(): Promise<void> {
            if (!this.idAtual) { return; }
            try {
                const resp = await fetch('/api/modelo-equipamento/pecas/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_equipamento: this.idAtual, pecas: this.pecas })
                });
                const res = await resp.json();
                if (res.status === 'sucesso') {
                    this.pecas = res.dados.map((p: any) => ({ part_number: p.part_number, descricao: p.descricao || '' }));
                    this.desenharPecas();
                    this.carregarModelos();
                    alert(res.mensagem);
                } else {
                    alert('Erro: ' + res.mensagem);
                }
            } catch (e) {
                alert('Erro ao comunicar com o servidor.');
            }
        }
    }

    window.addEventListener('DOMContentLoaded', () => {
        new G_modeloEquipamento();
    });

})();