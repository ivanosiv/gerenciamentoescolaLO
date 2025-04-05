
import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import create_engine, text
from io import BytesIO

# Conexão com Supabase via Pooler IPv4
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

        res = conn.execute(text("""
            SELECT escolas.nome, SUM(COALESCE(credito,0) - COALESCE(debito,0))
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

            dados = conn.execute(text("""
                SELECT data, mercadoria, descricao, debito, credito
                FROM lancamentos
                WHERE escola_id = :escola
                ORDER BY data DESC
            """), {"escola": escola_id}).fetchall()
            if dados:
                df = pd.DataFrame(dados, columns=["Data", "Mercadoria", "Descrição", "Débito", "Crédito"])
                df["Saldo"] = df["Crédito"] - df["Débito"]
                df["Saldo Acumulado"] = df["Saldo"][::-1].cumsum()[::-1]
                st.dataframe(df.style.format({"Débito": "R$ {:.2f}", "Crédito": "R$ {:.2f}", "Saldo": "R$ {:.2f}", "Saldo Acumulado": "R$ {:.2f}"}))
            else:
                st.info("Nenhum lançamento ainda.")

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
        st.markdown("### Escolas Cadastradas")
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
        st.markdown("### Mercadorias Cadastradas")
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
        st.markdown("### Descrições Cadastradas")
        for id_, texto in get_todos("descricoes", "texto"):
            col1, col2 = st.columns([4, 1])
            col1.write(texto)
            if col2.button("Remover", key=f"remover_desc_{id_}"):
                conn.execute(text("DELETE FROM descricoes WHERE id=:i"), {"i": id_})
                st.rerun()
else:
    tela_login()
