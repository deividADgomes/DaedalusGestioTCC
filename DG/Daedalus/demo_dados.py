"""
Gerador dos dados de demonstração do Daedalus Gestio (somente Python, sem Django).

Tudo aqui é FICTÍCIO: empresas, CNPJs, pessoas, números de série e números de peça.
O comando `python manage.py popular_demo` usa este módulo para gravar os dados no banco.

Os dados são montados para que o dashboard conte uma história durante a apresentação:
- um técnico fora do limite de controle (crítico), um em atenção, um destaque e um com amostra pequena;
- um modelo que concentra o NFF (peça funcional trocada sem necessidade);
- NFF em alta nas últimas semanas, diagnósticos divergentes e séries reincidentes.
"""
import random
import zlib
from datetime import date, datetime, time, timedelta

SEED_PADRAO = 56
SENHA_DEMO = 'Demo@2026'
EMAIL_DOMINIO = 'daedalusdemo.com.br'


def cnpj_valido(base8):
    """CNPJ de 14 dígitos (8 da base + filial 0001 + dígitos verificadores)."""
    nums = [int(c) for c in f'{base8:08d}0001']
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        soma = sum(n * p for n, p in zip(nums, pesos))
        resto = soma % 11
        nums.append(0 if resto < 2 else 11 - resto)
    return ''.join(map(str, nums))


# ------------------------------------------------------------------
# Empresas, pessoas e modelos
# ------------------------------------------------------------------
PRESTADORAS = [
    ('TecField Assistência Técnica Ltda', 11250031, ['SP', 'MG']),
    ('Rede Norte Serviços de TI Ltda', 22340144, ['BA', 'PE', 'GO']),
    ('InfoCampo Soluções em Tecnologia', 33450257, ['RJ', 'MG']),
    ('Prime Field Service Ltda', 44560370, ['PR', 'RS']),
]
CLIENTES = [
    ('Banco Meridional S.A.', 55670483, 14), ('Farmácias Vida Rede de Drogarias', 66780596, 10),
    ('Supermercados Boa Compra', 77890609, 9), ('Hospital São Lucas', 88900712, 9),
    ('Construtora Alvorada Ltda', 99010825, 6), ('Universidade Horizonte', 10120938, 8),
    ('Transportadora Rápido Sul', 21231041, 7), ('Grupo Educacional Saber', 32341154, 6),
    ('Clínica Vital Saúde', 43451267, 4), ('Lojas Central Varejo', 54561370, 8),
]
CIDADES = {
    'SP': ['São Paulo', 'Campinas', 'Santos', 'Sorocaba'], 'MG': ['Belo Horizonte', 'Uberlândia', 'Juiz de Fora'],
    'BA': ['Salvador', 'Feira de Santana'], 'PE': ['Recife', 'Caruaru'], 'GO': ['Goiânia', 'Anápolis'],
    'RJ': ['Rio de Janeiro', 'Niterói', 'Volta Redonda'], 'PR': ['Curitiba', 'Londrina', 'Maringá'],
    'RS': ['Porto Alegre', 'Caxias do Sul', 'Pelotas'],
}
# nome, prestadora (índice), probabilidade de NFF, peso de volume
TECNICOS = [
    ('Rafael Moreira', 0, 0.22, 14), ('Bruno Tavares', 0, 0.70, 12), ('Camila Duarte', 0, 0.27, 10),
    ('Marcos Vinícius Lopes', 1, 0.30, 11), ('Aline Ferraz', 1, 0.10, 9), ('Jonas Pacheco', 1, 0.50, 9),
    ('Patrícia Nogueira', 2, 0.25, 10), ('Diego Andrade', 2, 0.33, 8), ('Letícia Barros', 2, 0.28, 7),
    ('Eduardo Ramos', 3, 0.30, 8), ('Sérgio Matos', 3, 0.26, 6), ('Natália Freitas', 3, 0.35, 0.9),
]
# login, cargo, nome, primeiro_acesso
FUNCIONARIOS = [
    (1001, 'Administrador', 'Carlos Eduardo Mendes', False),
    (1002, 'Gestor', 'Fernanda Lima Rocha', False),
    (1003, 'Analista de Triagem', 'Juliana Prado', False),
    (1004, 'Analista de Triagem', 'Thiago Cardoso', False),
    (1005, 'Analista de Triagem', 'Beatriz Almeida', False),
    (1006, 'Analista de Triagem', 'Rodrigo Silveira', False),
    (1007, 'Funcionário', 'Marina Duarte', False),
    (1008, 'Funcionário', 'Lucas Pereira', True),     # senha = matrícula: demonstra o primeiro acesso
]
ANALISTAS = [1003, 1004, 1005, 1006]

NOTEBOOK, DESKTOP, IMPRESSORA = 'notebook', 'desktop', 'impressora'
# pn, modelo, família, peso de volume, reforço de NFF
MODELOS = [
    ('8GM15LA', 'HP ProBook 450 G9 Notebook', NOTEBOOK, 5.0, 1.45),
    ('6S6Y2LA', 'HP EliteBook 840 G8 Notebook', NOTEBOOK, 3.0, 1.0),
    ('1Y8D3LA', 'HP 14-dq2000 Notebook', NOTEBOOK, 2.5, 1.0),
    ('7K2N4LA', 'HP ZBook Firefly 14 G8', NOTEBOOK, 1.5, 0.9),
    ('2M6C8LA', 'HP ProBook 440 G8 Notebook', NOTEBOOK, 2.5, 1.0),
    ('6N7Q2LA', 'HP Elite Dragonfly G3', NOTEBOOK, 1.0, 0.8),
    ('3C7F1LA', 'HP ProDesk 400 G7 Desktop SFF', DESKTOP, 2.5, 1.0),
    ('5F9H7LA', 'HP EliteDesk 800 G6 Mini', DESKTOP, 2.0, 0.9),
    ('9T1B6LA', 'HP Z2 Tower G9 Workstation', DESKTOP, 1.0, 0.9),
    ('3W4X1LA', 'HP ProOne 440 G9 All-in-One', DESKTOP, 1.0, 1.0),
    ('4R5P9LA', 'HP LaserJet Pro M404dn', IMPRESSORA, 1.5, 1.0),
    ('0J3V5LA', 'HP OfficeJet Pro 9010', IMPRESSORA, 1.0, 1.0),
]

# tipo de peça: rótulo, peso de falha, famílias, textos
TIPOS = {
    'bateria': dict(rotulo='Bateria', peso=22, fam=[NOTEBOOK],
        queixas=['Bateria dura poucos minutos', 'Notebook desliga ao tirar da tomada', 'Bateria não carrega'],
        diag=['Bateria não carrega', 'Bateria viciada', 'Bateria inchada'],
        esp=['Bateria com capacidade de 31% do projeto', 'Células da bateria desbalanceadas'],
        nff=['Bateria dentro da especificação; calibração resolveu', 'Nenhum defeito constatado na bateria'],
        teste_ok='HP PC Hardware Diagnostics: bateria aprovada; ciclo completo de carga e descarga sem falhas',
        teste_falha='HP PC Hardware Diagnostics: bateria reprovada (capacidade abaixo de 40%)'),
    'tela': dict(rotulo='Tela LCD', peso=14, fam=[NOTEBOOK, DESKTOP],
        queixas=['Tela com listras verticais', 'Imagem não aparece no display', 'Tela trincada'],
        diag=['Tela com defeito', 'Display quebrado', 'Painel LCD com listras'],
        esp=['Painel LCD com linhas verticais por falha na placa T-CON'],
        nff=['Cabo flat da tela com mau contato; painel funcional', 'Nenhum defeito constatado no display'],
        teste_ok='Teste de pixels e cores aprovado; sem manchas ou linhas após 1 h de uso',
        teste_falha='Teste de pixels reprovado: linhas verticais permanentes'),
    'placa': dict(rotulo='Placa-mãe', peso=14, fam=[NOTEBOOK, DESKTOP],
        queixas=['Equipamento não liga', 'Equipamento desliga sozinho', 'Tela preta ao ligar'],
        diag=['Placa-mãe com defeito', 'Falha na placa-mãe'],
        esp=['Placa-mãe com curto na linha de alimentação', 'Falha no controlador de energia da placa-mãe'],
        nff=['Equipamento liga normalmente; falha causada por fonte externa', 'BIOS desatualizada; placa-mãe funcional'],
        teste_ok='Diagnóstico de sistema aprovado; stress test de 30 min sem falhas',
        teste_falha='Diagnóstico de sistema reprovado: sem sinal de vídeo e sem POST'),
    'teclado': dict(rotulo='Teclado', peso=11, fam=[NOTEBOOK],
        queixas=['Teclas não respondem', 'Teclado digita caracteres errados'],
        diag=['Teclado com defeito', 'Teclas falhando'],
        esp=['Membrana do teclado oxidada'],
        nff=['Teclado funcional; driver desatualizado', 'Nenhum defeito constatado no teclado'],
        teste_ok='Teste de teclas aprovado: todas as teclas respondem',
        teste_falha='Teste de teclas reprovado: 6 teclas sem resposta'),
    'ssd': dict(rotulo='SSD', peso=10, fam=[NOTEBOOK, DESKTOP], compartilhado='L85592-001',
        queixas=['Sistema lento e trava', 'Windows não inicializa'],
        diag=['SSD com falha', 'Disco não reconhecido'],
        esp=['SSD com setores realocados acima do limite'],
        nff=['SSD saudável (SMART aprovado); sistema operacional corrompido', 'Nenhum defeito constatado no SSD'],
        teste_ok='SMART aprovado; teste de leitura e escrita sem erros',
        teste_falha='SMART reprovado: setores realocados acima do limite'),
    'fonte': dict(rotulo='Fonte de alimentação', peso=9, fam=[NOTEBOOK, DESKTOP],
        queixas=['Equipamento não carrega', 'Carregador esquenta demais'],
        diag=['Fonte com defeito', 'Carregador não fornece tensão'],
        esp=['Fonte com tensão de saída abaixo de 17 V'],
        nff=['Fonte dentro da tensão nominal; cabo de energia com mau contato', 'Nenhum defeito constatado na fonte'],
        teste_ok='Tensão de saída medida dentro da especificação sob carga',
        teste_falha='Tensão de saída abaixo da especificação sob carga'),
    'memoria': dict(rotulo='Memória RAM', peso=6, fam=[NOTEBOOK, DESKTOP], compartilhado='M12345-001',
        queixas=['Tela azul frequente', 'Equipamento reinicia sozinho'],
        diag=['Memória RAM com falha', 'Erros de memória'],
        esp=['Módulo de memória com erros no teste de 4 passes'],
        nff=['Memória aprovada em 4 passes; erros causados por driver', 'Nenhum defeito constatado na memória'],
        teste_ok='Teste de memória em 4 passes sem erros',
        teste_falha='Teste de memória em 4 passes com erros'),
    'cooler': dict(rotulo='Cooler', peso=5, fam=[NOTEBOOK, DESKTOP],
        queixas=['Ruído alto no ventilador', 'Equipamento superaquece'],
        diag=['Cooler com defeito', 'Ventilador travando'],
        esp=['Rolamento do ventilador desgastado'],
        nff=['Ventilador funcional; dissipador com poeira (limpeza resolveu)', 'Nenhum defeito constatado no cooler'],
        teste_ok='Rotação do ventilador dentro do esperado sob carga',
        teste_falha='Ventilador com rotação irregular e ruído de atrito'),
    'wifi': dict(rotulo='Placa Wi-Fi', peso=4, fam=[NOTEBOOK, DESKTOP], compartilhado='L77815-001',
        queixas=['Wi-Fi cai constantemente', 'Não detecta redes'],
        diag=['Placa Wi-Fi com defeito'],
        esp=['Módulo Wi-Fi sem sinal de antena'],
        nff=['Driver de rede desatualizado; placa funcional', 'Nenhum defeito constatado na placa Wi-Fi'],
        teste_ok='Conexão estável por 1 h; potência de sinal normal',
        teste_falha='Módulo não detecta redes mesmo com antena reconectada'),
    'dobradica': dict(rotulo='Dobradiça', peso=3, fam=[NOTEBOOK],
        queixas=['Tampa solta', 'Dobradiça quebrada'],
        diag=['Dobradiça quebrada'],
        esp=['Dobradiça com fratura no suporte metálico'],
        nff=['Parafusos soltos; dobradiça íntegra'],
        teste_ok='Abertura e fechamento 50 vezes sem folga',
        teste_falha='Folga excessiva e fratura visível no suporte'),
    'fusor': dict(rotulo='Fusor', peso=4, fam=[IMPRESSORA],
        queixas=['Impressão com manchas', 'Papel enrolando na saída'],
        diag=['Fusor com defeito'],
        esp=['Fusor com resistência queimada'],
        nff=['Fusor funcional; papel úmido causava o problema'],
        teste_ok='Impressão de 100 páginas de teste sem manchas',
        teste_falha='Fusor não atinge a temperatura de operação'),
    'rolo': dict(rotulo='Rolo de tração', peso=4, fam=[IMPRESSORA],
        queixas=['Papel não é puxado', 'Atolamento frequente'],
        diag=['Rolo de tração desgastado'],
        esp=['Rolo de tração ressecado'],
        nff=['Rolo íntegro; bandeja desalinhada'],
        teste_ok='Alimentação de 200 folhas sem atolamento',
        teste_falha='Rolo patina e não traciona o papel'),
    'formatadora': dict(rotulo='Placa formatadora', peso=3, fam=[IMPRESSORA],
        queixas=['Impressora trava na inicialização', 'Erro 79 no visor'],
        diag=['Placa formatadora com defeito'],
        esp=['Placa formatadora com firmware sem recuperação'],
        nff=['Atualização de firmware resolveu; placa funcional'],
        teste_ok='Inicialização completa e impressão de página de teste',
        teste_falha='Impressora não conclui a inicialização'),
}
LEGENDAS = ['Peça retornada, vista frontal', 'Etiqueta com número de série', 'Detalhe do conector',
            'Teste na bancada', 'Peça retornada, vista posterior', 'Embalagem recebida']


def _pn_peca(modelo_pn, tipo, usados):
    comp = TIPOS[tipo].get('compartilhado')
    if comp:
        return comp
    n = zlib.crc32(f'{modelo_pn}-{tipo}'.encode()) % 90000 + 10000
    pn = f'L{n}-001'
    while pn in usados:
        n += 1
        pn = f'L{n}-001'
    return pn


def _sn(rng):
    letras, alnum = 'ABCDEFGHJKLMNPQRSTUVWXYZ', 'ABCDEFGHJKLMNPQRSTUVWXYZ0123456789'
    return f"{rng.randint(1, 9)}{''.join(rng.choice(letras) for _ in range(2))}{rng.randint(100, 999)}{''.join(rng.choice(alnum) for _ in range(4))}"


def _escolher(rng, itens, pesos):
    return rng.choices(itens, weights=pesos, k=1)[0]


def gerar(hoje, total=420, dias=120, seed=SEED_PADRAO):
    """Devolve um dicionário com todos os dados (listas de dicts) prontos para gravar."""
    rng = random.Random(seed)
    empresas = [dict(razao_social=n, cnpj=cnpj_valido(b), tipo=1) for n, b, _ in PRESTADORAS]
    empresas += [dict(razao_social=n, cnpj=cnpj_valido(b), tipo=2) for n, b, _ in CLIENTES]
    tecnicos = [dict(nome=n, prestadora_cnpj=empresas[i]['cnpj'], p_nff=p, peso=w) for n, i, p, w in TECNICOS]
    funcionarios = []
    for login, cargo, nome, primeiro in FUNCIONARIOS:
        primeiro_nome = nome.split()[0].lower().replace('á', 'a').replace('í', 'i')
        ultimo = nome.split()[-1].lower().replace('á', 'a').replace('í', 'i')
        funcionarios.append(dict(login=login, cargo=cargo, nome=nome, primeiro_acesso=primeiro,
                                 email=f'{primeiro_nome}.{ultimo}@{EMAIL_DOMINIO}'))

    # catálogo de peças e modelos
    pecas, modelos, usados = {}, [], set()
    for pn, nome, fam, peso, reforco in MODELOS:
        tipos = [t for t, d in TIPOS.items() if fam in d['fam']]
        if fam == NOTEBOOK:
            tipos = [t for t in tipos if rng.random() < 0.92 or t in ('bateria', 'tela', 'placa')]
        ligadas = []
        for t in tipos:
            ppn = _pn_peca(pn, t, usados)
            if ppn not in pecas:
                usados.add(ppn)
                desc = (f"{TIPOS[t]['rotulo']} compatível com vários modelos" if TIPOS[t].get('compartilhado')
                        else f"{TIPOS[t]['rotulo']} para {nome}")
                pecas[ppn] = dict(part_number=ppn, descricao=desc)
            ligadas.append((t, ppn))
        modelos.append(dict(pn=pn, modelo=nome, familia=fam, peso=peso, reforco=reforco, pecas=ligadas))

    # triagens
    inicio = hoje - timedelta(days=dias)
    datas = [inicio + timedelta(days=i) for i in range(dias)]          # até ontem
    pesos_dia = []
    for i, d in enumerate(datas):
        base = 0.6 + 0.8 * i / (dias - 1)                              # volume cresce ao longo do período
        pesos_dia.append(base * (0.03 if d.weekday() >= 5 else 1.0))
    ultimo_ticket, linhas = 481200, []

    def uma_triagem(sn=None, modelo=None, data=None, tecnico=None):
        t = tecnico or _escolher(rng, tecnicos, [x['peso'] for x in tecnicos])
        pres_idx = next(i for i, e in enumerate(empresas) if e['cnpj'] == t['prestadora_cnpj'])
        uf = rng.choice(PRESTADORAS[pres_idx][2])
        cliente = _escolher(rng, empresas[len(PRESTADORAS):], [c[2] for c in CLIENTES])
        m = modelo or _escolher(rng, modelos, [x['peso'] for x in modelos])
        tipo, ppn = _escolher(rng, m['pecas'], [TIPOS[t_]['peso'] for t_, _ in m['pecas']])
        d = data or _escolher(rng, datas, pesos_dia)
        dias_atras = (hoje - d).days
        rampa = 1.0 + 0.5 * max(0, 28 - dias_atras) / 28                  # NFF em alta nas últimas 4 semanas
        p = min(0.92, t['p_nff'] * m['reforco'] * rampa)
        nff = rng.random() < p
        return dict(tecnico=t, cliente=cliente, uf=uf, m=m, tipo=tipo, ppn=ppn, data=d, nff=nff, sn=sn or _sn(rng))

    sementes = [uma_triagem() for _ in range(total)]
    # reincidências: 14 séries voltam 2 ou 3 vezes (mesmo modelo, intervalo mínimo de 10 dias)
    extras = []
    for base in rng.sample(sementes, 14):
        for _ in range(rng.choice([1, 1, 2])):
            novo_dia = base['data'] + timedelta(days=rng.randint(10, 30))
            if novo_dia <= hoje - timedelta(days=1):
                extras.append(uma_triagem(sn=base['sn'], modelo=base['m'], data=novo_dia))
    sementes += extras
    sementes.sort(key=lambda s: s['data'])

    for s in sementes:
        k = TIPOS[s['tipo']]
        hora = time(rng.randint(8, 17), rng.randint(0, 59))
        ultimo_ticket += rng.randint(1, 9)
        diag = rng.choice(k['diag'])
        if s['nff']:
            constatado = rng.choice(k['nff'])
            testes = k['teste_ok']
            analise = f"Peça retornada submetida a testes de bancada. {testes}. {constatado}."
            conclusao = 'Peça funcional (NFF): a troca em campo não era necessária.'
            status = 1
        else:
            if rng.random() < 0.7:
                constatado = diag.lower() if rng.random() < 0.3 else diag
                conclusao = 'Defeito confirmado. O diagnóstico do técnico de campo procede.'
            else:
                constatado = rng.choice(k['esp'])
                conclusao = 'Defeito confirmado, com causa mais específica que a informada em campo.'
            testes = k['teste_falha']
            analise = f"Peça retornada submetida a testes de bancada. {testes}. Defeito confirmado: {constatado}."
            status = 2
        sem_peca = rng.random() < 0.08
        linha = dict(
            n_ticket=ultimo_ticket, nf=rng.randint(100000, 999999), cidade=rng.choice(CIDADES[s['uf']]), estado=s['uf'],
            tecnico_nome=s['tecnico']['nome'], cliente_cnpj=s['cliente']['cnpj'], modelo_pn=s['m']['pn'],
            analista_chamado=rng.choice(ANALISTAS + [1002]), analista_triagem=rng.choice(ANALISTAS),
            sn=s['sn'], status=status, data=datetime.combine(s['data'], hora),
            peca_pn=None if sem_peca else s['ppn'],
            troca=('Troca do equipamento completo' if sem_peca else
                   rng.choice(['Substituição da peça em campo', 'Peça trocada conforme diagnóstico do técnico',
                               'Troca realizada durante o chamado'])),
            defeito_usuario=rng.choice(k['queixas']), defeito_tecnico=diag, defeito_constatado=constatado,
            testes=testes, analise=analise, conclusao=conclusao, tipo_peca=s['tipo'], fotos=[])
        # fotos: mais comuns nos casos de NFF (servem de evidência)
        if rng.random() < (0.7 if status == 1 else 0.35):
            for legenda in rng.sample(LEGENDAS, rng.choice([1, 2, 2, 3])):
                linha['fotos'].append(dict(tipo=s['tipo'], legenda=legenda))
        linhas.append(linha)

    # pedidos de senha: um pendente (aparece no painel do administrador) e um já atendido
    solicitacoes = [dict(login=1007, atendida=False, dias_atras=0), dict(login=1005, atendida=True, dias_atras=9)]
    return dict(empresas=empresas, tecnicos=tecnicos, funcionarios=funcionarios, pecas=list(pecas.values()),
                modelos=modelos, triagens=linhas, solicitacoes=solicitacoes)
