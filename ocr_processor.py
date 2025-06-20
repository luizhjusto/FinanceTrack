import easyocr
import re
import pandas as pd
from utils import Utils as utils
from datetime import datetime

class OcrProcessor:

    reader = easyocr.Reader(['pt'])

    @classmethod
    def extract_text_from_image(cls, image_path):
        text = cls.reader.readtext(image_path)
        final_text = '\n'.join([detection[1] for detection in text])
        return final_text

    @classmethod
    def extract_transactions_from_text(self, text, bank_name):
        # Remove linhas indesejadas e padroniza "RS" para "R$"
        lines = [
            line.strip().replace("RS ", "R$ ").replace("Rs ", "R$ ")  # Corrige "RS" para "R$"
            for line in text.split('\n') 
            if line.strip() 
            and not line.startswith(('Cartão', 'Cartão Virtual', 'Cartaio Vinal', 'Subtotal', '——', 'EI Cartão', 'Inclusão de Pagamento', 'USD'))
        ]

        regex = utils.get_regex_pattern(bank_name)
        cleaned_transactions = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(regex[0], line):  # Linha começa com data (nova transação)
                transaction_parts = [line]  # Inicia com a data
                i += 1
                # Agrupa todas as partes da transação até a próxima data
                while i < len(lines) and not re.match(regex[0], lines[i]):
                    if not lines[i].startswith('Em processamento'):
                        sucesso, valor = utils.tryparse_decimal(lines[i])
                        if sucesso:
                            lines[i] = f"***{'R$'}***{valor}***"
                        transaction_parts.append(lines[i])
                    i += 1

                # print(transaction_parts)
                
                # Junta as partes e corrige a ordem dos campos
                raw_transaction = " ".join(transaction_parts)
                corrected_transaction = self.correct_transaction_order(raw_transaction)
                cleaned_transactions.append(corrected_transaction)
            else:
                i += 1

        sorted_transactions = sorted(cleaned_transactions, key=lambda item: datetime.strptime(item.split()[0], "%d/%m"), reverse=True)
        # print(f"Transações extraídas: {sorted_transactions}")
        return sorted_transactions
    
    @classmethod
    def extract_transactions_from_textt(self, text, bank_name):
        # Remove linhas indesejadas e padroniza "RS" para "R$"
        lines = [
            line.strip().replace("RS ", "R$ ").replace("Rs ", "R$ ")  # Corrige "RS" para "R$"
            for line in text.split('\n') 
            if line.strip() and not line.startswith(
                ('Cartão', 'Cartão Virtual', 'Cartaio Vinal', 'Subtotal', '——', 'EI Cartão', 'Inclusão de Pagamento')
            )
        ]

        patterns = utils.get_regex_pattern(bank_name)
        cleaned_transactions = []
        transaction_parts = []
        i = 0
        date = None
        while i <= len(lines):

            if i == len(lines):
                raw_transaction = " ".join(transaction_parts)
                corrected_transaction = self.correct_transaction_order(raw_transaction)
                cleaned_transactions.append(corrected_transaction)
                break

            line = lines[i]

            if(line == "Estorno"):
                i += 1
                continue            

            for index, pattern in enumerate(patterns):
                if re.match(pattern, line) and index == 0:
                    date = line
                    break
                elif index > 0:
                    if re.match(pattern, line):
                        raw_transaction = " ".join(transaction_parts)
                        if raw_transaction != "":
                            corrected_transaction = self.correct_transaction_order(raw_transaction)
                            cleaned_transactions.append(corrected_transaction)
                        transaction_parts.clear()
                        transaction_parts = [date]
                    else:
                        transaction_parts.append(lines[i])

            i += 1

        sorted_transactions = sorted(cleaned_transactions, key=lambda x: x.split()[0])  # Ordena por data
        return sorted_transactions

    def correct_transaction_order(raw_transaction):
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
            r'(?:Parcela\s+(\d+ de \d+)\s+)?'       # Parcelamento (opcional)
            r'(R\$\s+[\d.,]+)'                   # Valor (R$24,15 ou R$ 24,15)
        )        
        
        # Tenta o padrão normal (descrição antes do valor)
        match_normal = pattern_normal.search(raw_transaction)
        if match_normal:
            data, descricao, valor, parcelamento = match_normal.groups()
            text_formatted = f"{data} {descricao.strip()} {valor} {parcelamento.strip()}".strip()
            return text_formatted
        
        # Tenta o padrão invertido (valor antes da descrição)
        match_inverted = pattern_inverted.search(raw_transaction)
        if match_inverted:
            data, valor, resto, _, parcelamento = match_inverted.groups()
            if parcelamento and parcelamento in resto:
                descricao = resto.replace(parcelamento, "").strip()
            else:
                descricao = resto.strip()
            text_formatted = f"{data} {descricao} {valor} {parcelamento if parcelamento else ''}".strip()
            return text_formatted
        
        # Tenta o padrão normal (descrição antes do valor)
        match_full_date = pattern_full_date.search(raw_transaction)
        if match_full_date:
            data, descricao, valor, hora = match_full_date.groups()
            text_formatted = f"{data} {descricao.strip()} {valor} {hora.strip()}".strip()
            return text_formatted
        
        match_full_date_parcela = pattern_full_date_parcela.search(raw_transaction)
        if match_full_date_parcela:
            data, descricao, parcelamento, valor = match_full_date_parcela.groups()
            text_formatted = f"{data} {descricao.strip()} {valor} {parcelamento if parcelamento else '-'}".strip()       
            return text_formatted    
        
        # Se nenhum padrão for encontrado, retorna o original (para debug)
        # print(f"⚠️ Transação não parseada: {raw_transaction}")
        return raw_transaction

    @classmethod
    def parse_credit_card_statement(self, text):

        pattern = re.compile(
            r'(\d{2}/\d{2})\s+'          # Data (DD/MM)
            r'(.+?)\s+'                   # Descrição (até o valor)
            r'R\$\s+([\d.,]+)'            # Valor (R$ 150,90)
            r'(?:\s+Parcela\s+(\d+)\s+ de \s+(\d+))?'  # Parcelamento (opcional)
        )

        pattern_full_date = re.compile(
            r'(\d{2}/\d{2}/\d{4})\s+'     # Data
            r'(.*?)\s+'                   # Descrição (não guloso)
            r'(R\$\s+[\d.,]+)\s+'         # Valor
            r'(Parcela \d+ de \d+)?'      # Parcelamento (opcional)
        )

        inlineText = "\n".join(text)

        transacoes_limpas = self.clean_extracted_text(inlineText)
        transacoes_formatted = []
        # print(f"Transações limpas: {transacoes_limpas}")
        for transacao in transacoes_limpas:
            match = pattern.search(transacao)
            if match:
                data, descricao, valor, parcela_atual, parcela_total = match.groups()
                # print(f"Transação 1: {data} {descricao} {valor} {parcela_atual} de {parcela_total}")
                transacoes_formatted.append({
                    'Data': data,
                    'Descrição': descricao.strip(),
                    'Parcela': f"{parcela_atual or '-'}/{parcela_total or '-'}",
                    'Valor': valor.replace('.', '')
                })

            match_full_date = pattern_full_date.search(transacao)
            if match_full_date:
                data, descricao, valor, parcelamento = match_full_date.groups()
                # print(f"Transação 2: {data} {descricao} {valor} {parcelamento}")
                transacoes_formatted.append({
                    'Data': data,
                    'Descrição': descricao.strip(),
                    'Parcela': f"{parcelamento or '-'}",
                    'Valor': valor.replace('.', '')
                })

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