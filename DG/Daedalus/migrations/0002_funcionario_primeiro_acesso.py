from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='primeiro_acesso',
            field=models.BooleanField(default=True),
        ),
    ]
