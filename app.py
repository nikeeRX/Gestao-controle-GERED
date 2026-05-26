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
    prioridade = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Pendente')
    data_solicitacao = db.Column(db.Date, default=datetime.utcnow().date)
    data_inicio = db.Column(db.Date, nullable=True)
    data_prevista = db.Column(db.Date, nullable=False)
    data_prorrogacao = db.Column(db.Date, nullable=True) 
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
    try:
        db.session.execute(db.text("ALTER TABLE demandas ADD COLUMN IF NOT EXISTS data_prorrogacao DATE;"))
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
    <a href="/atas" class="nav-item {% if page == 'atas' %}active{% endif %}">
        <i class="bi bi-journal-text nav-icon"></i>
        <span>Atas</span>
    </a>
</div>
"""

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
                <a href="/?status=Pendente&area={{ filtro_area }}" class="btn btn-sm {% if filtro_status == 'Pendente' %}btn-secondary text-white{% else %}btn-light text-muted{% endif %} fw-bold py-2" style="font-size: 0.85rem;">⏳ Pendentes</a>
                <a href="/?status=Iniciado&area={{ filtro_area }}" class="btn btn-sm {% if filtro_status == 'Iniciado' %}btn-primary text-white{% else %}btn-light text-muted{% endif %} fw-bold py-2" style="font-size: 0.85rem;">🚀 Iniciados</a>
                <a href="/?status=Finalizado&area={{ filtro_area }}" class="btn btn-sm {% if filtro_status == 'Finalizado' %}btn-success text-white{% else %}btn-light text-muted{% endif %} fw-bold py-2" style="font-size: 0.85rem;">✅ Finalizados</a>
            </div>
        </div>
        
        <div class="d-flex overflow-auto mb-3 pb-1 scroll-menu" style="gap: 8px; white-space: nowrap;">
            <a href="/?status={{ filtro_status }}&area=Todas" class="btn btn-sm {% if filtro_area == 'Todas' %}btn-dark{% else %}btn-outline-secondary bg-white{% endif %} rounded-pill px-3 fw-bold" style="font-size: 0.8rem;">Todas</a>
            <a href="/?status={{ filtro_status }}&area=CODER" class="btn btn-sm {% if filtro_area == 'CODER' %}btn-dark{% else %}btn-outline-secondary bg-white{% endif %} rounded-pill px-3 fw-bold" style="font-size: 0.8rem;">CODER</a>
            <a href="/?status={{ filtro_status }}&area=COCAP" class="btn btn-sm {% if filtro_area == 'COCAP' %}btn-dark{% else %}btn-outline-secondary bg-white{% endif %} rounded-pill px-3 fw-bold" style="font-size: 0.8rem;">COCAP</a>
            <a href="/?status={{ filtro_status }}&area=CONEC" class="btn btn-sm {% if filtro_area == 'CONEC' %}btn-dark{% else %}btn-outline-secondary bg-white{% endif %} rounded-pill px-3 fw-bold" style="font-size: 0.8rem;">CONEC</a>
            <a href="/?status={{ filtro_status }}&area=GERED" class="btn btn-sm {% if filtro_area == 'GERED' %}btn-dark{% else %}btn-outline-secondary bg-white{% endif %} rounded-pill px-3 fw-bold" style="font-size: 0.8rem;">GERED</a>
            <a href="/?status={{ filtro_status }}&area=EXTERNO" class="btn btn-sm {% if filtro_area == 'EXTERNO' %}btn-dark{% else %}btn-outline-secondary bg-white{% endif %} rounded-pill px-3 fw-bold" style="font-size: 0.8rem;">EXTERNO</a>
        </div>
        
        <a href="{{ link_whatsapp }}" target="_blank" class="btn btn-success btn-app w-100 mb-4 shadow-sm" style="border-radius: 16px;">
            <i class="bi bi-whatsapp"></i> Enviar Resumo Zap
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
                        <div class="me-2 pe-2">
                            <span class="badge bg-dark mb-1">{{ demanda.area }}</span>
                            {% if demanda.prioridade == 'Extremo' %}<span class="badge bg-danger">🔴 Extremo</span>
                            {% elif demanda.prioridade == 'Alto' %}<span class="badge bg-warning text-dark">🟡 Alto</span>
                            {% elif demanda.prioridade == 'Médio' %}<span class="badge bg-info text-dark">🔵 Médio</span>
                            {% else %}<span class="badge bg-secondary">🟢 Mínimo</span>{% endif %}
                            
                            <h6 class="mt-2 mb-1 fw-bold text-dark" style="line-height: 1.3;">{{ demanda.titulo }}</h6>
                        </div>
                        
                        <div class="text-end" style="min-width: 110px;">
                            <div class="d-flex justify-content-end align-items-center mb-1">
                                <span class="badge bg-light text-dark border me-1">{{ percentual }}%</span>
                                {% if demanda.status == 'Finalizado' %}<span class="badge bg-success">Finalizado</span>
                                {% elif demanda.status == 'Iniciado' %}<span class="badge bg-primary">Iniciado</span>
                                {% else %}<span class="badge bg-secondary">Pendente</span>{% endif %}
                            </div>
                            <small class="text-danger fw-bold d-block" style="font-size: 0.7rem;">📅 P: {{ demanda.data_prevista.strftime('%d/%m/%Y') }}</small>
                            {% if demanda.data_prorrogacao %}
                                <small class="text-warning text-dark fw-bold d-block" style="font-size: 0.7rem;">⏳ PR: {{ demanda.data_prorrogacao.strftime('%d/%m/%Y') }}</small>
                            {% endif %}
                        </div>
                    </div>
                </div>
                
                <div id="collapse{{ demanda.id }}" class="collapse" data-bs-parent="#accordionDemandas">
                    <div class="card-body p-3 border-top">
                        <form action="/atualizar/{{ demanda.id }}?status={{ filtro_status }}&area={{ filtro_area }}" method="POST">
                            
                            <div class="row mb-2">
                                <div class="col-12 mb-2">
                                    <label class="form-label fw-bold text-secondary small mb-1">Status da Demanda</label>
                                    <select name="status" class="form-select form-select-sm border-primary shadow-sm">
                                        <option value="Pendente" {% if demanda.status == 'Pendente' %}selected{% endif %}>⏳ Pendente</option>
                                        <option value="Iniciado" {% if demanda.status == 'Iniciado' %}selected{% endif %}>🚀 Iniciado</option>
                                        <option value="Finalizado" {% if demanda.status == 'Finalizado' %}selected{% endif %}>✅ Finalizado</option>
                                    </select>
                                </div>
                                <div class="col-6 mb-2">
                                    <label class="form-label fw-bold text-secondary small mb-1">Data Início</label>
                                    <input type="date" name="data_inicio" class="form-control form-control-sm" value="{{ demanda.data_inicio.strftime('%Y-%m-%d') if demanda.data_inicio else '' }}">
                                </div>
                                <div class="col-6 mb-2">
                                    <label class="form-label fw-bold text-warning text-dark small mb-1">Prorrogação</label>
                                    <input type="date" name="data_prorrogacao" class="form-control form-control-sm border-warning" value="{{ demanda.data_prorrogacao.strftime('%Y-%m-%d') if demanda.data_prorrogacao else '' }}">
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label fw-bold text-secondary small mb-1">Observações / Detalhes (Editável)</label>
                                <textarea name="descricao" class="form-control form-control-sm border" rows="4">{{ demanda.descricao }}</textarea>
                            </div>
                            
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h6 class="fw-bold text-secondary m-0 small">Progresso Checklist</h6>
                                <button type="button" class="btn btn-sm btn-outline-primary rounded-pill py-0 px-2" style="font-size:0.75rem;" onclick="addChkEdit({{ demanda.id }})">+ Item</button>
                            </div>
                            
                            <div class="d-flex align-items-center mb-3">
                                <div class="progress flex-grow-1 me-2 rounded-pill" style="height: 10px;">
                                    <div class="progress-bar {% if percentual == 100 %}bg-success{% else %}bg-primary{% endif %} rounded-pill" style="width: {{ percentual }}%;"></div>
                                </div>
                                <small class="fw-bold text-muted" style="font-size: 0.8rem;">{{ percentual }}%</small>
                            </div>

                            <div class="mb-4">
                                {% for chk in demanda.checklists %}
                                <div class="d-flex align-items-center mb-2">
                                    <input class="form-check-input mt-0 me-2 border-secondary" type="checkbox" name="chk_status_{{ chk.id }}" value="1" {% if chk.concluido %}checked{% endif %} style="transform: scale(1.15);">
                                    <input type="text" name="chk_texto_{{ chk.id }}" class="form-control form-control-sm {% if chk.concluido %}text-decoration-line-through text-success fw-bold{% else %}text-dark{% endif %}" value="{{ chk.passo }}" style="border: 1px dashed transparent; background: transparent; transition: 0.3s;" onfocus="this.style.border='1px dashed #ccc'; this.style.background='#fff';" onblur="this.style.border='1px dashed transparent'; this.style.background='transparent';">
                                </div>
                                {% else %}
                                <p class="text-muted small">Nenhuma subetapa cadastrada.</p>
                                {% endfor %}
                                <div id="new-chk-container-{{ demanda.id }}"></div>
                            </div>
                            <button type="submit" class="btn btn-primary btn-app w-100 shadow-sm">💾 Salvar Modificações</button>
                        </form>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="text-center py-5">
                <i class="bi bi-inbox fs-1 text-muted"></i>
                <p class="text-muted mt-2">Nenhuma demanda neste filtro! 🎉</p>
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
            div.innerHTML = `<span class="me-2 text-primary" style="width: 16px;"><i class="bi bi-dot"></i></span>
                             <input type="text" name="novo_passo[]" class="form-control form-control-sm border-primary" placeholder="Novo item da etapa...">`;
            container.appendChild(div);
        }
    </script>
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
                <label class="form-label fw-bold text-secondary small">Título da Demanda</label>
                <input type="text" name="titulo" class="form-control" placeholder="Ex: Criação de Dashboard ANS..." required>
            </div>
            
            <div class="row mb-3">
                <div class="col-6">
                    <label class="form-label fw-bold text-secondary small">Área Responsável</label>
                    <select name="area" class="form-select" required>
                        <option value="CODER">CODER</option>
                        <option value="COCAP">COCAP</option>
                        <option value="CONEC">CONEC</option>
                        <option value="GERED">GERED</option>
                        <option value="EXTERNO">EXTERNO</option>
                    </select>
                </div>
                <div class="col-6">
                    <label class="form-label fw-bold text-secondary small">Prioridade</label>
                    <select name="prioridade" class="form-select" required>
                        <option value="Mínimo">🟢 Mínimo</option>
                        <option value="Médio" selected>🔵 Médio</option>
                        <option value="Alto">🟡 Alto</option>
                        <option value="Extremo">🔴 Extremo</option>
                    </select>
                </div>
            </div>
            
            <div class="mb-3">
                <label class="form-label fw-bold text-secondary small">Observações / Escopo Detalhado</label>
                <textarea name="descricao" class="form-control" rows="3" placeholder="Insira os detalhes técnicos, links ou resumos..." required></textarea>
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
    filtro_status = request.args.get('status', 'Pendente')
    filtro_area = request.args.get('area', 'Todas')
    
    query = Demanda.query.filter(Demanda.status == filtro_status)
    if filtro_area != 'Todas':
        query = query.filter(Demanda.area == filtro_area)
        
    demandas_filtradas = query.all()
    peso_prioridade = {'Extremo': 4, 'Alto': 3, 'Médio': 2, 'Mínimo': 1}
    demandas_filtradas.sort(key=lambda x: (-peso_prioridade.get(x.prioridade, 0), x.data_prevista))
    
    demandas_em_aberto = Demanda.query.filter(Demanda.status != 'Finalizado').all()
    demandas_em_aberto.sort(key=lambda x: (-peso_prioridade.get(x.prioridade, 0), x.data_prevista))
    
    texto_whats = "🚀 *RESUMO DE DEMANDAS ATIVAS*\n\n"
    icones = {'Extremo': '🔴', 'Alto': '🟡', 'Médio': '🔵', 'Mínimo': '🟢'}
    
    for d in demandas_em_aberto:
        ico = icones.get(d.prioridade, '🔹')
        vencimento = d.data_prorrogacao.strftime('%d/%m/%Y') if d.data_prorrogacao else d.data_prevista.strftime('%d/%m/%Y')
        
        # ---------------------------------------------------------
        # NOVA LÓGICA DE PERCENTUAL NO PYTHON (PARA O ZAP)
        # ---------------------------------------------------------
        total_chk = len(d.checklists)
        concluidos = sum(1 for chk in d.checklists if chk.concluido)
        percentual = int((concluidos / total_chk) * 100) if total_chk > 0 else 0
        # ---------------------------------------------------------
        
        texto_whats += f"{ico} *{d.titulo}*\n"
        texto_whats += f"🏢 *Área:* {d.area}\n"
        texto_whats += f"📅 *Vencimento:* {vencimento}\n"
        # ADICIONADO O PERCENTUAL AQUI DO LADO DO STATUS
        texto_whats += f"📊 *Status:* {d.status} ({percentual}%)\n"
        texto_whats += "------------------------\n"
        
    if not demandas_em_aberto:
        texto_whats += "✅ Nenhuma demanda pendente no momento!\n"
        
    texto_codificado = urllib.parse.quote(texto_whats)
    numero_destino = "5561995414168"
    link_whatsapp = f"https://wa.me/{numero_destino}?text={texto_codificado}"

    return render_template_string(TELA_PRINCIPAL, demandas=demandas_filtradas, link_whatsapp=link_whatsapp, page='demandas', filtro_status=filtro_status, filtro_area=filtro_area)

@app.route('/nova_demanda', methods=['GET', 'POST'])
def nova_demanda():
    if request.method == 'POST':
        nova_dem = Demanda(
            titulo=request.form.get('titulo', 'Sem título'),
            area=request.form['area'], 
            descricao=request.form['descricao'], 
            prioridade=request.form['prioridade'], 
            data_inicio=datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date() if request.form.get('data_inicio') else None, 
            data_prevista=datetime.strptime(request.form['data_prevista'], '%Y-%m-%d').date()
        )
        db.session.add(nova_dem)
        db.session.flush() 
        for passo in request.form.getlist('passo_checklist[]'):
            if passo.strip(): 
                db.session.add(Checklist(demanda_id=nova_dem.id, passo=passo))
        db.session.commit()
        return redirect(url_for('index', status='Pendente'))
    return render_template_string(TELA_NOVA_DEMANDA)

@app.route('/atualizar/<int:id>', methods=['POST'])
def atualizar(id):
    demanda = Demanda.query.get_or_404(id)
    origem_status = request.args.get('status', 'Pendente')
    origem_area = request.args.get('area', 'Todas')
    
    demanda.status = request.form.get('status', demanda.status)
    demanda.descricao = request.form.get('descricao', demanda.descricao)
    
    d_inicio = request.form.get('data_inicio')
    demanda.data_inicio = datetime.strptime(d_inicio, '%Y-%m-%d').date() if d_inicio else None
    
    d_prorrog = request.form.get('data_prorrogacao')
    demanda.data_prorrogacao = datetime.strptime(d_prorrog, '%Y-%m-%d').date() if d_prorrog else None
    
    if demanda.status == 'Finalizado':
        demanda.data_conclusao = datetime.utcnow().date()
    else:
        demanda.data_conclusao = None
    
    for chk in demanda.checklists:
        chk.concluido = f'chk_status_{chk.id}' in request.form
        novo_texto = request.form.get(f'chk_texto_{chk.id}')
        if novo_texto:
            chk.passo = novo_texto
            
    novos_passos = request.form.getlist('novo_passo[]')
    for np in novos_passos:
        if np.strip():
            db.session.add(Checklist(demanda_id=demanda.id, passo=np.strip()))
            
    db.session.commit()
    return redirect(url_for('index', status=origem_status, area=origem_area))

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
        
        def limpa_texto(texto):
            return str(texto).encode('latin-1', 'replace').decode('latin-1')
        
        pdf.set_font("helvetica", style="B", size=16)
        titulo_completo = limpa_texto(f"Ata de Reunião: {ata.assunto}")
        linhas_titulo = textwrap.wrap(titulo_completo, width=45, break_long_words=True)
        for linha_t in linhas_titulo:
            pdf.multi_cell(0, 10, linha_t, align="C", new_x="LMARGIN", new_y="NEXT")
        
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
                for pedaco in linhas_quebradas:
                    pdf.multi_cell(0, 8, pedaco, new_x="LMARGIN", new_y="NEXT")
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
