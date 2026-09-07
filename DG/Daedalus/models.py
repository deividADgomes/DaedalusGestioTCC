from django.db import models

class Empresa(models.Model):
    id_empresa = models.AutoField(primary_key=True)
    cnpj = models.CharField(max_length=14, unique=True)
    razao_social = models.CharField(max_length=255)
    tipo = models.IntegerField()

    def __str__(self):
        return self.razao_social

class Equipamento(models.Model):
    id_equipamento = models.AutoField(primary_key=True)
    pn = models.CharField(max_length=100)
    modelo = models.CharField(max_length=150)

    def __str__(self):
        return f"{self.pn} - {self.modelo}"

class Funcionario(models.Model):
    id_funcionario = models.AutoField(primary_key=True)
    cargo = models.CharField(max_length=100)
    nome = models.CharField(max_length=255)
    login = models.IntegerField(unique=True)
    senha = models.CharField(max_length=255)
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
    troca = models.CharField(max_length=255, null=True, blank=True)
    
    # Textos longos
    defeito_usuario = models.TextField(null=True, blank=True)
    defeito_tecnico = models.TextField(null=True, blank=True)
    defeito_constatado = models.TextField(null=True, blank=True)
    testes = models.TextField(null=True, blank=True)
    analise = models.TextField(null=True, blank=True)
    conclusao = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Ticket: {self.n_ticket} - SN: {self.sn}"