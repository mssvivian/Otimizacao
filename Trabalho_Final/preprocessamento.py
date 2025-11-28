import json

# Constantes que NÃO dependem dos dados (dias da semana)
MAPA_DIAS = {
    "seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6
}
DIAS_SEMANA = list(MAPA_DIAS.keys())


def _time_para_slot(hora_str, slots_por_dia, duracao_slot):
    """
    (Função interna) Converte 'HH:MM' para um índice de slot.
    """
    if hora_str == "24:00":
        return slots_por_dia
    try:
        horas, minutos = map(int, hora_str.split(':'))
        total_minutos = horas * 60 + minutos
        return total_minutos // duracao_slot
    except ValueError:
        print(f"Erro: Formato de hora inválido '{hora_str}'. Use 'HH:MM'.")
        return 0

def _processar_disponibilidade(regras_disponibilidade, total_slots, slots_por_dia, duracao_slot):
    """
    (Função interna) Converte regras de disponibilidade (pessoas) em vetores binários.
    Entrada:
      - regras_disponibilidade: dicionário com regras por pessoa (campo "availability" do JSON)
      - total_slots: número total de slots no horizonte
      - slots_por_dia: número de slots por dia
      - duracao_slot: duração de cada slot em minutos
    Retorna um dicionário { pessoa: [0/1, ...] } com comprimento total_slots.
    """
    disponibilidade_final = {}

    for pessoa, regras in regras_disponibilidade.items():
        vetor_pessoa = [0] * total_slots

        for regra in regras:
            dias_para_aplicar = []
            if regra["dia"] == "todos":
                dias_para_aplicar = DIAS_SEMANA
            else:
                dias_para_aplicar = [regra["dia"]]

            slot_inicio_dia = _time_para_slot(regra["inicio"], slots_por_dia, duracao_slot)
            slot_fim_dia = _time_para_slot(regra["fim"], slots_por_dia, duracao_slot)

            for nome_dia in dias_para_aplicar:
                if nome_dia not in MAPA_DIAS:
                    print(f"Aviso: Dia '{nome_dia}' inválido para '{pessoa}'. Pulando regra.")
                    continue

                indice_dia = MAPA_DIAS[nome_dia]
                offset_dia = indice_dia * slots_por_dia

                for i in range(slot_inicio_dia, slot_fim_dia):
                    indice_global = offset_dia + i
                    if indice_global < total_slots:
                        vetor_pessoa[indice_global] = 1

        disponibilidade_final[pessoa] = vetor_pessoa

    return disponibilidade_final

def _processar_janelas_tarefas(janelas_tarefas, dados_tarefas, total_slots, slots_por_dia, duracao_slot, total_dias):
    """
    Converte janelas de tempo das tarefas em vetores binários.
    Retorna um dicionário: { "tarefa": [1, 1, 0, 0, ...], ... }
    Parâmetros:
      - janelas_tarefas: dicionário com janelas (campo "horario_tarefas" do JSON)
      - dados_tarefas: dicionário com informações das tarefas (campo "tarefas")
      - total_slots, slots_por_dia, duracao_slot, total_dias: parâmetros de horizonte
    """
    # Inicializa todas as tarefas como 100% disponíveis (vetor de uns)
    disponibilidade_tarefas = {}
    for tarefa in dados_tarefas.keys():
        disponibilidade_tarefas[tarefa] = [1] * total_slots

    # Aplica as restrições definidas em janelas_tarefas
    for nome_tarefa, janelas in janelas_tarefas.items():
        if nome_tarefa not in dados_tarefas:
            print(f"Aviso: Janela definida para tarefa '{nome_tarefa}', mas ela não existe em 'tarefas'.")
            continue

        # Se tem janela definida, começamos zerando a disponibilidade e marcando apenas os inícios permitidos
        disponibilidade_tarefas[nome_tarefa] = [0] * total_slots

        # Quantos slots a tarefa dura
        duracao_em_slots = dados_tarefas[nome_tarefa]["duracao"] // duracao_slot

        for janela in janelas:
            inicio_no_dia = _time_para_slot(janela["inicio"], slots_por_dia, duracao_slot)
            fim_no_dia = _time_para_slot(janela["fim"], slots_por_dia, duracao_slot)

            # Último início válido para que a tarefa caiba na janela
            limite_inicio_valido = fim_no_dia - duracao_em_slots

            # Aplica para cada dia do horizonte (janelas repetidas diariamente)
            for dia in range(total_dias):
                offset = dia * slots_por_dia

                s_min = offset + inicio_no_dia
                s_max = offset + limite_inicio_valido

                # Marca como 1 os slots de início permitidos (note: s_max é exclusivo)
                for t in range(s_min, s_max):
                    if 0 <= t < total_slots:
                        disponibilidade_tarefas[nome_tarefa][t] = 1

    return disponibilidade_tarefas

def carregar_dados(caminho_arquivo):
    """
    Função principal. Carrega JSON, processa Pessoas e Tarefas.
    """
    print(f"Carregando dados de '{caminho_arquivo}'...")
    
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except FileNotFoundError:
        print(f"Erro: Arquivo '{caminho_arquivo}' não encontrado.")
        return None
    except json.JSONDecodeError:
        print(f"Erro: Arquivo '{caminho_arquivo}' não é um JSON válido.")
        return None

    # 2. LÊ AS CONSTANTES
    try:
        duracao_slot = dados['slot_duracao_min']
        total_dias = dados['dias']
        total_slots = total_dias * (24 * 60) // duracao_slot

        regras_disponibilidade = dados["disponibilidade_pessoas"]
        dados_tarefas = dados["tarefas"]
        janelas_tarefas = dados.get("disponibilidade_tarefas", {})

    except KeyError as e:
        print(f"Erro: Chave obrigatória {e} não encontrada no JSON.")
        return None

    # 3. VALIDAÇÕES
    if duracao_slot <= 0:
        print("Erro: 'slot_duration_min' deve ser positivo.")
        return None
        
    slots_por_dia = (24 * 60) // duracao_slot

    # 4. PROCESSA DISPONIBILIDADE DAS PESSOAS
    vetores_pessoas = _processar_disponibilidade(
        regras_disponibilidade,
        total_slots,
        slots_por_dia,
        duracao_slot,
    )
    dados["disponibilidade_pessoas_binaria"] = vetores_pessoas

    # 5. PROCESSA JANELAS DAS TAREFAS 
    print("Processando janelas de tarefas...")
    vetores_tarefas = _processar_janelas_tarefas(
        janelas_tarefas,
        dados_tarefas,
        total_slots,
        slots_por_dia,
        duracao_slot,
        total_dias,
    )
    # Salva no dicionário principal
    dados["disponibilidade_tarefas_binaria"] = vetores_tarefas
    
    print("Dados carregados e processados com sucesso!")
    return dados