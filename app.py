import os
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for
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
# CRIA AS TABELAS
# ==========================================
with app.app_context():
    db.create_all()

# ==========================================
# TELAS (HTML EMBUTIDO NO PYTHON)
# ==========================================
TELA_PRINCIPAL = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Sistema-JPMS | Demandas</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>Acompanhamento de Demandas</h2>
            <div>
                <a href="{{ link_whatsapp }}" target="_blank" class="btn btn-success fw-bold me-2">
                    📱 Enviar Resumo no WhatsApp
                </a>
                <a href="/nova_demanda" class="btn btn-primary fw-bold">+ Nova Demanda</a>
            </div>
        </div>
        
        <div class="card shadow-sm border-0">
            <div class="card-body p-0">
                <table class="table table-hover mb-0">
                    <thead class="table-dark">
                        <tr>
                            <th>Área</th>
                            <th>Descrição</th>
                            <th>Prioridade</th>
                            <th>Início</th>
                            <th>Previsão</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for demanda in demandas %}
                        <tr>
                            <td><span class="badge bg-secondary">{{ demanda.area }}</span></td>
                            <td class="text-truncate" style="max-width: 300px;">{{ demanda.descricao }}</td>
                            <td>
                                {% if demanda.prioridade == 'Extremo' %} <span class="badge bg-danger">Extremo</span>
                                {% elif demanda.prioridade == 'Alto' %} <span class="badge bg-warning text-dark">Alto</span>
                                {% else %} {{ demanda.prioridade }} {% endif %}
                            </td>
                            <td>{{ demanda.data_inicio.strftime('%d/%m/%Y') if demanda.data_inicio else '-' }}</td>
                            <td class="fw-bold">{{ demanda.data_prevista.strftime('%d/%m/%Y') }}</td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="5" class="text-center py-4 text-muted">Nenhuma demanda em andamento! 🚀</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

TELA_NOVA_DEMANDA = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Nova Demanda | Sistema-JPMS</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="card shadow-sm border-0 mx-auto" style="max-width: 800px;">
            <div class="card-header bg-dark text-white p-3">
                <h4 class="mb-0">Cadastrar Nova Demanda</h4>
            </div>
            <div class="card-body p-4">
                <form method="POST">
                    <div class="row mb-3">
                        <div class="col-md-6">
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
                        <div class="col-md-6">
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
                            <h5 class="mb-0">Checklist de Tarefas</h5>
                            <button type="button" class="btn btn-sm btn-outline-dark" onclick="adicionarPasso()">+ Adicionar Passo</button>
                        </div>
                        <div id="checklist-container">
                            <input type="text" name="passo_checklist[]" class="form-control mb-2" placeholder="Descreva a primeira etapa do processo...">
                        </div>
                    </div>

                    <div class="d-flex justify-content-between mt-4">
                        <a href="/" class="btn btn-secondary">Cancelar</a>
                        <button type="submit" class="btn btn-success px-5 fw-bold">Salvar Demanda</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
    <script>
        function adicionarPasso() {
            const container = document.getElementById('checklist-container');
            const input = document.createElement('input');
            input.type = 'text';
            input.name = 'passo_checklist[]';
            input.className = 'form-control mb-2';
            input.placeholder = 'Descreva a próxima etapa...';
            container.appendChild(input);
        }
    </script>
</body>
</html>
"""

# ==========================================
# ROTAS E LÓGICA DO SISTEMA
# ==========================================
@app.route('/')
def index():
    demandas_ativas = Demanda.query.filter_by(data_conclusao=None).order_by(Demanda.data_prevista).all()
    
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
        
    texto_codificado = urllib.parse.quote(texto_whats)
    link_whatsapp = f"https://wa.me/?text={texto_codificado}"
    
    # Aqui a gente puxa a string do Python em vez do arquivo externo
    return render_template_string(TELA_PRINCIPAL, demandas=demandas_ativas, link_whatsapp=link_whatsapp)

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
        
    # Aqui também puxa direto do Python
    return render_template_string(TELA_NOVA_DEMANDA)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
