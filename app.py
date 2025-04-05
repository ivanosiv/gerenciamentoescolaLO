
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date
from io import BytesIO

# Conexão com Supabase
db_url = st.secrets["database"]["url"]
engine = create_engine(db_url)
conn = engine.connect()

# Sessão de login
if "usuario" not in st.session_state:
    st.session_state.usuario = None

def login(email, senha):
    query = text("SELECT * FROM usuarios WHERE LOWER(email) = LOWER(:email) AND senha = :senha")
    result = conn.execute(query, {"email": email, "senha": senha}).fetchone()
    return result

def cadastrar(nome, email, senha):
    try:
        conn.execute(text("INSERT INTO usuarios (nome, email, senha) VALUES (:n, :e, :s)"),
                     {"n": nome, "e": email, "s": senha})
        return True
    except:
        return False

def get_todos(tabela):
    return conn.execute(text(f"SELECT id, nome FROM {tabela}")).fetchall()

def get_descricoes():
    return conn.execute(text("SELECT id, texto FROM descricoes")).fetchall()

def exportar_excel_formatado():
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        escolas = get_todos("escolas")
        resumo = []
        for escola_id, escola_nome in escolas:
            query = text("""
                SELECT data, mercadoria, descricao, debito, credito
                FROM lancamentos
                WHERE escola_id = :id
                ORDER BY data
            """)
            dados = conn.execute(query, {"id": escola_id}).fetchall()
            df = pd.DataFrame(dados, columns=["Data", "Mercadoria", "Descrição", "Débito", "Crédito"])
            df["Débito"] = df["Débito"].fillna(0)
            df["Crédito"] = df["Crédito"].fillna(0)
            df["Saldo"] = df["Crédito"] - df["Débito"]
            df["Saldo Acumulado"] = df["Saldo"].cumsum()
            df.to_excel(writer, sheet_name=escola_nome[:31], index=False)
            saldo_final = df["Saldo"].sum()
            resumo.append({"Escola": escola_nome, "Saldo Final": round(saldo_final, 2)})
        df_resumo = pd.DataFrame(resumo)
        df_resumo.to_excel(writer, sheet_name="Resumo", index=False)
    st.download_button(
        label="📥 Baixar Excel com todas as escolas",
        data=buffer.getvalue(),
        file_name="Controle_Escolas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def tela_login():
    st.title("🔐 Login")
    with st.form("login"):
        email = st.text_input("Email")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            user = login(email, senha)
            if user:
                st.session_state.usuario = {"id": user[0], "nome": user[1]}
                st.rerun()
            else:
                st.error("Credenciais inválidas.")

    st.subheader("Criar conta")
    with st.form("cadastro"):
        nome = st.text_input("Nome")
        email2 = st.text_input("Email (cadastro)")
        senha2 = st.text_input("Senha (cadastro)", type="password")
        if st.form_submit_button("Cadastrar"):
            if cadastrar(nome, email2, senha2):
                st.success("Conta criada! Faça login.")
            else:
                st.error("Erro ao cadastrar")

# App principal
if st.session_state.usuario:
    st.sidebar.title(f"Olá, {st.session_state.usuario['nome']}")
    menu = st.sidebar.radio("Menu", [
        "Dashboard 📊", "Entregas", "Financeiro",
        "Exportar Excel", "Gestão de Escolas",
        "Gestão de Mercadorias", "Gestão de Descrições", "Sair"
    ])

    if menu == "Sair":
        st.session_state.usuario = None
        st.rerun()

    elif menu == "Dashboard 📊":
        st.title("📊 Visão Geral")
        ent = conn.execute(text("""
            SELECT mercadorias.nome, SUM(quantidade)
            FROM entregas
            JOIN mercadorias ON mercadorias.id = entregas.mercadoria_id
            GROUP BY mercadorias.nome
        """)).fetchall()
        if ent:
            df = pd.DataFrame(ent, columns=["Produto", "Quantidade"])
            st.bar_chart(df.set_index("Produto"))
        else:
            st.info("Nenhuma entrega registrada ainda.")

    elif menu == "Entregas":
        st.title("📦 Registrar Entrega")
        escolas = get_todos("escolas")
        mercadorias = get_todos("mercadorias")
        if escolas and mercadorias:
            escola = st.selectbox("Escola", [e[1] for e in escolas])
            escola_id = [e[0] for e in escolas if e[1] == escola][0]
            mercadoria = st.selectbox("Mercadoria", [m[1] for m in mercadorias])
            mercadoria_id = [m[0] for m in mercadorias if m[1] == mercadoria][0]
            data = st.date_input("Data", value=date.today())
            qtd = st.number_input("Quantidade", 0, 10000)
            if st.button("Registrar Entrega"):
                conn.execute(text("""
                    INSERT INTO entregas (escola_id, mercadoria_id, data, quantidade)
                    VALUES (:e, :m, :d, :q)
                """), {"e": escola_id, "m": mercadoria_id, "d": data, "q": qtd})
                st.success("Entrega registrada!")

    elif menu == "Financeiro":
        st.title("💰 Lançamento Financeiro")
        escolas = get_todos("escolas")
        mercadorias = get_todos("mercadorias")
        descricoes = get_descricoes()
        if escolas and mercadorias and descricoes:
            escola = st.selectbox("Escola", [e[1] for e in escolas])
            escola_id = [e[0] for e in escolas if e[1] == escola][0]
            mercadoria = st.selectbox("Mercadoria", [m[1] for m in mercadorias])
            descricao = st.selectbox("Descrição", [d[1] for d in descricoes])
            data = st.date_input("Data")
            debito = st.number_input("Débito", 0.0)
            credito = st.number_input("Crédito", 0.0)
            if st.button("Lançar"):
                conn.execute(text("""
                    INSERT INTO lancamentos (escola_id, data, mercadoria, descricao, debito, credito)
                    VALUES (:e, :d, :m, :desc, :deb, :cred)
                """), {
                    "e": escola_id, "d": data, "m": mercadoria, "desc": descricao,
                    "deb": debito, "cred": credito
                })
                st.success("Lançamento registrado!")

    elif menu == "Exportar Excel":
        st.title("📤 Exportar por Escola")
        exportar_excel_formatado()

    elif menu == "Gestão de Escolas":
        st.title("🏫 Gestão de Escolas")
        with st.form("nova_escola"):
            nova = st.text_input("Nova Escola")
            if st.form_submit_button("Adicionar"):
                try:
                    conn.execute(text("INSERT INTO escolas (nome) VALUES (:n)"), {"n": nova})
                    st.success("Escola adicionada!")
                except:
                    st.error("Erro: escola já existe.")
        for id_, nome in get_todos("escolas"):
            col1, col2 = st.columns([4, 1])
            col1.write(nome)
            if col2.button("Remover", key=f"remover_escola_{id_}"):
                conn.execute(text("DELETE FROM escolas WHERE id=:i"), {"i": id_})
                st.rerun()

    elif menu == "Gestão de Mercadorias":
        st.title("📦 Gestão de Mercadorias")
        with st.form("nova_mercadoria"):
            nova = st.text_input("Nova Mercadoria")
            if st.form_submit_button("Adicionar"):
                try:
                    conn.execute(text("INSERT INTO mercadorias (nome) VALUES (:n)"), {"n": nova})
                    st.success("Mercadoria adicionada!")
                except:
                    st.error("Erro: mercadoria já existe.")
        for id_, nome in get_todos("mercadorias"):
            col1, col2 = st.columns([4, 1])
            col1.write(nome)
            if col2.button("Remover", key=f"remover_merc_{id_}"):
                conn.execute(text("DELETE FROM mercadorias WHERE id=:i"), {"i": id_})
                st.rerun()

    elif menu == "Gestão de Descrições":
        st.title("📝 Gestão de Descrições")
        with st.form("nova_descricao"):
            nova = st.text_input("Nova Descrição")
            if st.form_submit_button("Adicionar"):
                try:
                    conn.execute(text("INSERT INTO descricoes (texto) VALUES (:t)"), {"t": nova})
                    st.success("Descrição adicionada!")
                except:
                    st.error("Erro: descrição já existe.")
        for id_, texto in get_descricoes():
            col1, col2 = st.columns([4, 1])
            col1.write(texto)
            if col2.button("Remover", key=f"remover_desc_{id_}"):
                conn.execute(text("DELETE FROM descricoes WHERE id=:i"), {"i": id_})
                st.rerun()

else:
    tela_login()
