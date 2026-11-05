import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0025_auditorialog'),
    ]

    operations = [
        migrations.CreateModel(
            name='AlertaNaoAgendado',
            fields=[
                ('id_alerta_nao_agendado', models.AutoField(primary_key=True, serialize=False)),
                ('destinatario', models.CharField(max_length=500)),
                ('enviado_em', models.DateTimeField(auto_now_add=True)),
                ('chamado', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='alerta_nao_agendado', to='Daedalus.chamadorfb')),
            ],
        ),
    ]
