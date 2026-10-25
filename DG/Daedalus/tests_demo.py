import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .models import Empresa, Equipamento, FotoTriagem, Funcionario, SolicitacaoSenha, Tecnico, Triagem
from .services import FuncionarioService


class PopularDemoTests(TestCase):
    """Garante que o banco de demonstração é criado de forma coerente e que o sistema funciona com ele."""

    def rodar(self, *args):
        saida = StringIO()
        call_command('popular_demo', *args, stdout=saida)
        return saida.getvalue()

    def test_cria_dados_coerentes_sem_fotos(self):
        texto = self.rodar('--quantidade', '60', '--dias', '30', '--sem-fotos')
        self.assertIn('criado com sucesso', texto)
        self.assertEqual(Empresa.objects.filter(tipo=1).count(), 4)
        self.assertEqual(Empresa.objects.filter(tipo=2).count(), 10)
        self.assertEqual(Tecnico.objects.count(), 12)
        self.assertEqual(Funcionario.objects.count(), 8)
        self.assertEqual(Equipamento.objects.count(), 12)
        self.assertGreaterEqual(Triagem.objects.count(), 60)
        # a peça trocada sempre pertence ao catálogo do modelo
        for t in Triagem.objects.exclude(peca_trocada=None).select_related('equipamento'):
            self.assertTrue(t.equipamento.pecas.filter(pk=t.peca_trocada_id).exists())

    def test_acessos_de_demonstracao(self):
        self.rodar('--quantidade', '20', '--dias', '15', '--sem-fotos')
        admin = FuncionarioService.autenticar(1001, 'Demo@2026')
        self.assertIsNotNone(admin)
        self.assertFalse(admin.primeiro_acesso)
        novo = FuncionarioService.autenticar(1008, '1008')       # senha provisória = matrícula
        self.assertIsNotNone(novo)
        self.assertTrue(novo.primeiro_acesso)
        self.assertTrue(SolicitacaoSenha.objects.filter(atendida=False).exists())   # pedido pendente para o painel

    def test_recusa_banco_com_dados_e_limpar_recria(self):
        args = ('--quantidade', '20', '--dias', '15', '--sem-fotos')
        self.rodar(*args)
        with self.assertRaises(CommandError):
            self.rodar(*args)
        self.rodar(*args, '--limpar')
        self.assertEqual(Funcionario.objects.count(), 8)

    def test_gera_fotos_no_disco(self):
        with tempfile.TemporaryDirectory() as pasta, override_settings(MEDIA_ROOT=pasta):
            self.rodar('--quantidade', '25', '--dias', '15')
            self.assertGreater(FotoTriagem.objects.count(), 0)
            for foto in FotoTriagem.objects.all()[:5]:
                self.assertTrue(foto.arquivo.storage.exists(foto.arquivo.name))
                self.assertIsNotNone(foto.criado_em)

    def test_dashboard_funciona_com_os_dados_do_demo(self):
        self.rodar('--quantidade', '120', '--dias', '60', '--sem-fotos')
        entrada = self.client.post('/api/login/', {'login': 1001, 'senha': 'Demo@2026'}, content_type='application/json')
        self.assertEqual(entrada.status_code, 200)
        resposta = self.client.get('/api/dashboard/?preset=tudo')
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()['dados']
        self.assertGreater(dados['kpis']['triagens']['valor'], 100)
        self.assertGreater(len(dados['tecnicos']), 5)
