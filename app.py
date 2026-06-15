import os
import urllib.parse
import io
import textwrap
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
    titulo = db.Column(db.String(150), nullable=False, default='Demanda sem título')
    area = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    prioridade = db.Column(db.String(20), nullable=False, default='15') 
    status = db.Column(db.String(20), default='Pendente')
    data_solicitacao = db.Column(db.Date, default=datetime.utcnow().date)
    data_inicio = db.Column(db.Date, nullable=True)
    data_prevista = db.Column(db.Date, nullable=False)
    data_prorrogacao = db.Column(db.Date, nullable=True) 
    data_conclusao = db.Column(db.Date, nullable=True)
    
    # NOVAS COLUNAS DA MATRIZ GUT
    gravidade = db.Column(db.Integer, default=0)
    urgencia = db.Column(db.Integer, default=0)
    tendencia = db.Column(db.Integer, default=0)
    
    checklists = db.relationship('Checklist', backref='demanda', cascade='all, delete-orphan', lazy=True)

    # CÁLCULO OFICIAL DA MATRIZ GUT (Multiplicação)
    @property
    def gut_score(self):
        return (self.gravidade or 0) * (self.urgencia or 0) * (self.tendencia or 0)
            
    @property
    def data_sort(self):
        dt = self.data_prorrogacao or self.data_prevista
        return dt if dt else datetime.max.date()

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
    # Injeção segura das novas colunas GUT sem apagar o banco
    try:
        db.session.execute(db.text("ALTER TABLE demandas ADD COLUMN IF NOT EXISTS data_prorrogacao DATE;"))
        db.session.execute(db.text("ALTER TABLE demandas ADD COLUMN IF NOT EXISTS gravidade INTEGER DEFAULT 0;"))
        db.session.execute(db.text("ALTER TABLE demandas ADD COLUMN IF NOT EXISTS urgencia INTEGER DEFAULT 0;"))
        db.session.execute(db.text("ALTER TABLE demandas ADD COLUMN IF NOT EXISTS tendencia INTEGER DEFAULT 0;"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()

# ==========================================
# 3. CSS GLOBAL E DESIGN MOBILE (APP STYLE)
# ==========================================
ESTILO_APP = """
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">
<style>
    body { background-color: #f4f6f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding-top: 65px; padding-bottom: 85px; }
    .app-header { position: fixed; top: 0; left: 0; right: 0; background: #ffffff; height: 60px; display: flex; align-items: center; justify-content: center; z-index: 1030; box-shadow: 0 1px 3px rgba(0,0,0,0.05); font-weight: 700; font-size: 1.15rem; color: #1d1d1f; }
    .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: #ffffff; height: 65px; display: flex; justify-content: space-around; align-items: center; z-index: 1030; box-shadow: 0 -2px 10px rgba(0,0,0,0.04); padding-bottom: env(safe-area-inset-bottom); border-top: 1px solid #f1f1f1; }
    .nav-item { text-decoration: none; color: #8e8e93; display: flex; flex-direction: column; align-items: center; font-size: 0.75rem; flex: 1; font-weight: 500; }
    .nav-item.active { color: #007aff; }
    .nav-icon { font-size: 1.35rem; margin-bottom: 2px; }
    .container-app { max-width: 600px; margin: auto; padding: 0 15px; }
    .card-app { background: #fff; border-radius: 16px; border: none; box-shadow: 0 2px 8px rgba(0,0,0,0.03); margin-bottom: 14px; overflow: hidden; }
    .card-app-header { padding: 15px; border-bottom: 1px solid #f8f9fa; cursor: pointer; }
    .fab { position: fixed; bottom: 85px; right: 20px; background: #007aff; color: white; width: 56px; height: 56px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 26px; box-shadow: 0 4px 12px rgba(0,122,255,0.35); text-decoration: none; z-index: 1020; }
    .fab:active { transform: scale(0.95); color: white; }
    .form-control, .form-select { border-radius: 12px; padding: 12px; border: 1px solid #e5e5ea; background-color: #fcfcfc; font-size: 0.95rem; }
    .form-control:focus, .form-select:focus { border-color: #007aff; box-shadow: 0 0 0 0.25rem rgba(0,122,255,0.1); }
    .btn-app { border-radius: 12px; padding: 12px; font-weight: 600; font-size: 0.95rem; }
    .scroll-menu::-webkit-scrollbar { display: none; }
    .scroll-menu { -ms-overflow-style: none; scrollbar-width: none; }
</style>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
"""

MENU_INFERIOR = """
<div class="bottom-nav">
    <a href="/" class="nav-item {% if page == 'demandas' %}active{% endif %}">
        <i class="bi bi-card-checklist nav-icon"></i>
        <span>Demandas</span>
    </a>
    <a href="/gut" class="nav-item {% if page == 'gut' %}active{% endif %}">
        <i class="bi bi-bar-chart-steps nav-icon"></i>
        <span>Análise GUT</span>
    </a>
    <a href="/atas" class="nav-item {% if page == 'atas' %}active{% endif %}">
        <i class="bi bi-journal-text nav-icon"></i>
        <span>Atas</span>
    </a>
</div>
"""

# ==========================================
# 4. TEMPLATES HTML
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
        <div class="d-flex justify-content-center mb-2">
            <div class="btn-group w-100 shadow-sm" style="border-radius: 12px; overflow: hidden; border: 1px solid #e5e5ea;">
                <a href="/?status=Todos&area={{ filtro_area }}" class="btn btn-sm {% if filtro_status == 'Todos' %}btn-dark text-white{% else %}btn-light text-muted{% endif %} fw-bold py-2" style="font-size: 0.8rem;">📋 Todos</a>
                <a href="/?status=Pendente&area={{ filtro_area }}" class="btn btn-sm {% if filtro_status == 'Pendente' %}btn-secondary text-white{% else %}btn-light text-muted{% endif %} fw-bold py-2" style="font-size: 0.8rem;">⏳ Pendentes</a>
                <a href="/?status=Iniciado&area={{ filtro_area }}" class="btn btn-sm {% if filtro_status == 'Iniciado' %}btn-primary text-white{% else %}btn-light text-muted{% endif %} fw-bold py-2" style="font-size: 0.8rem;">🚀 Iniciados</a>
                <a href="/?status=Finalizado&area={{ filtro_area }}" class="btn btn-sm {% if filtro_status == 'Finalizado' %}btn-success text-white{% else %}btn-light text-muted{% endif %} fw-bold py-2" style="font-size: 0.8rem;">✅ Finalizados</a>
            </div>
        </div>
        
        <div class="d-flex overflow-auto mb-3 pb-1 scroll-menu" style="gap: 8px; white-space: nowrap;">
            {% for a in ['Todas', 'CODER', 'COCAP', 'CONEC', 'GERED', 'EXTERNO'] %}
            <a href="/?status={{ filtro_status }}&area={{ a }}" class="btn btn-sm {% if filtro_area == a %}btn-dark{% else %}btn-outline-secondary bg-white{% endif %} rounded-pill px-3 fw-bold">{{ a }}</a>
            {% endfor %}
        </div>
        
        <a href="{{ link_whatsapp }}" target="_blank" class="btn btn-success btn-app w-100 mb-4 shadow-sm" style="border-radius: 16px;">
            <i class="bi bi-whatsapp"></i> Enviar Resumo Zap
        </a>
        
        <div class="accordion" id="accordionDemandas">
            {% for demanda in demandas %}
            {% set total_chk = demanda.checklists|length %}
            {% set ns = namespace(concluidos=0) %}
            {% for chk in demanda.checklists %}{% if chk.concluido %}{% set ns.concluidos = ns.concluidos + 1 %}{% endif %}{% endfor %}
            {% set percentual = (ns.concluidos / total_chk * 100)|round|int if total_chk > 0 else 0 %}
            
            <!-- PEGA A POSIÇÃO GLOBAL BASEADO NA NOTA GUT -->
            {% set rank = ranking_global.get(demanda.id, 999) %}

            <div class="card-app">
                <div class="card-app-header" data-bs-toggle="collapse" data-bs-target="#collapse{{ demanda.id }}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="me-2 pe-2">
                            <span class="badge bg-dark mb-1">{{ demanda.area }}</span>
                            
                            {% if demanda.status == 'Finalizado' %}
                                <span class="badge bg-secondary">✅ Arquivado</span>
                            {% else %}
                                {% if rank <= 3 %}
                                    <span class="badge bg-danger">🔴 {{ rank }}º Lugar</span>
                                {% elif rank <= 6 %}
                                    <span class="badge bg-warning text-dark">🟡 {{ rank }}º Lugar</span>
                                {% elif rank <= 10 %}
                                    <span class="badge bg-success">🟢 {{ rank }}º Lugar</span>
                                {% else %}
                                    <span class="badge bg-primary">🔵 {{ rank }}º Lugar</span>
                                {% endif %}
                                <span class="badge bg-dark ms-1">GUT: {{ demanda.gut_score }}</span>
                            {% endif %}
                            
                            <h6 class="mt-2 mb-1 fw-bold text-dark">{{ demanda.titulo }}</h6>
                        </div>
                        <div class="text-end" style="min-width: 110px;">
                            <div class="d-flex justify-content-end align-items-center mb-1">
                                <span class="badge bg-light text-dark border me-1">{{ percentual }}%</span>
                                <span class="badge {% if demanda.status == 'Finalizado' %}bg-success{% elif demanda.status == 'Iniciado' %}bg-primary{% else %}bg-secondary{% endif %}">{{ demanda.status }}</span>
                            </div>
                            <small class="text-danger fw-bold d-block">📅 {{ (demanda.data_prorrogacao or demanda.data_prevista).strftime('%d/%m/%Y') if (demanda.data_prorrogacao or demanda.data_prevista) else 'S/D' }}</small>
                        </div>
                    </div>
                </div>
                
                <div id="collapse{{ demanda.id }}" class="collapse" data-bs-parent="#accordionDemandas">
                    <div class="card-body p-3 border-top">
                        <form id="form-deletar-{{ demanda.id }}" action="/deletar/{{ demanda.id }}?status={{ filtro_status }}&area={{ filtro_area }}" method="POST" style="display:none;"></form>

                        <form action="/atualizar/{{ demanda.id }}?status={{ filtro_status }}&area={{ filtro_area }}" method="POST">
                            <div class="row g-2 mb-3">
                                <div class="col-6">
                                    <label class="small fw-bold">Área Responsável</label>
                                    <select name="area" class="form-select form-select-sm">
                                        {% for a in ['CODER', 'COCAP', 'CONEC', 'GERED', 'EXTERNO'] %}
                                        <option value="{{ a }}" {% if demanda.area == a %}selected{% endif %}>{{ a }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                <div class="col-6">
                                    <label class="small fw-bold">Status</label>
                                    <select name="status" class="form-select form-select-sm">
                                        <option value="Pendente" {% if demanda.status == 'Pendente' %}selected{% endif %}>⏳ Pendente</option>
                                        <option value="Iniciado" {% if demanda.status == 'Iniciado' %}selected{% endif %}>🚀 Iniciado</option>
                                        <option value="Finalizado" {% if demanda.status == 'Finalizado' %}selected{% endif %}>✅ Finalizado</option>
                                    </select>
                                </div>
                                
                                <!-- EDIÇÃO DE GUT DIRETO NO CARD -->
                                <div class="col-12 mt-2"><h6 class="fw-bold small text-primary m-0">Reavaliar Matriz GUT (1 a 5)</h6></div>
                                <div class="col-4">
                                    <label class="small text-muted" style="font-size:0.7rem;">Gravidade</label>
                                    <select name="g" class="form-select form-select-sm border-danger text-center fw-bold" style="color: #dc3545;">
                                        {% for n in range(1, 6) %}<option value="{{ n }}" {% if demanda.gravidade == n %}selected{% endif %}>{{ n }}</option>{% endfor %}
                                    </select>
                                </div>
                                <div class="col-4">
                                    <label class="small text-muted" style="font-size:0.7rem;">Urgência</label>
                                    <select name="u" class="form-select form-select-sm border-warning text-center fw-bold" style="color: #ffc107;">
                                        {% for n in range(1, 6) %}<option value="{{ n }}" {% if demanda.urgencia == n %}selected{% endif %}>{{ n }}</option>{% endfor %}
                                    </select>
                                </div>
                                <div class="col-4">
                                    <label class="small text-muted" style="font-size:0.7rem;">Tendência</label>
                                    <select name="t" class="form-select form-select-sm border-info text-center fw-bold" style="color: #0dcaf0;">
                                        {% for n in range(1, 6) %}<option value="{{ n }}" {% if demanda.tendencia == n %}selected{% endif %}>{{ n }}</option>{% endfor %}
                                    </select>
                                </div>
                                
                                <div class="col-6 mt-3">
                                    <label class="small fw-bold">Data Início</label>
                                    <input type="date" name="data_inicio" class="form-control form-control-sm" value="{{ demanda.data_inicio.strftime('%Y-%m-%d') if demanda.data_inicio else '' }}">
                                </div>
                                <div class="col-6 mt-3">
                                    <label class="small fw-bold text-dark">Prorrogação</label>
                                    <input type="date" name="data_prorrogacao" class="form-control form-control-sm border-warning" value="{{ demanda.data_prorrogacao.strftime('%Y-%m-%d') if demanda.data_prorrogacao else '' }}">
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="small fw-bold">Observações (Editável)</label>
                                <textarea name="descricao" class="form-control form-control-sm" rows="4">{{ demanda.descricao }}</textarea>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h6 class="fw-bold m-0 small">Checklist</h6>
                                <button type="button" class="btn btn-sm btn-outline-primary rounded-pill py-0 px-2" onclick="addChkEdit({{ demanda.id }})">+ Item</button>
                            </div>
                            <div class="mb-4">
                                {% for chk in demanda.checklists %}
                                <div class="d-flex align-items-center mb-2">
                                    <input class="form-check-input mt-0 me-2" type="checkbox" name="chk_status_{{ chk.id }}" value="1" {% if chk.concluido %}checked{% endif %}>
                                    <input type="text" name="chk_texto_{{ chk.id }}" class="form-control form-control-sm" value="{{ chk.passo }}" style="border: none; background: transparent;">
                                </div>
                                {% endfor %}
                                <div id="new-chk-container-{{ demanda.id }}"></div>
                            </div>
                            
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-primary btn-app flex-grow-1 shadow-sm">💾 Salvar Modificações</button>
                                <button type="button" class="btn btn-outline-danger btn-app shadow-sm px-3" onclick="if(confirm('Tem certeza que deseja apagar permanentemente esta demanda?')) document.getElementById('form-deletar-{{ demanda.id }}').submit();">
                                    <i class="bi bi-trash3-fill"></i>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="text-center py-5">
                <i class="bi bi-inbox fs-1 text-muted"></i>
                <p class="text-muted mt-2">Nenhuma demanda neste filtro!</p>
            </div>
            {% endfor %}
        </div>
    </div>
    <a href="/nova_demanda" class="fab"><i class="bi bi-plus-lg"></i></a>
    """ + MENU_INFERIOR + """
    <script>
        function addChkEdit(id) {
            const container = document.getElementById('new-chk-container-' + id);
            const div = document.createElement('div');
            div.className = 'd-flex align-items-center mb-2';
            div.innerHTML = `<span class="me-2 text-primary"><i class="bi bi-dot"></i></span>
                             <input type="text" name="novo_passo[]" class="form-control form-control-sm border-primary" placeholder="Nova etapa...">`;
            container.appendChild(div);
        }
    </script>
</body>
</html>
"""

TELA_GUT = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>JPMS | Matriz GUT</title>
    """ + ESTILO_APP + """
</head>
<body>
    <div class="app-header">📊 Análise de GUT</div>
    <div class="container-app mt-3">
        <div class="alert alert-info small text-center p-2 mb-3 shadow-sm" style="border-radius: 12px; font-size:0.8rem;">
            A Matriz GUT <strong>multiplica</strong> os valores (G x U x T) para ranquear as demandas matematicamente.<br>
            <strong>(1 = Mais leve | 5 = Extremamente Crítico)</strong>
        </div>
        
        {% for demanda in demandas %}
        {% set rank = loop.index %}
        <div class="card-app p-3 mb-3 border-start border-4 {% if rank <= 3 %}border-danger{% elif rank <= 6 %}border-warning{% elif rank <= 10 %}border-success{% else %}border-primary{% endif %} shadow-sm">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="fw-bold m-0 text-dark" style="font-size: 0.85rem; line-height: 1.2; max-width:70%;">{{ rank }}º - {{ demanda.titulo }}</h6>
                <span class="badge bg-dark ms-2" style="font-size:0.75rem;">GUT: {{ demanda.gut_score }}</span>
            </div>
            
            <!-- AUTOSAVE ATIVADO: É SÓ TOCAR NO NÚMERO QUE ELE SALVA E RECALCULA SOZINHO -->
            <form action="/salvar_gut/{{ demanda.id }}" method="POST">
                <div class="row g-1">
                    <div class="col-3">
                        <label class="small fw-bold text-muted d-block text-center" style="font-size:0.65rem;">Gravidade</label>
                        <select name="g" class="form-select form-select-sm text-center fw-bold border-danger shadow-sm" style="color: #dc3545;" onchange="this.form.submit()">
                            {% for n in range(1, 6) %}<option value="{{ n }}" {% if demanda.gravidade == n %}selected{% endif %}>{{ n }}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="col-3">
                        <label class="small fw-bold text-muted d-block text-center" style="font-size:0.65rem;">Urgência</label>
                        <select name="u" class="form-select form-select-sm text-center fw-bold border-warning shadow-sm" style="color: #ffc107;" onchange="this.form.submit()">
                            {% for n in range(1, 6) %}<option value="{{ n }}" {% if demanda.urgencia == n %}selected{% endif %}>{{ n }}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="col-3">
                        <label class="small fw-bold text-muted d-block text-center" style="font-size:0.65rem;">Tendência</label>
                        <select name="t" class="form-select form-select-sm text-center fw-bold border-info shadow-sm" style="color: #0dcaf0;" onchange="this.form.submit()">
                            {% for n in range(1, 6) %}<option value="{{ n }}" {% if demanda.tendencia == n %}selected{% endif %}>{{ n }}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="col-3 d-flex align-items-end">
                        <button type="submit" class="btn btn-primary btn-sm w-100 fw-bold shadow-sm" style="height: 31px;"><i class="bi bi-check-lg"></i></button>
                    </div>
                </div>
            </form>
        </div>
        {% else %}
        <div class="text-center py-5">
            <i class="bi bi-check-circle fs-1 text-success"></i>
            <p class="text-muted mt-2">Nenhuma demanda ativa para analisar!</p>
        </div>
        {% endfor %}
    </div>
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
        <a href="/" class="position-absolute start-0 ms-3 text-dark fs-3"><i class="bi bi-arrow-left-short"></i></a>
        Nova Demanda
    </div>
    <div class="container-app mt-3">
        <form method="POST">
            <div class="mb-3">
                <label class="fw-bold small">Título da Demanda</label>
                <input type="text" name="titulo" class="form-control" placeholder="Título resumido..." required>
            </div>
            
            <div class="mb-3">
                <label class="fw-bold small">Área</label>
                <select name="area" class="form-select" required>
                    {% for a in ['CODER', 'COCAP', 'CONEC', 'GERED', 'EXTERNO'] %}
                    <option value="{{ a }}">{{ a }}</option>
                    {% endfor %}
                </select>
            </div>
            
            <div class="row g-2 mb-3">
                <div class="col-12"><label class="fw-bold small text-primary">Análise Inicial (1 a 5)</label></div>
                <div class="col-4">
                    <label class="small text-danger fw-bold" style="font-size:0.7rem;">Gravidade</label>
                    <select name="g" class="form-select border-danger text-center">
                        {% for n in range(1, 6) %}<option value="{{ n }}">{{ n }}</option>{% endfor %}
                    </select>
                </div>
                <div class="col-4">
                    <label class="small text-warning text-dark fw-bold" style="font-size:0.7rem;">Urgência</label>
                    <select name="u" class="form-select border-warning text-center">
                        {% for n in range(1, 6) %}<option value="{{ n }}">{{ n }}</option>{% endfor %}
                    </select>
                </div>
                <div class="col-4">
                    <label class="small text-info text-dark fw-bold" style="font-size:0.7rem;">Tendência</label>
                    <select name="t" class="form-select border-info text-center">
                        {% for n in range(1, 6) %}<option value="{{ n }}">{{ n }}</option>{% endfor %}
                    </select>
                </div>
            </div>
            
            <div class="mb-3">
                <label class="fw-bold small">Observações iniciais</label>
                <textarea name="descricao" class="form-control" rows="3" required></textarea>
            </div>
            <div class="row g-2 mb-4">
                <div class="col-6"><label class="fw-bold small">Data Início</label><input type="date" name="data_inicio" class="form-control"></div>
                <div class="col-6"><label class="fw-bold small text-danger">Previsão Fim</label><input type="date" name="data_prevista" class="form-control border-danger" required></div>
            </div>
            <div class="card-app p-3 mb-4 border">
                <div class="d-flex justify-content-between mb-3"><h6 class="fw-bold m-0">Checklist</h6><button type="button" class="btn btn-sm btn-outline-primary" onclick="adicionarPasso()">+ Item</button></div>
                <div id="checklist-container"><input type="text" name="passo_checklist[]" class="form-control mb-2" placeholder="Etapa 1..."></div>
            </div>
            <button type="submit" class="btn btn-primary btn-app w-100 mb-4 shadow-sm">Salvar Registro</button>
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
    <title>JPMS | Atas</title>
    """ + ESTILO_APP + """
</head>
<body>
    <div class="app-header">📁 Histórico de Atas</div>
    <div class="container-app mt-3">
        <form method="GET" action="/atas" class="mb-4">
            <div class="input-group shadow-sm" style="border-radius: 12px; overflow: hidden;">
                <input type="text" name="busca" class="form-control border-0" placeholder="🔍 Pesquisar ata..." value="{{ busca }}">
                <button class="btn btn-primary px-3" type="submit">Buscar</button>
            </div>
        </form>
        {% for ata in atas %}
        <div class="card-app p-3">
            <div class="d-flex justify-content-between mb-2">
                <h6 class="fw-bold text-dark text-truncate m-0" style="max-width: 70%;">{{ ata.assunto }}</h6>
                <span class="badge bg-light text-dark border">{{ ata.data_criacao.strftime('%d/%m/%Y') }}</span>
            </div>
            <p class="text-muted small mb-3 text-truncate">{{ ata.topicos }}</p>
            <a href="/gerar_pdf_ata/{{ ata.id }}" class="btn btn-outline-danger btn-sm w-100 rounded-pill fw-bold"><i class="bi bi-file-earmark-pdf-fill"></i> Baixar PDF</a>
        </div>
        {% endfor %}
    </div>
    <a href="/nova_ata" class="fab"><i class="bi bi-plus-lg"></i></a>
    """ + MENU_INFERIOR + """
</body>
</html>
"""

TELA_NOVA_ATA = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Gerar Ata</title>
    """ + ESTILO_APP + """
</head>
<body>
    <div class="app-header"><a href="/atas" class="position-absolute start-0 ms-3 text-dark fs-3"><i class="bi bi-arrow-left-short"></i></a>Gerar Ata</div>
    <div class="container-app mt-3">
        <form method="POST">
            <div class="mb-3"><label class="fw-bold small">Assunto da Pauta</label><input type="text" name="assunto" class="form-control" required></div>
            <div class="mb-4"><label class="fw-bold small">Tópicos (Um por linha)</label><textarea name="topicos" class="form-control" rows="10" required></textarea></div>
            <button type="submit" class="btn btn-info text-white btn-app w-100 shadow">💾 Salvar e Criar PDF</button>
        </form>
    </div>
</body>
</html>
"""

# ==========================================
# 5. ROTAS E LÓGICA DO BACKEND
# ==========================================
@app.route('/')
def index():
    filtro_status = request.args.get('status', 'Todos')
    filtro_area = request.args.get('area', 'Todas')
    
    if filtro_status == 'Todos':
        query = Demanda.query.filter(Demanda.status != 'Finalizado')
    else:
        query = Demanda.query.filter(Demanda.status == filtro_status)
        
    if filtro_area != 'Todas': 
        query = query.filter(Demanda.area == filtro_area)
        
    demandas_filtradas = query.all()
    demandas_filtradas.sort(key=lambda x: (-x.gut_score, x.data_sort))
    
    # Cria um Dicionário de Ranking Global (1º, 2º, 3º lugar) baseado no GUT
    todas_ativas = Demanda.query.filter(Demanda.status != 'Finalizado').all()
    todas_ativas.sort(key=lambda x: (-x.gut_score, x.data_sort))
    ranking_global = {d.id: idx+1 for idx, d in enumerate(todas_ativas)}
    
    texto_whats = "📋 *RELATÓRIO DE DEMANDAS (RANKING GUT)*\n"
    texto_whats += "=========================================\n\n"
    
    for idx, d in enumerate(todas_ativas):
        rank = idx + 1
        venc = (d.data_prorrogacao or d.data_prevista).strftime('%d/%m/%Y') if (d.data_prorrogacao or d.data_prevista) else 'S/D'
        total_chk = len(d.checklists)
        concluidos = sum(1 for chk in d.checklists if chk.concluido)
        perc = int((concluidos / total_chk) * 100) if total_chk > 0 else 0
        
        if rank <= 3: bloco_ico = "🔴"
        elif rank <= 6: bloco_ico = "🟡"
        elif rank <= 10: bloco_ico = "🟢"
        else: bloco_ico = "🔵"
        
        texto_whats += f"{bloco_ico} *{rank}º Lugar [GUT: {d.gut_score}]* - {d.titulo}\n"
        texto_whats += f"└ *Setor:* {d.area} | *Venc:* {venc}\n"
        texto_whats += f"└ *Status:* {d.status} ({perc}%)\n"
        texto_whats += "-----------------------------------------\n"
        
    if not todas_ativas:
        texto_whats += "✅ Nenhuma demanda ativa no momento!\n"
        
    texto_codificado = urllib.parse.quote(texto_whats)
    link_whatsapp = f"https://wa.me/5561995414168?text={texto_codificado}"
    
    return render_template_string(TELA_PRINCIPAL, demandas=demandas_filtradas, link_whatsapp=link_whatsapp, page='demandas', filtro_status=filtro_status, filtro_area=filtro_area, ranking_global=ranking_global)

# NOVA ROTA: ABA DA MATRIZ GUT
@app.route('/gut')
def gut():
    demandas = Demanda.query.filter(Demanda.status != 'Finalizado').all()
    demandas.sort(key=lambda x: (-x.gut_score, x.data_sort))
    return render_template_string(TELA_GUT, demandas=demandas, page='gut')

# NOVA ROTA: SALVAMENTO RÁPIDO DO GUT
@app.route('/salvar_gut/<int:id>', methods=['POST'])
def salvar_gut(id):
    demanda = Demanda.query.get_or_404(id)
    demanda.gravidade = int(request.form.get('g', 1))
    demanda.urgencia = int(request.form.get('u', 1))
    demanda.tendencia = int(request.form.get('t', 1))
    db.session.commit()
    # Retorna para a mesma página para não atrapalhar o fluxo
    return redirect(request.referrer or url_for('gut'))

@app.route('/nova_demanda', methods=['GET', 'POST'])
def nova_demanda():
    if request.method == 'POST':
        nova_dem = Demanda(
            titulo=request.form.get('titulo'), 
            area=request.form['area'], 
            descricao=request.form['descricao'], 
            gravidade=int(request.form.get('g', 1)),
            urgencia=int(request.form.get('u', 1)),
            tendencia=int(request.form.get('t', 1)),
            data_inicio=datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date() if request.form.get('data_inicio') else None, 
            data_prevista=datetime.strptime(request.form['data_prevista'], '%Y-%m-%d').date()
        )
        db.session.add(nova_dem)
        db.session.flush() 
        for passo in request.form.getlist('passo_checklist[]'):
            if passo.strip(): db.session.add(Checklist(demanda_id=nova_dem.id, passo=passo))
        db.session.commit()
        return redirect(url_for('index', status='Todos'))
    return render_template_string(TELA_NOVA_DEMANDA)

@app.route('/atualizar/<int:id>', methods=['POST'])
def atualizar(id):
    demanda = Demanda.query.get_or_404(id)
    origem_status = request.args.get('status', 'Todos')
    origem_area = request.args.get('area', 'Todas')
    
    demanda.area = request.form.get('area', demanda.area)
    demanda.status = request.form.get('status', demanda.status)
    demanda.descricao = request.form.get('descricao', demanda.descricao)
    
    if request.form.get('g'): demanda.gravidade = int(request.form.get('g'))
    if request.form.get('u'): demanda.urgencia = int(request.form.get('u'))
    if request.form.get('t'): demanda.tendencia = int(request.form.get('t'))
    
    if request.form.get('data_inicio'): demanda.data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()
    if request.form.get('data_prorrogacao'): demanda.data_prorrogacao = datetime.strptime(request.form['data_prorrogacao'], '%Y-%m-%d').date()
    
    demanda.data_conclusao = datetime.utcnow().date() if demanda.status == 'Finalizado' else None
    
    for chk in demanda.checklists:
        chk.concluido = f'chk_status_{chk.id}' in request.form
        if request.form.get(f'chk_texto_{chk.id}'): chk.passo = request.form.get(f'chk_texto_{chk.id}')
    for np in request.form.getlist('novo_passo[]'):
        if np.strip(): db.session.add(Checklist(demanda_id=demanda.id, passo=np.strip()))
        
    db.session.commit()
    return redirect(url_for('index', status=origem_status, area=origem_area))

@app.route('/deletar/<int:id>', methods=['POST'])
def deletar(id):
    demanda = Demanda.query.get_or_404(id)
    origem_status = request.args.get('status', 'Todos')
    origem_area = request.args.get('area', 'Todas')
    
    db.session.delete(demanda)
    db.session.commit()
    return redirect(url_for('index', status=origem_status, area=origem_area))

@app.route('/atas')
def lista_atas():
    busca = request.args.get('busca', '')
    query = AtaReuniao.query
    if busca: query = query.filter((AtaReuniao.assunto.ilike(f'%{busca}%')) | (AtaReuniao.topicos.ilike(f'%{busca}%')))
    atas = query.order_by(AtaReuniao.data_criacao.desc()).all()
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
        def limpa_texto(texto): return str(texto).encode('latin-1', 'replace').decode('latin-1')
        pdf.set_font("helvetica", style="B", size=16)
        titulo_comp = limpa_texto(f"Ata de Reuniao: {ata.assunto}")
        lin_t = textwrap.wrap(titulo_comp, width=45, break_long_words=True)
        for lt in lin_t: pdf.multi_cell(0, 10, lt, align="C", new_x="LMARGIN", new_y="NEXT")
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
                texto_final = limpa_texto(f"{contador}. {linha_limpa}")
                linhas_quebradas = textwrap.wrap(texto_final, width=65, break_long_words=True)
                for pedaco in linhas_quebradas: pdf.multi_cell(0, 8, pedaco, new_x="LMARGIN", new_y="NEXT")
                contador += 1
        pdf_bytes = bytes(pdf.output())
        return send_file(io.BytesIO(pdf_bytes), as_attachment=True, download_name=f"Ata_{ata.data_criacao.strftime('%d-%m-%Y')}.pdf", mimetype='application/pdf')
    except Exception as e: return f"<h3>Erro interno ao renderizar PDF:</h3><p>{str(e)}</p>", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
