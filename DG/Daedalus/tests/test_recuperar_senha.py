from django.core import mail

from ..models import Funcionario, SolicitacaoSenha
from .base import BaseTestCase


class RecuperarSenhaTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.criar_funcionario(cargo='Administrador', login=1, nome='Admin', email='admin@exemplo.com')
        self.usuario = self.criar_funcionario(cargo='Funcionário', login=2, nome='Maria', email='maria@exemplo.com')

    def pedir(self, login=2, email='maria@exemplo.com'):
        # Rota pública: funciona sem login.
        return self.post_json('/api/recuperar-senha/', {'login': login, 'email': email})

    def test_pedido_valido_registra_e_avisa_o_administrador(self):
        r = self.pedir()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SolicitacaoSenha.objects.filter(funcionario=self.usuario, atendida=False).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin@exemplo.com'])
        self.assertEqual(mail.outbox[0].reply_to, ['maria@exemplo.com'])

    def test_email_diferente_do_cadastro_nao_registra_mas_responde_igual(self):
        valido = self.pedir().json()['mensagem']
        SolicitacaoSenha.objects.all().delete()
        r = self.pedir(email='outro@exemplo.com')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['mensagem'], valido)       # não revela se a matrícula/e-mail existem
        self.assertEqual(SolicitacaoSenha.objects.count(), 0)

    def test_matricula_inexistente_responde_igual_e_nao_registra(self):
        r = self.pedir(login=999)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SolicitacaoSenha.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_e_comparado_sem_diferenciar_maiusculas(self):
        self.pedir(email='MARIA@Exemplo.com')
        self.assertEqual(SolicitacaoSenha.objects.count(), 1)

    def test_pedido_repetido_nao_duplica(self):
        self.pedir()
        self.pedir()
        self.assertEqual(SolicitacaoSenha.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_limite_de_pedidos_por_ip(self):
        for _ in range(5):
            self.assertEqual(self.pedir(login=999).status_code, 200)
        self.assertEqual(self.pedir(login=999).status_code, 429)

    def test_lista_de_pedidos_so_para_gestao(self):
        self.pedir()
        self.entrar(self.admin)
        r = self.client.get('/api/solicitacoes-senha/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p['login'] for p in r.json()['dados']], [2])

        self.client.get('/logout/')
        self.entrar(self.usuario)
        self.assertEqual(self.client.get('/api/solicitacoes-senha/').status_code, 403)

    def test_redefinir_a_senha_encerra_o_pedido_e_forca_troca(self):
        self.pedir()
        self.entrar(self.admin)
        r = self.post_json('/api/funcionario/', {
            'id': self.usuario.id_funcionario, 'nome': 'Maria', 'cargo': 'Funcionário',
            'login': 2, 'email': 'maria@exemplo.com', 'senha': 'Provisoria#2026',
        })
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(SolicitacaoSenha.objects.filter(atendida=False).count(), 0)
        self.assertTrue(Funcionario.objects.get(pk=self.usuario.pk).primeiro_acesso)
        self.assertEqual(self.client.get('/api/solicitacoes-senha/').json()['dados'], [])

    def test_editar_sem_trocar_a_senha_nao_encerra_o_pedido(self):
        self.pedir()
        self.entrar(self.admin)
        self.post_json('/api/funcionario/', {
            'id': self.usuario.id_funcionario, 'nome': 'Maria Silva', 'cargo': 'Funcionário',
            'login': 2, 'email': 'maria@exemplo.com', 'senha': '',
        })
        self.assertEqual(SolicitacaoSenha.objects.filter(atendida=False).count(), 1)
