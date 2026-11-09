from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0032_triagem_ct'),
    ]

    operations = [
        migrations.AddField(
            model_name='triagem',
            name='motivo_troca_indevida',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
        migrations.AddField(
            model_name='triagem',
            name='justificativa_troca_indevida',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
    ]
