import datetime

from django.db import migrations, models


def copiar_do_cabecalho(apps, schema_editor):
    """Se já existirem saídas criadas no formato antigo, leva destinatário, NF e data do cabeçalho para cada linha."""
    ItemSaida = apps.get_model('Daedalus', 'ItemSaida')
    for item in ItemSaida.objects.select_related('saida'):
        item.destinatario = (item.saida.destinatario or '')[:255]
        item.ticket = (item.saida.referencia or '')[:30]
        item.numero_nf = (item.saida.numero_nf or '')[:30]
        item.data_solicitacao = item.saida.criado_em.date()
        item.save(update_fields=['destinatario', 'ticket', 'numero_nf', 'data_solicitacao'])


class Migration(migrations.Migration):

    dependencies = [
        ('Daedalus', '0029_saida_pecas'),
    ]

    operations = [
        migrations.AddField(model_name='itemsaida', name='ticket', field=models.CharField(blank=True, default='', max_length=30)),
        migrations.AddField(model_name='itemsaida', name='cliente', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='itemsaida', name='equipamento', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='itemsaida', name='destinatario', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='itemsaida', name='telefone', field=models.CharField(blank=True, default='', max_length=30)),
        migrations.AddField(model_name='itemsaida', name='cidade', field=models.CharField(blank=True, default='', max_length=100)),
        migrations.AddField(model_name='itemsaida', name='estado', field=models.CharField(blank=True, default='', max_length=2)),
        migrations.AddField(model_name='itemsaida', name='data_solicitacao', field=models.DateField(default=datetime.date.today)),
        migrations.AddField(model_name='itemsaida', name='numero_nf', field=models.CharField(blank=True, default='', max_length=30)),
        migrations.AddField(model_name='itemsaida', name='rastreio', field=models.CharField(blank=True, default='', max_length=100)),
        migrations.AddField(model_name='itemsaida', name='observacao', field=models.CharField(blank=True, default='', max_length=500)),
        migrations.RunPython(copiar_do_cabecalho, migrations.RunPython.noop),
        migrations.RemoveField(model_name='itemsaida', name='valor_unitario'),
        migrations.RemoveField(model_name='saidapecas', name='destinatario'),
        migrations.RemoveField(model_name='saidapecas', name='finalidade'),
        migrations.RemoveField(model_name='saidapecas', name='referencia'),
        migrations.RemoveField(model_name='saidapecas', name='numero_nf'),
        migrations.RemoveField(model_name='saidapecas', name='data_nf'),
    ]
