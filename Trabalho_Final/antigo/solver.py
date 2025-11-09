import json
import pulp
import pandas as pd


# ==============================
# 1. Leitura do arquivo JSON
# ==============================
with open("input.json", "r") as f:
    data = json.load(f)

P = data["people"]
T = list(data["tasks"].keys())
K = data["slots"]

# Parâmetros
L = {t: data["tasks"][t]["duration"] for t in T}
I = {t: range(data["tasks"][t]["occurrences"]) for t in T}
A = {p: data["availability"][p] for p in P}
C = data["capacity"]
D = data.get("dependencies", {})

# ==============================
# 2. Criação do modelo
# ==============================
model = pulp.LpProblem("Alocacao_Cuidados_Bebe", pulp.LpMinimize)

# Variáveis de decisão: y[p][t][i][s] = 1 se p inicia tarefa t,i no slot s
y = {}
for p in P:
    y[p] = {}
    for t in T:
        y[p][t] = {}
        for i in range(data["tasks"][t]["occurrences"]):
            y[p][t][i] = {}
            for s in range(K):
                y[p][t][i][s] = pulp.LpVariable(f"y_{p}_{t}_{i}_{s}", cat="Binary")

# Proibir inícios inválidos: se s + L[t] > K então y[...] == 0
for p in P:
    for t in T:
        dur = L[t]
        last_start = K - dur  # último slot válido para iniciar t
        for i in I[t]:
            for s in range(K):
                if s > last_start:
                    model += y[p][t][i][s] == 0

# ==============================
# 3. Função Objetivo
# ==============================
# Minimiza a soma ponderada pela "incapacidade" (1 - C[p][t])
model += pulp.lpSum(
    (1 - C[p][t]) * y[p][t][i][s]
    for p in P
    for t in T
    for i in I[t]
    for s in range(K)
)

# ==============================
# 4. Restrições
# ==============================

# Restrição global: no máximo 1 tarefa ocupando o bebê por slot s
for s in range(K):
    # somamos todas as tarefas que cobrem o slot s (inícios s' tal que s' <= s < s' + L[t])
    expr = []
    for p in P:
        for t in T:
            dur = L[t]
            # s' varia de s - dur + 1 até s (inícios que cobrem o slot s)
            s_start_min = max(0, s - dur + 1)
            s_start_max = min(s, K - dur)  # início não pode ultrapassar last_start
            for i in I[t]:
                for s_start in range(s_start_min, s_start_max + 1):
                    expr.append(y[p][t][i][s_start])
    model += pulp.lpSum(expr) <= 1


# 4.1 Cada ocorrência de tarefa deve ser realizada exatamente uma vez
for t in T:
    for i in I[t]:
        model += pulp.lpSum(y[p][t][i][s] for p in P for s in range(K)) == 1

# 4.2 Pessoa não pode fazer duas tarefas simultaneamente
for p in P:
    for s in range(K):
        model += (
            pulp.lpSum(
                y[p][t][i][s2]
                for t in T
                for i in I[t]
                for s2 in range(max(0, s - L[t] + 1), s + 1)
                if s2 + L[t] > s
            )
            <= 1
        )

# 4.3 Respeitar disponibilidade
for p in P:
    for t in T:
        for i in I[t]:
            for s in range(K):
                if A[p][s] == 0:
                    model += y[p][t][i][s] == 0

# 4.4 Precedência corrigida (amamentar -> arrotar dentro de janela W)
for t1 in D:                               # e.g. "amamentar"
    t2 = D[t1]["next"]                     # e.g. "arrotar"
    W = D[t1]["window"]                    # largura da janela em slots
    # número de ocorrências: se t1 e t2 têm contagens diferentes, decidir qual mapping usar.
    # aqui assumimos que I[t1] e I[t2] têm mesmo tamanho e o índice i corresponde
    for i in I[t1]:
        for s2 in range(K):                # s2 = possível início de t2 (arroto)
            # calcular intervalo permitido para s1 (início de t1) que permitam t2 começar em s2
            s1_min = max(0, s2 - L[t1] - W)
            s1_max = min(s2 - L[t1], K - L[t1])  # inclusive
            # se não há s1 válido, então não permitimos qualquer início de t2 em s2
            if s1_min > s1_max:
                # força que nenhum p2 pode iniciar t2 em s2 (porque não é possível haver t1 antes)
                for p2 in P:
                    for p2_flag in range(1):  # só para criar a restrição uma vez por p2,s2,i
                        model += pulp.lpSum([]) >= pulp.lpSum(y[p2][t2][i][s2] for _ in [0])  # 0 >= y -> forces 0
                continue

            # soma de todos os possíveis inícios s1 e pessoas p1 que representam um t1 que termina
            lhs = []
            for p1 in P:
                for s1 in range(s1_min, s1_max + 1):
                    lhs.append(y[p1][t1][i][s1])

            # garantir: y[p2,t2,i,s2] <= sum_{p1,s1 in window} y[p1,t1,i,s1]  for todo p2
            for p2 in P:
                model += pulp.lpSum(lhs) >= y[p2][t2][i][s2]

# 4.5 Restrição de periodicidade (tarefas recorrentes)
if "periodicity" in data:
    for t, P_t in data["periodicity"].items():
        dur = L[t]
        last_start = K - dur
        for i in range(data["tasks"][t]["occurrences"] - 1):
            # considere apenas s1 que são possíveis starts válidos
            for s1 in range(0, last_start + 1):
                s2 = s1 + P_t
                # também exige que s2 seja um início válido para a  ocorrencia i+1
                if s2 <= last_start:
                    model += pulp.lpSum(y[p][t][i][s1] for p in P) == \
                             pulp.lpSum(y[p][t][i+1][s2] for p in P)
                # se s2 excede last_start, então não é possível ter s1 ali -> elimine s1
                else:
                    # força que nenhum p inicie i em s1 (pois não há espaço para i+1)
                    model += pulp.lpSum(y[p][t][i][s1] for p in P) == 0


# ==============================
# 5. Resolver modelo
# ==============================
model.solve(pulp.PULP_CBC_CMD(msg=False))

# ==============================
# 6. Exportar solução em JSON
# ==============================
solution = []
for p in P:
    for t in T:
        for i in I[t]:
            for s in range(K):
                if pulp.value(y[p][t][i][s]) == 1:
                    solution.append({
                        "pessoa": p,
                        "tarefa": t,
                        "ocorrencia": i,
                        "inicio_slot": s,
                        "fim_slot": s + L[t]
                    })

# Ordena por tempo
solution = sorted(solution, key=lambda x: x["inicio_slot"])

print(json.dumps(solution, indent=2))


# Cria DataFrame
df = pd.DataFrame(solution)

# Salva em CSV
df.to_csv("solucao_cuidados.csv", index=False, encoding="utf-8")
#df.to_excel("solucao_cuidados.xlsx", index=False)