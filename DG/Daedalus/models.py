import datetime
from decimal import Decimal

from django.db import models
from django.utils import timezone

class Empresa(models.Model):
    id_empresa = models.AutoField(primary_key=True)
    cnpj = models.CharField(max_length=14, unique=True)
    razao_social = models.CharField(max_length=255)
    tipo = models.IntegerField()

    def __str__(self):
        return self.razao_social

class Peca(models.Model):
    """Peça de reposição (catálogo). Uma mesma peça pode servir a vários equipamentos."""
    id_peca = models.AutoField(primary_key=True)
    part_number = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True, default='')
    # True quando o "item" é a máquina inteira (troca do equipamento completo), e não uma peça.
    equipamento_completo = models.BooleanField(default=False)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.part_number} - {self.descricao[:60]}"

    def cotacao_atual(self):
        """Cotação mais recente (por data; empate desempata pelo lançamento mais novo)."""
        return self.cotacoes.select_related('fornecedor').order_by('-data_cotacao', '-id_cotacao').first()


class CotacaoPeca(models.Model):
    """Cotação lançada manualmente para uma peça: fornecedor, valor e data."""
    id_cotacao = models.AutoField(primary_key=True)
    peca = models.ForeignKey(Peca, on_delete=models.CASCADE, related_name='cotacoes')
    fornecedor = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='cotacoes_fornecidas')
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    data_cotacao = models.DateField()
    observacao = models.CharField(max_length=255, blank=True, default='')
    criado_por = models.ForeignKey('Funcionario', on_delete=models.SET_NULL, null=True, blank=True, related_name='cotacoes_lancadas')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_cotacao', '-id_cotacao']

    def __str__(self):
        return f"{self.peca.part_number} - {self.fornecedor.razao_social} - R$ {self.valor}"

class Equipamento(models.Model):
    id_equipamento = models.AutoField(primary_key=True)
    pn = models.CharField(max_length=100, unique=True)
    modelo = models.CharField(max_length=150)
    tipo = models.CharField(max_length=100, blank=True, default='')
    marca = models.CharField(max_length=100, blank=True, default='')
    # Aparece nas listas do RFB (novo chamado). Desmarcar só esconde o modelo; nada é apagado.
    rfb = models.BooleanField(default=False)
    pecas = models.ManyToManyField(Peca, related_name='equipamentos', blank=True)
    pecas_sincronizadas_em = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.pn} - {self.modelo}"

class Funcionario(models.Model):
    id_funcionario = models.AutoField(primary_key=True)
    cargo = models.CharField(max_length=100)
    nome = models.CharField(max_length=255)
    login = models.IntegerField(unique=True)
    senha = models.CharField(max_length=255)
    primeiro_acesso = models.BooleanField(default=True)
    # E-mail do usuário: sai no laudo como e-mail do analista e receberá os avisos de SLA do RFB.
    email = models.EmailField(max_length=254, blank=True, default='')

    def __str__(self):
        return self.nome

class SolicitacaoSenha(models.Model):
    """Pedido de redefinição de senha feito na tela de login e atendido por um Administrador/Gestor."""
    id_solicitacao = models.AutoField(primary_key=True)
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='solicitacoes_senha')
    data_solicitacao = models.DateTimeField(default=timezone.now)
    atendida = models.BooleanField(default=False)

    def __str__(self):
        return f"Pedido de {self.funcionario.nome} em {self.data_solicitacao:%d/%m/%Y %H:%M}"

class Tecnico(models.Model):
    id_tecnico = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='IDEmpresa')
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome

class Triagem(models.Model):
    id_triagem = models.AutoField(primary_key=True)
    n_ticket = models.IntegerField()
    nf = models.IntegerField()
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    
    tecnico = models.ForeignKey(Tecnico, on_delete=models.PROTECT, db_column='IDTecnico')
    cliente = models.ForeignKey(Empresa, on_delete=models.PROTECT, db_column='IDCliente', related_name='triagens_cliente')
    equipamento = models.ForeignKey(Equipamento, on_delete=models.PROTECT, db_column='IDEquipamento')
    
    analista_chamado = models.ForeignKey(Funcionario, on_delete=models.PROTECT, related_name='chamados_atribuidos')
    analista_triagem = models.ForeignKey(Funcionario, on_delete=models.PROTECT, related_name='triagens_efetuadas')
    
    sn = models.CharField(max_length=100)
    status = models.IntegerField()
    troca = models.CharField(max_length=255, null=True, blank=True)
    # Peça escolhida entre as do modelo (melhora o ranking de peças do BI). Quando preenchida, `troca` guarda o
    # texto "PN - descrição" dela; sem peça cadastrada, `troca` continua sendo texto livre.
    peca_trocada = models.ForeignKey(Peca, on_delete=models.SET_NULL, null=True, blank=True, related_name='triagens_trocadas')
    # A troca da peça foi indevida? Vazio = não informado (triagens anteriores a este campo).
    troca_indevida = models.BooleanField(null=True, blank=True)
    # CT: o PN terminado em -601, exigido quando a peça trocada é um "System".
    ct = models.CharField(max_length=60, blank=True, default='')
    
    defeito_usuario = models.TextField(null=True, blank=True)
    defeito_tecnico = models.TextField(null=True, blank=True)
    defeito_constatado = models.TextField(null=True, blank=True)
    testes = models.TextField(null=True, blank=True)
    analise = models.TextField(null=True, blank=True)
    conclusao = models.TextField(null=True, blank=True)

    # Datas para o BI. Triagens antigas ficam sem data (NULL) e são tratadas como "histórico".
    criado_em = models.DateTimeField(null=True, blank=True, editable=False)
    atualizado_em = models.DateTimeField(null=True, blank=True, editable=False)

    def __str__(self):
        return f"Ticket: {self.n_ticket} - SN: {self.sn}"


class TriagemHistorico(models.Model):
    """Cada correção feita numa triagem já salva: quem alterou, quando e o que mudou."""
    id_historico = models.AutoField(primary_key=True)
    triagem = models.ForeignKey(Triagem, on_delete=models.CASCADE, related_name='historico')
    funcionario = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, blank=True, related_name='alteracoes_triagem')
    funcionario_nome = models.CharField(max_length=255, blank=True, default='')   # cópia do nome no momento
    alteracoes = models.JSONField(default=list)   # [{"campo": "...", "de": "...", "para": "..."}]
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id_historico']

    def __str__(self):
        return f"Triagem {self.triagem_id} alterada por {self.funcionario_nome or '—'}"

class ChamadoRFB(models.Model):
    STATUS_CHOICES = [
        ('aberto', 'Aberto'),
        ('andamento', 'Em Andamento'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado'),
    ]

    id_chamado = models.AutoField(primary_key=True)
    ticket = models.CharField(max_length=50, unique=True, verbose_name="Ticket")
    data_abertura = models.DateTimeField(verbose_name="Data de Abertura")
    estado = models.CharField(max_length=2, verbose_name="Estado (UF)")
    cidade = models.CharField(max_length=150, verbose_name="Cidade")
    is_metropolitana = models.BooleanField(default=False, blank=True)
    descricao_defeito = models.TextField(verbose_name="Breve Descrição do Defeito")
    horas_consumidas = models.FloatField(default=0.0)
    modelo_equipamento = models.CharField(max_length=150, verbose_name="Modelo do Equipamento")
    tipo_chamado = models.CharField(max_length=50, default='Não informado', verbose_name="Tipo de Chamado")
    sn = models.CharField(max_length=100, verbose_name="SN")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberto')
    alerta_60h_enviado = models.BooleanField(default=False)
    observacao = models.CharField(max_length=255, blank=True, null=True, verbose_name="Observação")
    analista_responsavel = models.ForeignKey(Funcionario, related_name='chamados_rfb_analista', on_delete=models.SET_NULL, null=True, blank=True)
    tecnico_atendimento = models.ForeignKey(Funcionario, related_name='chamados_rfb_tecnico', on_delete=models.SET_NULL, null=True, blank=True)
    resolucao_caso = models.TextField(blank=True, null=True, verbose_name="Resolução do Caso")
    peca_utilizada = models.CharField(max_length=500, blank=True, null=True, verbose_name="Peça Utilizada")
    # Modelo cadastrado em "Modelos e peças" e peças padronizadas usadas no encerramento.
    equipamento = models.ForeignKey(Equipamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='chamados_rfb')
    pecas_utilizadas = models.ManyToManyField(Peca, blank=True, related_name='chamados_rfb')
    data_conclusao = models.DateTimeField(blank=True, null=True, verbose_name="Data Real de Conclusão")
    # Chamado resolvido sem ir a campo (orientação remota, cliente resolveu...): sem técnico e sem peças.
    sem_intervencao_tecnica = models.BooleanField(default=False)

    def __str__(self):
        return f"RFB Ticket: {self.ticket} - {self.cidade}/{self.estado}"

class AgendamentoChamado(models.Model):
    STATUS_AGENDAMENTO = [
        ('pendente', 'Pendente'),
        ('realizado', 'Realizado'),
        ('frustrado', 'Frustrado'),
    ]

    id_agendamento = models.AutoField(primary_key=True)
    chamado = models.ForeignKey(ChamadoRFB, on_delete=models.CASCADE, related_name='agendamentos')
    
    data_registro_pausa = models.DateTimeField(null=True, blank=True, verbose_name="Data de Registro")
    data_agendamento = models.DateTimeField(null=True, blank=True, verbose_name="Data do Agendamento")
    data_inicio_tentativas = models.DateTimeField(null=True, blank=True, verbose_name="Início das Tentativas")
    data_resposta_cliente = models.DateTimeField(null=True, blank=True, verbose_name="Resposta do Cliente")
    
    tipo_pausa = models.CharField(max_length=30, default='agendamento') # 'agendamento' ou 'sem_resposta'
    
    status = models.CharField(max_length=20, choices=STATUS_AGENDAMENTO, default='pendente')

    def __str__(self):
        return f"Logística {self.chamado.ticket} - Status: {self.get_status_display()}"


class Orcamento(models.Model):
    """Laudo + orçamento de assistência técnica (documento emitido ao cliente)."""
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('emitido', 'Emitido'),
        ('aprovado', 'Aprovado'),
        ('recusado', 'Recusado'),
        ('cancelado', 'Cancelado'),
    ]
    DISPONIBILIDADE_CHOICES = [
        ('', 'Não informado'),
        ('disponivel', 'Disponível'),
        ('indisponivel', 'Indisponível'),
    ]

    id_orcamento = models.AutoField(primary_key=True)
    numero = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='rascunho')
    triagem = models.ForeignKey(Triagem, on_delete=models.SET_NULL, null=True, blank=True, related_name='orcamentos')
    ticket = models.CharField(max_length=50, blank=True, default='')

    # Dados do cliente (cópia no momento da emissão: o documento não muda se o cadastro mudar)
    cliente_nome = models.CharField(max_length=255)
    cliente_responsavel = models.CharField(max_length=255, blank=True, default='')
    cliente_email = models.CharField(max_length=255, blank=True, default='')
    cliente_telefone = models.CharField(max_length=30, blank=True, default='')
    cliente_cidade = models.CharField(max_length=100, blank=True, default='')
    cliente_uf = models.CharField(max_length=2, blank=True, default='')
    cliente_endereco = models.CharField(max_length=255, blank=True, default='')
    cliente_cep = models.CharField(max_length=10, blank=True, default='')
    cliente_complemento = models.CharField(max_length=255, blank=True, default='')

    # Equipamento
    equipamento = models.ForeignKey(Equipamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='orcamentos')
    equip_tipo = models.CharField(max_length=100, blank=True, default='')
    equip_marca = models.CharField(max_length=100, blank=True, default='')
    equip_modelo = models.CharField(max_length=150, blank=True, default='')
    equip_sn = models.CharField(max_length=100, blank=True, default='')
    motivo_problema = models.TextField(blank=True, default='')
    motivo_recusa = models.CharField(max_length=300, blank=True, default='')   # preenchido quando o cliente não aprova
    analise = models.TextField(blank=True, default='')

    disponibilidade = models.CharField(max_length=15, choices=DISPONIBILIDADE_CHOICES, blank=True, default='')
    # True: preço = valor da peça x margem (+ adicionais na 1ª peça). False: o valor digitado é o valor cheio.
    aplicar_regra = models.BooleanField(default=True)
    prazo_estimado = models.CharField(max_length=100, blank=True, default='')
    tecnico_responsavel = models.CharField(max_length=255, blank=True, default='')

    analista = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, blank=True, related_name='orcamentos_emitidos')
    analista_nome = models.CharField(max_length=255, blank=True, default='')
    analista_email = models.CharField(max_length=255, blank=True, default='')

    data_emissao = models.DateField()
    validade_ate = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_emissao', '-id_orcamento']

    def __str__(self):
        return f"{self.numero} - {self.cliente_nome}"

    @property
    def valor_total(self):
        from decimal import Decimal
        return sum((i.subtotal for i in self.itens.all()), Decimal('0.00'))


class ItemOrcamento(models.Model):
    id_item = models.AutoField(primary_key=True)
    orcamento = models.ForeignKey(Orcamento, on_delete=models.CASCADE, related_name='itens')
    peca = models.ForeignKey(Peca, on_delete=models.SET_NULL, null=True, blank=True, related_name='itens_orcamento')
    cotacao = models.ForeignKey(CotacaoPeca, on_delete=models.SET_NULL, null=True, blank=True, related_name='itens_orcamento')
    nome = models.CharField(max_length=150, blank=True, default='')
    descricao = models.CharField(max_length=255, blank=True, default='')
    part_number = models.CharField(max_length=100, blank=True, default='')
    quantidade = models.PositiveIntegerField(default=1)
    # Valor da peça (cotação) no momento do orçamento: não muda se a cotação for atualizada depois.
    valor_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Valor cobrado por unidade = valor_base x margem (ver settings.ORCAMENTO_PRECIFICACAO).
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    # Valor fixo somado uma única vez: só a primeira peça do orçamento o recebe.
    adicional = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ['id_item']

    @property
    def subtotal(self):
        return self.valor_unitario * self.quantidade + self.adicional


class OrcamentoHistorico(models.Model):
    """Registro de cada alteração feita em um laudo depois de emitido (quem, quando, por quê e o que mudou)."""
    id_historico = models.AutoField(primary_key=True)
    orcamento = models.ForeignKey(Orcamento, on_delete=models.CASCADE, related_name='historico')
    funcionario = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, blank=True, related_name='alteracoes_orcamento')
    funcionario_nome = models.CharField(max_length=255, blank=True, default='')   # cópia do nome no momento
    motivo = models.CharField(max_length=500)
    alteracoes = models.JSONField(default=list)   # [{"campo": "...", "de": "...", "para": "..."}]
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id_historico']

    def __str__(self):
        return f"{self.orcamento.numero} - {self.motivo[:40]}"


class SnapshotSLA(models.Model):
    """Retrato diário do backlog do RFB (o passado não pode ser reconstruído depois)."""
    id_snapshot = models.AutoField(primary_key=True)
    data = models.DateField(unique=True)
    ativos = models.PositiveIntegerField(default=0)
    ate_60 = models.PositiveIntegerField(default=0)
    faixa_60_80 = models.PositiveIntegerField(default=0)
    faixa_80_100 = models.PositiveIntegerField(default=0)
    acima_100 = models.PositiveIntegerField(default=0)
    abertos_dia = models.PositiveIntegerField(default=0)
    concluidos_dia = models.PositiveIntegerField(default=0)
    por_uf = models.JSONField(default=dict)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data']

    def __str__(self):
        return f"SLA {self.data}: {self.ativos} ativos"


class Insight(models.Model):
    """Aviso gerado automaticamente pelo BI (SLA, laudos a vencer, picos, reincidência...)."""
    SEVERIDADES = [('info', 'Informativo'), ('atencao', 'Atenção'), ('critico', 'Crítico')]
    id_insight = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=40)
    severidade = models.CharField(max_length=10, choices=SEVERIDADES, default='info')
    titulo = models.CharField(max_length=200)
    texto = models.CharField(max_length=500, blank=True, default='')
    link = models.CharField(max_length=200, blank=True, default='')
    chave = models.CharField(max_length=120, unique=True)   # evita repetir o mesmo aviso no mesmo dia
    lido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id_insight']

    def __str__(self):
        return f"[{self.severidade}] {self.titulo}"


class AlertaSLAEnviado(models.Model):
    """Controle dos e-mails de SLA já enviados, para não repetir o mesmo aviso."""
    id_alerta = models.AutoField(primary_key=True)
    chamado = models.ForeignKey(ChamadoRFB, on_delete=models.CASCADE, related_name='alertas_sla')
    faixa = models.PositiveSmallIntegerField()   # 60, 80 ou 100
    destinatario = models.CharField(max_length=254)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('chamado', 'faixa')]


class AlertaNaoAgendado(models.Model):
    """Chamado RFB sem agendamento que já consumiu o limite de SLA configurado: o aviso é enviado uma única vez."""
    id_alerta_nao_agendado = models.AutoField(primary_key=True)
    chamado = models.OneToOneField(ChamadoRFB, on_delete=models.CASCADE, related_name='alerta_nao_agendado')
    destinatario = models.CharField(max_length=500)
    enviado_em = models.DateTimeField(auto_now_add=True)


class AuditoriaLog(models.Model):
    """Registro de quem gravou ou excluiu cadastros (funcionários, empresas, técnicos, modelos, peças e cotações)."""
    id_log = models.AutoField(primary_key=True)
    funcionario = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, blank=True, related_name='auditoria')
    funcionario_nome = models.CharField(max_length=255, blank=True, default='')   # cópia do nome no momento
    acao = models.CharField(max_length=30)
    entidade = models.CharField(max_length=60)
    entidade_id = models.IntegerField(null=True, blank=True)
    descricao = models.CharField(max_length=300, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id_log']

    def __str__(self):
        return f"{self.funcionario_nome} {self.acao} {self.entidade}"


class EstoquePeca(models.Model):
    """Controle de estoque de uma peça do catálogo: saldo, mínimo desejado, local e custo médio."""
    id_estoque = models.AutoField(primary_key=True)
    peca = models.OneToOneField(Peca, on_delete=models.CASCADE, related_name='estoque')
    saldo = models.IntegerField(default=0)
    minimo = models.PositiveIntegerField(default=0)        # 0 = sem alerta de estoque mínimo
    local = models.CharField(max_length=100, blank=True, default='')
    custo_medio = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.peca.part_number}: {self.saldo}"


class MovimentoEstoque(models.Model):
    """Cada entrada, saída ou ajuste de contagem. O saldo é sempre explicável somando estes registros."""
    TIPOS = [('entrada', 'Entrada'), ('saida', 'Saída'), ('contagem', 'Ajuste de contagem')]

    id_movimento = models.AutoField(primary_key=True)
    peca = models.ForeignKey(Peca, on_delete=models.PROTECT, related_name='movimentos_estoque')
    tipo = models.CharField(max_length=20, choices=TIPOS)
    quantidade = models.IntegerField()                     # com sinal: positivo entra, negativo sai
    saldo_apos = models.IntegerField()
    custo_unitario = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)   # só nas entradas
    motivo = models.CharField(max_length=300, blank=True, default='')
    referencia = models.CharField(max_length=30, blank=True, default='')       # ex.: número da saída de peças que originou o movimento
    funcionario = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimentos_estoque')
    funcionario_nome = models.CharField(max_length=255, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id_movimento']

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.quantidade} em {self.peca.part_number}"


class SaidaPecas(models.Model):
    """
    Lista de saída de peças, sem passar por orçamento, enviada ao setor fiscal para emitir as notas.
    Cada linha (ItemSaida) é uma peça com o seu ticket e o seu destinatário. Os itens que saem do nosso estoque
    dão baixa quando a lista é enviada ao fiscal; NF e rastreio são preenchidos depois, linha a linha.
    """
    STATUS = [('rascunho', 'Rascunho'), ('enviada', 'Enviada ao fiscal'), ('nota_emitida', 'Nota emitida'), ('cancelada', 'Cancelada')]

    id_saida = models.AutoField(primary_key=True)
    numero = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=STATUS, default='rascunho')
    observacao = models.TextField(blank=True, default='')                   # observação geral para o fiscal
    criado_por = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, blank=True, related_name='saidas_criadas')
    criado_por_nome = models.CharField(max_length=255, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    enviado_por_nome = models.CharField(max_length=255, blank=True, default='')
    emails_fiscal = models.CharField(max_length=500, blank=True, default='')
    cancelado_em = models.DateTimeField(null=True, blank=True)
    motivo_cancelamento = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        ordering = ['-criado_em', '-id_saida']

    def __str__(self):
        return f"{self.numero} ({self.get_status_display()})"


class ItemSaida(models.Model):
    """Uma linha da lista: as colunas são as da planilha (Ticket, Cliente, Equip., Peça, QTDE, PN, Dest., Número, Cidade, Estado, Dia Solic., NF, RASTREIO, Observação)."""
    ORIGENS = [('estoque', 'Sai do nosso estoque'), ('externa', 'Não sai do nosso estoque')]

    id_item = models.AutoField(primary_key=True)
    saida = models.ForeignKey(SaidaPecas, on_delete=models.CASCADE, related_name='itens')
    ticket = models.CharField(max_length=30, blank=True, default='')
    cliente = models.CharField(max_length=255, blank=True, default='')
    equipamento = models.CharField(max_length=255, blank=True, default='')
    peca = models.ForeignKey(Peca, on_delete=models.SET_NULL, null=True, blank=True, related_name='itens_saida')   # vazio se o PN não está no catálogo
    descricao = models.CharField(max_length=500, blank=True, default='')       # coluna "Peça"
    quantidade = models.PositiveIntegerField()
    part_number = models.CharField(max_length=100)
    origem = models.CharField(max_length=10, choices=ORIGENS, default='estoque')
    destinatario = models.CharField(max_length=255, blank=True, default='')
    telefone = models.CharField(max_length=30, blank=True, default='')        # coluna "Número"
    cidade = models.CharField(max_length=100, blank=True, default='')
    estado = models.CharField(max_length=2, blank=True, default='')
    data_solicitacao = models.DateField(default=datetime.date.today)
    numero_nf = models.CharField(max_length=30, blank=True, default='')
    rastreio = models.CharField(max_length=100, blank=True, default='')
    observacao = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        ordering = ['id_item']

    def __str__(self):
        return f"{self.quantidade}x {self.part_number}"
