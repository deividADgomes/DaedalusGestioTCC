from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0030_saida_no_formato_da_planilha'),
    ]

    operations = [
        migrations.AddField(
            model_name='triagem',
            name='troca_indevida',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
