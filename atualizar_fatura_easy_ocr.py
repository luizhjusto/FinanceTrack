import logging
import io
import os
import pandas as pd
import re
import easyocr
import locale
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from oauth2client.service_account import ServiceAccountCredentials

reader = easyocr.Reader(['pt'])  # You can add more languages if needed
pt_locale = 'pt_BR.UTF-8'  #Linux
# pt_locale = 'Portuguese_Brazil.1252'  #windows

def get_current_month():
    from datetime import datetime

    logging.basicConfig(level=logging.INFO)
    logging.info("✅ Este é um log visível no GitHub Actions!")
    logging.info("Default locale: ", locale.getdefaultlocale())
    logging.info("Locale alias: ", locale.locale_alias)
                 
    print("Default locale: ", locale.getdefaultlocale())
    print("Locale alias: ", locale.locale_alias)



    locale.setlocale(locale.LC_ALL, pt_locale)
    month = datetime.now().strftime("%b").capitalize()
    return month

def get_current_year():
    from datetime import datetime
    locale.setlocale(locale.LC_ALL, pt_locale)
    year = datetime.now().strftime("%Y")
    return year

def get_first_line(bank):
    if bank == "c6":
        return 37, 3, 4
    elif bank == "xp":
        return 25, 7, 8

def get_folder_id_from_bank_name(year, bank_name):
    
    # Exemplo de uso:
    folder_id = find_folder_id(
        credentials_path='credencial_google.json',
        base_folder_name='Financeiro',
        year=year,
        bank_name=bank_name
    )
    
    return folder_id

def find_folder_id(credentials_path, base_folder_name, year, bank_name=None):
    # Configuração da API
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    
    # Primeiro encontra a pasta base (Financeiro)
    base_folder_id = None
    results = service.files().list(
        q=f"name='{base_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        pageSize=1,
        fields="files(id, name)"
    ).execute()
    
    if not results.get('files'):
        print(f"❌ Pasta base '{base_folder_name}' não encontrada")
        return None
    
    base_folder_id = results['files'][0]['id']
    print(f"✅ Pasta base encontrada: {base_folder_name} ({base_folder_id})")
    
    # Agora encontra a pasta do ano
    bank_folder_id = None
    results = service.files().list(
        q=f"'{base_folder_id}' in parents and name='{bank_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        pageSize=1,
        fields="files(id, name)"
    ).execute()
    
    if not results.get('files'):
        print(f"❌ Pasta do banco '{bank_name}' não encontrada")
        return None
    
    bank_folder_id = results['files'][0]['id']
    print(f"✅ Pasta do banco encontrada: {bank_name} ({bank_folder_id})")    
    
    # Agora encontra a pasta do ano
    year_folder_id = None
    results = service.files().list(
        q=f"'{bank_folder_id}' in parents and name='{year}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        pageSize=1,
        fields="files(id, name)"
    ).execute()
    
    if not results.get('files'):
        print(f"❌ Pasta do ano '{year}' não encontrada")
        return None
    
    year_folder_id = results['files'][0]['id']
    print(f"✅ Pasta do ano encontrada: {year} ({year_folder_id})")
    
    return year_folder_id

def download_images_from_drive(folder_id, local_dir, credentials_path='credencial_google.json'):
   # Escopos combinados (Sheets + Drive)
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.readonly'
    ]
    
    # Autenticação (mesmo método do update_specific_cells_batch)
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scopes=SCOPES)
    
    # Cria serviço do Drive
    service = build('drive', 'v3', credentials=creds)
    
    # Cria diretório local se não existir
    os.makedirs(local_dir, exist_ok=True)
    
    # Busca arquivos na pasta
    query = f"'{folder_id}' in parents and mimeType contains 'image/'"
    results = service.files().list(
        q=query,
        pageSize=10,
        fields="nextPageToken, files(id, name, mimeType)"
    ).execute()
    
    items = results.get('files', [])
    
    if not items:
        print('Nenhuma imagem encontrada na pasta.', folder_id, local_dir)
        return
    
    file_name = ""
    
    # Download de cada imagem
    for item in items:
        file_name = item['name']
        request = service.files().get_media(fileId=item['id'])
        fh = io.FileIO(os.path.join(local_dir, item['name']), 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}% - {item['name']}")
    
    print(f"\n{len(items)} imagens salvas em: {os.path.abspath(local_dir)}")
    
    return file_name

def tryparse_decimal(texto):
    try:
        # Remove pontos de milhar (opcional) e substitui vírgula por ponto
        texto_limpo = texto.replace(".", "").replace(",", ".")
        valor = float(texto_limpo)
        return (True, str(valor).replace('.', ','))
    except (ValueError, AttributeError):
        return (False, None)

def extract_text_from_image(image_path):
    text = reader.readtext(image_path)
    final_text = '\n'.join([detection[1] for detection in text])
    # print(final_text)
    return final_text

def extract_transactions_from_text(text):
    # Remove linhas indesejadas e padroniza "RS" para "R$"
    lines = [
        line.strip().replace("RS ", "R$ ").replace("Rs ", "R$ ")  # Corrige "RS" para "R$"
        for line in text.split('\n') 
        if line.strip() 
        and not line.startswith(('Cartão', 'Cartão Virtual', 'Cartaio Vinal', 'Subtotal', '——', 'EI Cartão', 'Inclusão de Pagamento'))
    ]
    
    # print("Texto:", text + "\n")

    cleaned_transactions = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'\d{2}/\d{2}', line):  # Linha começa com data (nova transação)
            transaction_parts = [line]  # Inicia com a data
            i += 1
            # Agrupa todas as partes da transação até a próxima data
            while i < len(lines) and not re.match(r'\d{2}/\d{2}', lines[i]):
                if not lines[i].startswith('Em processamento'):
                    # print("Valor:", lines[i])
                    sucesso, valor = tryparse_decimal(lines[i])
                    if sucesso:
                        lines[i] = f"***{'R$'}***{valor}***"
                    transaction_parts.append(lines[i])
                i += 1
            
            # Junta as partes e corrige a ordem dos campos
            raw_transaction = " ".join(transaction_parts)
            # print("Transação bruta:", raw_transaction)
            corrected_transaction = correct_transaction_order(raw_transaction)
            # print("Transação corrigida:", corrected_transaction)
            cleaned_transactions.append(corrected_transaction)
        else:
            i += 1
    return cleaned_transactions

def extract_transactions_from_text_xp(text):
    # Remove linhas indesejadas e padroniza "RS" para "R$"
    lines = [
        line.strip().replace("RS ", "R$ ").replace("Rs ", "R$ ")  # Corrige "RS" para "R$"
        for line in text.split('\n') 
        if line.strip() 
        and not line.startswith(('Cartão', 'Cartaio Vinal', 'Subtotal', '——', 'EI Cartão', 'Inclusão de Pagamento'))
    ]
    
    print("Texto:", text + "\n")

    cleaned_transactions = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'\d{2}/\d{2}', line):  # Linha começa com data (nova transação)
            transaction_parts = [line]  # Inicia com a data
            i += 1
            # Agrupa todas as partes da transação até a próxima data
            while i < len(lines) and not re.match(r'\d{2}/\d{2}', lines[i]):
                if not lines[i].startswith('Em processamento'):
                    print("Valor:", lines[i])
                    sucesso, valor = tryparse_decimal(lines[i])
                    if sucesso:
                        lines[i] = f"***{'R$'}***{valor}***"
                    transaction_parts.append(lines[i])
                i += 1
            
            # Junta as partes e corrige a ordem dos campos
            raw_transaction = " ".join(transaction_parts)
            # print("Transação bruta:", raw_transaction)
            corrected_transaction = correct_transaction_order(raw_transaction)
            # print("Transação corrigida:", corrected_transaction)
            cleaned_transactions.append(corrected_transaction)
        else:
            i += 1
    return cleaned_transactions

def correct_transaction_order(raw_transaction):
    """
    Corrige a ordem para: DATA + DESCRIÇÃO + VALOR + PARCELAMENTO.
    Trata casos onde o valor está antes ou depois da descrição.
    """
    # Padroniza "RS" para "R$" e remove espaços extras
    raw_transaction = raw_transaction.replace("RS ", "R$ ").replace("Rs ", "R$ ").strip()
    
    # Padrão 1: Descrição ANTES do valor (ex: "01/08 PG 'B4A GLAMBOX R$ 76,76 Parcela")
    pattern_normal = re.compile(
        r'(\d{2}/\d{2})\s+'          # Data (DD/MM)
        r'(.*?)\s+'                   # Descrição (não guloso)
        r'(R\$\s+[\d.,]+)\s*'        # Valor (R$ X,XX)
        r'(.*)'                       # Parcelamento (opcional)
    )
    
    # Padrão 2: Valor ANTES da descrição (ex: "17/02 R$ 58,13 APP 'MONTISTUDIO")
    pattern_inverted = re.compile(
        r'(\d{2}/\d{2})\s+'          # Data
        r'(R\$\s+[\d.,]+)\s+'        # Valor
        r'(.+?)\s+(?=(R\$|Parcela))'                   # Descrição + Parcelamento
        r'(Parcela \d+ de \d+)?'      # Parcelamento (opcional)
    )

    # Padrão 3:
    pattern_full_date = re.compile(
        r'(\d{2}/\d{2}/\d{4})\s+'     # Data
        r'(.*?)\s+'                   # Descrição (não guloso)
        r'(R\$\s+[\d.,]+)\s+'         # Valor
        r'(.*)'                       # Parcelamento (opcional)
    ) 

    # Padrão 4:
    pattern_full_date_parcela = re.compile(
        r'(\d{2}/\d{2}/(?:\d{2}|\d{4}))\s+'  # Data (dd/mm/aa OU dd/mm/aaaa)
        r'(.+?)\s+'                          # Descrição (não gulosa, até o próximo padrão)
        r'(?:Parcela\s+(\d+/\d+)\s+)?'             # Parcelamento (opcional)
        r'R\$\s*([\d.,]+)'                   # Valor (R$24,15 ou R$ 24,15)
    )        
    
    # Tenta o padrão normal (descrição antes do valor)
    match_normal = pattern_normal.search(raw_transaction)
    if match_normal:
        data, descricao, valor, parcelamento = match_normal.groups()
        text_formatted = f"{data} {descricao.strip()} {valor} {parcelamento.strip()}".strip()
        # print("Texto formatado:", text_formatted)
        return text_formatted
    
    # Tenta o padrão invertido (valor antes da descrição)
    match_inverted = pattern_inverted.search(raw_transaction)
    if match_inverted:
        data, valor, resto, _, parcelamento = match_inverted.groups()
        # Remove o parcelamento da descrição (se já estiver incluso no "resto")
        if parcelamento and parcelamento in resto:
            descricao = resto.replace(parcelamento, "").strip()
        else:
            descricao = resto.strip()
        text_formatted = f"{data} {descricao} {valor} {parcelamento if parcelamento else ''}".strip()
        # print("Texto formatado invertido:", text_formatted)
        return text_formatted
    
    # Tenta o padrão normal (descrição antes do valor)
    match_full_date = pattern_full_date.search(raw_transaction)
    if match_full_date:
        data, descricao, valor, hora = match_full_date.groups()
        text_formatted = f"{data} {descricao.strip()} {valor} {hora.strip()}".strip()
        # print("Texto formatado:", text_formatted)
        return text_formatted
    
    # Padrão 4:
    ttt = re.compile(
        r'(\d{2}/\d{2}/(?:\d{2}|\d{4}))\s+'  # Data (dd/mm/aa OU dd/mm/aaaa)
        r'(.+?)\s+'                          # Descrição (não gulosa, até o próximo padrão)
        r'(?:Parcela\s+(\d+/\d+)\s+)?'             # Parcelamento (opcional)
        r'R\$\s*([\d.,]+)'                   # Valor (R$24,15 ou R$ 24,15)
    ) 
    test = "14/04/2023 EBN'CANVA Parcela 1/2 R$24,15"
    tt = ttt.search(raw_transaction)
    if tt:
        data, descricao, parcelamento, valor = tt.groups()
        aa = f"{data} {descricao.strip()} {valor} {parcelamento}".strip()
        # print("func:", aa)
    
    match_full_date_parcela = pattern_full_date_parcela.search(raw_transaction)
    if match_full_date_parcela:
        data, descricao, parcelamento, valor = match_full_date_parcela.groups()
        text_formatted = f"{data} {descricao.strip()} {valor} {parcelamento if parcelamento else ''}".strip()
        # print("Texto formatado:", text_formatted)
        return text_formatted    
    
    # Se nenhum padrão for encontrado, retorna o original (para debug)
    # print(f"⚠️ Transação não parseada: {raw_transaction}")
    return raw_transaction

def parse_credit_card_statement(text):

    pattern = re.compile(
        r'(\d{2}/\d{2})\s+'          # Data (DD/MM)
        r'(.+?)\s+'                   # Descrição (até o valor)
        r'R\$\s+([\d.,]+)'            # Valor (R$ 150,90)
        r'(?:\s+Parcela\s+(\d+)\s+de\s+(\d+))?'  # Parcelamento (opcional)
    )

    pattern_full_date = re.compile(
        r'(\d{2}/\d{2}/\d{4})\s+'     # Data
        r'(.*?)\s+'                   # Descrição (não guloso)
        r'(R\$\s+[\d.,]+)\s+'         # Valor
        r'(.*)'                       # Parcelamento (opcional)
    )     

    inlineText = "\n".join(text)

    transacoes_limpas = clean_extracted_text(inlineText)
    transacoes_formatted = []

    for transacao in transacoes_limpas:
        match = pattern.search(transacao)
        if match:
            data, descricao, valor, parcela_atual, parcela_total = match.groups()
            transacoes_formatted.append({
                'Data': data,
                'Descrição': descricao.strip(),
                'Parcela': f"{parcela_atual or '-'}/{parcela_total or '-'}",
                'Valor': valor.replace('.', '')
            })
            # print(f"Data: {data} | Descrição: {descricao} | Valor: R$ {valor} | Parcela: {parcela_atual or '-'}/{parcela_total or '-'}")

        match_full_date = pattern_full_date.search(transacao)
        if match_full_date:
            data, descricao, valor, hora = match_full_date.groups()
            transacoes_formatted.append({
                'Data': data,
                'Descrição': descricao.strip(),
                'Parcela': f"{'-'}/{'-'}",
                'Valor': valor.replace('.', '')
            })

    # transactions = pattern.findall(text)
    # print("Transações limpas:", transacoes_limpas)
    # print("Transações formatadas:", transacoes_formatted)
    return pd.DataFrame(transacoes_formatted, columns=['Data', 'Descrição', 'Parcela', 'Valor'])

def clean_extracted_text(text):
    # Remove caracteres estranhos e linhas irrelevantes
    text = re.sub(r'Í\?ª\.|tm|Cartão virtual \d+', '', text)
    
    # Separa as linhas e filtra as válidas
    lines = [
        line.strip() for line in text.split('\n') 
        if line.strip() 
        and not any(word in line for word in ['Cartão', 'Subtotal', '——'])
    ]
    
    # Agrupa linhas que pertencem à mesma transação
    cleaned_transactions = []
    current_transaction = []
    
    for line in lines:
        if re.match(r'\d{2}/\d{2}', line):  # Nova transação
            if current_transaction:
                cleaned_transactions.append(" ".join(current_transaction))
            current_transaction = [line]
        else:
            current_transaction.append(line)
    
    if current_transaction:
        cleaned_transactions.append(" ".join(current_transaction))
    
    return cleaned_transactions
    images = convert_from_path(pdf_path)
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img, lang='por')
    return text

def update_specific_cells_batch(df, sheet_name, worksheet_name, start_row, col_descricao, col_valor):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credencial_google.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).worksheet(worksheet_name)
    
    # Pega todos os valores das colunas de descrição e valor
    descricoes = sheet.col_values(col_descricao)  # Coluna B (descrições)
    valores = sheet.col_values(col_valor)         # Coluna C (valores)
    
    updates = []
    for i in range(len(df)):
        linha_planilha = start_row + i
        parcelamento = str(df.iloc[i, 2])
        if parcelamento.startswith('-'):
            parcelamento =  ''
        descricao = f"{str(df.iloc[i, 1])} {parcelamento}"
        novo_valor = str(df.iloc[i, 3])

        # print(linha_planilha, "Novo valor:", novo_valor, "Descrição:", descricao, "Linha:", len(descricoes), "Linhas planilha:", linha_planilha)

        # Remove aspas indesejadas (se houver)
        if novo_valor.startswith("'") or novo_valor.startswith('"'):
            novo_valor = novo_valor[1:]
        if novo_valor.endswith("'") or novo_valor.endswith('"'):
            novo_valor = novo_valor[:-1]        
        
        # Verifica se a linha existe e se a descrição NÃO começa com "VR"
        if len(descricoes) >= linha_planilha:
            descricao_planilha = descricoes[linha_planilha - 1]
            # if descricao.startswith(("VR", "[Gabi]", "[Gabi]")):
            #     print(f"⚠️ Linha {linha_planilha} ignorada")
            #     continue
            if descricao_planilha != descricao:
                descricao = descricao_planilha
                
        
        # Adiciona à lista de atualizações
        updates.append({
            'range': f"{gspread.utils.rowcol_to_a1(linha_planilha, col_descricao)}:{gspread.utils.rowcol_to_a1(linha_planilha, col_valor)}",
            'values': [[descricao, novo_valor]]
        })

        # print(updates)
    
    # Executa todas as atualizações de uma vez
    if updates:
        sheet.batch_update(updates)

def run_expenses(bank):    
    start_row, col_descricao, col_valor = get_first_line("c6")
    file_name = download_images_from_drive(
        folder_id=get_folder_id_from_bank_name(get_current_year(), bank),  # Substitua pelo ID da sua pasta
        local_dir=f'./{bank}'
    )
    text = extract_text_from_image(f"{bank}/{file_name}")
    transacoes_limpas = extract_transactions_from_text(text)
    df = parse_credit_card_statement(transacoes_limpas)
    update_specific_cells_batch(df, "Financeiro", "Fev", start_row, col_descricao, col_valor)

# Executar
if __name__ == "__main__":
    # run_expenses("xp")
    run_expenses("c6")