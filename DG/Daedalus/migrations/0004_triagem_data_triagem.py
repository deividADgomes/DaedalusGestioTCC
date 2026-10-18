import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0003_remove_triagem_analista_triagem_analista_chamado_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='triagem',
            name='data_triagem',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
