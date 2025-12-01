import os
import json
import datetime
from flask import (
    Flask, 
    render_template, 
    request, 
    flash, 
    redirect, 
    url_for,
    send_from_directory
)

from modulos.gerador_pdf import gerar_recibo_pdf

try:
    from modulos.enviador_gzappy import enviar_via_gzappy_api
except ImportError:
    print("AVISO: 'enviador_gzappy.py' nao encontrado. Usando simulacao.")
    def enviar_via_gzappy_api(telefone, texto_mensagem, caminho_pdf=None):
        print(f"SIMULACAO DE ENVIO")
        print(f"Para: {telefone} | Mensagem: {texto_mensagem} | Anexo: {caminho_pdf}")
        return True

app = Flask(__name__)
app.secret_key = "alex_contabilidade_v3_secret" 
DB_PATH = os.path.join('dados', 'base_clientes.json')
MESES_LISTA = [
    'JANEIRO', 'FEVEREIRO', 'MARCO', 'ABRIL', 'MAIO', 'JUNHO', 
    'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO'
]

def load_data():
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        flash(f"ERRO CRITICO: Arquivo '{DB_PATH}' nao encontrado.", "error")
        return []
    except json.JSONDecodeError:
        flash(f"ERRO CRITICO: O arquivo '{DB_PATH}' esta mal formatado.", "error")
        return []

def save_data(data):
    try:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        flash(f"ERRO CRITICO: Falha ao salvar dados. {e}", "error")
        return False

def get_mes_referencia():
    data_hoje = datetime.datetime.now()
    mes_referencia_num = data_hoje.month - 1
    if mes_referencia_num == 0:
        mes_referencia_num = 12
    
    mes_map = {i+1: mes for i, mes in enumerate(MESES_LISTA)}
    return mes_map[mes_referencia_num]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/gerenciar')
def gerenciar_clientes():
    search_query = request.args.get('q', '') 
    clientes_todos = load_data()
    
    if search_query:
        clientes_filtrados = []
        for cliente in clientes_todos:
            if search_query.lower() in cliente['nome_cliente'].lower():
                clientes_filtrados.append(cliente)
        
        return render_template('gerenciar.html', clientes=clientes_filtrados, search_query=search_query, meses=MESES_LISTA)
    else:
        return render_template('gerenciar.html', clientes=clientes_todos, search_query=search_query, meses=MESES_LISTA)

@app.route('/salvar_selecao', methods=['POST'])
def salvar_selecao():
    clientes = load_data()
    
    for cliente in clientes:
        if cliente.get('status_cliente', 'ATIVO') == 'ATIVO':
            form_field_name = f"selecao_{cliente['id']}"
            if request.form.get(form_field_name):
                cliente['selecao'] = True
            else:
                cliente['selecao'] = False
    
    if save_data(clientes):
        flash("Selecao de clientes salva com sucesso!", "success")
    else:
        flash("Erro ao salvar a selecao.", "error")
        
    return redirect(url_for('gerenciar_clientes'))

@app.route('/add_cliente', methods=['POST'])
def add_cliente():
    clientes = load_data()
    
    if clientes:
        new_id = max([c['id'] for c in clientes]) + 1
    else:
        new_id = 1
    
    status_padrao = {mes: "EM ABERTO" for mes in MESES_LISTA}
    
    novo_cliente = {
        "id": new_id,
        "selecao": False,
        "nome_cliente": request.form.get('nome_cliente'),
        "telefone": request.form.get('telefone'),
        "valor_mensalidade": request.form.get('valor_mensalidade'),
        "status_meses": status_padrao,
        "status_cliente": "ATIVO"
    }
    
    clientes.append(novo_cliente)
    
    if save_data(clientes):
        flash(f"Cliente '{novo_cliente['nome_cliente']}' cadastrado com sucesso!", "success")
    else:
        flash("Erro ao cadastrar novo cliente.", "error")
        
    return redirect(url_for('gerenciar_clientes'))

@app.route('/editar/<int:cliente_id>')
def editar_cliente(cliente_id):
    clientes = load_data()
    cliente_para_editar = next((c for c in clientes if c['id'] == cliente_id), None)
    
    if cliente_para_editar:
        return render_template('editar_cliente.html', cliente=cliente_para_editar, meses=MESES_LISTA)
    else:
        flash(f"Cliente com ID {cliente_id} nao encontrado.", "error")
        return redirect(url_for('gerenciar_clientes'))

@app.route('/salvar_edicao/<int:cliente_id>', methods=['POST'])
def salvar_edicao(cliente_id):
    clientes = load_data()
    cliente_para_editar = next((c for c in clientes if c['id'] == cliente_id), None)
    
    if not cliente_para_editar:
        flash(f"Cliente com ID {cliente_id} nao encontrado.", "error")
        return redirect(url_for('gerenciar_clientes'))
        
    for mes in MESES_LISTA:
        novo_status = request.form.get(f'status_{mes}')
        if novo_status:
            cliente_para_editar['status_meses'][mes] = novo_status
            
    if save_data(clientes):
        flash(f"Status do cliente '{cliente_para_editar['nome_cliente']}' atualizados!", "success")
    else:
        flash("Erro ao salvar alteracoes de status.", "error")
        
    return redirect(url_for('gerenciar_clientes'))

@app.route('/salvar_edicao_completa/<int:cliente_id>', methods=['POST'])
def salvar_edicao_completa(cliente_id):
    clientes = load_data()
    cliente_para_editar = next((c for c in clientes if c['id'] == cliente_id), None)
    
    if not cliente_para_editar:
        flash(f"Cliente com ID {cliente_id} nao encontrado.", "error")
        return redirect(url_for('gerenciar_clientes'))
    
    cliente_para_editar['nome_cliente'] = request.form.get('nome_cliente')
    cliente_para_editar['telefone'] = request.form.get('telefone')
    cliente_para_editar['valor_mensalidade'] = request.form.get('valor_mensalidade')
    cliente_para_editar['status_cliente'] = request.form.get('status_cliente', 'ATIVO')
    
    if cliente_para_editar['status_cliente'] == 'INATIVO':
        cliente_para_editar['selecao'] = False
    
    for mes in MESES_LISTA:
        novo_status = request.form.get(f'status_{mes}')
        if novo_status:
            cliente_para_editar['status_meses'][mes] = novo_status
            
    if save_data(clientes):
        flash(f"Dados do cliente '{cliente_para_editar['nome_cliente']}' atualizados com sucesso!", "success")
    else:
        flash("Erro ao salvar alteracoes.", "error")
        
    return redirect(url_for('gerenciar_clientes'))

@app.route('/editar_selecionados', methods=['POST'])
def editar_selecionados():
    clientes = load_data()
    clientes_selecionados = [c for c in clientes if c['selecao'] and c.get('status_cliente', 'ATIVO') == 'ATIVO']
    
    if not clientes_selecionados:
        flash("Nenhum cliente ativo selecionado para edicao.", "error")
        return redirect(url_for('gerenciar_clientes'))
    
    return render_template('editar_lote.html', 
                         clientes=clientes_selecionados, 
                         meses=MESES_LISTA)

@app.route('/salvar_edicao_lote', methods=['POST'])
def salvar_edicao_lote():
    cliente_ids = request.form.get('cliente_ids', '').split(',')
    mes = request.form.get('mes')
    status = request.form.get('status')
    
    if not mes or not status:
        flash("Selecione o mes e o status.", "error")
        return redirect(url_for('gerenciar_clientes'))
    
    clientes = load_data()
    clientes_afetados = 0
    
    for cliente in clientes:
        if str(cliente['id']) in cliente_ids and cliente.get('status_cliente', 'ATIVO') == 'ATIVO':
            cliente['status_meses'][mes] = status
            clientes_afetados += 1
    
    if save_data(clientes):
        flash(f"Status '{status}' definido para {clientes_afetados} cliente(s) no mes de {mes}!", "success")
    else:
        flash("Erro ao salvar alteracoes em lote.", "error")
        
    return redirect(url_for('gerenciar_clientes'))

@app.route('/executar_cobranca', methods=['POST'])
def executar_cobranca():
    print("Iniciando processo de cobranca em lote...")
    logs_processamento = []

    filtro_selecao = request.form.get('filtro_selecao') 
    msg_13 = request.form.get('msg_13')
    msg_18 = request.form.get('msg_18')
    msg_livre = request.form.get('msg_livre')

    mensagens_preenchidas = [msg for msg in [msg_13, msg_18, msg_livre] if msg]
    if len(mensagens_preenchidas) != 1:
        flash("Erro: Voce deve preencher EXATAMENTE um campo de mensagem.", "error")
        return redirect(url_for('index'))
    
    texto_mensagem = mensagens_preenchidas[0]
    tipo_envio = "LIVRE"
    if msg_13 or msg_18:
        tipo_envio = "RECIBO"

    clientes = load_data()
    MES_REFERENCIA = get_mes_referencia() 
    print(f"Mes de referencia calculado: {MES_REFERENCIA}")

    for cliente in clientes:
        if cliente.get('status_cliente', 'ATIVO') == 'INATIVO':
            continue
            
        status_atual = cliente['status_meses'].get(MES_REFERENCIA, 'EM ABERTO')
        
        if status_atual == 'PAGO':
            continue 
        if filtro_selecao == 'Selecao' and not cliente['selecao']:
            continue 
        if cliente['telefone'] == 'S. FONE' or not cliente['telefone']:
            logs_processamento.append(f"AVISO: Cliente '{cliente['nome_cliente']}' pulado (S. FONE ou sem numero).")
            continue
            
        print(f"Processando cliente: {cliente['nome_cliente']}...")
        
        try:
            if tipo_envio == "RECIBO":
                if msg_13:
                    mensagem_padrao = f"Ola {cliente['nome_cliente']}, este e um lembrete para voce efetuar o pagamento de R$ {cliente['valor_mensalidade']} da sua mensalidade!"
                    mensagem_completa = f"{mensagem_padrao}\n\n{msg_13}"
                else:
                    mensagem_padrao = f"Ola {cliente['nome_cliente']}, este e outro lembrete para voce efetuar o pagamento de R$ {cliente['valor_mensalidade']} da sua mensalidade!"
                    mensagem_completa = f"{mensagem_padrao}\n\n{msg_18}"
                
                logs_processamento.append(f"Gerando PDF para {cliente['nome_cliente']}...")
                caminho_pdf = gerar_recibo_pdf(cliente['nome_cliente'], cliente['valor_mensalidade'])
                
                if not caminho_pdf:
                    logs_processamento.append(f"ERRO: Falha ao GERAR PDF para {cliente['nome_cliente']}.")
                    continue 
                
                sucesso_envio = enviar_via_gzappy_api(cliente['telefone'], mensagem_completa, caminho_pdf)
                
                if sucesso_envio:
                    logs_processamento.append(f"SUCESSO: Recibo enviado para {cliente['nome_cliente']}.")
                else:
                    logs_processamento.append(f"ERRO: Falha na API ao ENVIAR para {cliente['nome_cliente']}.")

            elif tipo_envio == "LIVRE":
                sucesso_envio = enviar_via_gzappy_api(cliente['telefone'], msg_livre, None)
                
                if sucesso_envio:
                    logs_processamento.append(f"SUCESSO: Mensagem livre enviada para {cliente['nome_cliente']}.")
                else:
                    logs_processamento.append(f"ERRO: Falha na API ao ENVIAR para {cliente['nome_cliente']}.")

        except Exception as e:
            logs_processamento.append(f"ERRO INESPERADO ao processar {cliente['nome_cliente']}: {e}")

    print("\n--- RESUMO DO PROCESSAMENTO ---")
    for log in logs_processamento:
        print(log)
    print("---------------------------------")

    flash("Processo de cobranca concluido! Verifique os logs no terminal para detalhes.", "success")
    return redirect(url_for('index'))

@app.route('/static/<filename>')
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)