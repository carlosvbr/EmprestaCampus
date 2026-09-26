from django.contrib import admin
from .models import Categoria, Equipamento


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    # define quais colunas aparecem na listagem do admin
    list_display = ('nome', 'descricao')

    # habilita a caixa de busca no topo da listagem
    search_fields = ('nome',)


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'patrimonio', 'categoria', 'status', 'data_cadastro')

    list_filter = ('status', 'categoria')

    search_fields = ('nome', 'patrimonio')

    readonly_fields = ('data_cadastro',)