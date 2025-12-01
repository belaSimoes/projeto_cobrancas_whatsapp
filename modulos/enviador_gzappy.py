import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

GZAPPY_TOKEN = os.getenv("GZAPPY_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

URL_TEXTO = "https://v2-api.gzappy.com/message/send-text"
URL_MIDIA = "https://v2-api.gzappy.com/message/send-media"

def upload_pdf_para_supabase(caminho_pdf, nome_arquivo):
    """Faz upload do PDF para Supabase e retorna URL publica"""
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("ERRO: Configuracao do Supabase nao encontrada")
            return None
        
        nome_base = os.path.splitext(nome_arquivo)[0]
        timestamp = int(time.time())
        nome_unico = f"{nome_base}_{timestamp}.pdf"
        
        with open(caminho_pdf, 'rb') as f:
            file_data = f.read()
        
        headers = {
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/pdf',
            'Cache-Control': 'no-cache'
        }
        
        upload_url = f"{SUPABASE_URL}/storage/v1/object/recibos/{nome_unico}"
        response = requests.post(upload_url, headers=headers, data=file_data)
        
        if response.status_code == 200:
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/recibos/{nome_unico}"
            print(f"SUCESSO: PDF upload para {public_url}")
            
            test_response = requests.get(public_url)
            if test_response.status_code == 200:
                print("URL esta acessivel publicamente")
                return public_url
            else:
                print(f"URL nao esta acessivel: {test_response.status_code}")
                return None
        else:
            print(f"ERRO no upload: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"ERRO no upload para Supabase: {e}")
        return None

def enviar_via_gzappy_api(telefone_cliente, texto_mensagem, caminho_anexo_pdf=None):
    
    if not GZAPPY_TOKEN:
        print("ERRO: GZAPPY_TOKEN nao encontrado")
        return False

    telefone_formatado = telefone_cliente.replace('+', '')

    headers = {
        'Authorization': f'Bearer {GZAPPY_TOKEN}',
        'Content-Type': 'application/json'
    }

    try:
        if caminho_anexo_pdf:
            nome_arquivo = os.path.basename(caminho_anexo_pdf)
            url_publica = upload_pdf_para_supabase(caminho_anexo_pdf, nome_arquivo)
            
            if not url_publica:
                print("ERRO: Nao foi possivel fazer upload do PDF")
                return False
            
            # FORMATO EXATO fornecido pelo suporte do Gzappy
            payload = {
                'phone': [telefone_formatado],
                'message': texto_mensagem,
                'media_public_url': url_publica,
                'file_name': nome_arquivo
            }
            
            print(f"Enviando PDF para {telefone_formatado}")
            print(f"Payload enviado para Gzappy: {payload}")
            response = requests.post(URL_MIDIA, headers=headers, json=payload)

        else:
            payload = {
                'phone': [telefone_formatado],
                'message': texto_mensagem,
            }
            
            print(f"Enviando texto para {telefone_formatado}")
            response = requests.post(URL_TEXTO, headers=headers, json=payload)

        print(f"Status da resposta: {response.status_code}")
        print(f"Resposta completa: {response.text}")
        
        if response.status_code == 200:
            print("SUCESSO: Mensagem enviada")
            return True
        else:
            print(f"FALHA: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"ERRO: {e}")
        return False