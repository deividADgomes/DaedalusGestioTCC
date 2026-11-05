"""Envio do laudo (orçamento) em Word por e-mail ao cliente."""
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email

from ..models import Funcionario, Orcamento, OrcamentoHistorico
from .laudo_docx import gerar_laudo_docx

logger = logging.getLogger(__name__)

DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
STATUS_ENVIAVEIS = ('emitido', 'aprovado', 'recusado')


class LaudoEmailService:
    @staticmethod
    def enviar(id_orcamento: int, destinatario: str, mensagem: str, id_funcionario) -> dict:
        orc = Orcamento.objects.prefetch_related('itens').get(pk=id_orcamento)
        if orc.status not in STATUS_ENVIAVEIS:
            raise ValueError("Só é possível enviar por e-mail um laudo já emitido (não rascunho nem cancelado).")
        if not getattr(settings, 'EMAIL_ENABLED', False):
            raise ValueError("O envio de e-mail não está configurado neste servidor. Baixe o Word e envie pelo seu e-mail.")

        destinatario = (destinatario or orc.cliente_email or '').strip()
        try:
            validate_email(destinatario)
        except ValidationError:
            raise ValueError("Informe um e-mail válido para o destinatário.")

        remetente = Funcionario.objects.filter(pk=id_funcionario).first()
        mensagem = (mensagem or '').strip()[:2000]
        if not mensagem:
            mensagem = (f"Prezados,\n\nsegue o orçamento {orc.numero} referente ao equipamento {orc.equip_modelo}, "
                        f"válido até {orc.validade_ate:%d/%m/%Y}.\n\nFicamos à disposição para qualquer dúvida.")
        if remetente:
            mensagem += f"\n\nAtenciosamente,\n{remetente.nome}"

        arquivo, nome = gerar_laudo_docx(orc)
        email = EmailMessage(
            subject=f"Orçamento {orc.numero}: {orc.equip_modelo}", body=mensagem,
            from_email=settings.DEFAULT_FROM_EMAIL, to=[destinatario],
            reply_to=[remetente.email] if remetente and remetente.email else None)
        email.attach(nome, arquivo.getvalue(), DOCX_MIME)
        try:
            email.send(fail_silently=False)
        except Exception:
            logger.exception("Falha ao enviar o laudo %s por e-mail", orc.numero)
            raise ValueError("Não foi possível enviar o e-mail agora. Confira a configuração de e-mail do servidor e tente de novo.")

        OrcamentoHistorico.objects.create(
            orcamento=orc, funcionario=remetente, funcionario_nome=remetente.nome if remetente else '',
            motivo='Laudo enviado por e-mail', alteracoes=[{'campo': 'E-mail do laudo', 'de': '—', 'para': destinatario}])
        return {'destinatario': destinatario}
