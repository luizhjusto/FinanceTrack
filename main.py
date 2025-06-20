import os
from ocr_processor import OcrProcessor as ocr
from google_manager import GoogleManager as gdrive
from utils import Utils as utils

def run_expenses(bank):
    start_row, col_descricao, col_valor = utils.get_first_line(bank)

    # Baixa múltiplas imagens e recebe uma lista de nomes de arquivos
    image_files = gdrive.download_images_from_drive(
        credentials_path=gdrive.credentials_path,
        folder_id=gdrive.get_folder_id_from_bank_name(utils.get_current_year(), bank),
        local_dir=f"./{bank}"
    )

    # Garante que image_files é uma lista
    if isinstance(image_files, str):
        image_files = [image_files]

    # Extrai e concatena texto de todas as imagens
    text = ""
    for file_name in image_files:
        full_path = f"{bank}/{file_name}"
        text += ocr.extract_text_from_image(full_path) + "\n"

    for arquivo in os.listdir(f"./{bank}"):
        caminho_arquivo = os.path.join(f"./{bank}", arquivo)
        if os.path.isfile(caminho_arquivo):
            os.remove(caminho_arquivo)

    transacoes_limpas = ocr.extract_transactions_from_text(text, bank)
    # print(f"Transações extraídas: {transacoes_limpas}")
    df = ocr.parse_credit_card_statement(transacoes_limpas)
    gdrive.update_specific_cells_batch(df, "Financeiro", "Fev", start_row, col_descricao, col_valor)



if __name__ == "__main__":
    # run_expenses("xp")
    run_expenses("c6")