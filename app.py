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
    send_from_directory,
)

# =========================
# CONFIG
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_CLIENTES = os.path.join(BASE_DIR, "dados", "base_clientes.json")
PASTA_RECIBOS = os.path.join(BASE_DIR, "recibos_gerados")

MESES_LISTA = [
    "JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"
]

# =========================
# IMPORTS DOS MÓDULOS
# =========================
try:
    from modulos.gerador_pdf import gerar_recibo_pdf
except Exception as e:
    print("ERRO REAL AO IMPORTAR modulos.gerador_pdf:", repr(e))
    raise

try:
    from modulos.enviador_gzappy import enviar_via_gzappy_api
except Exception as e:
    print("ERRO REAL AO IMPORTAR modulos.enviador_gzappy:", repr(e))
    raise

# =========================
# APP
# =========================
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_key")


# =========================
# HELPERS (JSON / VALORES)
# =========================
def carregar_clientes():
    if not os.path.exists(ARQUIVO_CLIENTES):
        return []
    with open(ARQUIVO_CLIENTES, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_clientes(clientes):
    os.makedirs(os.path.dirname(ARQUIVO_CLIENTES), exist_ok=True)
    with open(ARQUIVO_CLIENTES, "w", encoding="utf-8") as f:
        json.dump(clientes, f, ensure_ascii=False, indent=4)


def str_para_float(valor_str: str) -> float:
    if valor_str is None:
        return 0.0
    s = str(valor_str).strip()
    s = s.replace("R$", "").strip()
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0


def float_para_str_br(v: float) -> str:
    try:
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,00"


def mes_referencia_anterior() -> str:
    hoje = datetime.date.today()
    primeiro_dia_mes = hoje.replace(day=1)
    mes_passado = primeiro_dia_mes - datetime.timedelta(days=1)
    return MESES_LISTA[mes_passado.month - 1]


def garantir_campos_padrao(cliente: dict):
    if "status_meses" not in cliente or not isinstance(cliente["status_meses"], dict):
        cliente["status_meses"] = {m: "EM ABERTO" for m in MESES_LISTA}
    else:
        for m in MESES_LISTA:
            cliente["status_meses"].setdefault(m, "EM ABERTO")

    if "pagamentos_parciais" not in cliente or not isinstance(cliente["pagamentos_parciais"], dict):
        cliente["pagamentos_parciais"] = {}

    cliente.setdefault("id", 0)
    cliente.setdefault("selecao", False)
    cliente.setdefault("status_cliente", "ATIVO")
    cliente.setdefault("valor_mensalidade", "0,00")
    cliente.setdefault("telefone", "")
    cliente.setdefault("nome_cliente", "")
    cliente.setdefault("pendencia", "0,00")  # ← NOVO CAMPO


def _get_first_nonempty(form, keys):
    for k in keys:
        v = (form.get(k) or "").strip()
        if v:
            return v
    return ""


# =========================
# ROTAS
# =========================

@app.route("/")
def index():
    clientes = carregar_clientes()
    for c in clientes:
        garantir_campos_padrao(c)
    salvar_clientes(clientes)

    mes_ref = mes_referencia_anterior()

    return render_template(
        "index.html",
        clientes=clientes,
        meses=MESES_LISTA,
        mes_ref=mes_ref
    )


@app.route("/gerenciar_clientes")
def gerenciar_clientes():
    clientes = carregar_clientes()
    for c in clientes:
        garantir_campos_padrao(c)

    q = (request.args.get("q") or "").strip().lower()
    if q:
        clientes = [
            c for c in clientes
            if q in str(c.get("nome_cliente", "")).lower()
            or q in str(c.get("telefone", "")).lower()
        ]

    mes_ref = mes_referencia_anterior()

    return render_template(
        "gerenciar.html",
        clientes=clientes,
        search_query=q,
        meses=MESES_LISTA,
        mes_ref=mes_ref
    )


@app.route("/add_cliente", methods=["POST"])
def add_cliente():
    clientes = carregar_clientes()
    for c in clientes:
        garantir_campos_padrao(c)

    nome_cliente = (request.form.get("nome_cliente") or "").strip()
    telefone = (request.form.get("telefone") or "").strip()
    valor_mensalidade = (request.form.get("valor_mensalidade") or "").strip()

    if not nome_cliente:
        flash("Nome do cliente é obrigatório.", "error")
        return redirect(url_for("gerenciar_clientes"))

    max_id = max([int(c.get("id", 0)) for c in clientes] or [0])
    novo_id = max_id + 1

    novo = {
        "id": novo_id,
        "selecao": False,
        "nome_cliente": nome_cliente,
        "telefone": telefone,
        "valor_mensalidade": valor_mensalidade,
        "status_meses": {m: "EM ABERTO" for m in MESES_LISTA},
        "pagamentos_parciais": {},
        "status_cliente": "ATIVO",
        "pendencia": "0,00",  # ← NOVO
    }

    clientes.append(novo)
    salvar_clientes(clientes)
    flash("Cliente adicionado com sucesso!", "success")
    return redirect(url_for("gerenciar_clientes"))


@app.route("/salvar_selecao", methods=["POST"])
def salvar_selecao():
    clientes = carregar_clientes()
    for c in clientes:
        garantir_campos_padrao(c)

    ids_selecionados = set()
    for k in request.form.keys():
        if k.startswith("selecao_"):
            try:
                ids_selecionados.add(int(k.split("_", 1)[1]))
            except:
                pass

    for c in clientes:
        c["selecao"] = int(c.get("id", 0)) in ids_selecionados

    salvar_clientes(clientes)
    flash("Seleção salva!", "success")
    return redirect(url_for("gerenciar_clientes"))


@app.route("/editar_selecionados", methods=["POST"])
def editar_selecionados():
    clientes = carregar_clientes()
    for c in clientes:
        garantir_campos_padrao(c)

    clientes_selecionados = [
        c for c in clientes
        if c.get("selecao") and c.get("status_cliente", "ATIVO").upper() == "ATIVO"
    ]

    if not clientes_selecionados:
        flash("Nenhum cliente ativo selecionado para edição em lote.", "error")
        return redirect(url_for("gerenciar_clientes"))

    return render_template(
        "editar_lote.html",
        clientes=clientes_selecionados,
        meses=MESES_LISTA
    )


@app.route("/salvar_edicao_lote", methods=["POST"])
def salvar_edicao_lote():
    cliente_ids_raw = request.form.get("cliente_ids", "")
    mes = request.form.get("mes")
    novo_status = request.form.get("status")

    if not cliente_ids_raw or not mes or not novo_status:
        flash("Dados incompletos para edição em lote.", "error")
        return redirect(url_for("gerenciar_clientes"))

    cliente_ids = [int(id_str) for id_str in cliente_ids_raw.split(",") if id_str.strip().isdigit()]

    if not cliente_ids:
        flash("Nenhum cliente válido selecionado.", "error")
        return redirect(url_for("gerenciar_clientes"))

    clientes = carregar_clientes()
    for c in clientes:
        garantir_campos_padrao(c)
        if int(c.get("id", 0)) in cliente_ids and c.get("status_cliente", "ATIVO").upper() == "ATIVO":
            c["status_meses"][mes] = novo_status
            if novo_status != "PARCIAL":
                if mes in c.get("pagamentos_parciais", {}):
                    del c["pagamentos_parciais"][mes]

    salvar_clientes(clientes)
    flash(f"Status do mês {mes} atualizado para {novo_status} em {len(cliente_ids)} cliente(s).", "success")
    return redirect(url_for("gerenciar_clientes"))


@app.route("/editar_cliente/<int:cliente_id>", methods=["GET"])
def editar_cliente(cliente_id):
    clientes = carregar_clientes()
    for c in clientes:
        garantir_campos_padrao(c)

    cliente = next((c for c in clientes if int(c.get("id", 0)) == cliente_id), None)
    if not cliente:
        flash("Cliente não encontrado.", "error")
        return redirect(url_for("gerenciar_clientes"))

    return render_template(
        "editar_cliente.html",
        cliente=cliente,
        meses=MESES_LISTA
    )


@app.route("/salvar_edicao_completa/<int:cliente_id>", methods=["POST"])
def salvar_edicao_completa(cliente_id):
    clientes = carregar_clientes()
    for c in clientes:
        garantir_campos_padrao(c)

    cliente = next((c for c in clientes if int(c.get("id", 0)) == cliente_id), None)
    if not cliente:
        flash("Cliente não encontrado.", "error")
        return redirect(url_for("gerenciar_clientes"))

    cliente["nome_cliente"] = (request.form.get("nome_cliente") or "").strip()
    cliente["telefone"] = (request.form.get("telefone") or "").strip()
    cliente["valor_mensalidade"] = (request.form.get("valor_mensalidade") or cliente["valor_mensalidade"]).strip()
    cliente["pendencia"] = (request.form.get("pendencia") or "0,00").strip()  # ← NOVO

    for mes in MESES_LISTA:
        status_key = f"status_{mes}"
        pago_key = f"valor_pago_{mes}"

        if status_key in request.form:
            cliente["status_meses"][mes] = (request.form.get(status_key) or "EM ABERTO").strip().upper()

        valor_pago = (request.form.get(pago_key) or "").strip()
        if valor_pago:
            cliente["pagamentos_parciais"][mes] = valor_pago
        else:
            cliente["pagamentos_parciais"].pop(mes, None)

    salvar_clientes(clientes)
    flash("Cliente atualizado!", "success")
    return redirect(url_for("gerenciar_clientes"))


@app.route("/executar_cobranca", methods=["POST"])
def executar_cobranca():
    clientes = carregar_clientes()
    for c in clientes:
        garantir_campos_padrao(c)

    mes_ref = mes_referencia_anterior()
    print("Iniciando cobranca...")
    print(f"Mes de referencia: {mes_ref}")

    # ====================================================
    # IDENTIFICAR QUAL CAMPO FOI PREENCHIDO
    # ====================================================
    campos_prioridade = ["msg_13", "msg_18", "msg_livre"]
    campo_preenchido = None
    msg_digitada = ""
    for campo in campos_prioridade:
        valor = request.form.get(campo, "").strip()
        if valor:
            campo_preenchido = campo
            msg_digitada = valor
            break

    # ====================================================
    # CASO ESPECIAL: MENSAGEM LIVRE (msg_livre)
    # ====================================================
    if campo_preenchido == "msg_livre":
        print("Modo: Mensagem Livre (sem recibo, sem template, ignora status)")
        for cliente in clientes:
            if not cliente.get("selecao"):
                continue
            telefone = cliente.get("telefone", "")
            nome = cliente.get("nome_cliente", "")
            if not telefone:
                print(f"Cliente {nome} sem telefone, pulando.")
                continue

            print(f"Enviando mensagem livre para: {nome}")
            mensagem_final = msg_digitada.strip()
            ok = enviar_via_gzappy_api(telefone, mensagem_final, caminho_anexo_pdf=None)
            if not ok:
                print(f"FALHA ao enviar mensagem livre para: {nome} ({telefone})")

        flash("Mensagens livres enviadas!", "success")
        return redirect(url_for("index"))

    # ====================================================
    # DEMAIS CAMPOS (msg_13, msg_18)
    # ====================================================
    templates = {
        "msg_13": "Olá {NOME}, segue o recibo de cobrança da mensalidade referente ao mês {MES} no valor total em aberto de R$ {VALOR}.\n\nchave pix: 704.856.581-00",
        "msg_18": "Olá {NOME}, este é outro lembrete para você efetuar o pagamento de R$ {VALOR} da sua mensalidade!\n\nchave pix: 704.856.581-00",
    }

    template_fallback = "Olá {NOME}, segue o recibo referente ao mês {MES} no valor total em aberto de R$ {VALOR}."

    if campo_preenchido and campo_preenchido in templates:
        msg_padrao_template = templates[campo_preenchido]
    else:
        msg_padrao_template = template_fallback

    for cliente in clientes:
        if not cliente.get("selecao"):
            continue
        if str(cliente.get("status_cliente", "ATIVO")).upper() != "ATIVO":
            continue

        nome = cliente.get("nome_cliente", "")
        telefone = cliente.get("telefone", "")
        valor_mensalidade = cliente.get("valor_mensalidade", "0,00")
        pendencia = cliente.get("pendencia", "0,00")  # ← NOVO

        status_mes = cliente.get("status_meses", {}).get(mes_ref, "EM ABERTO").upper()

        if status_mes == "PAGO":
            continue

        # --- CÁLCULO DO VALOR TOTAL (MENSALIDADE + PENDÊNCIA) ---
        valor_base = str_para_float(valor_mensalidade)
        valor_pend = str_para_float(pendencia)

        if status_mes == "PARCIAL":
            pago_str = cliente.get("pagamentos_parciais", {}).get(mes_ref, "0,00")
            restante = max(0.0, valor_base - str_para_float(pago_str))
            valor_total = restante + valor_pend
        else:  # EM ABERTO
            valor_total = valor_base + valor_pend

        valor_final_str = float_para_str_br(valor_total)

        print(f"Processando: {nome} (Mensalidade: {valor_mensalidade}, Pendência: {pendencia}, Total: {valor_final_str})")

        caminho_pdf = gerar_recibo_pdf(nome, valor_final_str)

        msg_padrao = (
            msg_padrao_template
            .replace("{NOME}", nome)
            .replace("{MES}", mes_ref)
            .replace("{VALOR}", valor_final_str)
        ).strip()

        mensagem_final = msg_padrao
        if msg_digitada:
            mensagem_final += "\n\n" + msg_digitada.strip()

        print("Mensagem final enviada:", mensagem_final)

        ok = enviar_via_gzappy_api(telefone, mensagem_final, caminho_pdf)
        if not ok:
            print(f"FALHA ao enviar para: {nome} ({telefone})")

    flash("Cobranças enviadas!", "success")
    return redirect(url_for("index"))


@app.route("/recibos/<path:filename>")
def recibos(filename):
    return send_from_directory(PASTA_RECIBOS, filename)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")