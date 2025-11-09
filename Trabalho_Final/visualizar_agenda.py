import pandas as pd

def criar_planilha_agenda(arquivo_csv="solucao_cuidados.csv", arquivo_excel="agenda_semanal.xlsx"):
    """
    Lê o CSV da solução e o transforma em uma planilha de agenda (formato Excel).
    """
    print(f"Lendo '{arquivo_csv}' para gerar a agenda...")
    
    try:
        # --- 1. Ler a solução ---
        df_solucao = pd.read_csv(arquivo_csv)
    except FileNotFoundError:
        print(f"Erro: Arquivo '{arquivo_csv}' não encontrado.")
        return

    if df_solucao.empty:
        print("A solução está vazia. Nenhuma agenda para gerar.")
        return

    # --- 2. "Explodir" tarefas para preencher todos os slots ---
    # Transforma (inicio=0, fim=4) em (slot=0), (slot=1), (slot=2), (slot=3)
    agenda_data = []
    for _, row in df_solucao.iterrows():
        pessoa = row['pessoa']
        tarefa = row['tarefa']
        
        # O range vai do início até (fim - 1), o que é correto
        for slot_t in range(row['inicio_slot'], row['fim_slot']):
            agenda_data.append({
                "slot_id": slot_t,
                "pessoa": pessoa,
                "tarefa": tarefa
            })
    
    df_expanded = pd.DataFrame(agenda_data)

    # --- 3. Pivotar: Slots como linhas, Pessoas como colunas ---
    print("Montando a grade da agenda...")
    try:
        agenda_pivot = df_expanded.pivot_table(
            index="slot_id",    # As linhas serão os slots de tempo
            columns="pessoa",   # As colunas serão as pessoas
            values="tarefa",    # O conteúdo da célula será a tarefa
            aggfunc=", ".join   # Se houver sobreposição (não deveria), junta com vírgula
        )
    except Exception as e:
        print(f"Erro ao pivotar os dados: {e}")
        return

    # --- 4. Reindexar para incluir todos os slots (0 a 671) ---
    # Isso garante que mesmo os slots vazios (sem tarefas) apareçam na agenda.
    # Assumindo 672 slots (7 dias * 96 slots/dia) do seu JSON
    total_slots_esperado = 672 
    full_index = pd.Index(range(total_slots_esperado), name="slot_id")

    # Reindexa e preenche slots vazios (NaN) com uma string vazia ("")
    agenda_final = agenda_pivot.reindex(full_index).fillna("")

    # --- 5. (Opcional, mas recomendado) Converter índice de slot para Hora/Dia ---
    dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
    slots_por_dia = 96 # (24 * 60 / 15)

    novo_indice_legivel = []
    for slot in agenda_final.index:
        # Descobre o dia da semana (ex: slot 100 // 96 = dia 1 -> "Ter")
        dia_da_semana = dias[slot // slots_por_dia]
        
        # Descobre o slot dentro do dia (ex: 100 % 96 = slot 4)
        slot_no_dia = slot % slots_por_dia
        
        # Converte o slot do dia em minutos
        total_minutos_dia = slot_no_dia * 15
        
        # Converte minutos em Hora:Minuto
        hora = total_minutos_dia // 60
        minuto = total_minutos_dia % 60
        
        timestamp_str = f"{dia_da_semana} - {hora:02d}:{minuto:02d}"
        novo_indice_legivel.append(timestamp_str)
        
    agenda_final.index = pd.Index(novo_indice_legivel, name="Dia e Hora")

    # --- 6. Exportar para Excel ---
    try:
        agenda_final.to_excel(arquivo_excel)
        print(f"Sucesso! Agenda salva em '{arquivo_excel}'.")
    except Exception as e:
        print(f"Erro ao salvar o arquivo Excel: {e}")

# ===============================================
# Para usar este script
# ===============================================

# Se você adicionou isso ao seu main.py, chame a função
# logo após salvar o CSV (se a solução for ótima).
#
# if status_string == "Optimal":
#     # ... (seu código que salva o CSV) ...
#     criar_planilha_agenda() # <-- Chama a nova função
#

# Se este for um arquivo separado (ex: visualizar_agenda.py),
# apenas chame a função no final:
if __name__ == "__main__":
    criar_planilha_agenda(arquivo_csv="solucao_cuidados_20251109_094713.csv", arquivo_excel="agenda_semanal_20251109_094713.xlsx")