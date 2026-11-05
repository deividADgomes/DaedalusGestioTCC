import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0024_orcamento_motivo_recusa'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditoriaLog',
            fields=[
                ('id_log', models.AutoField(primary_key=True, serialize=False)),
                ('funcionario_nome', models.CharField(blank=True, default='', max_length=255)),
                ('acao', models.CharField(max_length=30)),
                ('entidade', models.CharField(max_length=60)),
                ('entidade_id', models.IntegerField(blank=True, null=True)),
                ('descricao', models.CharField(blank=True, default='', max_length=300)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('funcionario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='auditoria', to='Daedalus.funcionario')),
            ],
            options={
                'ordering': ['-criado_em', '-id_log'],
            },
        ),
    ]
