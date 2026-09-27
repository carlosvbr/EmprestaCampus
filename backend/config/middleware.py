import zoneinfo
from django.utils import timezone


class FusoHorarioUsuarioMiddleware:
    """
    Ativa o fuso horário do navegador do aluno (enviado via cookie
    'fuso_horario_usuario', setado por JS nas telas do site) nas
    páginas comuns do sistema.

    As páginas do Django Admin (/admin/) são propositalmente
    ignoradas aqui: o admin sempre vê os horários no fuso do servidor
    (settings.TIME_ZONE)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            # Admin sempre no fuso do servidor: desativa qualquer
            # fuso previamente ativado, garantindo o padrão de
            # settings.TIME_ZONE.
            timezone.deactivate()
        else:
            tz_name = request.COOKIES.get('fuso_horario_usuario')
            if tz_name:
                try:
                    timezone.activate(zoneinfo.ZoneInfo(tz_name))
                except zoneinfo.ZoneInfoNotFoundError:
                    # Cookie com valor inválido/corrompido: cai no
                    # fuso padrão do servidor em vez de quebrar a página.
                    timezone.deactivate()
            else:
                # Aluno ainda não tem o cookie (ex: primeiro acesso,
                # antes do JS rodar) — usa o fuso padrão por enquanto.
                timezone.deactivate()

        return self.get_response(request)