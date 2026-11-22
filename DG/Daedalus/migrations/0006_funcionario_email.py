from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0005_solicitacaosenha'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
    ]
