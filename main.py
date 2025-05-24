from ocr_processor import OcrProcessor as ocr
from google_manager import GoogleManager as gdrive
from utils import Utils as utils

def run_expenses(bank):    

    start_row, col_descricao, col_valor = utils.get_first_line(bank)
    file_name = gdrive.download_images_from_drive(
        credentials_path=gdrive.credentials_path,
        folder_id=gdrive.get_folder_id_from_bank_name(utils.get_current_year(), bank),
        local_dir=f'./{bank}'
    )
    file_name = f"{bank}/{file_name}"
    text = ocr.extract_text_from_image(file_name)
    transacoes_limpas = ocr.extract_transactions_from_textt(text, bank)
    df = ocr.parse_credit_card_statement(transacoes_limpas)
    print(df)
    # gdrive.update_specific_cells_batch(df, "Financeiro", "Fev", start_row, col_descricao, col_valor)



if __name__ == "__main__":
    run_expenses("xp")
    # run_expenses("c6")