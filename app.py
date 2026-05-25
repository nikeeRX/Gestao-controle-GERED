import os
import urllib.parse
import io
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from fpdf import FPDF

app = Flask(__name__)

# ==========================================
# 1. CONFIGURAÇÃO DO BANCO DE DADOS
# ==========================================
db_url = os.getenv("DATABASE_URL", "sqlite:///banco_local.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==========================================
# 2. MODELOS DE BANCO DE DADOS
# ==========================================
class Demanda(db.Model):
    __tablename__ = 'demandas'
    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    prioridade = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Pendente')
    data_solicitacao = db.Column(db.Date, default=datetime.utcnow().date)
    data_inicio = db.Column(db.Date, nullable=True)
    data_prevista = db.Column(db.Date, nullable=False)
    data_conclusao = db.Column(db.Date, nullable=True)
    checklists = db.relationship('Checklist', backref='demanda', cascade='all, delete-orphan', lazy=True)

class Checklist(db.Model):
    __tablename__ = 'checklists'
    id = db.Column(db.Integer, primary_key=True)
    demanda_id = db.Column(db.Integer, db.ForeignKey('demandas.id'), nullable=False)
    passo = db.Column(db.String(200), nullable=False)
    concluido = db.Column(db.Boolean, default=False)

class AtaReuniao(db.Model):
    __tablename__ = 'atas_reuniao'
    id = db.Column(db.Integer, primary_key=True)
    assunto = db.Column(db.String(200), nullable=False)
    data_criacao = db.Column(db.Date, default=datetime.utcnow().date)
    topicos = db.Column(db.Text, nullable=False)

with app.app_context():
    db.create_all()

# ==========================================
# 3. CSS GLOBAL E DESIGN MOBILE (APP STYLE)
# ==========================================
ESTILO_APP = """
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">
<style>
    body { background-color: #f4f6f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding-top: 65px; padding-bottom: 85px; }
    
    /* Header Fixo superior */
    .app-header { position: fixed; top: 0; left: 0; right: 0; background: #ffffff; height: 60px; display: flex; align-items: center; justify-content: center; z-index: 1030; box-shadow: 0 1px 3px rgba(0,0,0,0.05); font-weight: 700; font-size: 1.15rem; color: #1d1d1f; }
    
    /* Menu Fixo Inferior */
    .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: #ffffff; height: 65px; display: flex; justify-content: space-around; align-items: center; z-index: 1030; box-shadow: 0 -2px 10px rgba(0,0,0,0.04); padding-bottom: env(safe-area-inset-bottom); border-top: 1px solid #f1f1f1; }
    .nav-item { text-decoration: none; color: #8e8e93; display: flex; flex-direction: column; align-items: center; font-size: 0.75rem; flex: 1; font-weight: 500; }
    .nav-item.active { color: #007aff; }
    .nav-icon { font-size: 1.35rem; margin-bottom: 2px; }
    
    /* Container Limitador */
    .container-app { max-width: 600px; margin: auto; padding: 0 15px; }
    
    /* Cards Arredondados Mobile */
    .card-app { background: #fff; border-radius: 16px; border: none; box-shadow: 0 2px 8px rgba(0,0,0,0.03); margin-bottom: 14px; overflow: hidden; }
    .card-app-header { padding: 15px; border-bottom: 1px solid #f8f9fa; cursor: pointer; }
    
    /* Botão Flutuante Direito (FAB) */
    .fab { position: fixed; bottom: 85px; right: 20px; background: #007aff; color: white; width: 56px; height: 56px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 26px; box-shadow: 0 4px 12px rgba(0,122,255,0.35); text-decoration: none; z-index: 1020; }
    .fab:active { transform: scale(0.95); color: white; }
    
    /* Form Customizations */
    .form-control, .form-select { border-radius: 12px; padding: 12px; border: 1px solid #e5e5ea; background-color: #fcfcfc; font-size: 0.95rem; }
    .form-control:focus, .form-select:focus { border-color: #007aff; box-shadow: 0 0 0 0.25rem rgba(0,122,255,0.1); }
    .btn-app { border-radius: 12px; padding: 12px; font-weight: 600; font-size: 0.95rem; }
</style>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
"""

MENU_INFERIOR = """
<div class="bottom-nav">
    <a href="/" class="nav-item {% if page == 'demandas' %}active{% endif %}">
        <i class="bi bi-card-checklist nav-icon"></i>
        <span>Demandas</span>
    </a>
    <a href="/atas" class="nav-item {% if page == 'atas' %}active{% endif %}">
        <i class="bi bi-journal-text nav-icon"></i>
        <span>Atas</span>
    </a>
</div>
"""

# ==========================================
# 4. TEMPLATES HTML COMPATÍVEIS
# ==========================================
TELA_PRINCIPAL = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>JPMS System | Demandas</title>
    """ + ESTILO_APP + """
</head>
<body>
    <div class="app-header">🚀 JPMS System</div>
    
    <div class="container-app mt-3">
        <a href="{{ link_whatsapp }}" target="_blank" class="btn btn-success btn-app w-100 mb-4 shadow-sm">
            <i class="bi bi-whatsapp"></i> Enviar Resumo no WhatsApp
        </a>
        
        <div class="accordion" id="accordionDemandas">
            {% for demanda in demandas %}
            
            {% set total_chk = demanda.checklists|length %}
            {% set ns = namespace(concluidos=0) %}
            {% for chk in demanda.checklists %}
                {% if chk.concluido %}{% set ns.concluidos = ns.concluidos + 1 %}{% endif %}
            {% endfor %}
            {% set percentual = (ns.concluidos / total_chk * 100)|round|int if total_chk > 0 else 0 %}

            <div class="card-app">
                <div class="card-app-header" data-bs-toggle="collapse" data-bs-target="#collapse{{ demanda.id }}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="me-2">
                            <span class="badge bg-dark mb-1">{{ demanda.area }}</span>
                            {% if demanda.prioridade == 'Extremo' %}<span class="badge bg-danger">🔴 Extremo</span>
                            {% elif demanda.prioridade == 'Alto' %}<span class="badge bg-warning text-dark">🟡 Alto</span>
                            {% elif demanda.prioridade == 'Médio' %}<span class="badge bg-info text-dark">🔵 Médio</span>
                            {% else %}<span class="badge bg-secondary">🟢 Mínimo</span>{% endif %}
                            <h6 class="mt-2 mb-1 fw-bold text-dark">{{ demanda.descricao[:55] }}...</h6>
                        </div>
                        <div class="text-end" style="min-width: 95px;">
                            {% if demanda.status == 'Finalizado' %}<span class="badge bg-success d-block mb-1">Finalizado</span>
                            {% elif demanda.status == 'Iniciado' %}<span class="badge bg-primary d-block mb-1">Iniciado</span>
                            {% else %}<span class="badge bg-secondary d-block mb-1">Pendente</span>{% endif %}
                            <small class="text-danger fw-bold d-block" style="font-size: 0.7rem;">📅 {{ demanda.data_prevista.strftime('%d/%m/%Y') }}</small>
                        </div>
                    </div>
                </div>
                
                <div id="collapse{{ demanda.id }}" class="collapse" data-bs-parent="#accordionDemandas">
                    <div class="card-body p-3 border-top">
                        <form action="/atualizar/{{ demanda.id }}" method="POST">
                            <label class="form-label fw-bold text-secondary small">Status da Demanda</label>
                            <select name="status" class="form-select form-select-sm mb-3 border-primary shadow-sm">
                                <option value="Pendente" {% if demanda.status == 'Pendente' %}selected{% endif %}>⏳ Pendente</option>
                                <option value="Iniciado" {% if demanda.status == 'Iniciado' %}selected{% endif %}>🚀 Iniciado</option>
                                <option value="Finalizado" {% if demanda.status == 'Finalizado' %}selected{% endif %}>✅ Finalizado</option>
                            </select>
                            
                            <div class="bg-light p-3 rounded mb-3">
                                <small class="text-dark d-block"><strong>Descrição Completa:</strong> {{ demanda.descricao }}</small>
                            </div>
                            
                            <h6 class="fw-bold text-secondary mb-2 small">Progresso do Checklist</h6>
                            <div class="d-flex align-items-center mb-3">
                                <div class="progress flex-grow-1 me-2 rounded-pill" style="height: 10px;">
                                    <div class="progress-bar {% if percentual == 100 %}bg-success{% else %}bg-primary{% endif %} rounded-pill" style="width: {{ percentual }}%;"></div>
                                </div>
                                <small class="fw-bold text-muted" style="font-size: 0.8rem;">{{ percentual }}%</small>
                            </div>

                            <div class="mb-4">
                                {% for chk in demanda.checklists %}
                                <div class="form-check mb-2">
                                    <input class="form-check-input" type="checkbox" name="checklist_passos[]" value="{{ chk.id }}" id="chk{{ chk.id }}" {% if chk.concluido %}checked{% endif %} style="transform: scale(1.15); margin-right: 6px;">
                                    <label class="form-check-label {% if chk.concluido %}text-decoration-line-through text-success fw-bold{% else %}text-dark{% endif %}" for="chk{{ chk.id }}">{{ chk.passo }}</label>
                                </div>
                                {% else %}
                                <p class="text-muted small">Nenhuma subetapa cadastrada.</p>
                                {% endfor %}
                            </div>
                            <button type="submit" class="btn btn-primary btn-app w-100">💾 Salvar Alterações</button>
                        </form>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="text-center py-5">
                <i class="bi bi-inbox fs-1 text-muted"></i>
                <p class="text-muted mt-2">Nenhuma demanda pendente por aqui! 🚀</p>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <a href="/nova_demanda" class="fab"><i class="bi bi-plus-lg"></i></a>
    """ + MENU_INFERIOR + """
</body>
</html>
"""

TELA_NOVA_DEMANDA = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Nova Demanda</title>
    """ + ESTILO_APP + """
</head>
<body>
    <div class="app-header">
        <a href="/" class="position-absolute start-0 ms-3 text-dark fs-3" style="line-height:1;"><i class="bi bi-arrow-left-short"></i></a>
        Nova Demanda
    </div>
    
    <div class="container-app mt-3">
        <form method="POST">
            <div class="mb-3">
                <label class="form-label fw-bold text-secondary small">Área Responsável</label>
                <select name="area" class="form-select" required>
                    <option value="CODER">CODER</option>
                    <option value="COCAP">COCAP</option>
                    <option value="CONEC">CONEC</option>
                    <option value="GERED">GERED</option>
                    <option value="EXTERNO">EXTERNO</option>
                </select>
            </div>
            
            <div class="mb-3">
                <label class="form-label fw-bold text-secondary small">Prioridade</label>
                <select name="prioridade" class="form-select" required>
                    <option value="Mínimo">🟢 Mínimo</option>
                    <option value="Médio" selected>🔵 Médio</option>
                    <option value="Alto">🟡 Alto</option>
                    <option value="Extremo">🔴 Extremo</option>
                </select>
            </div>
            
            <div class="mb-3">
                <label class="form-label fw-bold text-secondary small">Descrição do Trabalho</label>
                <textarea name="descricao" class="form-control" rows="3" placeholder="Insira o escopo ou resumo..." required></textarea>
            </div>
            
            <div class="row mb-4">
                <div class="col-6">
                    <label class="form-label fw-bold text-secondary small">Data de Início</label>
                    <input type="date" name="data_inicio" class="form-control">
                </div>
                <div class="col-6">
                    <label class="form-label fw-bold text-danger small">Previsão Fim</label>
                    <input type="date" name="data_prevista" class="form-control border-danger" required>
                </div>
            </div>
            
            <div class="card-app bg-white p-3 mb-4 border">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6 class="mb-0 fw-bold text-secondary">Checklist Auxiliar</h6>
                    <button type="button" class="btn btn-sm btn-outline-primary rounded-pill px-3" onclick="adicionarPasso()">+ Item</button>
                </div>
                <div id="checklist-container">
                    <input type="text" name="passo_checklist[]" class="form-control mb-2" placeholder="Ex: Tratar planilha no Excel...">
                </div>
            </div>
            
            <button type="submit" class="btn btn-primary btn-app w-100 mb-4">Salvar Registro</button>
        </form>
    </div>
    <script>
        function adicionarPasso() {
            const c = document.getElementById('checklist-container');
            const i = document.createElement('input');
            i.type='text'; i.name='passo_checklist[]'; i.className='form-control mb-2'; i.placeholder='Próxima etapa...';
            c.appendChild(i);
        }
    </script>
</body>
</html>
"""

TELA_ATAS = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JPMS System | Atas</title>
    """ + ESTILO_APP + """
</head>
<body>
    <div class="app-header">📁 Histórico de Atas</div>
    
    <div class="container-app mt-3">
        <form method="GET" action="/atas" class="mb-4">
            <div class="input-group shadow-sm" style="border-radius: 12px; overflow: hidden;">
                <input type="text" name="busca" class="form-control border-0" placeholder="🔍 Digite o assunto para pesquisar..." value="{{ busca }}">
                <button class="btn btn-primary px-3" type="submit">Buscar</button>
            </div>
            {% if busca %}
                <div class="text-end mt-1"><a href="/atas" class="text-decoration-none small text-secondary">❌ Limpar filtro</a></div>
            {% endif %}
        </form>

        <div class="row">
            {% for ata in atas %}
            <div class="col-12">
                <div class="card-app p-3">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h6 class="fw-bold text-dark text-truncate m-0" style="max-width: 70%;">{{ ata.assunto }}</h6>
                        <span class="badge bg-light text-dark border font-monospace" style="font-size: 0.75rem;">{{ ata.data_criacao.strftime('%d/%m/%Y') }}</span>
                    </div>
                    <p class="text-muted small mb-3" style="display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; white-space: pre-wrap;">
                        {{ ata.topicos }}
                    </p>
                    
                    <a href="/gerar_pdf_ata/{{ ata.id }}" class="btn btn-outline-danger btn-sm w-100 rounded-pill fw-bold">
                        <i class="bi bi-file-earmark-pdf-fill"></i> Baixar Arquivo PDF
                    </a>
                </div>
            </div>
            {% else %}
            <div class="text-center py-5">
                <i class="bi bi-journal-x fs-1 text-muted"></i>
                <p class="text-muted mt-2">Nenhuma ata localizada na busca.</p>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <a href="/nova_ata" class="fab" style="background: #007aff;"><i class="bi bi-plus-lg"></i></a>
    """ + MENU_INFERIOR + """
</body>
</html>
"""

TELA_NOVA_ATA = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Nova Ata de Reunião</title>
    """ + ESTILO_APP + """
</head>
<body>
    <div class="app-header">
        <a href="/atas" class="position-absolute start-0 ms-3 text-dark fs-3" style="line-height:1;"><i class="bi bi-arrow-left-short"></i></a>
        Gerar Nova Ata
    </div>
    
    <div class="container-app mt-3">
        <form method="POST">
            <div class="mb-3">
                <label class="form-label fw-bold text-secondary small">Título / Assunto da Pauta</label>
                <input type="text" name="assunto" class="form-control" placeholder="Ex: Alinhamento de Demandas ANS" required>
            </div>
            <div class="mb-4">
                <label class="form-label fw-bold text-secondary small">Pontos Acordados e Tópicos</label>
                <div class="form-text text-muted mb-2 small">Aperte 'Enter' para criar cada tópico em linhas separadas.</div>
                <textarea name="topicos" class="form-control" rows="8" placeholder="Digite as deliberações aqui..." required></textarea>
            </div>
            <button type="submit" class="btn btn-info text-white btn-app w-100 mb-4 shadow">💾 Salvar e Criar PDF</button>
        </form>
    </div>
</body>
</html>
"""

# ==========================================
# 5. ROTAS E INTERAÇÕES DO BACKEND
# ==========================================
@app.route('/')
def index():
    demandas_ativas = Demanda.query.filter(Demanda.status != 'Finalizado').all()
    peso_prioridade = {'Extremo': 4, 'Alto': 3, 'Médio': 2, 'Mínimo': 1}
    demandas_ativas.sort(key=lambda x: (-peso_prioridade.get(x.prioridade, 0), x.data_prevista))
    
    texto_whats = "🚀 *RESUMO DIÁRIO - DEMANDAS*\n\n"
    texto_whats += f"Temos *{len(demandas_ativas)} demandas* em aberto:\n\n"
    icones = {'Extremo': '🔴', 'Alto': '🟡', 'Médio': '🔵', 'Mínimo': '🟢'}
    
    for d in demandas_ativas:
        ico = icones.get(d.prioridade, '🔹')
        texto_whats += f"{ico} *[{d.prioridade.upper()}]* {d.descricao[:50]}...\n"
        texto_whats += f"└ *Setor:* {d.area} | *Prev:* {d.data_prevista.strftime('%d/%m/%Y')} | *Status:* {d.status}\n\n"
        
    texto_codificado = urllib.parse.quote(texto_whats)
    link_whatsapp = f"https://wa.me/?text={texto_codificado}"
    
    return render_template_string(TELA_PRINCIPAL, demandas=demandas_ativas, link_whatsapp=link_whatsapp, page='demandas')

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
        for passo in request.form.getlist('passo_checklist[]'):
            if passo.strip(): 
                db.session.add(Checklist(demanda_id=nova_dem.id, passo=passo))
        db.session.commit()
        return redirect(url_for('index'))
    return render_template_string(TELA_NOVA_DEMANDA)

@app.route('/atualizar/<int:id>', methods=['POST'])
def atualizar(id):
    demanda = Demanda.query.get_or_404(id)
    demanda.status = request.form.get('status')
    
    if demanda.status == 'Finalizado':
        demanda.data_conclusao = datetime.utcnow().date()
    else:
        demanda.data_conclusao = None
    
    passos_marcados = request.form.getlist('checklist_passos[]')
    ids_marcados = [int(i) for i in pasos_marcados]
    
    for chk in demanda.checklists:
        chk.concluido = chk.id in ids_marcados
        
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/atas')
def lista_atas():
    busca = request.args.get('busca', '')
    if busca:
        atas = AtaReuniao.query.filter((AtaReuniao.assunto.ilike(f'%{busca}%')) | (AtaReuniao.topicos.ilike(f'%{busca}%'))).order_by(AtaReuniao.data_criacao.desc()).all()
    else:
        atas = AtaReuniao.query.order_by(AtaReuniao.data_criacao.desc()).all()
    return render_template_string(TELA_ATAS, atas=atas, busca=busca, page='atas')

@app.route('/nova_ata', methods=['GET', 'POST'])
def nova_ata():
    if request.method == 'POST':
        nova = AtaReuniao(assunto=request.form['assunto'], topicos=request.form['topicos'])
        db.session.add(nova)
        db.session.commit()
        return redirect(url_for('lista_atas'))
    return render_template_string(TELA_NOVA_ATA)

@app.route('/gerar_pdf_ata/<int:id>')
def gerar_pdf_ata(id):
    ata = AtaReuniao.query.get_or_404(id)
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Filtro de codificação robusto contra quebras de caracteres especiais/emojis
        def limpa_texto(texto):
            return str(texto).encode('latin-1', 'replace').decode('latin-1')
        
        pdf.set_font("helvetica", style="B", size=16)
        pdf.cell(0, 10, limpa_texto(f"Ata de Reuniao: {ata.assunto}"), new_x="LMARGIN", new_y="NEXT", align="C")
        
        pdf.set_font("helvetica", style="I", size=10)
        pdf.cell(0, 10, limpa_texto(f"Data: {ata.data_criacao.strftime('%d/%m/%Y')}"), new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(10)
        
        pdf.set_font("helvetica", style="B", size=12)
        pdf.cell(0, 10, "Topicos Discutidos:", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        
        pdf.set_font("helvetica", size=11)
        
        contador = 1
        for linha in ata.topicos.split('\n'):
            linha_limpa = linha.strip()
            if linha_limpa:
                pdf.multi_cell(0, 8, limpa_texto(f"{contador}. {linha_limpa}"))
                contador += 1
                
        pdf_bytes = bytes(pdf.output())
        
        return send_file(
            io.BytesIO(pdf_bytes), 
            as_attachment=True, 
            download_name=f"Ata_{ata.data_criacao.strftime('%d-%m-%Y')}.pdf", 
            mimetype='application/pdf'
        )
    except Exception as e:
        return f"<h3>Erro interno ao renderizar PDF:</h3><p>{str(e)}</p>", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
