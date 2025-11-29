import json
import math

def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def dur_slots(mins, slot):
    return mins // slot

def main():
    data = load('input_semanal_1dia.json')
    slot = data['slot_duration_min']
    days = data['days']
    slots_per_day = (24*60)//slot
    total_slots = slots_per_day * days

    print(f"Slots por dia: {slots_per_day}, dias: {days}, total_slots: {total_slots}")

    # 1 - carga total das tarefas do bebê
    baby_tasks = {k:v for k,v in data['tasks'].items() if v.get('type')=='bebe'}
    total_baby_slots = 0
    for name,t in baby_tasks.items():
        s = dur_slots(t['duration'], slot) * t['occurrences']
        print(f"Tarefa {name}: dur_slots={dur_slots(t['duration'], slot)}, occ={t['occurrences']}, total={s}")
        total_baby_slots += s
    print(f"Total slots exigidos (tarefas do bebê): {total_baby_slots}")

    # 2 - periodicity span check
    if 'periodicity' in data:
        for tname, period in data['periodicity'].items():
            p_slots = math.ceil(period/slot)
            occ = data['tasks'][tname]['occurrences']
            span = (occ-1)*p_slots
            last_start_allowed = total_slots - dur_slots(data['tasks'][tname]['duration'], slot)
            earliest_start_max = last_start_allowed - span
            print(f"Periodicidade {tname}: period_slots={p_slots}, occ={occ}, span={span}, earliest_start_max={earliest_start_max}")
            if earliest_start_max < 0:
                print(f"  -> INVIÁVEL: periodicidade de {tname} ocupa mais do que o horizonte disponível.")

    # 3 - dependências (window 0 suspicious)
    if 'dependencies' in data:
        for a,b in data['dependencies'].items():
            w = b.get('window',0)
            if w == 0:
                print(f"Atenção: dependencia '{a}' -> '{b['next']}' tem window=0 (início imediato). Isso é muito restritivo.")

    # 4 - disponibilidade coverage (quantos slots estão com pelo menos 1 pessoa disponível)
    avail = data.get('availability_binaria')
    if avail is None:
        print('Availability binária não encontrada (execute preprocessamento.carregar_dados primeiro).')
    else:
        # soma por slot
        slot_cover = [0]*total_slots
        for p,vec in avail.items():
            for i,v in enumerate(vec):
                if v:
                    slot_cover[i]+=1
        min_cover = min(slot_cover)
        avg_cover = sum(slot_cover)/len(slot_cover)
        zero_slots = sum(1 for x in slot_cover if x==0)
        print(f"Cobertura de disponibilidade: min={min_cover}, avg={avg_cover:.2f}, slots_sem_ninguem={zero_slots}")

    # 5 - heurística de clash: soma de todas durações (todas tarefas) vs slots
    total_all_slots = 0
    for name,t in data['tasks'].items():
        total_all_slots += dur_slots(t['duration'], slot) * t['occurrences']
    print(f"Total slots exigidos (todas tarefas): {total_all_slots}")
    if total_all_slots > total_slots:
        print("-> INVIÁVEL: a soma das durações de todas as tarefas excede o horizonte de tempo disponível.")

if __name__ == '__main__':
    main()
