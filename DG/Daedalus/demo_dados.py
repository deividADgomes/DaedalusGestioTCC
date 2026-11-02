import random
import zlib
from datetime import datetime, time, timedelta

from .dtos import CargoFuncionario, StatusPeca, TipoEmpresa

SEED_PADRAO = 56
SENHA_DEMO = 'Demo@2026'
EMAIL_DOMINIO = 'daedalusdemo.com.br'


PESOS_DO_CNPJ = (
    [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
    [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
)


def cnpj_valido(base_de_8_digitos):
    digitos = [int(caractere) for caractere in f'{base_de_8_digitos:08d}0001']
    for pesos in PESOS_DO_CNPJ:
        soma = sum(digito * peso for digito, peso in zip(digitos, pesos))
        resto = soma % 11
        digitos.append(0 if resto < 2 else 11 - resto)
    return ''.join(map(str, digitos))


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
TECNICOS = [
    ('Rafael Moreira', 0, 0.22, 14), ('Bruno Tavares', 0, 0.70, 12), ('Camila Duarte', 0, 0.27, 10),
    ('Marcos Vinícius Lopes', 1, 0.30, 11), ('Aline Ferraz', 1, 0.10, 9), ('Jonas Pacheco', 1, 0.50, 9),
    ('Patrícia Nogueira', 2, 0.25, 10), ('Diego Andrade', 2, 0.33, 8), ('Letícia Barros', 2, 0.28, 7),
    ('Eduardo Ramos', 3, 0.30, 8), ('Sérgio Matos', 3, 0.26, 6), ('Natália Freitas', 3, 0.35, 0.9),
]
FUNCIONARIOS = [
    (1001, CargoFuncionario.ADMINISTRADOR.value, 'Carlos Eduardo Mendes', False),
    (1002, CargoFuncionario.GESTOR.value, 'Fernanda Lima Rocha', False),
    (1003, CargoFuncionario.ANALISTA_TRIAGEM.value, 'Juliana Prado', False),
    (1004, CargoFuncionario.ANALISTA_TRIAGEM.value, 'Thiago Cardoso', False),
    (1005, CargoFuncionario.ANALISTA_TRIAGEM.value, 'Beatriz Almeida', False),
    (1006, CargoFuncionario.ANALISTA_TRIAGEM.value, 'Rodrigo Silveira', False),
    (1007, CargoFuncionario.FUNCIONARIO.value, 'Marina Duarte', False),
    (1008, CargoFuncionario.FUNCIONARIO.value, 'Lucas Pereira', True),
]
ANALISTAS = [1003, 1004, 1005, 1006]
MATRICULA_GESTOR = 1002
MATRICULA_SOLICITANTE_PENDENTE = 1007
MATRICULA_SOLICITANTE_ATENDIDO = 1005

NOTEBOOK, DESKTOP, IMPRESSORA = 'notebook', 'desktop', 'impressora'
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


SERIES_REINCIDENTES = 14
PROBABILIDADE_SEM_PECA = 0.08
PROBABILIDADE_DEFEITO_COM_CAUSA_ESPECIFICA = 0.3
PROBABILIDADE_DIAGNOSTICO_CONFIRMADO = 0.7
PROBABILIDADE_FOTO_NFF = 0.7
PROBABILIDADE_FOTO_DEFEITO = 0.35
DIAS_DA_RAMPA_DE_NFF = 28
TICKET_INICIAL = 481200


def _pn_peca(modelo_pn, tipo, usados):
    compartilhado = TIPOS[tipo].get('compartilhado')
    if compartilhado:
        return compartilhado
    numero = zlib.crc32(f'{modelo_pn}-{tipo}'.encode()) % 90000 + 10000
    part_number = f'L{numero}-001'
    while part_number in usados:
        numero += 1
        part_number = f'L{numero}-001'
    return part_number


def _sn(rng):
    letras, alfanumericos = 'ABCDEFGHJKLMNPQRSTUVWXYZ', 'ABCDEFGHJKLMNPQRSTUVWXYZ0123456789'
    prefixo = rng.randint(1, 9)
    parte_letras = ''.join(rng.choice(letras) for _ in range(2))
    meio = rng.randint(100, 999)
    sufixo = ''.join(rng.choice(alfanumericos) for _ in range(4))
    return f"{prefixo}{parte_letras}{meio}{sufixo}"


def _escolher(rng, itens, pesos):
    return rng.choices(itens, weights=pesos, k=1)[0]


def _sem_acento(parte):
    return parte.lower().replace('á', 'a').replace('í', 'i')


def _email_do_funcionario(nome):
    partes = nome.split()
    return f'{_sem_acento(partes[0])}.{_sem_acento(partes[-1])}@{EMAIL_DOMINIO}'


class GeradorDemo:
    def __init__(self, hoje, total, dias, seed):
        self.hoje = hoje
        self.total = total
        self.dias = dias
        self.rng = random.Random(seed)
        self.modelos = []
        self.empresas = self._montar_empresas()
        self.clientes = self.empresas[len(PRESTADORAS):]
        self.tecnicos = self._montar_tecnicos()
        self.funcionarios = self._montar_funcionarios()
        self.datas, self.pesos_dos_dias = self._montar_calendario()

    @staticmethod
    def _montar_empresas():
        prestadoras = [
            dict(razao_social=nome, cnpj=cnpj_valido(base), tipo=TipoEmpresa.PRESTADORA.value)
            for nome, base, _ in PRESTADORAS
        ]
        clientes = [
            dict(razao_social=nome, cnpj=cnpj_valido(base), tipo=TipoEmpresa.CLIENTE.value)
            for nome, base, _ in CLIENTES
        ]
        return prestadoras + clientes

    def _montar_tecnicos(self):
        return [
            dict(nome=nome, prestadora_cnpj=self.empresas[indice]['cnpj'], p_nff=probabilidade, peso=peso)
            for nome, indice, probabilidade, peso in TECNICOS
        ]

    @staticmethod
    def _montar_funcionarios():
        return [
            dict(
                login=login, cargo=cargo, nome=nome, primeiro_acesso=primeiro_acesso,
                email=_email_do_funcionario(nome),
            )
            for login, cargo, nome, primeiro_acesso in FUNCIONARIOS
        ]

    def _montar_calendario(self):
        inicio = self.hoje - timedelta(days=self.dias)
        datas = [inicio + timedelta(days=i) for i in range(self.dias)]
        pesos = []
        for indice, data in enumerate(datas):
            crescimento = 0.6 + 0.8 * indice / (self.dias - 1)
            fator_fim_de_semana = 0.03 if data.weekday() >= 5 else 1.0
            pesos.append(crescimento * fator_fim_de_semana)
        return datas, pesos

    def _montar_catalogo(self):
        rng = self.rng
        pecas, modelos, usados = {}, [], set()
        for pn, nome, familia, peso, reforco in MODELOS:
            tipos = [tipo for tipo, dados in TIPOS.items() if familia in dados['fam']]
            if familia == NOTEBOOK:
                tipos = [tipo for tipo in tipos if rng.random() < 0.92 or tipo in ('bateria', 'tela', 'placa')]

            ligadas = []
            for tipo in tipos:
                part_number = _pn_peca(pn, tipo, usados)
                if part_number not in pecas:
                    usados.add(part_number)
                    rotulo = TIPOS[tipo]['rotulo']
                    descricao = (
                        f"{rotulo} compatível com vários modelos"
                        if TIPOS[tipo].get('compartilhado')
                        else f"{rotulo} para {nome}"
                    )
                    pecas[part_number] = dict(part_number=part_number, descricao=descricao)
                ligadas.append((tipo, part_number))
            modelos.append(dict(pn=pn, modelo=nome, familia=familia, peso=peso, reforco=reforco, pecas=ligadas))
        self.modelos = modelos
        return list(pecas.values())

    def _sortear_triagem(self, sn=None, modelo=None, data=None):
        rng = self.rng
        tecnico = _escolher(rng, self.tecnicos, [t['peso'] for t in self.tecnicos])
        indice_prestadora = next(i for i, e in enumerate(self.empresas) if e['cnpj'] == tecnico['prestadora_cnpj'])
        uf = rng.choice(PRESTADORAS[indice_prestadora][2])
        cliente = _escolher(rng, self.clientes, [c[2] for c in CLIENTES])
        modelo = modelo or _escolher(rng, self.modelos, [m['peso'] for m in self.modelos])
        tipo, part_number = _escolher(rng, modelo['pecas'], [TIPOS[t]['peso'] for t, _ in modelo['pecas']])
        data = data or _escolher(rng, self.datas, self.pesos_dos_dias)

        dias_atras = (self.hoje - data).days
        rampa = 1.0 + 0.5 * max(0, DIAS_DA_RAMPA_DE_NFF - dias_atras) / DIAS_DA_RAMPA_DE_NFF
        probabilidade_nff = min(0.92, tecnico['p_nff'] * modelo['reforco'] * rampa)
        nff = rng.random() < probabilidade_nff
        return dict(
            tecnico=tecnico, cliente=cliente, uf=uf, m=modelo, tipo=tipo, ppn=part_number,
            data=data, nff=nff, sn=sn or _sn(rng),
        )

    def _sortear_reincidencias(self, sementes):
        rng = self.rng
        ontem = self.hoje - timedelta(days=1)
        extras = []
        for base in rng.sample(sementes, min(SERIES_REINCIDENTES, len(sementes))):
            for _ in range(rng.choice([1, 1, 2])):
                novo_dia = base['data'] + timedelta(days=rng.randint(10, 30))
                if novo_dia <= ontem:
                    extras.append(self._sortear_triagem(sn=base['sn'], modelo=base['m'], data=novo_dia))
        return extras

    def _parecer_da_bancada(self, tipo, diagnostico, nff):
        rng = self.rng
        if nff:
            constatado = rng.choice(tipo['nff'])
            testes = tipo['teste_ok']
            analise = f"Peça retornada submetida a testes de bancada. {testes}. {constatado}."
            conclusao = 'Peça funcional (NFF): a troca em campo não era necessária.'
            return StatusPeca.FUNCIONAL.value, constatado, testes, analise, conclusao

        if rng.random() < PROBABILIDADE_DIAGNOSTICO_CONFIRMADO:
            constatado = (
                diagnostico.lower() if rng.random() < PROBABILIDADE_DEFEITO_COM_CAUSA_ESPECIFICA else diagnostico
            )
            conclusao = 'Defeito confirmado. O diagnóstico do técnico de campo procede.'
        else:
            constatado = rng.choice(tipo['esp'])
            conclusao = 'Defeito confirmado, com causa mais específica que a informada em campo.'
        testes = tipo['teste_falha']
        analise = f"Peça retornada submetida a testes de bancada. {testes}. Defeito confirmado: {constatado}."
        return StatusPeca.NAO_FUNCIONAL.value, constatado, testes, analise, conclusao

    def _sortear_fotos(self, semente, status):
        rng = self.rng
        probabilidade = PROBABILIDADE_FOTO_NFF if status == StatusPeca.FUNCIONAL else PROBABILIDADE_FOTO_DEFEITO
        if rng.random() >= probabilidade:
            return []
        legendas = rng.sample(LEGENDAS, rng.choice([1, 2, 2, 3]))
        return [dict(tipo=semente['tipo'], legenda=legenda) for legenda in legendas]

    def _montar_triagem(self, semente, ticket):
        rng = self.rng
        tipo = TIPOS[semente['tipo']]
        hora = time(rng.randint(8, 17), rng.randint(0, 59))
        ticket += rng.randint(1, 9)
        diagnostico = rng.choice(tipo['diag'])
        status, constatado, testes, analise, conclusao = self._parecer_da_bancada(tipo, diagnostico, semente['nff'])
        sem_peca = rng.random() < PROBABILIDADE_SEM_PECA

        triagem = dict(
            n_ticket=ticket, nf=rng.randint(100000, 999999), cidade=rng.choice(CIDADES[semente['uf']]),
            estado=semente['uf'], tecnico_nome=semente['tecnico']['nome'],
            cliente_cnpj=semente['cliente']['cnpj'], modelo_pn=semente['m']['pn'],
            analista_chamado=rng.choice(ANALISTAS + [MATRICULA_GESTOR]), analista_triagem=rng.choice(ANALISTAS),
            sn=semente['sn'], status=status, data=datetime.combine(semente['data'], hora),
            peca_pn=None if sem_peca else semente['ppn'],
            troca=(
                'Troca do equipamento completo' if sem_peca else
                rng.choice([
                    'Substituição da peça em campo',
                    'Peça trocada conforme diagnóstico do técnico',
                    'Troca realizada durante o chamado',
                ])
            ),
            defeito_usuario=rng.choice(tipo['queixas']), defeito_tecnico=diagnostico,
            defeito_constatado=constatado, testes=testes, analise=analise, conclusao=conclusao,
            tipo_peca=semente['tipo'], fotos=[],
        )
        triagem['fotos'] = self._sortear_fotos(semente, status)
        return triagem, ticket

    def _montar_triagens(self):
        sementes = [self._sortear_triagem() for _ in range(self.total)]
        sementes += self._sortear_reincidencias(sementes)
        sementes.sort(key=lambda semente: semente['data'])

        triagens, ticket = [], TICKET_INICIAL
        for semente in sementes:
            triagem, ticket = self._montar_triagem(semente, ticket)
            triagens.append(triagem)
        return triagens

    @staticmethod
    def _montar_solicitacoes_de_senha():
        return [
            dict(login=MATRICULA_SOLICITANTE_PENDENTE, atendida=False, dias_atras=0),
            dict(login=MATRICULA_SOLICITANTE_ATENDIDO, atendida=True, dias_atras=9),
        ]

    def gerar(self):
        pecas = self._montar_catalogo()
        triagens = self._montar_triagens()
        return dict(
            empresas=self.empresas, tecnicos=self.tecnicos, funcionarios=self.funcionarios, pecas=pecas,
            modelos=self.modelos, triagens=triagens, solicitacoes=self._montar_solicitacoes_de_senha(),
        )


def gerar(hoje, total=420, dias=120, seed=SEED_PADRAO):
    return GeradorDemo(hoje, total, dias, seed).gerar()
