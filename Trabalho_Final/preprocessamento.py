import json

# Constantes que NÃO dependem dos dados (dias da semana)
# Estas são as únicas que restam no escopo global.
MAPA_DIAS = {
    "seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6
}
DIAS_SEMANA = list(MAPA_DIAS.keys())


def _time_para_slot(hora_str, slots_por_dia, slot_duration):
    """
    (Função interna) Converte 'HH:MM' para um índice de slot.
    Agora recebe 'slots_por_dia' e 'slot_duration' como argumentos.
    """
    if hora_str == "24:00":
        return slots_por_dia  # Usa o argumento
    try:
        horas, minutos = map(int, hora_str.split(':'))
        total_minutos = horas * 60 + minutos
        return total_minutos // slot_duration  # Usa o argumento
    except ValueError:
        print(f"Erro: Formato de hora inválido '{hora_str}'. Use 'HH:MM'.")
        return 0

def _processar_disponibilidade(availability_rules, total_slots, slots_por_dia, slot_duration):
    """
    (Função interna) Converte regras em vetores binários.
    Agora recebe todas as constantes de tempo como argumentos.
    """
    disponibilidade_final = {}

    for pessoa, regras in availability_rules.items():
        # Usa o argumento 'total_slots'
        vetor_pessoa = [0] * total_slots

        for regra in regras:
            
            dias_para_aplicar = []
            
            if regra["dia"] == "todos":
                dias_para_aplicar = DIAS_SEMANA
            else:
                dias_para_aplicar = [regra["dia"]]
                
            # Passa os argumentos para a função interna
            slot_inicio_dia = _time_para_slot(
                regra["inicio"], slots_por_dia, slot_duration
            )
            slot_fim_dia = _time_para_slot(
                regra["fim"], slots_por_dia, slot_duration
            )
            
            for nome_dia in dias_para_aplicar:
                if nome_dia not in MAPA_DIAS:
                    print(f"Aviso: Dia '{nome_dia}' inválido para '{pessoa}'. Pulando regra.")
                    continue
                    
                indice_dia = MAPA_DIAS[nome_dia]
                # Usa o argumento 'slots_por_dia'
                offset_dia = indice_dia * slots_por_dia
                
                for i in range(slot_inicio_dia, slot_fim_dia):
                    indice_global = offset_dia + i
                    # Usa o argumento 'total_slots'
                    if indice_global < total_slots: 
                        vetor_pessoa[indice_global] = 1
                        
        disponibilidade_final[pessoa] = vetor_pessoa
        
    return disponibilidade_final

def carregar_dados(caminho_arquivo):
    """
    Função principal. Carrega o JSON, lê as constantes de tempo,
    e processa as regras de disponibilidade.
    """
    print(f"Carregando dados de '{caminho_arquivo}'...")
    
    # 1. Carrega o JSON inteiro
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except FileNotFoundError:
        print(f"Erro: Arquivo '{caminho_arquivo}' não encontrado.")
        return None
    except json.JSONDecodeError:
        print(f"Erro: Arquivo '{caminho_arquivo}' não é um JSON válido.")
        return None

    # 2. LÊ AS CONSTANTES DO JSON
    try:
        slot_duration = dados['slot_duration_min']
        total_slots = dados['slots']
        availability_rules = dados["availability"]
    except KeyError as e:
        print(f"Erro: Chave obrigatória {e} não encontrada no JSON.")
        return None

    # 3. CALCULA CONSTANTES DERIVADAS
    if slot_duration <= 0:
        print("Erro: 'slot_duration_min' deve ser um valor positivo.")
        return None
        
    # Assume 7 dias na semana.
    slots_por_dia = total_slots // 7
    
    # Adiciona uma verificação de sanidade para ajudar a depurar
    slots_dia_calculado = (24 * 60) // slot_duration
    if slots_por_dia != slots_dia_calculado:
        print("="*30)
        print("Aviso de Inconsistência de Dados:")
        print(f"  'total_slots' ({total_slots}) implica {slots_por_dia} slots/dia.")
        print(f"  'slot_duration_min' ({slot_duration}) implica {slots_dia_calculado} slots/dia.")
        print("  Os valores no seu JSON não são consistentes!")
        print(f"  Continuando com {slots_por_dia} slots/dia (baseado no total_slots).")
        print("="*30)
    
    # 4. CHAMA A FUNÇÃO DE PROCESSAMENTO COM AS CONSTANTES
    vetores_binarios = _processar_disponibilidade(
        availability_rules, 
        total_slots, 
        slots_por_dia, 
        slot_duration
    )
    
    # 5. Adiciona os vetores binários de volta ao dicionário principal
    dados["availability_binaria"] = vetores_binarios
    
    print("Dados carregados e processados com sucesso!")
    return dados