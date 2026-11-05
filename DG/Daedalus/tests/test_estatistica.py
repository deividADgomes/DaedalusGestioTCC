from django.test import SimpleTestCase

from ..services.estatistica import (classificar, comparar_diagnostico, intervalo_wilson, limites_controle,
                                    normalizar_texto, pct)


class EstatisticaTests(SimpleTestCase):
    def test_wilson_com_amostra_vazia(self):
        self.assertEqual(intervalo_wilson(0, 0), (0.0, 0.0))

    def test_wilson_valor_conhecido(self):
        inf, sup = intervalo_wilson(3, 10)
        self.assertAlmostEqual(inf, 0.108, places=3)
        self.assertAlmostEqual(sup, 0.603, places=3)

    def test_wilson_nunca_sai_de_0_a_1(self):
        for k, n in ((0, 5), (5, 5), (1, 1)):
            inf, sup = intervalo_wilson(k, n)
            self.assertGreaterEqual(inf, 0.0)
            self.assertLessEqual(sup, 1.0)

    def test_poucos_dados_nao_classifica(self):
        self.assertEqual(classificar(1.0, 0.3, 4), ('insuficiente', None))

    def test_classificacao_por_sigma(self):
        self.assertEqual(classificar(0.8, 0.3, 10)[0], 'critico')
        self.assertEqual(classificar(0.55, 0.3, 20)[0], 'atencao')
        self.assertEqual(classificar(0.0, 0.4, 30)[0], 'destaque')
        self.assertEqual(classificar(0.3, 0.3, 50)[0], 'normal')

    def test_media_degenerada_fica_normal(self):
        self.assertEqual(classificar(0.5, 0.0, 20), ('normal', 0.0))
        self.assertEqual(classificar(0.5, 1.0, 20), ('normal', 0.0))

    def test_limites_estreitam_com_o_volume_e_ficam_entre_0_e_100(self):
        pequeno, grande = limites_controle(0.3, 10), limites_controle(0.3, 200)
        self.assertGreater(pequeno['sup3'] - pequeno['inf3'], grande['sup3'] - grande['inf3'])
        for l in (pequeno, grande, limites_controle(0.05, 5)):
            for chave in ('sup2', 'inf2', 'sup3', 'inf3'):
                self.assertTrue(0.0 <= l[chave] <= 100.0)

    def test_comparacao_ignora_acento_caixa_e_pontuacao(self):
        self.assertEqual(comparar_diagnostico('Tela quebrada', 'TELA  quebrada!'), (True, False))
        self.assertEqual(comparar_diagnostico('Placa-mãe', 'Memória'), (True, True))

    def test_sem_um_dos_textos_nao_e_comparavel(self):
        self.assertEqual(comparar_diagnostico('Tela', ''), (False, False))
        self.assertEqual(comparar_diagnostico(None, 'Tela'), (False, False))

    def test_utilitarios(self):
        self.assertEqual(normalizar_texto('  Açúcar-Mãe!! '), 'acucar mae')
        self.assertEqual(pct(1, 3), 33.3)
        self.assertEqual(pct(1, 0), 0.0)
