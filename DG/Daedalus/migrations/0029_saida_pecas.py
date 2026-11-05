import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0028_estoque'),
    ]

    operations = [
        migrations.AddField(
            model_name='movimentoestoque',
            name='referencia',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
        migrations.CreateModel(
            name='SaidaPecas',
            fields=[
                ('id_saida', models.AutoField(primary_key=True, serialize=False)),
                ('numero', models.CharField(max_length=20, unique=True)),
                ('status', models.CharField(choices=[('rascunho', 'Rascunho'), ('enviada', 'Enviada ao fiscal'), ('nota_emitida', 'Nota emitida'), ('cancelada', 'Cancelada')], default='rascunho', max_length=20)),
                ('destinatario', models.CharField(max_length=255)),
                ('finalidade', models.CharField(max_length=60)),
                ('referencia', models.CharField(blank=True, default='', max_length=100)),
                ('observacao', models.TextField(blank=True, default='')),
                ('criado_por_nome', models.CharField(blank=True, default='', max_length=255)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('enviado_em', models.DateTimeField(blank=True, null=True)),
                ('enviado_por_nome', models.CharField(blank=True, default='', max_length=255)),
                ('emails_fiscal', models.CharField(blank=True, default='', max_length=500)),
                ('numero_nf', models.CharField(blank=True, default='', max_length=30)),
                ('data_nf', models.DateField(blank=True, null=True)),
                ('cancelado_em', models.DateTimeField(blank=True, null=True)),
                ('motivo_cancelamento', models.CharField(blank=True, default='', max_length=300)),
                ('criado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='saidas_criadas', to='Daedalus.funcionario')),
            ],
            options={
                'ordering': ['-criado_em', '-id_saida'],
            },
        ),
        migrations.CreateModel(
            name='ItemSaida',
            fields=[
                ('id_item', models.AutoField(primary_key=True, serialize=False)),
                ('part_number', models.CharField(max_length=100)),
                ('descricao', models.CharField(blank=True, default='', max_length=500)),
                ('quantidade', models.PositiveIntegerField()),
                ('origem', models.CharField(choices=[('estoque', 'Sai do nosso estoque'), ('externa', 'Não sai do nosso estoque')], default='estoque', max_length=10)),
                ('valor_unitario', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('peca', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='itens_saida', to='Daedalus.peca')),
                ('saida', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='Daedalus.saidapecas')),
            ],
            options={
                'ordering': ['id_item'],
            },
        ),
    ]
