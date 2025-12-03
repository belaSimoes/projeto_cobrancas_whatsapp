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

# Importar o gerador de PDF
from modulos.gerador_pdf import gerar_recibo_pdf

# Importar o enviador Gzappy
try:
    from modulos.enviador_gzappy import enviar_via_gzappy_api
except ImportError:
    print("AVISO: 'enviador_gzappy.py' nao encontrado. Usando simulacao.")
    def enviar_via_gzappy_api(telefone, texto_mensagem, caminho_pdf=None):
        print(f"--- SIMULANDO ENVIO ---")
        return True

app = Flask(__name__)
app.secret_key = "alex_contabilidade_v3_secret" 
DB_PATH = os.path.join('dados', 'base_clientes.json')

MESES_LISTA = [
    'JANEIRO', 'FEVEREIRO', 'MARCO', 'ABRIL', 'MAIO', 'JUNHO', 
    'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO'
]

# --- Funções Auxiliares de Conversão Monetária ---
def str_para_float(valor_str):
    """Converte '1.200,50' para 1200.50"""
    try:
        if not valor_str: return 0.0
        # Remove R$, pontos de milhar e troca vírgula por ponto
        limpo = str(valor_str).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(limpo)
    except:
        return 0.0

def float_para_str(valor_float):
    """Converte 1200.50 para '1.200,50'"""
    try:
        # Formata com 2 casas, troca ponto por virgula, adiciona milhar
        return f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,00"

# --- Funções de Banco de Dados ---
def load_data():
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Sanitização: garante que todo cliente tenha os campos novos
            for cliente in data:
                if 'pagamentos_parciais' not in cliente:
                    cliente['pagamentos_parciais'] = {}
                if 'status_cliente' not in cliente:
                    cliente['status_cliente'] = 'ATIVO'
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_data(data):
    try:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        flash(f"Erro ao salvar: {e}", "error")
        return False

def get_mes_referencia():
    data_hoje = datetime.datetime.now()
    mes_referencia_num = data_hoje.month - 1
    if mes_referencia_num == 0: mes_referencia_num = 12
    
    mes_map = {i+1: mes for i, mes in enumerate(MESES_LISTA)}
    return mes_map[mes_referencia_num]

# --- Função de Cálculo Cumulativo ---
def calcular_divida_total(cliente, mes_referencia_nome):
    """
    Soma: Pendências anteriores + Mensalidade atual (ou restante atual).
    Retorna: (valor_total_float, string_detalhes)
    """
    valor_mensalidade = str_para_float(cliente['valor_mensalidade'])
    divida_total = 0.0
    detalhes_pendencia = []

    try:
        index_ref = MESES_LISTA.index(mes_referencia_nome)
    except ValueError:
        return 0.0, ""

    # 1. Somar pendências dos MESES ANTERIORES
    for i in range(index_ref):
        mes_anterior = MESES_LISTA[i]
        status = cliente['status_meses'].get(mes_anterior, 'EM ABERTO')
        
        if status == 'EM ABERTO':
            divida_total += valor_mensalidade
            detalhes_pendencia.append(f"{mes_anterior} (integral)")
        elif status == 'PARCIAL':
            pago = str_para_float(cliente['pagamentos_parciais'].get(mes_anterior, "0"))
            restante = valor_mensalidade - pago
            if restante > 0.01:
                divida_total += restante
                detalhes_pendencia.append(f"{mes_anterior} (restante)")

    # 2. Somar o MÊS DE REFERÊNCIA (Atual)
    status_ref = cliente['status_meses'].get(mes_referencia_nome, 'EM ABERTO')
    
    if status_ref == 'EM ABERTO':
        divida_total += valor_mensalidade
    elif status_ref == 'PARCIAL':
        pago_ref = str_para_float(cliente['pagamentos_parciais'].get(mes_referencia_nome, "0"))
        restante_ref = valor_mensalidade - pago_ref
        divida_total += restante_ref
    
    texto_detalhe = ""
    if detalhes_pendencia:
        texto_detalhe = " (Inclui pendências: " + ", ".join(detalhes_pendencia) + ")"

    return divida_total, texto_detalhe

# --- Rotas do Sistema ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/gerenciar')
def gerenciar_clientes():
    search_query = request.args.get('q', '') 
    clientes_todos = load_data()
    
    if search_query:
        clientes_filtrados = [c for c in clientes_todos if search_query.lower() in c['nome_cliente'].lower()]
        return render_template('gerenciar.html', clientes=clientes_filtrados, search_query=search_query, meses=MESES_LISTA)
    
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
    save_data(clientes)
    return redirect(url_for('gerenciar_clientes'))

@app.route('/add_cliente', methods=['POST'])
def add_cliente():
    clientes = load_data()
    new_id = max([c['id'] for c in clientes]) + 1 if clientes else 1
    
    novo_cliente = {
        "id": new_id,
        "selecao": False,
        "nome_cliente": request.form.get('nome_cliente'),
        "telefone": request.form.get('telefone'),
        "valor_mensalidade": request.form.get('valor_mensalidade'),
        "status_meses": {mes: "EM ABERTO" for mes in MESES_LISTA},
        "pagamentos_parciais": {},
        "status_cliente": "ATIVO"
    }
    clientes.append(novo_cliente)
    save_data(clientes)
    flash(f"Cliente cadastrado com sucesso!", "success")
    return redirect(url_for('gerenciar_clientes'))

@app.route('/editar/<int:cliente_id>')
def editar_cliente(cliente_id):
    clientes = load_data()
    cliente = next((c for c in clientes if c['id'] == cliente_id), None)
    if cliente:
        return render_template('editar_cliente.html', cliente=cliente, meses=MESES_LISTA)
    else:
        flash("Cliente não encontrado.", "error")
        return redirect(url_for('gerenciar_clientes'))

@app.route('/salvar_edicao_completa/<int:cliente_id>', methods=['POST'])
def salvar_edicao_completa(cliente_id):
    clientes = load_data()
    cliente = next((c for c in clientes if c['id'] == cliente_id), None)
    
    if not cliente: return redirect(url_for('gerenciar_clientes'))
    
    # 1. Atualiza dados cadastrais
    cliente['nome_cliente'] = request.form.get('nome_cliente')
    cliente['telefone'] = request.form.get('telefone')
    cliente['valor_mensalidade'] = request.form.get('valor_mensalidade')
    cliente['status_cliente'] = request.form.get('status_cliente', 'ATIVO')
    
    if cliente['status_cliente'] == 'INATIVO':
        cliente['selecao'] = False
    
    # 2. Atualiza Status dos Meses e Parciais
    if 'pagamentos_parciais' not in cliente:
        cliente['pagamentos_parciais'] = {}

    for mes in MESES_LISTA:
        novo_status = request.form.get(f'status_{mes}')
        if novo_status:
            cliente['status_meses'][mes] = novo_status
            
            # Lógica do Pagamento Parcial
            if novo_status == "PARCIAL":
                valor_pago_str = request.form.get(f'valor_pago_{mes}')
                cliente['pagamentos_parciais'][mes] = valor_pago_str if valor_pago_str else "0,00"
            else:
                # Se mudou para PAGO ou EM ABERTO, limpa o registro parcial
                if mes in cliente['pagamentos_parciais']:
                    del cliente['pagamentos_parciais'][mes]
            
    save_data(clientes)
    flash("Alterações salvas com sucesso!", "success")
    return redirect(url_for('gerenciar_clientes'))

@app.route('/editar_selecionados', methods=['POST'])
def editar_selecionados():
    clientes = load_data()
    clientes_selecionados = [c for c in clientes if c['selecao'] and c.get('status_cliente', 'ATIVO') == 'ATIVO']
    
    if not clientes_selecionados:
        flash("Nenhum cliente ativo selecionado para edição.", "error")
        return redirect(url_for('gerenciar_clientes'))
    
    return render_template('editar_lote.html', 
                         clientes=clientes_selecionados, 
                         meses=MESES_LISTA)

@app.route('/salvar_edicao_lote', methods=['POST'])
def salvar_edicao_lote():
    cliente_ids = request.form.get('cliente_ids', '').split(',')
    mes = request.form.get('mes')
    status = request.form.get('status')
    
    if not mes or not status: return redirect(url_for('gerenciar_clientes'))
    
    clientes = load_data()
    for cliente in clientes:
        if str(cliente['id']) in cliente_ids and cliente.get('status_cliente', 'ATIVO') == 'ATIVO':
            cliente['status_meses'][mes] = status
            if status != "PARCIAL" and 'pagamentos_parciais' in cliente and mes in cliente['pagamentos_parciais']:
                del cliente['pagamentos_parciais'][mes]
                
    save_data(clientes)
    flash("Edição em lote concluída!", "success")
    return redirect(url_for('gerenciar_clientes'))

@app.route('/executar_cobranca', methods=['POST'])
def executar_cobranca():
    print("Iniciando cobranca...")
    logs = []
    
    filtro_selecao = request.form.get('filtro_selecao') 
    msgs = [request.form.get(k) for k in ['msg_13', 'msg_18', 'msg_livre']]
    msg_preenchida = next((m for m in msgs if m), None)
    
    if not msg_preenchida or len([m for m in msgs if m]) > 1:
        flash("Preencha EXATAMENTE um campo de mensagem.", "error")
        return redirect(url_for('index'))
    
    tipo_envio = "LIVRE" if request.form.get('msg_livre') else "RECIBO"
    
    clientes = load_data()
    mes_ref = get_mes_referencia()
    print(f"Mes de referencia: {mes_ref}")
    
    for cliente in clientes:
        # Filtros e Validações
        if cliente.get('status_cliente', 'ATIVO') == 'INATIVO': continue
        
        status = cliente['status_meses'].get(mes_ref, 'EM ABERTO')
        
        if status == 'PAGO': continue
        if filtro_selecao == 'Seleção' and not cliente['selecao']: continue
        if not cliente['telefone'] or cliente['telefone'] == 'S. FONE': continue
        
        print(f"Processando: {cliente['nome_cliente']}")
        
        try:
            if tipo_envio == "RECIBO":
                # --- CÁLCULO CUMULATIVO ---
                valor_a_cobrar, detalhes_pendencia = calcular_divida_total(cliente, mes_ref)
                
                # Se não deve nada, pula
                if valor_a_cobrar <= 0.01:
                    logs.append(f"Aviso: {cliente['nome_cliente']} não tem saldo devedor.")
                    continue

                valor_cobrar_str = float_para_str(valor_a_cobrar)
                
                # Mensagem Dinâmica
                texto_base = f"Olá {cliente['nome_cliente']}, segue recibo referente ao valor total em aberto de R$ {valor_cobrar_str}{detalhes_pendencia}."
                texto_final = f"{texto_base}\n\n{msg_preenchida}"
                
                # Gera PDF com Valor Total
                caminho_pdf = gerar_recibo_pdf(cliente['nome_cliente'], valor_cobrar_str)
                
                if caminho_pdf:
                    sucesso = enviar_via_gzappy_api(cliente['telefone'], texto_final, caminho_pdf)
                    if sucesso:
                        logs.append(f"Enviado para {cliente['nome_cliente']} (Valor Total: {valor_cobrar_str})")
                    else:
                        logs.append(f"ERRO GZAPPY: {cliente['nome_cliente']}")
            
            else:
                # Envio Livre
                enviar_via_gzappy_api(cliente['telefone'], msg_preenchida, None)
                logs.append(f"Mensagem livre para {cliente['nome_cliente']}")
                
        except Exception as e:
            print(f"Erro critico no cliente {cliente['nome_cliente']}: {e}")

    flash(f"Processo concluído! Verifique o terminal para detalhes.", "success")
    return redirect(url_for('index'))

@app.route('/static/<filename>')
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)