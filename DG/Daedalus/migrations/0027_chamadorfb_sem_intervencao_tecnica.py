from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0026_alertanaoagendado'),
    ]

    operations = [
        migrations.AddField(
            model_name='chamadorfb',
            name='sem_intervencao_tecnica',
            field=models.BooleanField(default=False),
        ),
    ]
