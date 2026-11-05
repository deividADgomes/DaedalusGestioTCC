from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0031_triagem_troca_indevida'),
    ]

    operations = [
        migrations.AddField(
            model_name='triagem',
            name='ct',
            field=models.CharField(blank=True, default='', max_length=60),
        ),
    ]
