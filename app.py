
import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import create_engine, text
from io import BytesIO

# Conexão com Supabase
db_url = st.secrets["database"]["url"]
engine = create_engine(db_url)
conn = engine.connect()

# =================== Funções utilitárias ===================

def get_todos(tabela, campo="nome"):
    result = conn.execute(text(f"SELECT id, {campo} FROM {tabela} ORDER BY id")).fetchall()
    return result

def usuario_existe(email, senha):
    return conn.execute(text(
        "SELECT * FROM usuarios WHERE LOWER(email) = LOWER(:email) AND senha = :senha"
    ), {"email": email, "senha": senha}).fetchone()

def cadastrar_usuario(nome, email, senha):
    try:
        conn.execute(text("INSERT INTO usuarios (nome, email, senha) VALUES (:n, :e, :s)"),
                     {"n": nome, "e": email, "s": senha})
        return True
    except:
        return False

# =================== Interface ===================

if "usuario" not in st.session_state:
    st.session_state.usuario = None

def tela_login():
    st.title("🔐 Login")
    with st.form("login"):
        email = st.text_input("Email")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            user = usuario_existe(email, senha)
            if user:
                st.session_state.usuario = {"id": user[0], "nome": user[1]}
                st.rerun()
            else:
                st.error("Email ou senha incorretos.")
    st.markdown("## Criar nova conta")
    with st.form("cadastro"):
        nome = st.text_input("Nome")
        email = st.text_input("Email")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Cadastrar"):
            if cadastrar_usuario(nome, email, senha):
                st.success("Usuário cadastrado!")
            else:
                st.error("Erro: email já utilizado.")

# =================== App Principal ===================

if st.session_state.usuario:
    st.sidebar.title(f"Bem-vindo, {st.session_state.usuario['nome']}!")
    menu = st.sidebar.radio("Menu", [
        "Dashboard 📊", "Entregas", "Financeiro",
        "Exportar Excel", "Gestão de Escolas", "Gestão de Mercadorias", "Gestão de Descrições", "Sair"
    ])

    if menu == "Sair":
        st.session_state.usuario = None
        st.rerun()

    elif menu == "Dashboard 📊":
        st.title("📊 Visão Geral")
        col1, col2 = st.columns(2)

        # Entregas por mercadoria
        res = conn.execute(text("""
            SELECT mercadorias.nome, SUM(entregas.quantidade)
            FROM entregas
            JOIN mercadorias ON mercadorias.id = entregas.mercadoria_id
            GROUP BY mercadorias.nome
        """)).fetchall()
        if res:
            df_ent = pd.DataFrame(res, columns=["Mercadoria", "Quantidade"])
            col1.subheader("Entregas por Produto")
            col1.bar_chart(df_ent.set_index("Mercadoria"))
        else:
            col1.info("Nenhuma entrega registrada.")

        # Saldo por escola
        res = conn.execute(text("""
            SELECT escolas.nome, SUM(COALESCE(lancamentos.credito,0) - COALESCE(lancamentos.debito,0))
            FROM lancamentos
            JOIN escolas ON escolas.id = lancamentos.escola_id
            GROUP BY escolas.nome
        """)).fetchall()
        if res:
            df_fin = pd.DataFrame(res, columns=["Escola", "Saldo"])
            col2.subheader("Saldo por Escola")
            col2.bar_chart(df_fin.set_index("Escola"))
        else:
            col2.info("Sem lançamentos financeiros.")

        # Saldo final
        st.subheader("Resumo de Saldos")
        resumo = []
        for e_id, nome in get_todos("escolas"):
            s = conn.execute(text("SELECT SUM(COALESCE(credito,0) - COALESCE(debito,0)) FROM lancamentos WHERE escola_id=:id"),
                             {"id": e_id}).scalar() or 0
            resumo.append({"Escola": nome, "Saldo Final": round(s, 2)})
        st.dataframe(pd.DataFrame(resumo))

    elif menu == "Entregas":
        st.title("📦 Registro de Entregas")
        escolas = get_todos("escolas")
        mercadorias = get_todos("mercadorias")
        if escolas and mercadorias:
            escola = st.selectbox("Escola", [e[1] for e in escolas])
            escola_id = dict(escolas)[escola]
            mercadoria = st.selectbox("Mercadoria", [m[1] for m in mercadorias])
            mercadoria_id = dict(mercadorias)[mercadoria]
            data = st.date_input("Data", value=date.today())
            quantidade = st.number_input("Quantidade", 0, 10000, 0)
            if st.button("Registrar Entrega"):
                conn.execute(text("""
                    INSERT INTO entregas (escola_id, mercadoria_id, data, quantidade)
                    VALUES (:e, :m, :d, :q)
                """), {"e": escola_id, "m": mercadoria_id, "d": data, "q": quantidade})
                st.success("Entrega registrada.")

    elif menu == "Financeiro":
        st.title("💰 Lançamentos Financeiros")
        escolas = get_todos("escolas")
        mercadorias = get_todos("mercadorias")
        descricoes = get_todos("descricoes", "texto")
        if escolas and mercadorias and descricoes:
            escola = st.selectbox("Escola", [e[1] for e in escolas])
            escola_id = dict(escolas)[escola]
            mercadoria = st.selectbox("Mercadoria", [m[1] for m in mercadorias])
            descricao = st.selectbox("Descrição", [d[1] for d in descricoes])
            data = st.date_input("Data")
            col1, col2 = st.columns(2)
            with col1:
                debito = st.number_input("Débito", 0.0)
            with col2:
                credito = st.number_input("Crédito", 0.0)
            if st.button("Registrar Lançamento"):
                conn.execute(text("""
                    INSERT INTO lancamentos (escola_id, data, mercadoria, descricao, debito, credito)
                    VALUES (:e, :d, :m, :desc, :deb, :cred)
                """), {
                    "e": escola_id, "d": data, "m": mercadoria, "desc": descricao,
                    "deb": debito, "cred": credito
                })
                st.success("Lançamento registrado.")
                st.rerun()

    elif menu == "Exportar Excel":
        st.title("📥 Exportar Dados")
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            entregas = conn.execute(text("""
                SELECT escolas.nome, mercadorias.nome, entregas.data, entregas.quantidade
                FROM entregas
                JOIN escolas ON escolas.id = entregas.escola_id
                JOIN mercadorias ON mercadorias.id = entregas.mercadoria_id
                ORDER BY entregas.data DESC
            """)).fetchall()
            df1 = pd.DataFrame(entregas, columns=["Escola", "Mercadoria", "Data", "Quantidade"])
            df1.to_excel(writer, sheet_name="Entregas", index=False)

            lancs = conn.execute(text("""
                SELECT escolas.nome, data, mercadoria, descricao, debito, credito
                FROM lancamentos
                JOIN escolas ON escolas.id = lancamentos.escola_id
                ORDER BY data DESC
            """)).fetchall()
            df2 = pd.DataFrame(lancs, columns=["Escola", "Data", "Mercadoria", "Descrição", "Débito", "Crédito"])
            df2["Saldo"] = df2["Crédito"].fillna(0) - df2["Débito"].fillna(0)
            df2.to_excel(writer, sheet_name="Financeiro", index=False)

        st.download_button("📥 Baixar Excel Completo", data=buffer.getvalue(),
                           file_name="Controle_Escolas.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    tela_login()
