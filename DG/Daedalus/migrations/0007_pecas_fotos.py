import Daedalus.models
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0006_funcionario_email'),
    ]

    operations = [
        migrations.CreateModel(
            name='Peca',
            fields=[
                ('id_peca', models.AutoField(primary_key=True, serialize=False)),
                ('part_number', models.CharField(max_length=100, unique=True)),
                ('descricao', models.CharField(blank=True, default='', max_length=255)),
            ],
            options={'ordering': ['part_number']},
        ),
        migrations.AddField(
            model_name='equipamento',
            name='pecas',
            field=models.ManyToManyField(blank=True, related_name='equipamentos', to='Daedalus.peca'),
        ),
        migrations.AddField(
            model_name='triagem',
            name='peca_trocada',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='triagens', to='Daedalus.peca'),
        ),
        migrations.CreateModel(
            name='FotoTriagem',
            fields=[
                ('id_foto', models.AutoField(primary_key=True, serialize=False)),
                ('arquivo', models.FileField(upload_to=Daedalus.models._caminho_foto)),
                ('legenda', models.CharField(blank=True, default='', max_length=150)),
                ('criado_em', models.DateTimeField(default=django.utils.timezone.now)),
                ('triagem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='fotos', to='Daedalus.triagem')),
            ],
            options={'ordering': ['criado_em', 'id_foto']},
        ),
    ]
