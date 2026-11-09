from decimal import Decimal
from pathlib import Path
import os
import sys
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# Configuração por variáveis de ambiente (veja o arquivo .env.example).
# Nada de segredo fica no código: SECRET_KEY e DATABASE_URL vêm do ambiente.
def _lista_env(nome, padrao=''):
    return [item.strip() for item in os.environ.get(nome, padrao).split(',') if item.strip()]


DEBUG = os.environ.get('DEBUG', 'False') == 'True'

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        # Chave só para desenvolvimento local; nunca é usada com DEBUG desligado.
        SECRET_KEY = 'dev-only-nao-usar-em-producao'
    else:
        raise ImproperlyConfigured(
            "Defina a variável de ambiente SECRET_KEY (gere uma com: "
            "python -c \"from django.core.management.utils import get_random_secret_key as g; print(g())\")."
        )

# Hosts permitidos, separados por vírgula. Ex.: ALLOWED_HOSTS=meuapp.exemplo.com,localhost
ALLOWED_HOSTS = _lista_env('ALLOWED_HOSTS', 'localhost,127.0.0.1')

# Origens HTTPS confiáveis para o CSRF (necessário atrás de proxy/plataforma). Ex.: https://meuapp.exemplo.com
CSRF_TRUSTED_ORIGINS = _lista_env('CSRF_TRUSTED_ORIGINS')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'Daedalus'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'Daedalus.middleware.AutenticacaoMiddleware',  # exige login e aplica permissões por cargo
    'Daedalus.auditoria.AuditoriaMiddleware',      # registra quem gravou/excluiu cadastros
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'DG.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR/'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'DG.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

# Defina DATABASE_URL (ex.: postgres://usuario:senha@host:5432/banco). Sem ela, usa um SQLite local.
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=int(os.environ.get('DB_CONN_MAX_AGE', '60')),
    )
}

# Trava de segurança: os testes criam e apagam um banco "test_..." e não devem rodar em banco remoto
# (ex.: Neon). Use o SQLite padrão ou um Postgres local. Para forçar, defina PERMITIR_TESTE_EM_BANCO_REMOTO=True.
if len(sys.argv) > 1 and sys.argv[1] == 'test':
    _host = DATABASES['default'].get('HOST') or ''
    if _host and _host not in ('localhost', '127.0.0.1', '::1') and os.environ.get('PERMITIR_TESTE_EM_BANCO_REMOTO') != 'True':
        raise ImproperlyConfigured(
            f"Os testes não rodam em banco remoto ({_host}). Remova a DATABASE_URL "
            "(PowerShell: Remove-Item Env:DATABASE_URL) e rode de novo."
        )
    DATABASES['default']['CONN_MAX_AGE'] = 0   # fecha a conexão ao fim de cada requisição de teste

# Cache usado para feriados, consulta ao IBGE e limites de tentativas (login/PartSurfer).
# LocMem é por processo: com vários workers cada um tem o seu. Para limites compartilhados,
# troque por Redis ou pelo cache em banco de dados.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'daedalus-cache',
    }
}

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/
STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Sessão: 30 minutos de inatividade (igual ao controle de inatividade do front-end, em BaseUI.ts).
SESSION_COOKIE_AGE = 1800

# Renova o prazo toda vez que o usuário interage com o back-end (salvar, pesquisar, etc)
SESSION_SAVE_EVERY_REQUEST = True

# Derruba a sessão automaticamente se o usuário fechar a aba/navegador
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Cookies e HTTPS (ligados quando DEBUG está desligado, ou seja, em produção)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
if not DEBUG:
    # A plataforma de hospedagem termina o HTTPS no proxy e repassa o protocolo neste cabeçalho.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600'))  # aumente após validar o HTTPS
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Permissões por cargo, avaliadas pelo middleware, na ordem: a primeira regra que casar vale.
# (prefixo da URL, métodos afetados ou None para todos, cargos permitidos)
# Quem não tem permissão recebe 403. Ajuste aqui conforme a política da empresa.
_GESTAO = {'Administrador', 'Gestor'}
_OPERACIONAL = {'Administrador', 'Gestor', 'Analista de Triagem'}
DAEDALUS_PERMISSOES = [
    ('/api/funcionario/', {'POST'}, _GESTAO),
    ('/api/solicitacoes-senha/', None, _GESTAO),
    ('/auditoria/', None, _GESTAO),
    ('/api/auditoria/', None, _GESTAO),
    ('/api/cotacoes/', {'DELETE'}, _GESTAO),
    ('/api/empresa/', {'POST'}, _OPERACIONAL),
    ('/api/tecnico/', {'POST'}, _OPERACIONAL),
    ('/api/modelo-equipamento/', {'POST', 'PUT', 'DELETE'}, _OPERACIONAL),
    ('/api/pecas/', {'POST', 'PUT', 'DELETE'}, _OPERACIONAL),
    ('/api/estoque/', {'POST', 'PUT', 'DELETE'}, _OPERACIONAL),
    ('/api/saidas/', {'POST', 'PUT', 'DELETE'}, _OPERACIONAL),
    ('/api/orcamentos/', {'POST', 'PUT', 'DELETE'}, _OPERACIONAL),
    ('/api/bi/atualizar/', {'POST'}, _GESTAO),
    ('/api/rfb/modelos/', {'POST'}, _GESTAO),
    ('/api/bi/insights/', {'POST'}, _OPERACIONAL),
]

# Precificação dos orçamentos (laudos):
#   valor unitário da peça = valor da cotação x margem
#   a PRIMEIRA peça do orçamento recebe ainda os adicionais (soma única, não por unidade)
#   validade = dias corridos após a emissão
ORCAMENTO_PRECIFICACAO = {
    'margem': Decimal('1.3'),
    'adicionais_primeira_peca': [Decimal('300'), Decimal('100')],
    'validade_dias': 15,
}

# BI / dashboard
BI_CONFIG = {
    'meta_sla': 95.0,                 # % de chamados concluídos dentro do SLA considerado bom
    'limiares': (60.0, 80.0, 100.0),  # faixas de consumo de SLA (% do limite): atenção, risco, estourado
    'refresh_minutos': 10,            # idade máxima do cálculo de SLA dos chamados ativos
    'cotacao_velha_dias': 30,
    'modelo_min_n': 20,               # mínimo de triagens para apontar um modelo como problemático
    'modelo_fator': 2.0,              # taxa de falha do modelo >= fator x a média geral
}

# E-mail (alertas de SLA). Sem EMAIL_HOST, nada é enviado (os avisos aparecem só no painel).
EMAIL_ENABLED = bool(os.environ.get('EMAIL_HOST'))
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend' if EMAIL_ENABLED else 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'daedalus@localhost')
# Destinatários extras (separados por vírgula) dos avisos de redefinição de senha, além dos administradores com e-mail.
DAEDALUS_EMAIL_ADMIN = os.environ.get('ADMIN_EMAIL', '')
# Alerta de chamado RFB NÃO agendado: dispara quando o SLA consumido chega a este percentual (padrão 75).
RFB_ALERTA_NAO_AGENDADO_PCT = float(os.environ.get('RFB_ALERTA_NAO_AGENDADO_PCT', '75'))
# Quem recebe: 'gestao' (Administradores e Gestores com e-mail, mais ADMIN_EMAIL), 'analista' (o analista responsável
# pelo chamado; sem e-mail ou sem analista, cai para a gestão) ou 'ambos'. Trocar é só mudar esta variável no Render.
RFB_ALERTA_NAO_AGENDADO_PARA = os.environ.get('RFB_ALERTA_NAO_AGENDADO_PARA', 'gestao').strip().lower()
# E-mail(s) do setor fiscal (separados por vírgula) que recebem as listas de saída de peças.
FISCAL_EMAIL = os.environ.get('FISCAL_EMAIL', '')
SITE_URL = os.environ.get('SITE_URL', '')   # ex.: https://meuapp.onrender.com (usado nos links dos e-mails)

# Monitoramento de erros (opcional). Para ligar: inclua `sentry-sdk` no requirements.txt e defina SENTRY_DSN no Render.
# Sem o DSN (ou sem o pacote) nada acontece. Dados pessoais dos usuários não são enviados.
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=SENTRY_DSN, send_default_pii=False, traces_sample_rate=0.0,
                        environment=os.environ.get('SENTRY_ENVIRONMENT', 'producao'))
    except ImportError:
        print('SENTRY_DSN definido, mas o pacote sentry-sdk não está instalado: o monitoramento ficou desligado.')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'padrao': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'padrao'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('LOG_LEVEL', 'INFO')},
}