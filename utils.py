import locale

pt_locale = 'en_US.UTF-8'  #Linux
# pt_locale = 'pt_BR.ISO8859-1'  #Linux
# pt_locale = 'Portuguese_Brazil.1252'  #windows

class Utils:

    def get_current_month():
        from datetime import datetime
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
            return 39, 3, 4
        elif bank == "xp":
            return 25, 7, 8

    def tryparse_decimal(texto):
        try:
            # Remove pontos de milhar (opcional) e substitui vírgula por ponto
            texto_limpo = texto.replace(".", "").replace(",", ".")
            valor = float(texto_limpo)
            return (True, str(valor).replace('.', ','))
        except (ValueError, AttributeError):
            return (False, None)
        
    def get_regex_pattern(bank_name):
        if bank_name == "c6":
            return [r'\d{2}/\d{2}']
        elif bank_name == "xp":
            return [
                r'\d{2}/\d{2}/\d{4}',
                r'\d{2}\.\d{2}'
            ]