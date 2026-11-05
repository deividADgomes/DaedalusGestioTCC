import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0020_peca_equipamento_completo'),
    ]

    operations = [
        migrations.CreateModel(
            name='SolicitacaoSenha',
            fields=[
                ('id_solicitacao', models.AutoField(primary_key=True, serialize=False)),
                ('data_solicitacao', models.DateTimeField(default=django.utils.timezone.now)),
                ('atendida', models.BooleanField(default=False)),
                ('funcionario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='solicitacoes_senha', to='Daedalus.funcionario')),
            ],
        ),
    ]
