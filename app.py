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
    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    prioridade = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='A Fazer') 
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

class AtaReuniao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assunto = db.Column(db.String(200), nullable=False)
    data_criacao = db.Column(db.Date, default=datetime.utcnow().date)
    topicos = db.Column(db.Text, nullable=False)

with app.app_context():
    db.create_all()

# ==========================================
# 3. TELAS (HTML + BOOTSTRAP)
# ==========================================
MENU_TOPO = """
<nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4 shadow-sm">
    <div class="container" style="max-width: 1000px;">
        <a class="navbar-brand fw-bold" href="/">🚀 JPMS System</a>
        <div class="d-flex">
            <a href="/" class="btn btn-outline-light btn-sm me-2">📋 Demandas</a>
            <a href="/atas" class="btn btn-outline-info btn-sm">📁 Atas de Reunião</a>
        </div>
    </div>
</nav>
"""

TELA_PRINCIPAL = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Demandas | Sistema-JPMS</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</head>
<body class="bg-light">
    {MENU_TOPO}
    <div class="container" style="max-width: 1000px;">
        <div class="d-flex flex-wrap justify-content-between align-items-center mb-4">
            <h3 class="mb-2 mb-md-0 text-secondary">Acompanhamento de Demandas</h3>
            <div>
                <a href="{{{{ link_whatsapp }}}}" target="_blank" class="btn btn-success fw-bold btn-sm me-1">📱 Resumo Zap</a>
                <a href="/nova_demanda" class="btn btn-primary fw-bold btn-sm">+ Nova Demanda</a>
            </div>
        </div>
        
        <div class="accordion" id="accordionDemandas">
            {{% for demanda in demandas %}}
            <div class="accordion-item mb-3 border-0 shadow-sm rounded">
                <h2 class="accordion-header" id="heading{{{{ demanda.id }}}}">
                    <button class="accordion-button collapsed rounded" type="button" data-bs-toggle="collapse" data-bs-target="#collapse{{{{ demanda.id }}}}">
                        <div class="d-flex align-items-center w-100 justify-content-between me-3 text-wrap">
                            <div>
                                <span class="badge bg-dark me-1">{{{{ demanda.area }}}}</span>
                                {{% if demanda.prioridade == 'Extremo' %}}
                                    <span class="badge bg-danger">🔴 Extremo</span>
                                {{% elif demanda.prioridade == 'Alto' %}}
                                    <span class="badge bg-warning text-dark">🟡 Alto</span>
                                {{% elif demanda.prioridade == 'Médio' %}}
                                    <span class="badge bg-info text-dark">🔵 Médio</span>
                                {{% else %}}
                                    <span class="badge bg-secondary">🟢 Mínimo</span>
                                {{% endif %}}
                                <div class="mt-1 text-dark fw-semibold" style="font-size: 0.95rem;">{{{{ demanda.descricao[:70] }}}}...</div>
                            </div>
                            <div class="text-end mt-2 mt-sm-0">
                                <span class="badge bg-light text-dark border d-block mb-1">{{{{ demanda.status }}}}</span>
                                <small class="text-danger fw-bold d-block">📅 {{{{ demanda.data_prevista.strftime('%d/%m/%Y') }}}}</small>
                            </div>
                        </div>
                    </button>
                </h2>
                <div id="collapse{{{{ demanda.id }}}}" class="accordion-collapse collapse" data-bs-parent="#accordionDemandas">
                    <div class="accordion-body bg-white border-top rounded-bottom">
                        <form action="/atualizar/{{{{ demanda.id }}}}" method="POST">
                            <div class="row mb-3">
                                <div class="col-md-4 border-end mb-3 mb-md-0">
                                    <label class="form-label fw-bold text-secondary">Status Atual</label>
                                    <select name="status" class="form-select form-select-sm mb-3">
                                        <option value="A Fazer" {{% if demanda.status == 'A Fazer' %}}selected{{% endif %}}>A Fazer</option>
                                        <option value="Em Andamento" {{% if demanda.status == 'Em Andamento' %}}selected{{% endif %}}>Em Andamento</option>
                                        <option value="Concluído" {{% if demanda.status == 'Concluído' %}}selected{{% endif %}}>Concluído</option>
                                    </select>
                                    <p class="mb-1 small"><strong>Solicitado:</strong> {{{{ demanda.data_solicitacao.strftime('%d/%m/%Y') }}}}</p>
                                    <p class="mb-1 small"><strong>Início:</strong> {{{{ demanda.data_inicio.strftime('%d/%m/%Y') if demanda.data_inicio else '-' }}}}</p>
                                </div>
                                <div class="col-md-8">
                                    <label class="form-label fw-bold text-secondary">Descrição Detalhada</label>
                                    <p class="bg-light p-2 rounded small text-dark" style="white-space: pre-wrap;">{{{{ demanda.descricao }}}}</p>
                                </div>
                            </div>
                            
                            <h6 class="fw-bold text-secondary mb-2">Checklist de Tarefas</h6>
                            <div class="mb-3 bg-light p-3 rounded">
                                {{% for chk in demanda.checklists %}}
                                <div class="form-check mb-2">
                                    <input class="form-check-input" type="checkbox" name="checklist_passos[]" value="{{{{ chk.id }}}}" id="chk{{{{ chk.id }}}}" {{% if chk.concluido %}}checked{{% endif %}}>
                                    <label class="form-check-label {{% if chk.concluido %}}text-decoration-line-through text-muted{{% endif %}}" for="chk{{{{ chk.id }}}}">{{{{ chk.passo }}}}</label>
                                </div>
                                {{% else %}}
                                <p class="text-muted small mb-0">Nenhum passo cadastrado.</p>
                                {{% endfor %}}
                            </div>
                            <div class="d-flex justify-content-end">
                                <button type="submit" class="btn btn-sm btn-success fw-bold px-4">Salvar Alterações</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
            {{% else %}}
            <div class="text-center py-5 bg-white rounded shadow-sm"><p class="text-muted mb-0 fs-5">Sem demandas ativas! 🚀</p></div>
            {{% endfor %}}
        </div>
    </div>
</body>
</html>
"""

TELA_ATAS = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Atas | Sistema-JPMS</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    {MENU_TOPO}
    <div class="container" style="max-width: 1000px;">
        <div class="d-flex flex-wrap justify-content-between align-items-center mb-4">
            <h3 class="mb-2 mb-md-0 text-secondary">📁 Atas de Reunião</h3>
            <a href="/nova_ata" class="btn btn-info text-white fw-bold btn-sm">+ Criar Ata</a>
        </div>

        <form method="GET" action="/atas" class="mb-4">
            <div class="input-group shadow-sm">
                <input type="text" name="busca" class="form-control" placeholder="Pesquisar atas..." value="{{{{ busca }}}}">
                <button class="btn btn-dark" type="submit">🔍 Buscar</button>
            </div>
        </form>

        <div class="row">
            {{% for ata in atas %}}
            <div class="col-md-6 mb-3">
                <div class="card shadow-sm border-0 h-100">
                    <div class="card-body d-flex flex-column justify-content-between">
                        <div>
                            <div class="d-flex justify-content-between align-items-start">
                                <h5 class="card-title text-dark fw-bold text-truncate" style="max-width: 75%;">{{{{ ata.assunto }}}}</h5>
                                <small class="text-muted">{{{{ ata.data_criacao.strftime('%d/%m/%Y') }}}}</small>
                            </div>
                            <p class="card-text text-muted small mt-2" style="display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
                                {{{{ ata.topicos }}}}
                            </p>
                        </div>
                        <a href="/gerar_pdf_ata/{{{{ ata.id }}}}" class="btn btn-sm btn-outline-danger fw-bold mt-3 align-self-start">📄 Baixar PDF</a>
                    </div>
                </div>
            </div>
            {{% else %}}
            <div class="col-12 text-center py-5 bg-white rounded shadow-sm"><p class="text-muted mb-0 fs-5">Nenhuma ata encontrada.</p></div>
            {{% endfor %}}
        </div>
    </div>
</body>
</html>
"""

TELA_NOVA_ATA = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nova Ata | Sistema-JPMS</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    {MENU_TOPO}
    <div class="container" style="max-width: 800px;">
        <div class="card shadow-sm border-0">
            <div class="card-header bg-info text-white p-3">
                <h4 class="mb-0">Cadastrar Ata de Reunião</h4>
            </div>
            <div class="card-body p-4">
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label fw-bold">Assunto / Título da Reunião</label>
                        <input type="text" name="assunto" class="form-control" required>
                    </div>
                    <div class="mb-4">
                        <label class="form-label fw-bold">Tópicos Discutidos (Um por linha)</label>
                        <textarea name="topicos" class="form-control" rows="8" placeholder="Pressione Enter para cada novo tópico..." required></textarea>
                    </div>
                    <div class="d-flex justify-content-between">
                        <a href="/atas" class="btn btn-secondary">Cancelar</a>
                        <button type="submit" class="btn btn-info text-white fw-bold px-5">Salvar e Gerar PDF</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

TELA_NOVA_DEMANDA = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nova Demanda | Sistema-JPMS</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    {MENU_TOPO}
    <div class="container" style="max-width: 800px;">
        <div class="card shadow-sm border-0">
            <div class="card-header bg-dark text-white p-3"><h4 class="mb-0">Cadastrar Nova Demanda</h4></div>
            <div class="card-body p-4">
                <form method="POST">
                    <div class="row mb-3">
                        <div class="col-md-6 mb-3 mb-md-0">
                            <label class="form-label fw-bold">Área Responsável</label>
                            <select name="area" class="form-select" required>
                                <option value="CODER">CODER</option>
                                <option value="COCAP">COCAP</option>
                                <option value="CONEC">CONEC</option>
                                <option value="GERED">GERED</option>
                                <option value="EXTERNO">EXTERNO</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label fw-bold">Prioridade</label>
                            <select name="prioridade" class="form-select" required>
                                <option value="Mínimo">Mínimo</option>
                                <option value="Médio" selected>Médio</option>
                                <option value="Alto">Alto</option>
                                <option value="Extremo">Extremo</option>
                            </select>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-bold">Descrição da Demanda</label>
                        <textarea name="descricao" class="form-control" rows="3" required></textarea>
                    </div>
                    <div class="row mb-4">
                        <div class="col-md-6 mb-3 mb-md-0">
                            <label class="form-label fw-bold">Data de Início</label>
                            <input type="date" name="data_inicio" class="form-control">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label fw-bold text-danger">Data Prevista para Conclusão</label>
                            <input type="date" name="data_prevista" class="form-control border-danger" required>
                        </div>
                    </div>
                    <div class="bg-light p-3 rounded border">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="mb-0">Checklist</h5>
                            <button type="button" class="btn btn-sm btn-outline-dark" onclick="adicionarPasso()">+ Passo</button>
                        </div>
                        <div id="checklist-container"><input type="text" name="passo_checklist[]" class="form-control mb-2" placeholder="Etapa 1..."></div>
                    </div>
                    <div class="d-flex justify-content-between mt-4">
                        <a href="/" class="btn btn-secondary">Cancelar</a>
                        <button type="submit" class="btn btn-success px-5 fw-bold">Salvar</button>
                    </div>
                </form>
            </div>
        </div>
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

# ==========================================
# 4. ROTAS E LÓGICA DO SISTEMA
# ==========================================
@app.route('/')
def index():
    demandas_ativas = Demanda.query.filter(Demanda.status != 'Concluído').all()
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
    return render_template_string(TELA_PRINCIPAL, demandas=demandas_ativas, link_whatsapp=link_whatsapp)

@app.route('/nova_demanda', methods=['GET', 'POST'])
def nova_demanda():
    if request.method == 'POST':
        nova_dem = Demanda(area=request.form['area'], descricao=request.form['descricao'], prioridade=request.form['prioridade'], data_inicio=datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date() if request.form['data_inicio'] else None, data_prevista=datetime.strptime(request.form['data_prevista'], '%Y-%m-%d').date())
        db.session.add(nova_dem)
        db.session.flush() 
        for passo in request.form.getlist('passo_checklist[]'):
            if passo.strip(): db.session.add(Checklist(demanda_id=nova_dem.id, passo=passo))
        db.session.commit()
        return redirect(url_for('index'))
    return render_template_string(TELA_NOVA_DEMANDA)

@app.route('/atualizar/<int:id>', methods=['POST'])
def atualizar(id):
    demanda = Demanda.query.get_or_404(id)
    demanda.status = request.form['status']
    demanda.data_conclusao = datetime.utcnow().date() if demanda.status == 'Concluído' else None
    
    ids_marcados = [int(i) for i in request.form.getlist('checklist_passos[]')]
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
    return render_template_string(TELA_ATAS, atas=atas, busca=busca)

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
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(0, 10, f"Ata de Reuniao: {ata.assunto}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("helvetica", style="I", size=10)
    pdf.cell(0, 10, f"Data: {ata.data_criacao.strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    pdf.set_font("helvetica", style="B", size=12)
    pdf.cell(0, 10, "Topicos Discutidos:", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("helvetica", size=11)
    
    contador = 1
    for linha in ata.topicos.split('\n'):
        linha_limpa = linha.strip()
        if linha_limpa:
            pdf.multi_cell(0, 8, f"{contador}. {linha_limpa}")
            contador += 1
            
    pdf_bytes = pdf.output()
    return send_file(io.BytesIO(pdf_bytes), as_attachment=True, download_name=f"Ata_{ata.data_criacao.strftime('%d-%m-%Y')}.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
