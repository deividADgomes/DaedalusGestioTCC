from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0023_triagemhistorico'),
    ]

    operations = [
        migrations.AddField(
            model_name='orcamento',
            name='motivo_recusa',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
    ]
