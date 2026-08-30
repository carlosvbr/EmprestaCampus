from django.http import HttpResponse
from rest_framework import generics, permissions
from .serializers import RegistroSerializer
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages


class RegistroView(generics.CreateAPIView):
    """
    Endpoint público de cadastro de usuário.

    Não exige autenticação (AllowAny), já que é justamente o passo que
    cria a conta. A senha chega em texto puro na requisição, mas nunca
    é salva assim: o RegistroSerializer.create() chama set_password,
    que aplica hash (PBKDF2, padrão do Django) antes de gravar no banco.
    """
    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]

def login_view(request):
    """
    Interface visual de login para validação da disciplina.
    Integra a checagem segura de credenciais utilizando os models 
    já estruturados na base de dados PostgreSQL.
    """
    # Restringe a submissão ao método POST para proteger credenciais no payload da requisição
    if request.method == 'POST':
        usuario_digitado = request.POST.get('username')
        senha_digitada = request.POST.get('password')
    # authenticate(): Abstrai a verificação de hash e previne SQL Injection na consulta
        user = authenticate(request, username=usuario_digitado, password=senha_digitada)

        if user is not None:
            # login(): Acopla o usuário validado à sessão, gerando o cookie HTTP-only
            login(request, user)
            return redirect('home') 
        else:
            # Mensagem genérica intencional para mitigar vulnerabilidade de Enumeração de Usuários
            messages.error(request, 'Credenciais inválidas. Verifique seu acesso e tente novamente.')

    return render(request, 'usuarios/login.html')

