import re
from datetime import datetime

class EdiParser:
    def __init__(self, content):
        self.raw_content = content
        self.clean_content = content.replace('\n', '').replace('\r', '')
        self.all_segments = self.clean_content.split("'")
        
        self.transactions = []
        
        print(f"[PARSER LOG] Initializing parser. Total segments found: {len(self.all_segments)}")
        self.parse_all()

    def parse_date(self, dtm_segment):
        try:
            parts = dtm_segment.split(':')
            if len(parts) < 2: return "Invalid Date"
            raw_date = parts[1]
            fmt_code = parts[2] if len(parts) > 2 else ''
            
            if fmt_code == '203': # YYYYMMDDHHMM
                dt = datetime.strptime(raw_date, '%Y%m%d%H%M')
                return dt.strftime('%d/%m/%Y %H:%M')
            elif fmt_code == '102': # YYYYMMDD
                dt = datetime.strptime(raw_date, '%Y%m%d')
                return dt.strftime('%d/%m/%Y')
            return raw_date
        except:
            return "Invalid Date"

    def parse_single_transaction(self, segments):
        """Processa um bloco único de segmentos (entre UNH e UNT)."""
        data = {
            "type": "UNKNOWN",
            "function": "Unknown",
            "container": "N/A",
            "iso_code": "N/A",
            "status": "N/A",
            "date": "N/A",
            "sender": "N/A",
            "receiver": "N/A",
            "weight": "N/A",
            "booking": "N/A",
            "seals": [],
            "transport": "N/A",
            "genset": "N/A",
            "remarks": []
        }

        for seg in segments:
            parts = seg.split('+')
            tag = parts[0]

            # UNH - Tipo da Mensagem
            if tag == 'UNH':
                if len(parts) > 2:
                    data['type'] = parts[2].split(':')[0]

            # BGM - Função
            elif tag == 'BGM':
                if len(parts) > 1:
                    func_code = parts[1]
                    if data['type'] == 'CODECO':
                        if func_code == '34': data['function'] = 'Gate In (Entrada)'
                        elif func_code == '36': data['function'] = 'Gate Out (Saída)'
                    elif data['type'] == 'COARRI':
                        if func_code == '46': data['function'] = 'Discharge (Descarga)'
                        elif func_code == '44': data['function'] = 'Load (Embarque)'
                        elif func_code == '98': data['function'] = 'Report (98)' # Adicionado
                    
                    if func_code == '270': data['function'] = 'Status Report (270)'

            # EQD - Container e Status
            elif tag == 'EQD':
                if len(parts) > 2: data['container'] = parts[2]
                if len(parts) > 3 and parts[3]: data['iso_code'] = parts[3].split(':')[0]
                if len(parts) >= 7:
                    st = parts[6]
                    if st == '4': data['status'] = 'Empty (Vazio)'
                    elif st == '5': data['status'] = 'Full (Cheio)'
                    else: data['status'] = st

            # DTM - Datas
            elif tag == 'DTM':
                if seg.startswith('DTM+132:') or seg.startswith('DTM+133:') or seg.startswith('DTM+203:') or seg.startswith('DTM+7:'):
                    if data['date'] == "N/A" or seg.startswith('DTM+203:'): 
                        data['date'] = self.parse_date(parts[1])

            # TDT Transporte e Navio
            elif tag == 'TDT':
                if len(parts) > 1:
                    mode = parts[1]
                    transport_name = ""
                    
                    last_part = parts[-1] 
                    if '::' in last_part:
                        transport_name = last_part.split('::')[-1]
                    elif ':' in last_part and len(last_part) > 3: # Formato :146:NOME
                         transport_name = last_part.split(':')[-1]
                    
                    if mode == '20': 
                        data['transport'] = f"Vessel: {transport_name}" if transport_name else "Vessel"
                    elif mode == '1':
                        truck = parts[5].split(':')[0] if len(parts) > 5 else ""
                        if not truck and len(parts) > 8: truck = parts[8].split(':')[0]
                        data['transport'] = f"Truck: {truck}" if truck else "Truck"
                    elif mode == '10':
                         data['transport'] = f"Vessel (Feeder): {transport_name}" if transport_name else "Vessel (Feeder)"

            # SEL - Lacres
            elif tag == 'SEL':
                if len(parts) > 1: data['seals'].append(parts[1])

            # FTX - Observações
            elif tag == 'FTX':
                if len(parts) > 4: data['remarks'].append(parts[4])

            # EQA - Genset
            elif tag == 'EQA':
                if len(parts) > 2: data['genset'] = f"{parts[1]}: {parts[2]}"
            
            elif tag == 'RFF':
                if len(parts) > 1 and parts[1]: 
                    ref_val = parts[1].split(':')
                    if len(ref_val) > 1:
                        if ref_val[0] == 'BN': data['booking'] = ref_val[1]
                        elif ref_val[0] == 'VON': data['booking'] = f"Voyage: {ref_val[1]}"
                    elif ref_val[0] == 'BN': 
                        pass

            # MEA - Peso
            elif tag == 'MEA':
                try:
                    if len(parts) > 3 and 'KGM' in parts[3]:
                        weight_val = parts[3].split(':')[1]
                        data['weight'] = f"{weight_val} KG"
                except: pass

        return data

    def parse_all(self):
        """Divide o conteúdo em blocos baseados em UNH...UNT e processa cada um."""
        current_segment_buffer = []
        in_message = False

        for seg in self.all_segments:
            clean_seg = seg.strip()
            if not clean_seg: continue

            if clean_seg.startswith('UNH+'):
                in_message = True
                current_segment_buffer = [clean_seg]
            elif clean_seg.startswith('UNT+'):
                if in_message:
                    current_segment_buffer.append(clean_seg)
                    parsed_data = self.parse_single_transaction(current_segment_buffer)
                    self.transactions.append(parsed_data)
                    current_segment_buffer = []
                    in_message = False
            else:
                if in_message:
                    current_segment_buffer.append(clean_seg)
        
        print(f"[PARSER LOG] Parsing complete. Found {len(self.transactions)} transactions.")