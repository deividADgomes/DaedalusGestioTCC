import random
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from Daedalus import demo_dados, demo_fotos
from Daedalus.models import (
    Empresa,
    Equipamento,
    FotoTriagem,
    Funcionario,
    Peca,
    SolicitacaoSenha,
    Tecnico,
    Triagem,
)
from Daedalus.services import FotoService

MIN_TRIAGENS = 10
MIN_DIAS = 7
MINUTOS_ENTRE_FOTOS = 5
LOTE_DO_PROGRESSO = 100


class Command(BaseCommand):
    help = (
        'Popula o banco com dados FICTÍCIOS de demonstração (empresas, técnicos, modelos, peças, '
        'triagens e fotos) para apresentar o Daedalus Gestio.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar', action='store_true',
            help='Apaga TODOS os dados atuais (inclusive fotos e funcionários) antes de criar o demo.',
        )
        parser.add_argument('--quantidade', type=int, default=420, help='Número base de triagens (padrão: 420).')
        parser.add_argument('--dias', type=int, default=120, help='Período coberto, em dias até ontem (padrão: 120).')
        parser.add_argument(
            '--semente', type=int, default=demo_dados.SEED_PADRAO,
            help='Semente do gerador (a padrão foi escolhida para o dashboard contar uma boa história).',
        )
        parser.add_argument('--sem-fotos', action='store_true', help='Não gera as fotos das triagens.')

    def handle(self, *args, **opcoes):
        if opcoes['quantidade'] < MIN_TRIAGENS or opcoes['dias'] < MIN_DIAS:
            raise CommandError(f'Use pelo menos --quantidade {MIN_TRIAGENS} e --dias {MIN_DIAS}.')
        if self._banco_tem_dados() and not opcoes['limpar']:
            raise CommandError('O banco já tem dados. Rode com --limpar para apagar tudo e recriar o demo.')
        if opcoes['limpar']:
            self._limpar()

        dados = demo_dados.gerar(
            timezone.localdate(), total=opcoes['quantidade'], dias=opcoes['dias'], seed=opcoes['semente']
        )
        triagens = self._gravar(dados)
        fotos = 0 if opcoes['sem_fotos'] else self._gerar_fotos(triagens, dados['triagens'], opcoes['semente'])
        self._exibir_resumo(dados, len(triagens), fotos)

    @staticmethod
    def _banco_tem_dados():
        return (
            Triagem.objects.exists()
            or Funcionario.objects.exists()
            or Empresa.objects.exists()
            or Equipamento.objects.exists()
        )

    def _limpar(self):
        self.stdout.write('Apagando os dados atuais...')
        for foto in FotoTriagem.objects.all():
            foto.arquivo.delete(save=False)
        for modelo in (
            FotoTriagem, Triagem, SolicitacaoSenha, Equipamento, Peca, Tecnico, Empresa, Funcionario,
        ):
            modelo.objects.all().delete()

    @staticmethod
    def _gravar_empresas_e_tecnicos(dados):
        empresas = {
            empresa['cnpj']: Empresa.objects.create(
                cnpj=empresa['cnpj'], razao_social=empresa['razao_social'], tipo=empresa['tipo']
            )
            for empresa in dados['empresas']
        }
        tecnicos = {
            tecnico['nome']: Tecnico.objects.create(
                empresa=empresas[tecnico['prestadora_cnpj']], nome=tecnico['nome']
            )
            for tecnico in dados['tecnicos']
        }
        return empresas, tecnicos

    @staticmethod
    def _gravar_funcionarios(dados):
        senha_demo = make_password(demo_dados.SENHA_DEMO)
        funcionarios = {}
        for funcionario in dados['funcionarios']:
            primeiro_acesso = funcionario['primeiro_acesso']
            senha = make_password(str(funcionario['login'])) if primeiro_acesso else senha_demo
            funcionarios[funcionario['login']] = Funcionario.objects.create(
                cargo=funcionario['cargo'],
                nome=funcionario['nome'],
                login=funcionario['login'],
                senha=senha,
                email=funcionario['email'],
                primeiro_acesso=primeiro_acesso,
            )
        return funcionarios

    @staticmethod
    def _gravar_catalogo(dados):
        pecas = {
            peca['part_number']: Peca.objects.create(part_number=peca['part_number'], descricao=peca['descricao'])
            for peca in dados['pecas']
        }
        equipamentos = {}
        for modelo in dados['modelos']:
            equipamento = Equipamento.objects.create(pn=modelo['pn'], modelo=modelo['modelo'])
            equipamento.pecas.set([pecas[part_number] for _, part_number in modelo['pecas']])
            equipamentos[modelo['pn']] = equipamento
        return pecas, equipamentos

    @staticmethod
    def _gravar_solicitacoes(dados, funcionarios):
        agora = timezone.now()
        for solicitacao in dados['solicitacoes']:
            SolicitacaoSenha.objects.create(
                funcionario=funcionarios[solicitacao['login']],
                data_solicitacao=agora - timedelta(days=solicitacao['dias_atras'], hours=1),
                atendida=solicitacao['atendida'],
            )

    @staticmethod
    def _gravar_triagem(dados_triagem, empresas, tecnicos, funcionarios, equipamentos, pecas):
        return Triagem.objects.create(
            n_ticket=dados_triagem['n_ticket'],
            nf=dados_triagem['nf'],
            cidade=dados_triagem['cidade'],
            estado=dados_triagem['estado'],
            tecnico=tecnicos[dados_triagem['tecnico_nome']],
            cliente=empresas[dados_triagem['cliente_cnpj']],
            equipamento=equipamentos[dados_triagem['modelo_pn']],
            analista_chamado=funcionarios[dados_triagem['analista_chamado']],
            analista_triagem=funcionarios[dados_triagem['analista_triagem']],
            sn=dados_triagem['sn'],
            status=dados_triagem['status'],
            data_triagem=timezone.make_aware(dados_triagem['data']),
            troca=dados_triagem['troca'],
            peca_trocada=pecas.get(dados_triagem['peca_pn']),
            defeito_usuario=dados_triagem['defeito_usuario'],
            defeito_tecnico=dados_triagem['defeito_tecnico'],
            defeito_constatado=dados_triagem['defeito_constatado'],
            testes=dados_triagem['testes'],
            analise=dados_triagem['analise'],
            conclusao=dados_triagem['conclusao'],
        )

    def _gravar(self, dados):
        self.stdout.write('Gravando empresas, técnicos, funcionários, modelos e peças...')
        with transaction.atomic():
            empresas, tecnicos = self._gravar_empresas_e_tecnicos(dados)
            funcionarios = self._gravar_funcionarios(dados)
            pecas, equipamentos = self._gravar_catalogo(dados)
            self._gravar_solicitacoes(dados, funcionarios)

            self.stdout.write(f"Gravando {len(dados['triagens'])} triagens...")
            return [
                self._gravar_triagem(item, empresas, tecnicos, funcionarios, equipamentos, pecas)
                for item in dados['triagens']
            ]

    def _gerar_fotos(self, triagens, linhas, semente):
        rng = random.Random(semente)
        total = sum(len(linha['fotos']) for linha in linhas)
        self.stdout.write(f'Gerando {total} fotos (pode levar alguns instantes)...')

        feitas = 0
        for triagem, linha in zip(triagens, linhas):
            for posicao, foto in enumerate(linha['fotos'], start=1):
                conteudo = demo_fotos.gerar_foto(foto['tipo'], foto['legenda'], triagem.n_ticket, rng.randint(1, 10**9))
                arquivo = SimpleUploadedFile(
                    f'foto_{triagem.n_ticket}_{posicao}.jpg', conteudo, content_type='image/jpeg'
                )
                resultado = FotoService.adicionar(triagem.id_triagem, arquivo, foto['legenda'])
                FotoTriagem.objects.filter(pk=resultado['id']).update(
                    criado_em=triagem.data_triagem + timedelta(minutes=MINUTOS_ENTRE_FOTOS * posicao)
                )
                feitas += 1
            if feitas and feitas % LOTE_DO_PROGRESSO == 0:
                self.stdout.write(f'  {feitas}/{total} fotos')
        return feitas

    def _exibir_resumo(self, dados, total_triagens, total_fotos):
        self.stdout.write(self.style.SUCCESS('\nBanco de demonstração criado com sucesso!'))
        self.stdout.write(
            f"  Empresas: {len(dados['empresas'])} | Técnicos: {len(dados['tecnicos'])} | "
            f"Funcionários: {len(dados['funcionarios'])} | Modelos: {len(dados['modelos'])} | "
            f"Peças: {len(dados['pecas'])} | Triagens: {total_triagens} | Fotos: {total_fotos}"
        )
        self.stdout.write('\nAcessos (matrícula / perfil):')
        for funcionario in dados['funcionarios']:
            primeiro_acesso = funcionario['primeiro_acesso']
            senha = str(funcionario['login']) if primeiro_acesso else demo_dados.SENHA_DEMO
            nota = '  <- primeiro acesso (troca de senha obrigatória)' if primeiro_acesso else ''
            self.stdout.write(
                f"  {funcionario['login']}  {funcionario['cargo']:<20} {funcionario['nome']:<24} "
                f"senha: {senha}{nota}"
            )
