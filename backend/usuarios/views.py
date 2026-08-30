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
    if request.method == 'POST':
        usuario_digitado = request.POST.get('username')
        senha_digitada = request.POST.get('password')

        user = authenticate(request, username=usuario_digitado, password=senha_digitada)

        if user is not None:
            login(request, user)
            return redirect('home') 
        else:
            messages.error(request, 'Credenciais inválidas. Verifique seu acesso e tente novamente.')

    return render(request, 'usuarios/login.html')

def home_view(request):
    """
    View temporária apenas para confirmar que o login funcionou
    e o redirecionamento foi feito com sucesso.
    """
    return HttpResponse("<h1>Login bem-sucedido! Bem-vindo ao EmprestaCampus.</h1><p>Esta é a tela inicial provisória.</p>")