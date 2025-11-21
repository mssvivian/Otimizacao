import json

# Constantes que NÃO dependem dos dados (dias da semana)
MAPA_DIAS = {
    "seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6
}
DIAS_SEMANA = list(MAPA_DIAS.keys())


def _time_para_slot(hora_str, slots_por_dia, slot_duration):
    """
    (Função interna) Converte 'HH:MM' para um índice de slot.
    """
    if hora_str == "24:00":
        return slots_por_dia
    try:
        horas, minutos = map(int, hora_str.split(':'))
        total_minutos = horas * 60 + minutos
        return total_minutos // slot_duration
    except ValueError:
        print(f"Erro: Formato de hora inválido '{hora_str}'. Use 'HH:MM'.")
        return 0

def _processar_disponibilidade(availability_rules, total_slots, slots_por_dia, slot_duration):
    """
    (Função interna) Converte regras de disponibilidade (Pessoas) em vetores binários.
    """
    disponibilidade_final = {}

    for pessoa, regras in availability_rules.items():
        vetor_pessoa = [0] * total_slots

        for regra in regras:
            dias_para_aplicar = []
            
            if regra["dia"] == "todos":
                dias_para_aplicar = DIAS_SEMANA
            else:
                dias_para_aplicar = [regra["dia"]]
                
            slot_inicio_dia = _time_para_slot(regra["inicio"], slots_por_dia, slot_duration)
            slot_fim_dia = _time_para_slot(regra["fim"], slots_por_dia, slot_duration)
            
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

def _processar_janelas_tarefas(task_windows, tasks_data, total_slots, slots_por_dia, slot_duration, total_days):
    """
    Converte janelas de tempo das TAREFAS em vetores binários.
    Retorna um dicionário: { "tarefa": [1, 1, 0, 0, ...], "outra": [1, 1, 1...] }
    """
    # 1. Inicializa todas as tarefas como 100% disponíveis (vetor de uns)
    #    Isso garante que tarefas sem restrição no JSON funcionem normalmente.
    task_availability = {}
    for tarefa in tasks_data.keys():
        task_availability[tarefa] = [1] * total_slots

    # 2. Aplica as restrições para as tarefas listadas em task_windows
    for tarefa_nome, janelas in task_windows.items():
        if tarefa_nome not in tasks_data:
            print(f"Aviso: Janela definida para tarefa '{tarefa_nome}', mas ela não existe em 'tasks'.")
            continue
            
        # Se tem janela definida, começamos zerando a disponibilidade dela
        # para marcar APENAS os horários permitidos.
        task_availability[tarefa_nome] = [0] * total_slots
        
        # Calcula quantos slots a tarefa dura
        duration_slots = tasks_data[tarefa_nome]["duration"] // slot_duration
        
        for janela in janelas:
            start_t_day = _time_para_slot(janela["start"], slots_por_dia, slot_duration)
            end_t_day = _time_para_slot(janela["end"], slots_por_dia, slot_duration)
            
            # O último slot possível para INÍCIO é quando a tarefa ainda cabe na janela
            # Ex: Janela termina 12:00, tarefa dura 30min. Último inicio possível é 11:30.
            valid_start_limit = end_t_day - duration_slots
            
            # Aplica para todos os dias da semana (janela diária repetida)
            for dia in range(total_days):
                offset = dia * slots_por_dia
                
                s_min = offset + start_t_day
                s_max = offset + valid_start_limit
                
                # Preenche com 1 onde é permitido INICIAR
                for t in range(s_min, s_max):
                    if 0 <= t < total_slots:
                        task_availability[tarefa_nome][t] = 1
                        
    return task_availability

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
        slot_duration = dados['slot_duration_min']
        total_days = dados['days']
        total_slots = total_days * (24 * 60) // slot_duration
        
        availability_rules = dados["availability"]
        tasks_data = dados["tasks"]
        # Se não houver task_windows, usa dicionário vazio
        task_windows = dados.get("task_windows", {}) 
        
    except KeyError as e:
        print(f"Erro: Chave obrigatória {e} não encontrada no JSON.")
        return None

    # 3. VALIDAÇÕES
    if slot_duration <= 0:
        print("Erro: 'slot_duration_min' deve ser positivo.")
        return None
        
    slots_por_dia = (24 * 60) // slot_duration
    
    # 4. PROCESSA DISPONIBILIDADE DAS PESSOAS
    vetores_pessoas = _processar_disponibilidade(
        availability_rules, 
        total_slots, 
        slots_por_dia, 
        slot_duration
    )
    dados["availability_binaria"] = vetores_pessoas

    # 5. PROCESSA JANELAS DAS TAREFAS 
    print("Processando janelas de tarefas...")
    vetores_tarefas = _processar_janelas_tarefas(
        task_windows,
        tasks_data,
        total_slots,
        slots_por_dia,
        slot_duration,
        total_days
    )
    # Salva no dicionário principal
    dados["task_availability_binaria"] = vetores_tarefas
    
    print("Dados carregados e processados com sucesso!")
    return dados