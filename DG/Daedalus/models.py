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
    """Peça de reposição (catálogo). Uma peça pode ser usada por vários modelos de equipamento."""
    id_peca = models.AutoField(primary_key=True)
    part_number = models.CharField(max_length=100, unique=True)
    descricao = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['part_number']

    def __str__(self):
        return f"{self.part_number} - {self.descricao}" if self.descricao else self.part_number


class Equipamento(models.Model):
    id_equipamento = models.AutoField(primary_key=True)
    pn = models.CharField(max_length=100)
    modelo = models.CharField(max_length=150)
    pecas = models.ManyToManyField(Peca, related_name='equipamentos', blank=True)

    def __str__(self):
        return f"{self.pn} - {self.modelo}"

class Funcionario(models.Model):
    id_funcionario = models.AutoField(primary_key=True)
    cargo = models.CharField(max_length=100)
    nome = models.CharField(max_length=255)
    login = models.IntegerField(unique=True)
    senha = models.CharField(max_length=255)
    email = models.EmailField(max_length=254, blank=True, default='')
    primeiro_acesso = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

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
    
    # Chaves Estrangeiras (Relacionamentos)
    tecnico = models.ForeignKey(Tecnico, on_delete=models.PROTECT, db_column='IDTecnico')
    cliente = models.ForeignKey(Empresa, on_delete=models.PROTECT, db_column='IDCliente', related_name='triagens_cliente')
    equipamento = models.ForeignKey(Equipamento, on_delete=models.PROTECT, db_column='IDEquipamento')
    
    # --- AQUI ESTÃO OS ANALISTAS SEPARADOS ---
    analista_chamado = models.ForeignKey(Funcionario, on_delete=models.PROTECT, related_name='chamados_atribuidos')
    analista_triagem = models.ForeignKey(Funcionario, on_delete=models.PROTECT, related_name='triagens_efetuadas')
    
    sn = models.CharField(max_length=100)
    status = models.IntegerField()
    data_triagem = models.DateTimeField(default=timezone.now)
    troca = models.CharField(max_length=255, null=True, blank=True)
    # Peça do catálogo do modelo que foi trocada em campo (alimenta o dashboard); `troca` segue como texto livre
    peca_trocada = models.ForeignKey(Peca, on_delete=models.SET_NULL, null=True, blank=True, related_name='triagens')

    # Textos longos
    defeito_usuario = models.TextField(null=True, blank=True)
    defeito_tecnico = models.TextField(null=True, blank=True)
    defeito_constatado = models.TextField(null=True, blank=True)
    testes = models.TextField(null=True, blank=True)
    analise = models.TextField(null=True, blank=True)
    conclusao = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Ticket: {self.n_ticket} - SN: {self.sn}"


class SolicitacaoSenha(models.Model):
    """UC09: pedido de redefinição de senha feito na tela de login e atendido pelo administrador."""
    id_solicitacao = models.AutoField(primary_key=True)
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='solicitacoes_senha')
    data_solicitacao = models.DateTimeField(default=timezone.now)
    atendida = models.BooleanField(default=False)


def _caminho_foto(instance, filename):
    return f"triagens/{instance.triagem_id}/{filename}"


class FotoTriagem(models.Model):
    """Foto anexada a uma triagem (registro fotográfico do laudo)."""
    id_foto = models.AutoField(primary_key=True)
    triagem = models.ForeignKey(Triagem, on_delete=models.CASCADE, related_name='fotos')
    arquivo = models.FileField(upload_to=_caminho_foto)
    legenda = models.CharField(max_length=150, blank=True, default='')
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['criado_em', 'id_foto']
