# Otimização - Alocação de Tarefas Domésticas e Cuidados de Recém Nascido para uma Rede de Apoio

## Descrição

Este projeto implementa um modelo de **Programação Linear Inteira Mista (MILP)** para otimizar a distribuição de tarefas domésticas e de cuidado com um recém nascido entre membros da família, babás e rede de apoio.

### Motivação
Formar uma família traz desafios logísticos imediatos para a casa. Com as mulheres precisando conciliar maternidade com o puerpério, uma rede de apoio sólida é essencial. Este trabalho propõe um modelo computacional para gerenciar as tarefas da casa e do bebê de forma otimizada.

### Objetivo
Criar uma agenda otimizada que:
- Distribui tarefas respeitando disponibilidade e horários de cada pessoa
- Considera a aptidão/capacidade de cada indivíduo para tarefas específicas
- Respeita precedências entre tarefas 
- Garante que tarefas do bebê não se sobrepõem
- Permite que tarefas da casa sejam realizadas em paralelo
- Balanceia a carga de trabalho entre os membros da rede de apoio

## Trabalho Principal

O trabalho principal está em `Trabalho_Final_Vivian.ipynb` e contém:
- Introdução e motivação do problema
- Modelo matemático detalhado com variáveis, parâmetros e restrições
- Implementação do solver usando PuLP + HiGHS
- Análise de resultados com diferentes valores de α (peso de balanceamento)
- Discussão a respeito do trabalho

## Estrutura de Arquivos

- **Trabalho_Final_Vivian.ipynb**: Notebook principal contendo a execução completa e análises.
- **model.py**: Código fonte com a implementação do modelo MILP (PuLP).
- **preprocessamento.py**: Scripts para limpeza e preparação dos dados brutos.
- **input_semanal.json**: Dataset completo com a rotina semanal (modelo não convergiu a tempo).
- **input_semanal_1dia.json**: Dataset utilizado para testar a modelagem.
- **saidas_alphas.txt**: Log de resultados variando os parâmetros alpha.
- **requirements.txt**: Lista de bibliotecas necessárias para rodar o projeto.

## Como Executar

### Opção 1: Executar o Notebook Jupyter
`Bash
cd Trabalho_Final
jupyter notebook Trabalho_Final_Vivian.ipynb
`

### Opção 2: Usar apenas o modelo (sem notebook)
`Bash
cd Trabalho_Final
python model.py
`

## Requisitos

- Python 3.8+
- Bibliotecas principais:
  - `pulp` - Modelagem de problemas de otimização
  - `pandas` - Manipulação de dados
  - `numpy` - Computação numérica
  - `highs` - Solver de programação linear/inteira (automático com PuLP)

### Instalar dependências
`Bash
pip install -r requirements.txt
`

## Formato dos Arquivos de Entrada

Os arquivos JSON contêm:
- **Pessoas**: Nome, disponibilidade (dias/horários), aptidão para cada tarefa, limite de carga horária
- **Tarefas**: Nome, duração (em slots), duração de slot, ocorrências, horários permitidos, precedências, periodicidade
- **Parâmetros**: Duração do slot de tempo, peso α de balanceamento, peso da falta de aptidão

## Formato da Saída

A solução é impressa no terminal como uma tabela com as alocações:
- Pessoa responsável
- Tarefa realizada
- Ocorrência
- Horário de início
- Horário de fim

## Autora

Vivian Souza - UFRJ, 2025

## Disciplina

Otimização - Trabalho Final
