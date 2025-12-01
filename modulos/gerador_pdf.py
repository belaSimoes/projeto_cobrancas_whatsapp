import os
import datetime
import locale 
from fpdf import FPDF
from num2words import num2words

NOME_CONTADOR = "Alex Sandro de Almeida Nunes"
CPF_CONTADOR = "CPF: 704.856.581-00"
CRC_CONTADOR = "CRC: 10.245/O-0"
LOCAL_CIDADE = "Nova Andradina"

CAMINHO_HEADER = "static/header.jpeg"
CAMINHO_QRCODE = "static/qrcode_pix.jpg"
CAMINHO_ASSINATURA = "static/assinatura.png"

PASTA_RECIBOS = "recibos_gerados"
if not os.path.exists(PASTA_RECIBOS):
    os.makedirs(PASTA_RECIBOS)

def _formatar_valor_extenso(valor_str):
    try:
        valor_limpo = valor_str.replace("R$", "").replace(".", "").replace(",", ".").strip()
        valor_float = float(valor_limpo)
        
        reais = int(valor_float)
        centavos = int(round((valor_float - reais) * 100))
        
        texto_reais = num2words(reais, lang='pt_BR')
        
        if centavos > 0:
            texto_centavos = num2words(centavos, lang='pt_BR')
            return f"{texto_reais.capitalize()} reais e {texto_centavos} centavos"
        else:
            return f"{texto_reais.capitalize()} reais"
            
    except Exception as e:
        print(f"Erro ao converter valor por extenso: {e}")
        return "(Valor invalido)"

def gerar_recibo_pdf(nome_cliente, valor_mensalidade):
    try:
        try:
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')
            except locale.Error:
                print("Aviso: Nao foi possivel definir o locale 'pt_BR'. O mes pode ficar em ingles.")
                
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=10)
        
        if os.path.exists(CAMINHO_HEADER):
            pdf.image(CAMINHO_HEADER, x=55, y=10, w=100)
        else:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "(Arquivo 'static/header.jpeg' nao encontrado)", ln=True, align='C')
        
        pdf.ln(65)

        pdf.set_font("Arial", size=12)
        
        pdf.write(7, "Recebemos de ")
        pdf.set_font("", 'B')
        pdf.write(7, f"{nome_cliente}")
        pdf.set_font("", '')
        pdf.write(7, ", a importancia abaixo discriminada:")
        pdf.ln(12)

        valor_extenso = _formatar_valor_extenso(valor_mensalidade)
        pdf.set_font("Arial", size=12)
        pdf.write(7, "Valor: ")
        pdf.set_font("", 'B')
        valor_formatado = f"R$ {valor_mensalidade}"
        pdf.write(7, f"{valor_formatado} ({valor_extenso})")
        pdf.ln(12)
        
        data_hoje = datetime.date.today()
        
        primeiro_dia_mes_atual = data_hoje.replace(day=1)
        data_mes_anterior = primeiro_dia_mes_atual - datetime.timedelta(days=1)
        
        mes_referencia = data_mes_anterior.strftime("%B").upper()
        ano_referencia = data_mes_anterior.year
        
        pdf.set_font("", '')
        pdf.write(7, f"Referente a mensalidade do mes de {mes_referencia} de {ano_referencia}.")
        
        pdf.ln(25)

        if os.path.exists(CAMINHO_QRCODE):
            pdf.image(CAMINHO_QRCODE, x=75, w=60)
        else:
            pdf.cell(0, 10, "(Arquivo 'static/qrcode_pix.jpg' nao encontrado)", ln=True, align='C')
        pdf.ln(15)
        
        data_formatada = data_hoje.strftime("%d/%m/%Y")
        local_e_data = f"{LOCAL_CIDADE}, {data_formatada}"
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, local_e_data, ln=True, align='C')
        pdf.ln(10)
        
        if os.path.exists(CAMINHO_ASSINATURA):
            pdf.image(CAMINHO_ASSINATURA, x=90, w=30)
        else:
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 10, "(Arquivo 'static/assinatura.png' nao encontrado)", ln=True, align='C')

        pdf.cell(0, 5, "________________________________________", ln=True, align='C')
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 6, NOME_CONTADOR, ln=True, align='C')
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 6, CPF_CONTADOR, ln=True, align='C')
        pdf.cell(0, 6, CRC_CONTADOR, ln=True, align='C')
        
        nome_arquivo_seguro = "".join(c for c in nome_cliente if c.isalnum() or c in (' ', '.')).rstrip()
        nome_arquivo = f"recibo_{nome_arquivo_seguro.replace(' ', '_')}.pdf"
        caminho_completo = os.path.join(PASTA_RECIBOS, nome_arquivo)
        
        pdf.output(caminho_completo)
        
        print(f"PDF gerado com sucesso: {caminho_completo}")
        return caminho_completo

    except Exception as e:
        print(f"ERRO ao gerar PDF para {nome_cliente}: {e}")
        return None