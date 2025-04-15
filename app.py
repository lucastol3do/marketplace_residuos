from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_session import Session
from flask_restful import Api, Resource
import sqlite3
from datetime import datetime
import hashlib
import requests
from geopy.distance import geodesic
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io
import pandas as pd
import json
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
api = Api(app)

def conectar_banco():
    conn = sqlite3.connect('C:/Users/Toledo/Desktop/marketplace_residuos/marketplace_residuos.db')
    conn.row_factory = sqlite3.Row
    return conn

def criar_tabelas():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            localizacao TEXT NOT NULL,
            email TEXT UNIQUE,
            senha TEXT,
            descricao TEXT,
            residuos_preferidos TEXT,
            contato TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS residuos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER,
            tipo_residuo TEXT NOT NULL,
            quantidade REAL NOT NULL,
            unidade TEXT NOT NULL,
            localizacao TEXT NOT NULL,
            data_registro TEXT NOT NULL,
            data_validade TEXT,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            residuo_id INTEGER,
            empresa_geradora_id INTEGER,
            empresa_recicladora_id INTEGER,
            quantidade REAL NOT NULL,
            co2_economizado REAL NOT NULL DEFAULT 0,
            data_transacao TEXT NOT NULL,
            FOREIGN KEY (residuo_id) REFERENCES residuos(id),
            FOREIGN KEY (empresa_geradora_id) REFERENCES empresas(id),
            FOREIGN KEY (empresa_recicladora_id) REFERENCES empresas(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER,
            mensagem TEXT NOT NULL,
            data TEXT NOT NULL,
            lida INTEGER DEFAULT 0,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS propostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            residuo_id INTEGER,
            empresa_geradora_id INTEGER,
            empresa_recicladora_id INTEGER,
            quantidade REAL NOT NULL,
            mensagem TEXT,
            status TEXT DEFAULT 'pendente',
            data TEXT NOT NULL,
            FOREIGN KEY (residuo_id) REFERENCES residuos(id),
            FOREIGN KEY (empresa_geradora_id) REFERENCES empresas(id),
            FOREIGN KEY (empresa_recicladora_id) REFERENCES empresas(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conquistas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER,
            nome TEXT NOT NULL,
            descricao TEXT NOT NULL,
            data TEXT NOT NULL,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    ''')
    conn.commit()
    conn.close()

def geocode_address(address):
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': address, 'format': 'json'},
            headers={'User-Agent': 'MarketplaceResiduos/1.0'}
        )
        data = response.json()
        if data and len(data) > 0:
            return float(data[0]['lat']), float(data[0]['lon'])
        return None, None
    except:
        return None, None

def calcular_co2_economizado(tipo_residuo, quantidade):
    fatores_co2 = {'plastico': 2.5, 'metal': 9.0, 'papel': 1.0, 'organico': 0.5}
    tipo_normalizado = tipo_residuo.lower()
    return quantidade * fatores_co2.get(tipo_normalizado, 1.0)

def login_required(f):
    def wrap(*args, **kwargs):
        if 'empresa_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM empresas WHERE id = ?', (session['empresa_id'],))
        if not cursor.fetchone():
            session.clear()
            flash('Sessão inválida. Faça login novamente.', 'danger')
            return redirect(url_for('login'))
        conn.close()
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        tipo = request.form['tipo']
        localizacao = request.form['localizacao']
        email = request.form['email']
        senha = request.form['senha']
        descricao = request.form.get('descricao', '')
        residuos_preferidos = request.form.get('residuos_preferidos', '')
        contato = request.form.get('contato', '')
        senha_hash = hashlib.sha256(senha.encode()).hexdigest()
        conn = conectar_banco()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO empresas (nome, tipo, localizacao, email, senha, descricao, residuos_preferidos, contato) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                           (nome, tipo, localizacao, email, senha_hash, descricao, residuos_preferidos, contato))
            conn.commit()
            flash('Cadastro realizado com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email já cadastrado.', 'danger')
        finally:
            conn.close()
    return render_template('cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        senha_hash = hashlib.sha256(senha.encode()).hexdigest()
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM empresas WHERE email = ? AND senha = ?', (email, senha_hash))
        empresa = cursor.fetchone()
        conn.close()
        if empresa:
            session['empresa_id'] = empresa['id']
            session['empresa_nome'] = empresa['nome']
            session['empresa_tipo'] = empresa['tipo']
            session['empresa_localizacao'] = empresa['localizacao']
            logging.debug(f"Login successful: empresa_id={empresa['id']}")
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            logging.debug("Login failed: Invalid email or password")
            flash('Email ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    conn = conectar_banco()
    cursor = conn.cursor()
    empresa_id = session['empresa_id']
    empresa_tipo = session['empresa_tipo']
    
    logging.debug(f"Session data: empresa_id={empresa_id}, empresa_tipo={empresa_tipo}")
    
    # CO2 total
    cursor.execute('SELECT SUM(co2_economizado) AS total_co2 FROM transacoes')
    total_co2 = cursor.fetchone()['total_co2'] or 0
    
    # Resíduos disponíveis
    cursor.execute('SELECT COUNT(*) AS count, SUM(quantidade) AS total FROM residuos WHERE quantidade > 0 AND (data_validade IS NULL OR data_validade >= date("now"))')
    residuos_disponiveis = cursor.fetchone()
    total_residuos_count = residuos_disponiveis['count'] or 0
    total_residuos_quantidade = residuos_disponiveis['total'] or 0
    
    # Atividade da empresa
    recentes = []
    if empresa_tipo == 'geradora':
        cursor.execute('SELECT COUNT(*) AS count, SUM(quantidade) AS total FROM residuos WHERE empresa_id = ? AND unidade = "Toneladas"', (empresa_id,))
        residuos_empresa = cursor.fetchone()
        residuos_registrados_count = residuos_empresa['count'] or 0
        residuos_registrados_quantidade = residuos_empresa['total'] or 0
        cursor.execute('SELECT r.*, e.nome AS empresa_nome FROM residuos r JOIN empresas e ON r.empresa_id = e.id WHERE r.empresa_id = ? ORDER BY r.data_registro DESC LIMIT 5', (empresa_id,))
        recentes = cursor.fetchall()
    else:
        cursor.execute('SELECT COUNT(*) AS count, SUM(quantidade) AS total FROM transacoes WHERE empresa_recicladora_id = ?', (empresa_id,))
        transacoes_empresa = cursor.fetchone()
        transacoes_realizadas_count = transacoes_empresa['count'] or 0
        transacoes_realizadas_quantidade = transacoes_empresa['total'] or 0
        cursor.execute('SELECT t.*, r.tipo_residuo FROM transacoes t JOIN residuos r ON t.residuo_id = r.id WHERE t.empresa_recicladora_id = ? ORDER BY t.data_transacao DESC LIMIT 5', (empresa_id,))
        recentes = cursor.fetchall()
    
    # Percentual de reciclagem por tipo
    cursor.execute('''
        SELECT r.tipo_residuo, SUM(t.quantidade) AS total 
        FROM transacoes t 
        JOIN residuos r ON t.residuo_id = r.id 
        GROUP BY r.tipo_residuo
    ''')
    trans_por_tipo = cursor.fetchall()
    total_trans = sum(t['total'] for t in trans_por_tipo) or 1
    percentuais = {t['tipo_residuo']: (t['total'] / total_trans * 100) for t in trans_por_tipo}
    
    # Tendências (últimos 6 meses)
    cursor.execute('SELECT strftime("%Y-%m", data_transacao) AS mes, SUM(quantidade) AS total FROM transacoes WHERE data_transacao >= date("now", "-6 months") GROUP BY mes')
    tendencias = cursor.fetchall()
    meses = [t['mes'] for t in tendencias]
    quantidades_tend = [t['total'] or 0 for t in tendencias]
    
    # Benchmarking
    cursor.execute('SELECT empresa_recicladora_id, SUM(co2_economizado) AS total_co2 FROM transacoes GROUP BY empresa_recicladora_id ORDER BY total_co2 DESC')
    ranking = cursor.fetchall()
    minha_posicao = next((i + 1 for i, r in enumerate(ranking) if r['empresa_recicladora_id'] == empresa_id), None)
    total_empresas = len(ranking)
    percentil = (1 - minha_posicao / total_empresas * 100) if minha_posicao and total_empresas else None
    
    # Notificações
    cursor.execute('SELECT * FROM notificacoes WHERE empresa_id = ? AND lida = 0 ORDER BY data DESC', (empresa_id,))
    notificacoes = cursor.fetchall()
    
    # Sugestões de matching
    preferidos_row = cursor.execute('SELECT residuos_preferidos FROM empresas WHERE id = ?', (empresa_id,)).fetchone()
    preferidos = preferidos_row['residuos_preferidos'] or '' if preferidos_row else ''
    preferidos = [p.strip() for p in preferidos.split(',') if p.strip()] if preferidos else []
    sugestoes = []
    if preferidos and empresa_tipo == 'recicladora':
        query = 'SELECT r.*, e.nome AS empresa_nome FROM residuos r JOIN empresas e ON r.empresa_id = e.id WHERE r.quantidade > 0 AND r.tipo_residuo IN ({}) AND (r.data_validade IS NULL OR r.data_validade >= date("now")) LIMIT 5'.format(','.join('?' for _ in preferidos))
        cursor.execute(query, preferidos)
        sugestoes = cursor.fetchall()
    
    # Conquistas
    cursor.execute('SELECT * FROM conquistas WHERE empresa_id = ? ORDER BY data DESC LIMIT 3', (empresa_id,))
    conquistas = cursor.fetchall()
    
    # Distribuição de resíduos
    cursor.execute('SELECT tipo_residuo, SUM(quantidade) AS total FROM residuos WHERE unidade = "Toneladas" GROUP BY tipo_residuo')
    residuos_por_tipo = cursor.fetchall()
    tipos = ['Plástico', 'Metal', 'Papel', 'Orgânico']
    quantidades = [0] * len(tipos)
    for r in residuos_por_tipo:
        if r['tipo_residuo'] in tipos:
            quantidades[tipos.index(r['tipo_residuo'])] = r['total'] or 0
    
    conn.close()
    
    return render_template(
        'index.html',
        total_co2=total_co2,
        total_residuos_count=total_residuos_count,
        total_residuos_quantidade=total_residuos_quantidade,
        empresa_tipo=empresa_tipo,
        residuos_registrados_count=residuos_registrados_count if empresa_tipo == 'geradora' else None,
        residuos_registrados_quantidade=residuos_registrados_quantidade if empresa_tipo == 'geradora' else None,
        transacoes_realizadas_count=transacoes_realizadas_count if empresa_tipo == 'recicladora' else None,
        transacoes_realizadas_quantidade=transacoes_realizadas_quantidade if empresa_tipo == 'recicladora' else None,
        recentes=recentes,
        percentuais=percentuais,
        meses=meses,
        quantidades_tend=quantidades_tend,
        minha_posicao=minha_posicao,
        percentil=percentil,
        notificacoes=notificacoes,
        sugestoes=sugestoes,
        conquistas=conquistas,
        tipos_residuos=tipos,
        quantidades_residuos=quantidades
    )

@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    conn = conectar_banco()
    cursor = conn.cursor()
    empresa_id = session['empresa_id']
    
    if request.method == 'POST':
        descricao = request.form['descricao']
        residuos_preferidos = request.form['residuos_preferidos']
        contato = request.form['contato']
        cursor.execute('UPDATE empresas SET descricao = ?, residuos_preferidos = ?, contato = ? WHERE id = ?',
                       (descricao, residuos_preferidos, contato, empresa_id))
        conn.commit()
        flash('Perfil atualizado com sucesso!', 'success')
        conn.close()
        return redirect(url_for('perfil'))
    
    cursor.execute('SELECT * FROM empresas WHERE id = ?', (empresa_id,))
    empresa = cursor.fetchone()
    cursor.execute('SELECT * FROM conquistas WHERE empresa_id = ? ORDER BY data DESC', (empresa_id,))
    conquistas = cursor.fetchall()
    conn.close()
    return render_template('perfil.html', empresa=empresa, conquistas=conquistas)

@app.route('/registrar_residuo', methods=['GET', 'POST'])
@login_required
def registrar_residuo():
    if session['empresa_tipo'] != 'geradora':
        flash('Apenas empresas geradoras podem registrar resíduos.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        empresa_id = session['empresa_id']
        tipo_residuo = request.form['tipo_residuo']
        quantidade = float(request.form['quantidade'])
        unidade = request.form['unidade']
        localizacao = request.form['localizacao']
        data_validade = request.form.get('data_validade') or None
        data_registro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO residuos (empresa_id, tipo_residuo, quantidade, unidade, localizacao, data_registro, data_validade) VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (empresa_id, tipo_residuo, quantidade, unidade, localizacao, data_registro, data_validade))
        residuo_id = cursor.lastrowid
        cursor.execute('SELECT id FROM empresas WHERE tipo = "recicladora" AND residuos_preferidos LIKE ?', (f'%{tipo_residuo}%',))
        recicladoras = cursor.fetchall()
        for r in recicladoras:
            cursor.execute('INSERT INTO notificacoes (empresa_id, mensagem, data) VALUES (?, ?, ?)',
                           (r['id'], f'Novo resíduo disponível: {tipo_residuo}, {quantidade} {unidade}.', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        flash('Resíduo registrado com sucesso!', 'success')
        return redirect(url_for('index'))
    tipos_residuos = ['Plástico', 'Metal', 'Papel', 'Orgânico']
    unidades = ['Toneladas', 'Quilogramas', 'Litros']
    return render_template('registrar_residuo.html', tipos_residuos=tipos_residuos, unidades=unidades)

@app.route('/buscar_residuos', methods=['GET', 'POST'])
@login_required
def buscar_residuos():
    residuos = []
    residuos_com_coordenadas = []
    tipos_residuos = ['Plástico', 'Metal', 'Papel', 'Orgânico']
    
    if request.method == 'POST':
        tipo_residuo = request.form['tipo_residuo']
        raio = float(request.form.get('raio', 0)) or None
        quantidade_min = float(request.form.get('quantidade_min', 0)) or None
        data_inicio = request.form.get('data_inicio') or None
        data_fim = request.form.get('data_fim') or None
        
        query = '''
            SELECT r.*, e.nome AS empresa_nome, e.contato, e.descricao 
            FROM residuos r 
            JOIN empresas e ON r.empresa_id = e.id 
            WHERE r.quantidade > 0 AND r.tipo_residuo LIKE ? 
            AND (r.data_validade IS NULL OR r.data_validade >= date("now"))
        '''
        params = [f'%{tipo_residuo}%']
        
        if quantidade_min:
            query += ' AND r.quantidade >= ?'
            params.append(quantidade_min)
        if data_inicio:
            query += ' AND r.data_registro >= ?'
            params.append(data_inicio)
        if data_fim:
            query += ' AND r.data_registro <= ?'
            params.append(data_fim)
        
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute(query, params)
        residuos = cursor.fetchall()
        
        if raio and session['empresa_localizacao']:
            empresa_lat, empresa_lon = geocode_address(session['empresa_localizacao'])
            if empresa_lat and empresa_lon:
                residuos_filtrados = []
                for r in residuos:
                    residuo_lat, residuo_lon = geocode_address(r['localizacao'])
                    if residuo_lat and residuo_lon:
                        distancia = geodesic((empresa_lat, empresa_lon), (residuo_lat, residuo_lon)).km
                        if distancia <= raio:
                            residuos_filtrados.append(r)
                residuos = residuos_filtrados
        
        for residuo in residuos:
            lat, lon = geocode_address(residuo['localizacao'])
            if lat and lon:
                residuos_com_coordenadas.append({
                    'id': residuo['id'],
                    'empresa_nome': residuo['empresa_nome'],
                    'tipo_residuo': residuo['tipo_residuo'],
                    'quantidade': residuo['quantidade'],
                    'unidade': residuo['unidade'],
                    'localizacao': residuo['localizacao'],
                    'data_registro': residuo['data_registro'],
                    'contato': residuo['contato'],
                    'descricao': residuo['descricao'],
                    'lat': lat,
                    'lon': lon
                })
        
        conn.close()
    
    return render_template('buscar_residuos.html', residuos=residuos, residuos_com_coordenadas=residuos_com_coordenadas, tipos_residuos=tipos_residuos)

@app.route('/calcular_rota', methods=['POST'])
@login_required
def calcular_rota():
    residuos_ids = request.form.getlist('residuos')
    if not residuos_ids:
        flash('Selecione pelo menos um resíduo.', 'danger')
        return redirect(url_for('buscar_residuos'))
    
    conn = conectar_banco()
    cursor = conn.cursor()
    query = f'SELECT * FROM residuos WHERE id IN ({",".join("?" for _ in residuos_ids)})'
    cursor.execute(query, residuos_ids)
    residuos = cursor.fetchall()
    conn.close()
    
    pontos = []
    for r in residuos:
        lat, lon = geocode_address(r['localizacao'])
        if lat and lon:
            pontos.append({'lat': lat, 'lon': lon, 'nome': f"{r['tipo_residuo']} ({r['quantidade']} {r['unidade']})"})
    
    if len(pontos) < 1:
        flash('Não foi possível calcular a rota.', 'danger')
        return redirect(url_for('buscar_residuos'))
    
    return render_template('rota.html', pontos=pontos)

@app.route('/transacoes', methods=['GET', 'POST'])
@login_required
def transacoes():
    if session['empresa_tipo'] != 'recicladora':
        flash('Apenas empresas recicladoras podem registrar transações.', 'danger')
        return redirect(url_for('index'))
    
    conn = conectar_banco()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        residuo_id = request.form['residuo_id']
        empresa_recicladora_id = session['empresa_id']
        quantidade = float(request.form['quantidade'])
        data_transacao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('SELECT empresa_id, tipo_residuo, quantidade FROM residuos WHERE id = ?', (residuo_id,))
        residuo = cursor.fetchone()
        if not residuo:
            flash('Resíduo não encontrado.', 'danger')
            conn.close()
            return redirect(url_for('transacoes'))
        if quantidade <= 0 or quantidade > residuo['quantidade']:
            flash('Quantidade inválida.', 'danger')
            conn.close()
            return redirect(url_for('transacoes'))
        
        empresa_geradora_id = residuo['empresa_id']
        tipo_residuo = residuo['tipo_residuo']
        co2_economizado = calcular_co2_economizado(tipo_residuo, quantidade)
        
        cursor.execute('INSERT INTO transacoes (residuo_id, empresa_geradora_id, empresa_recicladora_id, quantidade, co2_economizado, data_transacao) VALUES (?, ?, ?, ?, ?, ?)',
                       (residuo_id, empresa_geradora_id, empresa_recicladora_id, quantidade, co2_economizado, data_transacao))
        cursor.execute('UPDATE residuos SET quantidade = quantidade - ? WHERE id = ?', (quantidade, residuo_id))
        
        cursor.execute('INSERT INTO notificacoes (empresa_id, mensagem, data) VALUES (?, ?, ?)',
                       (empresa_geradora_id, f'Sua transação de {quantidade} {residuo["unidade"]} de {tipo_residuo} foi registrada.', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        cursor.execute('SELECT SUM(quantidade) AS total FROM transacoes WHERE empresa_recicladora_id = ?', (empresa_recicladora_id,))
        total_reciclado = cursor.fetchone()['total'] or 0
        if total_reciclado >= 100 and not cursor.execute('SELECT 1 FROM conquistas WHERE empresa_id = ? AND nome = "Reciclador de Ouro"', (empresa_recicladora_id,)).fetchone():
            cursor.execute('INSERT INTO conquistas (empresa_id, nome, descricao, data) VALUES (?, ?, ?, ?)',
                           (empresa_recicladora_id, 'Reciclador de Ouro', 'Reciclou 100 toneladas de resíduos.', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        flash('Transação registrada com sucesso!', 'success')
        return redirect(url_for('transacoes'))
    
    cursor.execute('SELECT r.id, r.empresa_id, r.tipo_residuo, r.quantidade, r.unidade, r.localizacao, r.data_registro, e.nome AS empresa_nome FROM residuos r JOIN empresas e ON r.empresa_id = e.id WHERE r.quantidade > 0 AND (r.data_validade IS NULL OR r.data_validade >= date("now"))')
    residuos = cursor.fetchall()
    residuos_dict = [{'id': r['id'], 'empresa_id': r['empresa_id'], 'empresa_nome': r['empresa_nome'], 'tipo_residuo': r['tipo_residuo'], 'quantidade': r['quantidade'], 'unidade': r['unidade'], 'localizacao': r['localizacao'], 'data_registro': r['data_registro']} for r in residuos]
    residuos_com_coordenadas = []
    for residuo in residuos:
        lat, lon = geocode_address(residuo['localizacao'])
        if lat and lon:
            residuos_com_coordenadas.append({
                'id': residuo['id'], 'empresa_id': residuo['empresa_id'], 'empresa_nome': residuo['empresa_nome'],
                'tipo_residuo': residuo['tipo_residuo'], 'quantidade': residuo['quantidade'], 'unidade': residuo['unidade'],
                'localizacao': residuo['localizacao'], 'data_registro': residuo['data_registro'], 'lat': lat, 'lon': lon
            })
    
    cursor.execute('SELECT DISTINCT e.id, e.nome FROM empresas e JOIN residuos r ON e.id = r.empresa_id WHERE e.tipo = "geradora" AND r.quantidade > 0 AND (r.data_validade IS NULL OR r.data_validade >= date("now")) ORDER BY e.nome')
    empresas_geradoras = cursor.fetchall()
    
    cursor.execute('SELECT t.*, r.tipo_residuo, e.nome AS empresa_geradora_nome FROM transacoes t JOIN residuos r ON t.residuo_id = r.id JOIN empresas e ON t.empresa_geradora_id = e.id ORDER BY t.data_transacao DESC')
    transacoes = cursor.fetchall()
    
    conn.close()
    
    return render_template('transacoes.html', transacoes=transacoes, residuos=residuos_dict, residuos_com_coordenadas=residuos_com_coordenadas, empresas_geradoras=empresas_geradoras)

@app.route('/notificacoes', methods=['POST'])
@login_required
def marcar_notificacao_lida():
    notificacao_id = request.form['notificacao_id']
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute('UPDATE notificacoes SET lida = 1 WHERE id = ?', (notificacao_id,))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/propostas', methods=['GET', 'POST'])
@login_required
def propostas():
    conn = conectar_banco()
    cursor = conn.cursor()
    empresa_id = session['empresa_id']
    
    if request.method == 'POST':
        residuo_id = request.form['residuo_id']
        quantidade = float(request.form['quantidade'])
        mensagem = request.form['mensagem']
        cursor.execute('SELECT empresa_id, quantidade FROM residuos WHERE id = ?', (residuo_id,))
        residuo = cursor.fetchone()
        if not residuo or quantidade <= 0 or quantidade > residuo['quantidade']:
            flash('Proposta inválida.', 'danger')
            conn.close()
            return redirect(url_for('propostas'))
        
        cursor.execute('INSERT INTO propostas (residuo_id, empresa_geradora_id, empresa_recicladora_id, quantidade, mensagem, data) VALUES (?, ?, ?, ?, ?, ?)',
                       (residuo_id, residuo['empresa_id'], empresa_id, quantidade, mensagem, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        flash('Proposta enviada com sucesso!', 'success')
    
    cursor.execute('SELECT p.*, r.tipo_residuo, e.nome AS geradora_nome FROM propostas p JOIN residuos r ON p.residuo_id = r.id JOIN empresas e ON p.empresa_geradora_id = e.id WHERE p.empresa_geradora_id = ? OR p.empresa_recicladora_id = ?', (empresa_id, empresa_id))
    propostas = cursor.fetchall()
    conn.close()
    return render_template('propostas.html', propostas=propostas)

@app.route('/proposta/<int:id>/aceitar', methods=['POST'])
@login_required
def aceitar_proposta(id):
    if session['empresa_tipo'] != 'geradora':
        flash('Apenas geradoras podem aceitar propostas.', 'danger')
        return redirect(url_for('propostas'))
    
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM propostas WHERE id = ? AND status = "pendente"', (id,))
    proposta = cursor.fetchone()
    if not proposta:
        flash('Proposta inválida ou já processada.', 'danger')
        conn.close()
        return redirect(url_for('propostas'))
    
    cursor.execute('SELECT quantidade FROM residuos WHERE id = ?', (proposta['residuo_id'],))
    residuo = cursor.fetchone()
    if residuo['quantidade'] < proposta['quantidade']:
        flash('Quantidade insuficiente no resíduo.', 'danger')
        conn.close()
        return redirect(url_for('propostas'))
    
    co2_economizado = calcular_co2_economizado(cursor.execute('SELECT tipo_residuo FROM residuos WHERE id = ?', (proposta['residuo_id'],)).fetchone()['tipo_residuo'], proposta['quantidade'])
    cursor.execute('INSERT INTO transacoes (residuo_id, empresa_geradora_id, empresa_recicladora_id, quantidade, co2_economizado, data_transacao) VALUES (?, ?, ?, ?, ?, ?)',
                   (proposta['residuo_id'], proposta['empresa_geradora_id'], proposta['empresa_recicladora_id'], proposta['quantidade'], co2_economizado, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    cursor.execute('UPDATE residuos SET quantidade = quantidade - ? WHERE id = ?', (proposta['quantidade'], proposta['residuo_id']))
    cursor.execute('UPDATE propostas SET status = "aceita" WHERE id = ?', (id,))
    cursor.execute('INSERT INTO notificacoes (empresa_id, mensagem, data) VALUES (?, ?, ?)',
                   (proposta['empresa_recicladora_id'], 'Sua proposta foi aceita!', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    flash('Proposta aceita com sucesso!', 'success')
    return redirect(url_for('propostas'))

@app.route('/proposta/<int:id>/rejeitar', methods=['POST'])
@login_required
def rejeitar_proposta(id):
    if session['empresa_tipo'] != 'geradora':
        flash('Apenas geradoras podem rejeitar propostas.', 'danger')
        return redirect(url_for('propostas'))
    
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute('UPDATE propostas SET status = "rejeitada" WHERE id = ?', (id,))
    cursor.execute('SELECT empresa_recicladora_id FROM propostas WHERE id = ?', (id,))
    recicladora_id = cursor.fetchone()['empresa_recicladora_id']
    cursor.execute('INSERT INTO notificacoes (empresa_id, mensagem, data) VALUES (?, ?, ?)',
                   (recicladora_id, 'Sua proposta foi rejeitada.', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    flash('Proposta rejeitada.', 'info')
    return redirect(url_for('propostas'))

@app.route('/certificado/<int:transacao_id>')
@login_required
def certificado(transacao_id):
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute('SELECT t.*, r.tipo_residuo, eg.nome AS geradora, er.nome AS recicladora FROM transacoes t JOIN residuos r ON t.residuo_id = r.id JOIN empresas eg ON t.empresa_geradora_id = eg.id JOIN empresas er ON t.empresa_recicladora_id = er.id WHERE t.id = ?', (transacao_id,))
    transacao = cursor.fetchone()
    conn.close()
    
    if not transacao:
        flash('Transação não encontrada.', 'danger')
        return redirect(url_for('transacoes'))
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.drawString(100, 750, "Certificado de Reciclagem")
    c.drawString(100, 720, f"Geradora: {transacao['geradora']}")
    c.drawString(100, 700, f"Recicladora: {transacao['recicladora']}")
    c.drawString(100, 680, f"Resíduo: {transacao['tipo_residuo']}")
    c.drawString(100, 660, f"Quantidade: {transacao['quantidade']} toneladas")
    c.drawString(100, 640, f"CO2 Economizado: {transacao['co2_economizado']:.2f} t CO2e")
    c.drawString(100, 620, f"Data: {transacao['data_transacao']}")
    c.showPage()
    c.save()
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name=f'certificado_{transacao_id}.pdf', mimetype='application/pdf')

@app.route('/relatorios', methods=['GET', 'POST'])
@login_required
def relatorios():
    if request.method == 'POST':
        tipo_relatorio = request.form['tipo_relatorio']
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        formato = request.form['formato']
        
        conn = conectar_banco()
        cursor = conn.cursor()
        query = ''
        params = [session['empresa_id']]
        
        if tipo_relatorio == 'residuos':
            query = 'SELECT r.* FROM residuos r WHERE r.empresa_id = ?'
            if data_inicio:
                query += ' AND r.data_registro >= ?'
                params.append(data_inicio)
            if data_fim:
                query += ' AND r.data_registro <= ?'
                params.append(data_fim)
        else:
            query = 'SELECT t.*, r.tipo_residuo FROM transacoes t JOIN residuos r ON t.residuo_id = r.id WHERE t.empresa_recicladora_id = ?'
            if data_inicio:
                query += ' AND t.data_transacao >= ?'
                params.append(data_inicio)
            if data_fim:
                query += ' AND t.data_transacao <= ?'
                params.append(data_fim)
        
        cursor.execute(query, params)
        dados = cursor.fetchall()
        conn.close()
        
        dados_dict = [dict(d) for d in dados]
        
        if formato == 'csv':
            df = pd.DataFrame(dados_dict)
            buffer = io.StringIO()
            df.to_csv(buffer, index=False)
            buffer.seek(0)
            return send_file(io.BytesIO(buffer.getvalue().encode()), as_attachment=True, download_name='relatorio.csv', mimetype='text/csv')
        
        return render_template('relatorios.html', dados=dados, tipo_relatorio=tipo_relatorio)
    
    return render_template('relatorios.html', dados=None)

@app.route('/ranking')
@login_required
def ranking():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute('SELECT e.nome, SUM(t.co2_economizado) AS total_co2 FROM transacoes t JOIN empresas e ON t.empresa_recicladora_id = e.id GROUP BY e.id ORDER BY total_co2 DESC LIMIT 10')
    ranking = cursor.fetchall()
    conn.close()
    return render_template('ranking.html', ranking=ranking)

@app.route('/calculadora', methods=['GET', 'POST'])
@login_required
def calculadora():
    tipos_residuos = ['Plástico', 'Metal', 'Papel', 'Orgânico']
    co2_economizado = None
    tipo_residuo = None
    quantidade = None
    
    if request.method == 'POST':
        try:
            tipo_residuo = request.form['tipo_residuo']
            quantidade = float(request.form['quantidade'])
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero.', 'danger')
                return render_template('calculadora.html', tipos_residuos=tipos_residuos, co2_economizado=None, tipo_residuo=tipo_residuo, quantidade=quantidade)
            co2_economizado = calcular_co2_economizado(tipo_residuo, quantidade)
        except ValueError:
            flash('Quantidade inválida. Use um número válido.', 'danger')
            return render_template('calculadora.html', tipos_residuos=tipos_residuos, co2_economizado=None, tipo_residuo=tipo_residuo, quantidade=quantidade)
    
    return render_template('calculadora.html', tipos_residuos=tipos_residuos, co2_economizado=co2_economizado, tipo_residuo=tipo_residuo, quantidade=quantidade)

class ResiduosAPI(Resource):
    def get(self):
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM residuos WHERE quantidade > 0 AND (data_validade IS NULL OR data_validade >= date("now"))')
        residuos = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return residuos

class TransacoesAPI(Resource):
    def post(self):
        data = request.get_json()
        if data.get('api_key') != 'sua_chave_secreta':
            return {'error': 'Autenticação inválida'}, 401
        return {'status': 'success'}, 201

api.add_resource(ResiduosAPI, '/api/residuos')
api.add_resource(TransacoesAPI, '/api/transacoes')

if __name__ == '__main__':
    criar_tabelas()
    app.run(debug=True)