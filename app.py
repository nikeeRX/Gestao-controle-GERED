import os
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuração do Banco de Dados no Railway
db_url = os.getenv("DATABASE_URL", "sqlite:///banco_local.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==========================================
# MODELOS DE BANCO DE DADOS
# ==========================================
class Demanda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    prioridade = db.Column(db.String(20), nullable=False)
    data_solicitacao = db.Column(db.Date, default=datetime.utcnow().date)
    data_inicio = db.Column(db.Date, nullable=True)
    data_prevista = db.Column(db.Date, nullable=False)
    data_conclusao = db.Column(db.Date, nullable=True)
    
    checklists = db.relationship('Checklist', backref='demanda', cascade='all, delete-orphan', lazy=True)

class Checklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    demanda_id = db.Column(db.Integer, db.ForeignKey('demanda.id'), nullable=False)
    passo = db.Column(db.String(200), nullable=False)
    concluido = db.Column(db.Boolean, default=False)

# ==========================================
# ROTAS E LÓGICA DO SISTEMA
# ==========================================
@app.route('/')
def index():
    demandas_ativas = Demanda.query.filter_by(data_conclusao=None).order_by(Demanda.data_prevista).all()
    
    # --- LÓGICA DO RELATÓRIO DO WHATSAPP ---
    hoje = datetime.utcnow().date()
    amanha = hoje + timedelta(days=1)
    vencendo = [d for d in demandas_ativas if d.data_prevista == amanha]
    
    texto_whats = "🚀 *Resumo Diário - Sistema-JPMS*\n\n"
    texto_whats += f"Temos *{len(demandas_ativas)} demandas* em andamento no trampo.\n"
    
    if vencendo:
        texto_whats += "\n⚠️ *VENCENDO AMANHÃ:*\n"
        for d in vencendo:
            texto_whats += f"- [{d.area}] {d.descricao[:40]}...\n"
    else:
        texto_whats += "\n✅ Nenhuma demanda vencendo amanhã!\n"
        
    # Transforma o texto em formato de link de internet
    texto_codificado = urllib.parse.quote(texto_whats)
    link_whatsapp = f"https://wa.me/?text={texto_codificado}"
    # ---------------------------------------
    
    return render_template('index.html', demandas=demandas_ativas, link_whatsapp=link_whatsapp)

@app.route('/nova_demanda', methods=['GET', 'POST'])
def nova_demanda():
    if request.method == 'POST':
        nova_dem = Demanda(
            area=request.form['area'],
            descricao=request.form['descricao'],
            prioridade=request.form['prioridade'],
            data_inicio=datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date() if request.form['data_inicio'] else None,
            data_prevista=datetime.strptime(request.form['data_prevista'], '%Y-%m-%d').date()
        )
        db.session.add(nova_dem)
        db.session.flush() 
        
        passos = request.form.getlist('passo_checklist[]')
        for passo in passos:
            if passo.strip():
                novo_check = Checklist(demanda_id=nova_dem.id, passo=passo)
                db.session.add(novo_check)
                
        db.session.commit()
        return redirect(url_for('index'))
        
    return render_template('nova_demanda.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
