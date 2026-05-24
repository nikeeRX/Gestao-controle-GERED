import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timedelta
import os
import requests

# ==========================================
# 1. CONFIGURAÇÃO DO BANCO DE DADOS
# ==========================================
db_url = os.getenv("DATABASE_URL", "sqlite:///banco_local.db")
# O SQLAlchemy exige 'postgresql://' ao invés de 'postgres://' (padrão antigo do Railway)
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Demanda(Base):
    __tablename__ = 'demandas'
    id = Column(Integer, primary_key=True)
    area = Column(String(50), nullable=False)
    descricao = Column(Text, nullable=False)
    prioridade = Column(String(20), nullable=False)
    data_solicitacao = Column(Date, default=datetime.utcnow().date)
    data_inicio = Column(Date, nullable=True)
    data_prevista = Column(Date, nullable=False)
    data_conclusao = Column(Date, nullable=True)
    checklists = relationship("Checklist", backref="demanda", cascade="all, delete-orphan")

class Checklist(Base):
    __tablename__ = 'checklists'
    id = Column(Integer, primary_key=True)
    demanda_id = Column(Integer, ForeignKey('demandas.id'))
    passo = Column(String(200), nullable=False)
    concluido = Column(Boolean, default=False)

# Cria as tabelas automaticamente se não existirem
Base.metadata.create_all(engine)

# ==========================================
# 2. ROBÔ DO WHATSAPP (SEGUNDO PLANO)
# ==========================================
@st.cache_resource
def iniciar_robo_whatsapp():
    from apscheduler.schedulers.background import BackgroundScheduler
    
    def enviar_resumo():
        session = SessionLocal()
        hoje = datetime.utcnow().date()
        amanha = hoje + timedelta(days=1)
        
        ativas = session.query(Demanda).filter(Demanda.data_conclusao == None).all()
        if not ativas:
            session.close()
            return
            
        vencendo = [d for d in ativas if d.data_prevista == amanha]
        
        msg = f"🚀 *Resumo do Sistema-JPMS*\n\nVocê tem {len(ativas)} demandas em andamento.\n"
        if vencendo:
            msg += f"\n⚠️ *VENCENDO AMANHÃ:*\n"
            for d in vencendo:
                msg += f"- [{d.area}] {d.descricao[:30]}...\n"
                
        # Puxa os dados das Variáveis do Railway
        numeros = [os.getenv("WHATSAPP_NUMERO_SEU"), os.getenv("WHATSAPP_NUMERO_GERENTE")]
        chaves = [os.getenv("WHATSAPP_API_KEY_SEU"), os.getenv("WHATSAPP_API_KEY_GERENTE")]
        
        for num, key in zip(numeros, chaves):
            if num and key:
                params = {'phone': num, 'text': msg, 'apikey': key}
                requests.get("https://api.callmebot.com/whatsapp.php", params=params)
                
        session.close()

    scheduler = BackgroundScheduler()
    # Roda todos os dias às 08:00
    scheduler.add_job(func=enviar_resumo, trigger="cron", hour=8, minute=0)
    scheduler.start()
    return scheduler

# Inicia o robô junto com o app
iniciar_robo_whatsapp()

# ==========================================
# 3. INTERFACE WEB (SISTEMA-JPMS)
# ==========================================
st.set_page_config(page_title="Sistema-JPMS | Demandas", layout="wide")
st.title("🚀 Sistema-JPMS - Gestão de Demandas")

menu = st.sidebar.radio("Navegação", ["Painel de Demandas", "Cadastrar Nova Demanda"])
session = SessionLocal()

if menu == "Painel de Demandas":
    st.subheader("Demandas em Andamento")
    demandas_ativas = session.query(Demanda).filter(Demanda.data_conclusao == None).order_by(Demanda.data_prevista).all()
    
    if not demandas_ativas:
        st.success("Tudo limpo! Nenhuma demanda pendente no momento.")
    else:
        for d in demandas_ativas:
            # Expander cria aquela "sanfona" que você clica e abre os detalhes
            with st.expander(f"[{d.area}] {d.descricao[:50]}... (Prev: {d.data_prevista.strftime('%d/%m/%Y')})"):
                cols = st.columns(3)
                cols[0].write(f"**Prioridade:** {d.prioridade}")
                cols[1].write(f"**Início:** {d.data_inicio.strftime('%d/%m/%Y') if d.data_inicio else '-'}")
                cols[2].write(f"**Solicitado em:** {d.data_solicitacao.strftime('%d/%m/%Y')}")
                st.write(f"**Descrição Completa:** {d.descricao}")
                
                # Checklists interativos
                st.markdown("---")
                st.write("**Checklist de Tarefas:**")
                for check in d.checklists:
                    concluido = st.checkbox(check.passo, value=check.concluido, key=f"check_{check.id}")
                    if concluido != check.concluido:
                        check.concluido = concluido
                        session.commit()
                        st.rerun()
                
                # Botão para fechar a demanda
                st.markdown("---")
                if st.button("✅ Encerrar Demanda", key=f"encerrar_{d.id}"):
                    d.data_conclusao = datetime.utcnow().date()
                    session.commit()
                    st.rerun()

elif menu == "Cadastrar Nova Demanda":
    st.subheader("Nova Demanda")
    
    with st.form("form_nova_demanda"):
        col1, col2 = st.columns(2)
        area = col1.selectbox("Área Responsável", ["CODER", "COCAP", "CONEC", "GERED", "EXTERNO"])
        prioridade = col2.selectbox("Prioridade", ["Mínimo", "Médio", "Alto", "Extremo"], index=1)
        
        descricao = st.text_area("Descrição da Demanda")
        
        col3, col4 = st.columns(2)
        data_inicio = col3.date_input("Data de Início", value=None)
        data_prevista = col4.date_input("Data Prevista para Conclusão")
        
        st.write("---")
        # O truque aqui é usar um campo de texto único e separar as linhas por 'Enter'
        passos_texto = st.text_area("Passos do Checklist (Digite uma etapa por linha)", 
                                    placeholder="- Levantar requisitos\n- Validar com o gerente\n- Executar a ação")
        
        salvar = st.form_submit_button("Salvar Demanda", use_container_width=True)
        
        if salvar:
            nova_dem = Demanda(
                area=area,
                descricao=descricao,
                prioridade=prioridade,
                data_inicio=data_inicio,
                data_prevista=data_prevista
            )
            session.add(nova_dem)
            session.flush() # Salva temporariamente para gerar o ID
            
            # Divide o texto do checklist a cada quebra de linha
            if passos_texto:
                linhas = passos_texto.split('\n')
                for linha in linhas:
                    if linha.strip():
                        novo_check = Checklist(demanda_id=nova_dem.id, passo=linha.strip())
                        session.add(novo_check)
            
            session.commit()
            st.success("Demanda cadastrada com sucesso! Vá para o Painel para acompanhar.")

session.close()
