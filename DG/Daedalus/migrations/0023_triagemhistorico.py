import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0022_triagem_peca_trocada'),
    ]

    operations = [
        migrations.CreateModel(
            name='TriagemHistorico',
            fields=[
                ('id_historico', models.AutoField(primary_key=True, serialize=False)),
                ('funcionario_nome', models.CharField(blank=True, default='', max_length=255)),
                ('alteracoes', models.JSONField(default=list)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('funcionario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alteracoes_triagem', to='Daedalus.funcionario')),
                ('triagem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historico', to='Daedalus.triagem')),
            ],
            options={
                'ordering': ['-criado_em', '-id_historico'],
            },
        ),
    ]
