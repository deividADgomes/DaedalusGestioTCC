import decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0027_chamadorfb_sem_intervencao_tecnica'),
    ]

    operations = [
        migrations.CreateModel(
            name='EstoquePeca',
            fields=[
                ('id_estoque', models.AutoField(primary_key=True, serialize=False)),
                ('saldo', models.IntegerField(default=0)),
                ('minimo', models.PositiveIntegerField(default=0)),
                ('local', models.CharField(blank=True, default='', max_length=100)),
                ('custo_medio', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.00'), max_digits=12)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('peca', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='estoque', to='Daedalus.peca')),
            ],
        ),
        migrations.CreateModel(
            name='MovimentoEstoque',
            fields=[
                ('id_movimento', models.AutoField(primary_key=True, serialize=False)),
                ('tipo', models.CharField(choices=[('entrada', 'Entrada'), ('saida', 'Saída'), ('contagem', 'Ajuste de contagem')], max_length=20)),
                ('quantidade', models.IntegerField()),
                ('saldo_apos', models.IntegerField()),
                ('custo_unitario', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('motivo', models.CharField(blank=True, default='', max_length=300)),
                ('funcionario_nome', models.CharField(blank=True, default='', max_length=255)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('funcionario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='movimentos_estoque', to='Daedalus.funcionario')),
                ('peca', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='movimentos_estoque', to='Daedalus.peca')),
            ],
            options={
                'ordering': ['-criado_em', '-id_movimento'],
            },
        ),
    ]
