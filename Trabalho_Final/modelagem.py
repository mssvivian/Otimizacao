import json
import pulp
import pandas as pd


# ==============================
# 1. Leitura do arquivo JSON
# ==============================
with open("input.json", "r") as f:
    data = json.load(f)

# Renomeando as variáveis de conjuntos/índices para corresponderem ao LaTeX
Pessoas = data["people"] # i
Tarefas = list(data["tasks"].keys()) # j
Slots = data["slots"] # t (slots de tempo: 0 a S-1)
Duration_per_slot = data["slot_duration_min"]

# Parâmetros
D = {j: data["tasks"][j]["duration"]//Duration_per_slot for j in Tarefas} # d_j (duração)
O = {j: range(data["tasks"][j]["occurrences"]) for j in Tarefas} # o (ocorrências)
A = {i: data["availability"][i] for i in Pessoas} # A_i,t (disponibilidade)
C = data["capacity"] # c_i,j (capacidade/aptidão)
Dependencies = data.get("dependencies", {})
Load_Limit = {i: (data["load_limit"][i]*60)//Duration_per_slot for i in Pessoas}  # L_i (limite de carga - assumindo que existe)

# ==============================
# 2. Criação do modelo
# ==============================
model = pulp.LpProblem("Alocacao_Cuidados_Bebe", pulp.LpMinimize)

# Variáveis de decisão: x[i][j][o][t] = 1 se pessoa i inicia tarefa j, ocorrência o no slot t
x = {}
for i in Pessoas:
    x[i] = {}
    for j in Tarefas:
        x[i][j] = {}
        for o in O[j]:
            x[i][j][o] = {}
            for t in range(Slots):
                # Usando o nome da variável do LaTeX na LPVariable
                x[i][j][o][t] = pulp.LpVariable(f"x_{i}_{j}_{o}_{t}", cat="Binary")

# Proibir inícios inválidos: se t + D[j] > Slots então x[...] == 0
for i in Pessoas:
    for j in Tarefas:
        dur = D[j]
        last_start = Slots - dur  # último slot válido para iniciar j
        for o in O[j]:
            for t in range(Slots):
                if t > last_start:
                    model += x[i][j][o][t] == 0

# ==============================
# 3. Função Objetivo
# ==============================
# Minimiza a soma ponderada pela "incapacidade" (1 - c_i,j)
model += pulp.lpSum(
    (1 - C[i][j]) * x[i][j][o][t]
    for i in Pessoas
    for j in Tarefas
    for o in O[j]
    for t in range(Slots)
)

# ==============================
# 4. Restrições
# ==============================

# 4.1 Cada ocorrência de tarefa deve ser realizada exatamente uma vez
for j in Tarefas:
    for o in O[j]:
        model += pulp.lpSum(x[i][j][o][t] for i in Pessoas for t in range(Slots)) == 1

# 4.2 Não sobreposição de tarefas por pessoa
for i in Pessoas:
    for t in range(Slots):
        # A soma considera todas as tarefas j que iniciaram em t' e estão ativas no slot t.
        model += (
            pulp.lpSum(
                x[i][j][o][t_start]
                for j in Tarefas
                for o in O[j]
                for t_start in range(max(0, t - D[j] + 1), t + 1)
            )
            <= 1
        )


# 4.3 Restrição Global de Não Sobreposição (Ocupação do Bebê)
for t in range(Slots):
    expr = []
    for i in Pessoas:
        for j in Tarefas:
            dur = D[j]
            # t_start varia de t - dur + 1 até t (inícios que cobrem o slot t)
            t_start_min = max(0, t - dur + 1)
            t_start_max = min(t, Slots - dur) 
            for o in O[j]:
                for t_start in range(t_start_min, t_start_max + 1):
                    expr.append(x[i][j][o][t_start])
    model += pulp.lpSum(expr) <= 1


# 4.4 Respeitar disponibilidade
for i in Pessoas:
    for j in Tarefas:
        for o in O[j]:
            for t in range(Slots):
                if A[i][t] == 0:
                    model += x[i][j][o][t] == 0 # x_i,j,o,t <= A_i,t (Restrição do LaTeX)

# 4.5 Precedência 
for j1_id in Dependencies:                   # e.g. "amamentar"
    j2_id = Dependencies[j1_id]["next"]      # e.g. "arrotar"
    W = Dependencies[j1_id]["window"]        # largura da janela em slots
    
    # Assumimos que a precedência é entre a ocorrência o de j1 e a ocorrência o de j2
    for o in O[j1_id]: 
        for t2 in range(Slots):                  # t2 = possível início de j2 (tarefa 2)
            
            # calcular intervalo permitido para t1 (início de j1) que permita j2 começar em t2
            d_j1 = D[j1_id]
            t1_min = max(0, t2 - d_j1 - W)
            t1_max = min(t2 - d_j1, Slots - d_j1)
            
            # Se não há t1 válido, então j2 não pode começar em t2
            if t1_min > t1_max:
                for i2 in Pessoas:
                    model += x[i2][j2_id][o][t2] == 0 
                continue

            # LHS: Soma de todos os possíveis inícios t1 e pessoas i1 que representam um j1 que termina a tempo
            lhs = []
            for i1 in Pessoas:
                for t1 in range(t1_min, t1_max + 1):
                    lhs.append(x[i1][j1_id][o][t1])

            # Restrição: x[i2,j2,o,t2] <= sum_{i1,t1 in window} x[i1,j1,o,t1]  para todo i2
            for i2 in Pessoas:
                model += pulp.lpSum(lhs) >= x[i2][j2_id][o][t2]

# 4.6 Restrição de periodicidade (tarefas recorrentes)
if "periodicity" in data:
    for j, P_j in data["periodicity"].items():
        dur = D[j]
        last_start = Slots - dur
        for o in range(len(O[j]) - 1):
            for t1 in range(0, last_start + 1):
                t2 = t1 + P_j
                if t2 <= last_start:
                    # Se ocorrência 'o' começa em t1, a ocorrência 'o+1' deve começar em t2
                    model += pulp.lpSum(x[i][j][o][t1] for i in Pessoas) == \
                             pulp.lpSum(x[i][j][o+1][t2] for i in Pessoas)
                else:
                    # Se t2 excede last_start, t1 não é um início válido para a ocorrência 'o'
                    model += pulp.lpSum(x[i][j][o][t1] for i in Pessoas) == 0

# 4.7 Limite de carga de trabalho
if Load_Limit:
    for i in Pessoas:
        L_i = Load_Limit[i]
        model += pulp.lpSum(
            D[j] * x[i][j][o][t] 
            for j in Tarefas
            for o in O[j]
            for t in range(Slots)
        ) <= L_i

# ==============================
# 5. Resolver modelo
# ==============================
model.solve(pulp.PULP_CBC_CMD(msg=False))

# ==============================
# 6. Exportar solução em JSON
# ==============================
solution = []
for i in Pessoas:
    for j in Tarefas:
        for o in O[j]:
            for t in range(Slots):
                if pulp.value(x[i][j][o][t]) == 1:
                    solution.append({
                        "pessoa": i,
                        "tarefa": j,
                        "ocorrencia": o,
                        "inicio_slot": t,
                        "fim_slot": t + D[j]
                    })

# Ordena por tempo
solution = sorted(solution, key=lambda x: x["inicio_slot"])

print(json.dumps(solution, indent=2))


# Cria DataFrame
df = pd.DataFrame(solution)

# Salva em CSV
df.to_csv("solucao_cuidados.csv", index=False, encoding="utf-8")
#df.to_excel("solucao_cuidados.xlsx", index=False)