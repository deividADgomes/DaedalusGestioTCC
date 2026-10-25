import random
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from Daedalus import demo_dados, demo_fotos
from Daedalus.models import (Empresa, Equipamento, FotoTriagem, Funcionario, Peca,
                             SolicitacaoSenha, Tecnico, Triagem)
from Daedalus.services import FotoService


class Command(BaseCommand):
    help = ('Popula o banco com dados FICTÍCIOS de demonstração (empresas, técnicos, modelos, peças, '
            'triagens e fotos) para apresentar o Daedalus Gestio.')

    def add_arguments(self, parser):
        parser.add_argument('--limpar', action='store_true',
                            help='Apaga TODOS os dados atuais (inclusive fotos e funcionários) antes de criar o demo.')
        parser.add_argument('--quantidade', type=int, default=420, help='Número base de triagens (padrão: 420).')
        parser.add_argument('--dias', type=int, default=120, help='Período coberto, em dias até ontem (padrão: 120).')
        parser.add_argument('--semente', type=int, default=demo_dados.SEED_PADRAO,
                            help='Semente do gerador (a padrão foi escolhida para o dashboard contar uma boa história).')
        parser.add_argument('--sem-fotos', action='store_true', help='Não gera as fotos das triagens.')

    def handle(self, *args, **opcoes):
        if opcoes['quantidade'] < 10 or opcoes['dias'] < 7:
            raise CommandError('Use pelo menos --quantidade 10 e --dias 7.')
        tem_dados = (Triagem.objects.exists() or Funcionario.objects.exists()
                     or Empresa.objects.exists() or Equipamento.objects.exists())
        if tem_dados and not opcoes['limpar']:
            raise CommandError('O banco já tem dados. Rode com --limpar para apagar tudo e recriar o demo.')
        if opcoes['limpar']:
            self._limpar()

        hoje = timezone.localdate()
        dados = demo_dados.gerar(hoje, total=opcoes['quantidade'], dias=opcoes['dias'], seed=opcoes['semente'])
        triagens = self._gravar(dados)
        fotos = 0 if opcoes['sem_fotos'] else self._fotos(triagens, dados['triagens'], opcoes['semente'])
        self._resumo(dados, len(triagens), fotos)

    # ------------------------------------------------------------------
    def _limpar(self):
        self.stdout.write('Apagando os dados atuais...')
        for foto in FotoTriagem.objects.all():
            foto.arquivo.delete(save=False)
        FotoTriagem.objects.all().delete()
        Triagem.objects.all().delete()
        SolicitacaoSenha.objects.all().delete()
        Equipamento.objects.all().delete()
        Peca.objects.all().delete()
        Tecnico.objects.all().delete()
        Empresa.objects.all().delete()
        Funcionario.objects.all().delete()

    def _gravar(self, dados):
        self.stdout.write('Gravando empresas, técnicos, funcionários, modelos e peças...')
        agora = timezone.now()
        with transaction.atomic():
            empresas = {e['cnpj']: Empresa.objects.create(cnpj=e['cnpj'], razao_social=e['razao_social'], tipo=e['tipo'])
                        for e in dados['empresas']}
            tecnicos = {t['nome']: Tecnico.objects.create(empresa=empresas[t['prestadora_cnpj']], nome=t['nome'])
                        for t in dados['tecnicos']}

            senha_demo = make_password(demo_dados.SENHA_DEMO)
            funcionarios = {}
            for f in dados['funcionarios']:
                # no primeiro acesso a senha provisória é a própria matrícula (como no cadastro real)
                senha = make_password(str(f['login'])) if f['primeiro_acesso'] else senha_demo
                funcionarios[f['login']] = Funcionario.objects.create(
                    cargo=f['cargo'], nome=f['nome'], login=f['login'], senha=senha,
                    email=f['email'], primeiro_acesso=f['primeiro_acesso'])

            pecas = {p['part_number']: Peca.objects.create(part_number=p['part_number'], descricao=p['descricao'])
                     for p in dados['pecas']}
            equipamentos = {}
            for m in dados['modelos']:
                equip = Equipamento.objects.create(pn=m['pn'], modelo=m['modelo'])
                equip.pecas.set([pecas[pn] for _, pn in m['pecas']])
                equipamentos[m['pn']] = equip

            for s in dados['solicitacoes']:
                SolicitacaoSenha.objects.create(
                    funcionario=funcionarios[s['login']],
                    data_solicitacao=agora - timedelta(days=s['dias_atras'], hours=1),
                    atendida=s['atendida'])

            self.stdout.write(f"Gravando {len(dados['triagens'])} triagens...")
            triagens = []
            for t in dados['triagens']:
                triagens.append(Triagem.objects.create(
                    n_ticket=t['n_ticket'], nf=t['nf'], cidade=t['cidade'], estado=t['estado'],
                    tecnico=tecnicos[t['tecnico_nome']], cliente=empresas[t['cliente_cnpj']],
                    equipamento=equipamentos[t['modelo_pn']],
                    analista_chamado=funcionarios[t['analista_chamado']],
                    analista_triagem=funcionarios[t['analista_triagem']],
                    sn=t['sn'], status=t['status'], data_triagem=timezone.make_aware(t['data']),
                    troca=t['troca'], peca_trocada=pecas.get(t['peca_pn']),
                    defeito_usuario=t['defeito_usuario'], defeito_tecnico=t['defeito_tecnico'],
                    defeito_constatado=t['defeito_constatado'], testes=t['testes'],
                    analise=t['analise'], conclusao=t['conclusao']))
        return triagens

    def _fotos(self, triagens, linhas, semente):
        rng = random.Random(semente)
        total = sum(len(l['fotos']) for l in linhas)
        self.stdout.write(f'Gerando {total} fotos (pode levar alguns instantes)...')
        feitas = 0
        for triagem, linha in zip(triagens, linhas):
            for i, f in enumerate(linha['fotos']):
                conteudo = demo_fotos.gerar_foto(f['tipo'], f['legenda'], triagem.n_ticket, rng.randint(1, 10**9))
                arquivo = SimpleUploadedFile(f'foto_{triagem.n_ticket}_{i + 1}.jpg', conteudo, content_type='image/jpeg')
                resultado = FotoService.adicionar(triagem.id_triagem, arquivo, f['legenda'])
                # a foto é "tirada" no dia da triagem
                FotoTriagem.objects.filter(pk=resultado['id']).update(
                    criado_em=triagem.data_triagem + timedelta(minutes=5 * (i + 1)))
                feitas += 1
            if feitas and feitas % 100 == 0:
                self.stdout.write(f'  {feitas}/{total} fotos')
        return feitas

    def _resumo(self, dados, n_triagens, n_fotos):
        self.stdout.write(self.style.SUCCESS('\nBanco de demonstração criado com sucesso!'))
        self.stdout.write(
            f"  Empresas: {len(dados['empresas'])} | Técnicos: {len(dados['tecnicos'])} | "
            f"Funcionários: {len(dados['funcionarios'])} | Modelos: {len(dados['modelos'])} | "
            f"Peças: {len(dados['pecas'])} | Triagens: {n_triagens} | Fotos: {n_fotos}")
        self.stdout.write('\nAcessos (matrícula / perfil):')
        for f in dados['funcionarios']:
            senha = str(f['login']) if f['primeiro_acesso'] else demo_dados.SENHA_DEMO
            nota = '  <- primeiro acesso (troca de senha obrigatória)' if f['primeiro_acesso'] else ''
            self.stdout.write(f"  {f['login']}  {f['cargo']:<20} {f['nome']:<24} senha: {senha}{nota}")
