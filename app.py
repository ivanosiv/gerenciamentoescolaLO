import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
from io import BytesIO

# ========== BANCO DE DADOS ==========
conn = sqlite3.connect("dados.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    email TEXT UNIQUE,
    senha TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS escolas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS mercadorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS descricoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto TEXT UNIQUE
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS entregas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    escola_id INTEGER,
    mercadoria_id INTEGER,
    data TEXT,
    quantidade INTEGER,
    FOREIGN KEY (escola_id) REFERENCES escolas(id),
    FOREIGN KEY (mercadoria_id) REFERENCES mercadorias(id)
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS lancamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    escola_id INTEGER,
    data TEXT,
    mercadoria TEXT,
    descricao TEXT,
    debito REAL,
    credito REAL,
    FOREIGN KEY (escola_id) REFERENCES escolas(id)
)
""")
conn.commit()
def get_escolas():
    cursor.execute("SELECT id, nome FROM escolas")
    return cursor.fetchall()

def get_mercadorias():
    cursor.execute("SELECT id, nome FROM mercadorias")
    return cursor.fetchall()

def get_descricoes():
    cursor.execute("SELECT id, texto FROM descricoes")
    return cursor.fetchall()

def usuario_existe(email, senha):
    cursor.execute("SELECT * FROM usuarios WHERE email=? AND senha=?", (email, senha))
    return cursor.fetchone()

def cadastrar_usuario(nome, email, senha):
    try:
        cursor.execute("INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)", (nome, email, senha))
        conn.commit()
        return True
    except:
        return False

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

        # Gráfico: Entregas por Produto
        cursor.execute("""
            SELECT mercadorias.nome, SUM(entregas.quantidade)
            FROM entregas
            JOIN mercadorias ON mercadorias.id = entregas.mercadoria_id
            GROUP BY mercadorias.nome
        """)
        dados_merc = cursor.fetchall()
        if dados_merc:
            df_ent = pd.DataFrame(dados_merc, columns=["Mercadoria", "Quantidade"])
            col1.subheader("Entregas por Tipo de Produto")
            col1.bar_chart(df_ent.set_index("Mercadoria"))
        else:
            col1.info("Nenhuma entrega registrada.")

        # Gráfico: Saldos por Escola
        cursor.execute("""
            SELECT escolas.nome, SUM(COALESCE(lancamentos.credito,0) - COALESCE(lancamentos.debito,0))
            FROM lancamentos
            JOIN escolas ON escolas.id = lancamentos.escola_id
            GROUP BY escolas.nome
        """)
        dados_fin = cursor.fetchall()
        if dados_fin:
            df_fin = pd.DataFrame(dados_fin, columns=["Escola", "Saldo"])
            col2.subheader("Saldo Financeiro por Escola")
            col2.bar_chart(df_fin.set_index("Escola"))
        else:
            col2.info("Sem lançamentos financeiros.")

        # Tabela de Saldos Finais
        st.subheader("Saldo Final por Escola")
        resumo = []
        for id_, nome in get_escolas():
            cursor.execute("SELECT SUM(COALESCE(credito,0) - COALESCE(debito,0)) FROM lancamentos WHERE escola_id=?", (id_,))
            saldo = cursor.fetchone()[0] or 0
            resumo.append({"Escola": nome, "Saldo Final": round(saldo, 2)})
        st.dataframe(pd.DataFrame(resumo))

    elif menu == "Entregas":
        st.title("📦 Registro de Entregas")
        escolas = get_escolas()
        mercadorias = get_mercadorias()
        if escolas and mercadorias:
            escola = st.selectbox("Escola", [e[1] for e in escolas])
            escola_id = [e[0] for e in escolas if e[1] == escola][0]
            mercadoria = st.selectbox("Mercadoria", [m[1] for m in mercadorias])
            mercadoria_id = [m[0] for m in mercadorias if m[1] == mercadoria][0]
            data = st.date_input("Data", value=date.today())
            quantidade = st.number_input("Quantidade", 0, 10000, 0)
            if st.button("Registrar Entrega"):
                cursor.execute("INSERT INTO entregas (escola_id, mercadoria_id, data, quantidade) VALUES (?, ?, ?, ?)",
                               (escola_id, mercadoria_id, data.isoformat(), quantidade))
                conn.commit()
                st.success("Entrega registrada com sucesso.")
        else:
            st.warning("Cadastre escolas e mercadorias antes.")

    elif menu == "Financeiro":
        st.title("💰 Lançamentos Financeiros")
        escolas = get_escolas()
        mercadorias = get_mercadorias()
        descricoes = get_descricoes()
        if escolas and mercadorias and descricoes:
            escola = st.selectbox("Escola", [e[1] for e in escolas])
            escola_id = [e[0] for e in escolas if e[1] == escola][0]
            mercadoria = st.selectbox("Mercadoria", [m[1] for m in mercadorias])
            descricao = st.selectbox("Descrição", [d[1] for d in descricoes])
            data = st.date_input("Data")
            col1, col2 = st.columns(2)
            with col1:
                debito = st.number_input("Débito", 0.0)
            with col2:
                credito = st.number_input("Crédito", 0.0)
            if st.button("Registrar Lançamento"):
                cursor.execute("INSERT INTO lancamentos (escola_id, data, mercadoria, descricao, debito, credito) VALUES (?, ?, ?, ?, ?, ?)",
                               (escola_id, data.isoformat(), mercadoria, descricao, debito, credito))
                conn.commit()
                st.success("Lançamento registrado com sucesso.")
                st.rerun()

            cursor.execute("SELECT data, mercadoria, descricao, debito, credito FROM lancamentos WHERE escola_id=? ORDER BY data DESC", (escola_id,))
            dados = cursor.fetchall()
            if dados:
                df = pd.DataFrame(dados, columns=["Data", "Mercadoria", "Descrição", "Débito", "Crédito"])
                df["Saldo"] = df["Crédito"] - df["Débito"]
                df["Saldo Acumulado"] = df["Saldo"][::-1].cumsum()[::-1]
                st.dataframe(df.style.format({"Débito": "R$ {:.2f}", "Crédito": "R$ {:.2f}", "Saldo": "R$ {:.2f}", "Saldo Acumulado": "R$ {:.2f}"}))
            else:
                st.info("Nenhum lançamento ainda.")
        else:
            st.warning("Cadastre escolas, mercadorias e descrições antes.")
    elif menu == "Exportar Excel":
        st.title("📥 Exportar Dados")
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            # Exportar entregas
            cursor.execute("""
            SELECT escolas.nome, mercadorias.nome, entregas.data, entregas.quantidade
            FROM entregas
            JOIN escolas ON escolas.id = entregas.escola_id
            JOIN mercadorias ON mercadorias.id = entregas.mercadoria_id
            ORDER BY entregas.data DESC
            """)
            df1 = pd.DataFrame(cursor.fetchall(), columns=["Escola", "Mercadoria", "Data", "Quantidade"])
            df1.to_excel(writer, sheet_name="Entregas", index=False)

            # Exportar lançamentos
            cursor.execute("""
            SELECT escolas.nome, data, mercadoria, descricao, debito, credito
            FROM lancamentos
            JOIN escolas ON escolas.id = lancamentos.escola_id
            ORDER BY data DESC
            """)
            df2 = pd.DataFrame(cursor.fetchall(), columns=["Escola", "Data", "Mercadoria", "Descrição", "Débito", "Crédito"])
            df2["Saldo"] = df2["Crédito"].fillna(0) - df2["Débito"].fillna(0)
            df2.to_excel(writer, sheet_name="Financeiro", index=False)

        st.download_button("📥 Baixar Excel Completo", data=buffer.getvalue(),
                           file_name="dados_completos.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    elif menu == "Gestão de Escolas":
        st.title("🏫 Gestão de Escolas")
        with st.form("nova_escola"):
            nova = st.text_input("Nova Escola")
            if st.form_submit_button("Adicionar"):
                try:
                    cursor.execute("INSERT INTO escolas (nome) VALUES (?)", (nova,))
                    conn.commit()
                    st.success("Escola adicionada!")
                except:
                    st.error("Erro: escola já existe.")
        st.markdown("### Escolas Cadastradas")
        for id_, nome in get_escolas():
            col1, col2 = st.columns([4, 1])
            col1.write(nome)
            if col2.button("Remover", key=f"remover_escola_{id_}"):
                cursor.execute("DELETE FROM escolas WHERE id=?", (id_,))
                conn.commit()
                st.success(f"Escola '{nome}' removida.")
                st.rerun()

    elif menu == "Gestão de Mercadorias":
        st.title("📦 Gestão de Mercadorias")
        with st.form("nova_mercadoria"):
            nova = st.text_input("Nova Mercadoria")
            if st.form_submit_button("Adicionar"):
                try:
                    cursor.execute("INSERT INTO mercadorias (nome) VALUES (?)", (nova,))
                    conn.commit()
                    st.success("Mercadoria adicionada!")
                except:
                    st.error("Erro: mercadoria já existe.")
        st.markdown("### Mercadorias Cadastradas")
        for id_, nome in get_mercadorias():
            col1, col2 = st.columns([4, 1])
            col1.write(nome)
            if col2.button("Remover", key=f"remover_merc_{id_}"):
                cursor.execute("DELETE FROM mercadorias WHERE id=?", (id_,))
                conn.commit()
                st.success(f"Mercadoria '{nome}' removida.")
                st.rerun()

    elif menu == "Gestão de Descrições":
        st.title("📝 Gestão de Descrições")
        with st.form("nova_descricao"):
            nova = st.text_input("Nova Descrição")
            if st.form_submit_button("Adicionar"):
                try:
                    cursor.execute("INSERT INTO descricoes (texto) VALUES (?)", (nova,))
                    conn.commit()
                    st.success("Descrição adicionada!")
                except:
                    st.error("Erro: descrição já existe.")
        st.markdown("### Descrições Cadastradas")
        for id_, texto in get_descricoes():
            col1, col2 = st.columns([4, 1])
            col1.write(texto)
            if col2.button("Remover", key=f"remover_desc_{id_}"):
                cursor.execute("DELETE FROM descricoes WHERE id=?", (id_,))
                conn.commit()
                st.success(f"Descrição '{texto}' removida.")
                st.rerun()
else:
    tela_login()
