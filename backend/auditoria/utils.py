import ipaddress


def get_client_ip(request):
    for cabecalho in ('HTTP_X_REAL_IP', 'REMOTE_ADDR'):
        valor = (request.META.get(cabecalho) or '').strip()
        try:
            return str(ipaddress.ip_address(valor))
        except ValueError:
            continue
    return None