import re

from django.urls import reverse

from .base import BaseTestCase

PAGINAS = ['principal', 'triagem', 'pesquisa', 'serie', 'dashboard', 'gerenciarRFB', 'emissaoLaudos', 'pesquisaLaudos',
           'estatisticasLaudos', 'gerenciarEmpresa', 'gerenciarTecnico', 'gerenciarFuncionario', 'gerenciarModeloEquipamento',
           'estoque', 'saidas', 'auditoria']


def lateral(html: str) -> str:
    return re.search(r'<aside id="sidebar".*?</aside>', html, re.S).group(0)


def grupo(html: str, titulo: str) -> str:
    """Trecho do submenu cujo título é `titulo`."""
    for bloco in re.findall(r'<details class="grupo-menu".*?</details>', html, re.S):
        if re.search(rf'<span class="text-sm flex-1">{titulo}</span>', bloco):
            return bloco
    raise AssertionError(f'submenu {titulo} não encontrado')


class MenuETelasTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.gestor = self.criar_funcionario(cargo='Gestor', login=71, nome='Gil Gestor', email='gil@exemplo.com')
        self.entrar(self.gestor)

    def abrir(self, nome):
        r = self.client.get(reverse(nome))
        self.assertEqual(r.status_code, 200, nome)
        return r.content.decode('utf-8')

    def test_todas_as_telas_abrem_com_o_menu_lateral_completo(self):
        for nome in PAGINAS:
            html = self.abrir(nome)
            self.assertIn('id="sidebar"', html, nome)
            for destino in PAGINAS:
                self.assertIn(f'href="{reverse(destino)}"', html, f'{nome} sem link para {destino}')

    def test_menu_lateral_rola_para_nao_cortar_os_itens_do_fim(self):
        html = self.abrir('principal')
        self.assertRegex(html, r'<nav class="[^"]*overflow-y-auto')

    def test_pesquisa_fica_dentro_do_submenu_de_triagem(self):
        html = self.abrir('principal')
        triagem = grupo(html, 'Triagem')
        for destino in ('triagem', 'pesquisa', 'serie'):
            self.assertIn(f'href="{reverse(destino)}"', triagem)
        # fora dos submenus, o menu lateral não tem mais o link solto da pesquisa
        solto = re.sub(r'<details class="grupo-menu".*?</details>', '', lateral(html), flags=re.S)
        self.assertNotIn(f'href="{reverse("pesquisa")}"', solto)

    def test_estoque_saidas_e_cadastros_ficam_em_seus_submenus(self):
        html = self.abrir('principal')
        self.assertIn(f'href="{reverse("estoque")}"', grupo(html, 'Estoque'))
        self.assertIn(f'href="{reverse("saidas")}"', grupo(html, 'Estoque'))
        for destino in ('gerenciarEmpresa', 'gerenciarTecnico', 'gerenciarFuncionario', 'gerenciarModeloEquipamento'):
            self.assertIn(f'href="{reverse(destino)}"', grupo(html, 'Cadastros'))
        for destino in ('emissaoLaudos', 'pesquisaLaudos', 'estatisticasLaudos'):
            self.assertIn(f'href="{reverse(destino)}"', grupo(html, 'Orçamentos'))

    def test_o_submenu_da_tela_atual_vem_aberto_e_os_outros_fechados(self):
        html = self.abrir('estoque')
        self.assertTrue(grupo(html, 'Estoque').startswith('<details class="grupo-menu" open>'))
        self.assertTrue(grupo(html, 'Cadastros').startswith('<details class="grupo-menu">'))
        self.assertTrue(grupo(self.abrir('pesquisa'), 'Triagem').startswith('<details class="grupo-menu" open>'))
        self.assertTrue(grupo(self.abrir('gerenciarEmpresa'), 'Cadastros').startswith('<details class="grupo-menu" open>'))

    def test_pagina_inicial_tem_cartoes_das_telas_novas(self):
        corpo = re.sub(r'<aside id="sidebar".*?</aside>', '', self.abrir('principal'), flags=re.S)       # só o conteúdo, sem o menu lateral
        for destino in ('serie', 'estoque', 'saidas', 'auditoria'):
            self.assertIn(f'href="{reverse(destino)}"', corpo, destino)

    def test_auditoria_so_aparece_para_a_gestao(self):
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Funcionário', login=72, nome='Maria', email='m@exemplo.com'))
        html = self.abrir('principal')
        self.assertNotIn(f'href="{reverse("auditoria")}"', html)          # nem no menu lateral nem nos cartões
        self.assertIn(f'href="{reverse("estoque")}"', html)

    def test_sino_geral_nao_duplica_na_tela_de_rfb(self):
        rfb = self.abrir('gerenciarRFB')
        self.assertNotIn('id="btn-avisos"', rfb)
        self.assertIn('id="btn-notificacoes"', rfb)                  # o sino de SLA da própria tela continua
        for nome in ('principal', 'estoque', 'saidas', 'triagem'):
            self.assertEqual(self.abrir(nome).count('id="btn-avisos"'), 1, nome)
