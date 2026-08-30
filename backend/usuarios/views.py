from django.http import HttpResponse
from rest_framework import generics, permissions
from .serializers import RegistroSerializer
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages

class RegistroView(generics.CreateAPIView):
    """
    Endpoint público de cadastro de usuário via API REST.
    Não exige autenticação (AllowAny), pois atua como porta de entrada.
    A senha é recebida em texto plano, mas o RegistroSerializer delega 
    a criptografia ao set_password(), aplicando hash (PBKDF2) antes da 
    persistência no banco PostgreSQL.
    """
    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]

def login_view(request):
    """
    Interface visual (Stateful) para autenticação de usuários via web.
    Integra a checagem segura de credenciais com o modelo do PostgreSQL.
    """
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

def home_view(request):
    """
    Endpoint de validação visual para comprovar a transição 
    de estado após o login via front-end (Caminho Feliz).
    """
    return HttpResponse("<h1>Login bem-sucedido! Bem-vindo ao EmprestaCampus.</h1><p>Esta é a tela inicial provisória.</p>")