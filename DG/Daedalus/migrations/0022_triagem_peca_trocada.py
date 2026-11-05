import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0021_solicitacaosenha'),
    ]

    operations = [
        migrations.AddField(
            model_name='triagem',
            name='peca_trocada',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='triagens_trocadas', to='Daedalus.peca'),
        ),
    ]
