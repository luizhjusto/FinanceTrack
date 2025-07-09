import io
import os
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from oauth2client.service_account import ServiceAccountCredentials

class GoogleManager:

    credentials_path = 'credencial_google.json'
    
    def download_images_from_drive(folder_id, local_dir, credentials_path):
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
            pageSize=20,
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        
        items = results.get('files', [])
        
        if not items:
            print('Nenhuma imagem encontrada na pasta.', folder_id, local_dir)
            return
        
        file_names = []
        
        # Download de cada imagem
        for item in items:
            file_name = item['name']
            file_names.append(file_name)
            request = service.files().get_media(fileId=item['id'])
            fh = io.FileIO(os.path.join(local_dir, item['name']), 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                # print(f"Download {int(status.progress() * 100)}% - {item['name']}")
        
        # print(f"\n{len(items)} imagens salvas em: {os.path.abspath(local_dir)}")        
        return file_names

    @classmethod
    def get_folder_id_from_bank_name(self, year, bank_name):
        # Exemplo de uso:
        folder_id = self.find_folder_id(
            credentials_path=self.credentials_path,
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
        # print(f"✅ Pasta base encontrada: {base_folder_name} ({base_folder_id})")
        
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
        # print(f"✅ Pasta do banco encontrada: {bank_name} ({bank_folder_id})")    
        
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
        # print(f"✅ Pasta do ano encontrada: {year} ({year_folder_id})")
        
        return year_folder_id 
    
    @classmethod
    def update_specific_cells_batch(self, df, sheet_name, worksheet_name, start_row, col_descricao, col_valor):
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_path, scope)
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        
        # Pega todos os valores das colunas de descrição e valor
        descricoes = sheet.col_values(col_descricao)
        valores = sheet.col_values(col_valor)
        
        updates = []
        for i in range(len(df)):
            linha_planilha = start_row + i
            parcelamento = str(df.iloc[i, 2])
            if parcelamento.startswith('-'):
                parcelamento =  ''
            descricao = f"{str(df.iloc[i, 1])} {parcelamento}"
            novo_valor = str(df.iloc[i, 3])

            # Remove aspas indesejadas (se houver)
            if novo_valor.startswith("'") or novo_valor.startswith('"'):
                novo_valor = novo_valor[1:]
            if novo_valor.endswith("'") or novo_valor.endswith('"'):
                novo_valor = novo_valor[:-1]        
            
            # Verifica se a linha existe e se a descrição NÃO começa com "VR"
            if len(descricoes) >= linha_planilha:
                descricao_planilha = descricoes[linha_planilha - 1]
                if len(descricao_planilha) > 0 and descricao_planilha != descricao:
                    descricao = descricao_planilha
                    
            
            # Adiciona à lista de atualizações
            updates.append({
                'range': f"{gspread.utils.rowcol_to_a1(linha_planilha, col_descricao)}:{gspread.utils.rowcol_to_a1(linha_planilha, col_valor)}",
                'values': [[descricao, novo_valor]]
            })
        
        # Executa todas as atualizações de uma vez
        if updates:
            sheet.batch_update(updates)
