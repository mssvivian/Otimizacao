import json
import pulp
import pandas as pd
import preprocessamento
import math
import itertools
import time

# Tenta importar tabulate para tabelas bonitas, senão usa pandas padrão
try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

# Script principal para montar e resolver o modelo de alocação de tarefas.
# Este arquivo monta um modelo MILP (pulp) a partir do JSON processado
# por `preprocessamento.carregar_dados(...)` e aplica as restrições

# ==============================
# 1. Leitura e Pré-processamento
# ==============================

# Carrega e processa o JSON com funções utilitárias (converte janelas e disponibilidades
# em vetores binários, calcula slots, etc.). O dicionário retornado contém tanto os dados
# originais quanto as chaves auxiliares `disponibilidade_pessoas_binaria` e `disponibilidade_tarefas_binaria`.
data = preprocessamento.carregar_dados("input_semanal_1dia.json")

if data is None:
    print("Erro fatal: Falha ao carregar ou processar os dados. Encerrando.")
    exit()

pessoas = data["pessoas"] # conjunto de pessoas
tarefas = list(data["tarefas"].keys()) # conjunto de tarefas
duracao_slot = data["slot_duracao_min"]
total_slots = data["dias"]*24*(60//duracao_slot) # número total de slots
disponibilidade_tarefas = data.get("disponibilidade_tarefas_binaria") # TA_{j,t}
alpha = data.get("alpha", 0) # Valor padrão 0 se não estiver definido
tarefas_bebe = [j for j, task_data in data["tarefas"].items() if task_data.get("tipo") == "bebe"]
duracao_tarefas = {
    j: math.ceil(data["tarefas"][j]["duracao"] / duracao_slot) 
    for j in tarefas
} # d_j (duração em slots)
ocorrencias = {j: range(data["tarefas"][j]["ocorrencias"]) for j in tarefas}
disponibilidade_pessoas = data["disponibilidade_pessoas_binaria"]
capacidade = data["aptidao"] # c_{i,j}
dependencias =  data["dependencias"] # dependências entre tarefas

limite_carga_horas = data.get("limite_carga_horas", {})
if duracao_slot > 0:
    limite_carga = {i: int((limite_em_horas * 60) / duracao_slot) 
                    for i, limite_em_horas in limite_carga_horas.items()}
else:
    limite_carga = {}
    print("Aviso: 'slot_duracao_min' é 0. O Limite de Carga não será aplicado.")

# ==============================
# 2. Criação do modelo
# ==============================

model = pulp.LpProblem("x_Cuidados_Bebe", pulp.LpMinimize)

# Variável Delta para o Balanceamento 
# Representa a maior diferença de % de carga entre duas pessoas
delta_balanceamento = pulp.LpVariable("Delta_Balanceamento", lowBound=0, cat="Continuous")

# Variáveis de decisão: x[i][j][o][t] = 1 se pessoa i inicia tarefa j, ocorrência o no slot t
x = {}
for i in pessoas:
    x[i] = {}
    for j in tarefas:
        x[i][j] = {}
        for o in ocorrencias[j]:
            x[i][j][o] = {}
            for t in range(total_slots):
                x[i][j][o][t] = pulp.LpVariable(f"x_{i}_{j}_{o}_{t}", cat="Binary")

# Proibir inícios inválidos: se t + D[j] > Slots então x[i][j][o][t] == 0
for i in pessoas:
    for j in tarefas:
        dur = duracao_tarefas[j]
        ultimo_inicio = total_slots - dur
        for o in ocorrencias[j]:
            for t in range(total_slots):
                if t > ultimo_inicio:
                    model += x[i][j][o][t] == 0

# ==============================
# 3. Função Objetivo
# ==============================

# Termo 1: Aptidão (Minimizar falta de aptidão)
objetivo_aptidao = pulp.lpSum(
    (1 - capacidade[i][j]) * x[i][j][o][t]
    for i in pessoas
    for j in tarefas 
    for o in ocorrencias[j]
    for t in range(total_slots)
)

# Termo 2: Penalidade de Desequilíbrio (alpha * delta)
model += objetivo_aptidao + (alpha * delta_balanceamento)

# ==============================
# 4. Restrições
# ==============================

# 4.1 Cada ocorrência de tarefa deve ser realizada exatamente uma vez
for j in tarefas:
    for o in ocorrencias[j]:
        model += pulp.lpSum(x[i][j][o][t] for i in pessoas for t in range(total_slots)) == 1

# 4.2 Não sobreposição de tarefas por pessoa
for i in pessoas:
    for t in range(total_slots):
        model += (
            pulp.lpSum(
                x[i][j][o][t_start]
                for j in tarefas
                for o in ocorrencias[j]
                for t_start in range(max(0, t - duracao_tarefas[j] + 1), t + 1)
            )
            <= 1
        )

# 4.3 Não sobreposição de tarefas do bebê
for t in range(total_slots):
    expr = []
    for i in pessoas:
        for j in tarefas_bebe:
            dur = duracao_tarefas[j]
            t_start_min = max(0, t - dur + 1)
            t_start_max = min(t, total_slots - dur)
            for o in ocorrencias[j]:
                for t_start in range(t_start_min, t_start_max + 1):
                    expr.append(x[i][j][o][t_start])
    model += pulp.lpSum(expr) <= 1


# 4.4 Respeitar disponibilidade das pessoas
for i in pessoas:
    for j in tarefas:
        for o in ocorrencias[j]:
            for t in range(total_slots):
                if disponibilidade_pessoas[i][t] == 0:
                    model += x[i][j][o][t] == 0

# 4.5 Respeitar horários das Tarefas
# Se disponibilidade_tarefas[j][t] == 0, a tarefa j não pode começar no slot t.
for j in tarefas:
    if disponibilidade_tarefas and 0 in disponibilidade_tarefas[j]:
        for o in ocorrencias[j]:
            for t in range(total_slots):
                if disponibilidade_tarefas[j][t] == 0:
                    for i in pessoas:
                        model += x[i][j][o][t] == 0

# 4.6 Precedência entre tarefas
for j1_id in dependencias:
    j2_id = dependencias[j1_id]["proxima_tarefa"]
    W = math.ceil(dependencias[j1_id]["janela_de_espera"] / duracao_slot)
    print(f"Aplicando precedência: {j1_id} -> {j2_id} com janela {W} slots.")

    for o in ocorrencias[j1_id]:
        for t2 in range(total_slots):
            d_j1 = duracao_tarefas[j1_id]
            t1_min = max(0, t2 - d_j1 - W)
            t1_max = min(t2 - d_j1, total_slots - d_j1)

            if t1_min > t1_max:
                # Se não existe nenhum início válido de j1 que permita j2 iniciar em t2,
                # então nenhum i2 pode iniciar j2 em t2 (forçamos a variável a 0).
                for i2 in pessoas:
                    model += x[i2][j2_id][o][t2] == 0
                continue

            lhs = []
            for i1 in pessoas:
                for t1 in range(t1_min, t1_max + 1):
                    lhs.append(x[i1][j1_id][o][t1])

            for i2 in pessoas:
                model += pulp.lpSum(lhs) >= x[i2][j2_id][o][t2]

# 4.6 Restrição de periodicidade (tarefas recorrentes)
if "periodicidade" in data:
    for j, P_j in data["periodicidade"].items():
        P_j_slots = math.ceil(P_j / duracao_slot)
        dur = duracao_tarefas[j]
        last_start = total_slots - dur
        for o in range(len(ocorrencias[j]) - 1):
            for t1 in range(0, last_start + 1):
                t2 = t1 + P_j_slots
                if t2 <= last_start:
                    model += pulp.lpSum(x[i][j][o][t1] for i in pessoas) == \
                             pulp.lpSum(x[i][j][o+1][t2] for i in pessoas)
                else:
                    # Se o deslocamento pela periodicidade ultrapassa o horizonte,
                    # então um início em t1 não é válido (eliminação de inicios inválidos).
                    model += pulp.lpSum(x[i][j][o][t1] for i in pessoas) == 0

# 4.8 e 4.9 : Limites e Balanceamento

# 1. Pré-cálculo das Expressões de Carga
# Isso cria a expressão linear da carga total (em slots) para cada pessoa UMA ÚNICA VEZ.
expressao_carga_pessoa = {}

for i in pessoas:
    # Monta a soma de (duração * variável_decisao)
    expressao_carga_pessoa[i] = pulp.lpSum(
        duracao_tarefas[j] * x[i][j][o][t]
        for j in tarefas
        for o in ocorrencias[j]
        for t in range(total_slots)
    )

# 2. Aplicação da Restrição "Hard" (Limite Máximo)
# Ninguém pode ultrapassar seu teto de horas, independente do balanceamento.
if limite_carga:
    for i in pessoas:
        if i in limite_carga:
            L_i = limite_carga[i]
            # Usa a expressão pré-calculada (muito mais rápido)
            model += expressao_carga_pessoa[i] <= L_i, f"Limite_Maximo_{i}"

# 3. Aplicação da Restrição "Soft" (Balanceamento Relativo / Minimax)
# Tenta igualar a % de ocupação entre as pessoas.
if limite_carga and alpha > 0:
    # Filtra apenas pessoas com limite definido > 0
    pessoas_validas = [p for p in pessoas if p in limite_carga and limite_carga[p] > 0]
    
    if len(pessoas_validas) >= 2:
        # itertools.combinations evita pares duplicados e auto-comparação (ex: A-B é igual B-A)
        for p1, p2 in itertools.combinations(pessoas_validas, 2):
            L1 = float(limite_carga[p1])
            L2 = float(limite_carga[p2])
            
            # Percentual de uso = Carga Real / Limite Total
            pct_p1 = expressao_carga_pessoa[p1] / L1
            pct_p2 = expressao_carga_pessoa[p2] / L2
            
            # Para forçar Delta >= |pc (norma infinita)t_p1 - pct_p2|, adicionamos duas restrições lineares:
            
            # 1. (P1 - P2) <= Delta
            model += pct_p1 - pct_p2 <= delta_balanceamento, f"Balanceamento_{p1}_{p2}_pos"
            
            # 2. (P2 - P1) <= Delta
            model += pct_p2 - pct_p1 <= delta_balanceamento, f"Balanceamento_{p1}_{p2}_neg"


# ==============================
# 5. Resolver modelo e mostrar solução
# ==================o pelo solver.
start_time = time.perf_counter()

solver = pulp.getSolver('HiGHS', timeLimit=300, msg=True)

#solver = pulp.getSolver('HiGHS', timeLimit=300, gapRel=0.05, msg=True)

model.solve(solver)
#model.solve(pulp.PULP_CBC_CMD(msg=False))
end_time = time.perf_counter()
elapsed_seconds = end_time - start_time

status_code = model.status
status_string = pulp.LpStatus[status_code]
print(f"Status do Modelo: {status_string}")
print(f"Tempo de resolução (s): {elapsed_seconds:.3f}")

""" if status_string != "Optimal":
    print("\nO modelo NÃO ENCONTROU uma solução ótima. O problema é INVIÁVEL (Infeasible).")
else:
    print(f"Valor da Função Objetivo: {pulp.value(model.objective):.2f}") """

if status_string != "Optimal" and status_string != "Feasible": # HiGHS pode retornar Feasible com Gap
    print("\nO modelo NÃO ENCONTROU uma solução viável.")
else:
    print(f"Valor da Função Objetivo: {pulp.value(model.objective):.2f}")


# ==============================
# 6. Exportar solução em JSON
# ==============================

if status_string == "Optimal" or status_string == "Feasible":
    solution = []
    for i in pessoas:
        for j in tarefas:
            for o in ocorrencias[j]:
                for t in range(total_slots):
                    if pulp.value(x[i][j][o][t]) > 0.99:
                        # Cálculos de tempo
                        slots_por_dia = (24 * 60) // duracao_slot
                        inicio_slot = t
                        fim_slot = t + duracao_tarefas[j]

                        dia_inicio = (inicio_slot // slots_por_dia) + 1
                        slot_no_dia_inicio = inicio_slot % slots_por_dia
                        minutos_inicio = slot_no_dia_inicio * duracao_slot
                        hora_inicio = f"{minutos_inicio // 60:02d}:{minutos_inicio % 60:02d}"

                        dia_fim = (fim_slot // slots_por_dia) + 1
                        slot_no_dia_fim = fim_slot % slots_por_dia
                        minutos_fim = slot_no_dia_fim * duracao_slot
                        hora_fim = f"{minutos_fim // 60:02d}:{minutos_fim % 60:02d}"

                        solution.append({
                            "dia_inicio": dia_inicio,
                            "hora_inicio": hora_inicio,
                            "hora_fim": hora_fim,
                            "pessoa": i,
                            "tarefa": j,
                            "ocorrencia": o,
                            "inicio_slot": inicio_slot, # mantido para ordenação
                            "fim_slot": fim_slot
                        })

    # Ordena por tempo global
    solution = sorted(solution, key=lambda x: x["inicio_slot"])
    
    # Cria DataFrame
    df = pd.DataFrame(solution)

    # ---------------------------------------------------------
    # IMPRESSÃO TABULAR NO TERMINAL (SEPARADA POR DIA)
    # ---------------------------------------------------------
    colunas_visuais = ['hora_inicio', 'hora_fim', 'pessoa', 'tarefa', 'ocorrencia']
    
    print("\n" + "="*50)
    print("           CRONOGRAMA DETALHADO")
    print("="*50)

    dias_unicos = sorted(df['dia_inicio'].unique())

    for dia in dias_unicos:
        print(f"\n>>> DIA {dia}")
        df_dia = df[df['dia_inicio'] == dia][colunas_visuais]
        
        if HAS_TABULATE:
            # Opções de tablefmt: 'psql', 'grid', 'simple', 'github'
            print(tabulate(df_dia, headers='keys', tablefmt='psql', showindex=False))
        else:
            print(df_dia.to_string(index=False))

    # ---------------------------------------------------------
    # EXPORTAÇÃO CSV
    # ---------------------------------------------------------
    now = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    file = f"solucao_cuidados_{now}_alpha_{alpha}.csv"
    # df.to_csv(file, index=False, encoding="utf-8")
    # print(f"\nSolução salva em {file}.")

else:
    print("\nNenhuma solução viável foi encontrada para exportar.")

'''if status_string == "Optimal":
    solution = []
    for i in pessoas:
        for j in tarefas:
            for o in ocorrencias[j]:
                for t in range(total_slots):
                    if pulp.value(x[i][j][o][t]) > 0.99:
                        # calcula dia e horário legíveis para início e fim
                        slots_por_dia = (24 * 60) // duracao_slot
                        inicio_slot = t
                        fim_slot = t + duracao_tarefas[j]

                        dia_inicio = (inicio_slot // slots_por_dia) + 1  # 1-based (1 = segunda, 2 = terça, ...)
                        slot_no_dia_inicio = inicio_slot % slots_por_dia
                        minutos_inicio = slot_no_dia_inicio * duracao_slot
                        hora_inicio = f"{minutos_inicio // 60:02d}:{minutos_inicio % 60:02d}"

                        dia_fim = (fim_slot // slots_por_dia) + 1
                        slot_no_dia_fim = fim_slot % slots_por_dia
                        minutos_fim = slot_no_dia_fim * duracao_slot
                        hora_fim = f"{minutos_fim // 60:02d}:{minutos_fim % 60:02d}"

                        solution.append({
                            "pessoa": i,
                            "tarefa": j,
                            "ocorrencia": o,
                            "inicio_slot": inicio_slot,
                            "fim_slot": fim_slot,
                            "dia_inicio": dia_inicio,
                            "hora_inicio": hora_inicio,
                            "dia_fim": dia_fim,
                            "hora_fim": hora_fim,
                        })

    # Ordena por tempo
    solution = sorted(solution, key=lambda x: x["inicio_slot"])

    print("\nSOLUÇÃO ENCONTRADA")
    print(json.dumps(solution, indent=2))


    # Cria DataFrame
    df = pd.DataFrame(solution)
    now = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    file = f"solucao_cuidados_{now}_alpha_{alpha}.csv"
    # Salva em CSV
#    df.to_csv(file, index=False, encoding="utf-8")
    print()
    print(f"Solução salva em {file}.")
else:
    print("\nNenhuma solução viável foi encontrada para exportar.")'''

