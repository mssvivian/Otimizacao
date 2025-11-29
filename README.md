# Otimização - Gerenciador de Tarefas para Famílias com Recém-nascidos

## Descrição

Este projeto implementa um modelo de **Programação Linear Inteira Mista (MILP)** para otimizar a distribuição de tarefas domésticas e de cuidado com bebês entre membros da família, babás e rede de apoio.

A ideia central é criar uma **agenda otimizada** que:
- Distribui tarefas respeitando disponibilidade e horários de cada pessoa
- Considera a aptidão/capacidade de cada indivíduo para tarefas específicas
- Respeita precedências entre tarefas (ex: banho antes de vestir)
- Balanceia a carga de trabalho entre os membros da rede de apoio
- Garante que tarefas do bebê não se sobrepõem (não é possível amamentar e dar banho simultaneamente)
- Permite que tarefas da casa sejam realizadas em paralelo

## Trabalho Principal

O trabalho principal encontra-se em **Trabalho_Final_Vivian.ipynb** que contém:
- Introdução e motivação
- Modelo matemático detalhado
- Implementação do solver
- Análise e visualização de resultados

## Estrutura do Projeto

\\\
Trabalho_Final/
+-- Trabalho_Final_Vivian.ipynb                       # Notebook principal com todo o projeto
+-- preprocessamento.py                               # Pré-processamento de dados
+-- diagnose.py                                       # Ferramentas de diagnóstico
+-- visualizar_agenda.py                              # Visualização das soluções
+-- test.py                                           # Testes do solver
+-- teste_solver.py                                   # Testes específicos do solver
+-- input.json                                        # Entrada com dados completos
+-- input_semanal.json                                # Entrada com dados semanais
+-- input_semanal_1dia.json                           # Entrada com um dia
+-- input_semanal_1dia_simplificado.json              # Entrada simplificada de um dia
+-- soluçoes/                                         # Soluções geradas (múltiplas execuções)
¦   +-- solucao_cuidados_*.csv                        # Arquivos de solução com timestamps
+-- antigo/                                           # Código anterior (não mais utilizado)
\\\

## Modelo Matemático

### Objetivo
Minimizar: **Falta de Aptidão + a × Desbalanceamento de Carga**

Onde:
- Falta de aptidão = custo de não usar a pessoa mais capacitada
- Desbalanceamento = máxima diferença de carga entre pessoas
- a = peso para balancear os dois objetivos

### Restrições Principais
1. Cada tarefa é realizada exatamente uma vez
2. Não há sobreposição de tarefas por pessoa
3. Não há sobreposição de tarefas do bebê
4. Respeito à disponibilidade de pessoas
5. Respeito aos horários permitidos das tarefas
6. Precedências entre tarefas
7. Periodicidade de tarefas recorrentes

## Requisitos

- Python 3.8+
- Bibliotecas: \ortools\, \pandas\, \
umpy\, \json\

## Como Executar

\\\ash
# Executar o notebook principal
jupyter notebook Trabalho_Final_Vivian.ipynb

# Ou testar o solver diretamente
python teste_solver.py
\\\

## Arquivos de Entrada

Os arquivos JSON contêm:
- **Pessoas**: dados de disponibilidade e aptidão
- **Tarefas**: duração, frequência, horários permitidos, precedências
- **Parâmetros**: tamanho de slots, peso de balanceamento (a), etc.

## Saídas

As soluções são salvas em \soluçoes/\ com timestamp e parâmetro a no nome do arquivo.
O formato é CSV com alocações de cada tarefa para cada pessoa e slot de tempo.

## Autora

Vivian - UFRJ, 2025
