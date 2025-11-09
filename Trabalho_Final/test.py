import json
import pulp
import pandas as pd
import preprocessamento

# ==============================
# 1. Leitura E PRÉ-PROCESSAMENTO
# ==============================

data = preprocessamento.carregar_dados("input_semanal.json")

if data is None:
    print("Erro fatal: Falha ao carregar ou processar os dados. Encerrando.")
    exit()

# ==============================
# 1. Leitura do arquivo JSON
# ==============================
#with open("input.json", "r") as f:
    #data = json.load(f)

# Renomeando as variáveis de conjuntos/índices para corresponderem ao LaTeX
Pessoas = data["people"] # i
Tarefas = list(data["tasks"].keys()) # j (Conjunto D)
Slots = data["slots"] # t (slots de tempo: 0 a S-1)
Duration_per_slot = data["slot_duration_min"]

### --- NOVO: Identifica os subconjuntos de tarefas --- ###
# Assume que o input.json tem "type": "bebe" nas tarefas relevantes
Tarefas_Bebe = [j for j, task_data in data["tasks"].items() if task_data.get("type") == "bebe"]
# Tarefas_Casa não é necessária para as restrições, pois D (Tarefas) já é usado na Restrição 4.2
print(Tarefas_Bebe)

# Parâmetros
D = {j: data["tasks"][j]["duration"]//Duration_per_slot for j in Tarefas} # d_j (duração)
O = {j: range(data["tasks"][j]["occurrences"]) for j in Tarefas} # o (ocorrências)
#A = {i: data["availability"][i] for i in Pessoas} # A_i,t (disponibilidade)
A = data["availability_binaria"]
C = data["capacity"] # c_i,j (capacidade/aptidão)
Dependencies = data.get("dependencies", {})

###  Carregamento robusto do Limite de Carga (Horas -> Slots) ##
load_limit_hours = data.get("load_limit", {})
if Duration_per_slot > 0:
    Load_Limit = {i: int((limit_in_hours * 60) / Duration_per_slot) 
                  for i, limit_in_hours in load_limit_hours.items()}
else:
    Load_Limit = {} # Dicionário vazio se a duração do slot for 0
    print("Aviso: 'slot_duration_min' é 0. O Limite de Carga (Load_Limit) não será aplicado.")

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
    for j in Tarefas # O objetivo ainda considera TODAS as tarefas (j in D)
    for o in O[j]
    for t in range(Slots)
)

# ==============================
# 4. Restrições
# ==============================

# 4.1 Cada ocorrência de tarefa deve ser realizada exatamente uma vez
for j in Tarefas: # j in D
    for o in O[j]:
        model += pulp.lpSum(x[i][j][o][t] for i in Pessoas for t in range(Slots)) == 1

# 4.2 Não sobreposição de tarefas por pessoa
for i in Pessoas:
    for t in range(Slots):
        # A soma considera TODAS as tarefas (j in D), conforme o LaTeX
        model += (
            pulp.lpSum(
                x[i][j][o][t_start]
                for j in Tarefas # j in D
                for o in O[j]
                for t_start in range(max(0, t - D[j] + 1), t + 1)
            )
            <= 1
        )


### --- 4.3 Restrição Global (Apenas Tarefas do Bebê) --- ###
# Conforme Restrição 3 do LaTeX, a soma é apenas para j in D_B
for t in range(Slots):
    expr = []
    for i in Pessoas:
        # Itera apenas sobre as tarefas do bebê (j in D_B)
        for j in Tarefas_Bebe: 
            dur = D[j]
            t_start_min = max(0, t - dur + 1)
            t_start_max = min(t, Slots - dur) 
            for o in O[j]:
                for t_start in range(t_start_min, t_start_max + 1):
                    expr.append(x[i][j][o][t_start])
    model += pulp.lpSum(expr) <= 1


# 4.4 Respeitar disponibilidade
for i in Pessoas:
    for j in Tarefas: # j in D
        for o in O[j]:
            for t in range(Slots):
                if A[i][t] == 0:
                    model += x[i][j][o][t] == 0 

# 4.5 Precedência 
for j1_id in Dependencies: 
    j2_id = Dependencies[j1_id]["next"] 
    W = Dependencies[j1_id]["window"] 
    
    for o in O[j1_id]: 
        for t2 in range(Slots): 
            d_j1 = D[j1_id]
            t1_min = max(0, t2 - d_j1 - W)
            t1_max = min(t2 - d_j1, Slots - d_j1) # Versão corrigida da lógica de precedência
            
            if t1_min > t1_max:
                for i2 in Pessoas:
                    model += x[i2][j2_id][o][t2] == 0 
                continue

            lhs = []
            for i1 in Pessoas:
                for t1 in range(t1_min, t1_max + 1):
                    lhs.append(x[i1][j1_id][o][t1])

            for i2 in Pessoas:
                model += pulp.lpSum(lhs) >= x[i2][j2_id][o][t2]

# 4.6 Restrição de periodicidade (tarefas recorrentes)
if "periodicity" in data:
    for j, P_j in data["periodicity"].items(): # j in D
        dur = D[j]
        last_start = Slots - dur
        for o in range(len(O[j]) - 1):
            for t1 in range(0, last_start + 1):
                t2 = t1 + P_j
                if t2 <= last_start:
                    model += pulp.lpSum(x[i][j][o][t1] for i in Pessoas) == \
                             pulp.lpSum(x[i][j][o+1][t2] for i in Pessoas)
                else:
                    model += pulp.lpSum(x[i][j][o][t1] for i in Pessoas) == 0

# 4.7 Limite de carga de trabalho
if Load_Limit:
    for i in Pessoas:
        # Verifica se a pessoa 'i' tem um limite definido no dicionário
        if i in Load_Limit: 
            L_i = Load_Limit[i]
            model += pulp.lpSum(
                D[j] * x[i][j][o][t] 
                for j in Tarefas # j in D
                for o in O[j]
                for t in range(Slots)
            ) <= L_i

# ==============================
# 5. Resolver modelo E DIAGNÓSTICO
# ==============================
model.solve(pulp.PULP_CBC_CMD(msg=False))

# --- Diagnóstico Adicionado ---
status_code = model.status
status_string = pulp.LpStatus[status_code]
print(f"\n--- DIAGNÓSTICO DA SOLUÇÃO ---")
print(f"Status do Modelo: {status_string}")

if status_string != "Optimal":
    print("\nO modelo NÃO ENCONTROU uma solução ótima. O problema é provavelmente INVIÁVEL (Infeasible).")
    print("Verifique os parâmetros no seu arquivo 'input.json', especialmente:")
    print("1. O número de ocorrências e a duração das tarefas vs. o total de Slots.")
    print("2. A restrição de Disponibilidade (A[i][t]) vs. as necessidades das tarefas (4.4).")
    print("3. As janelas de Precedência (W) e Periodicidade (P_j), que podem ser muito restritivas (4.5 e 4.6).")
else:
    print(f"Valor da Função Objetivo: {pulp.value(model.objective):.2f}")
# ------------------------------


# ==============================
# 6. Exportar solução em JSON
# ==============================
if status_string == "Optimal":
    solution = []
    for i in Pessoas:
        for j in Tarefas:
            for o in O[j]:
                for t in range(Slots):
                    # Usamos uma pequena tolerância para verificar se a variável é 1
                    if pulp.value(x[i][j][o][t]) > 0.99:
                        solution.append({
                            "pessoa": i,
                            "tarefa": j,
                            "ocorrencia": o,
                            "inicio_slot": t,
                            "fim_slot": t + D[j]
                        })

    # Ordena por tempo
    solution = sorted(solution, key=lambda x: x["inicio_slot"])

    print("\n--- SOLUÇÃO ENCONTRADA ---")
    print(json.dumps(solution, indent=2))


    # Cria DataFrame
    df = pd.DataFrame(solution)
    now = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    file = f"solucao_cuidados_{now}.csv"
    # Salva em CSV
    df.to_csv(file, index=False, encoding="utf-8")
    print("\nSolução salva em 'solucao_cuidados.csv'.")
else:
    print("\nNenhuma solução viável foi encontrada para exportar.")