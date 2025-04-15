# ♻️ Marketplace de Resíduos Industriais

Bem-vindo ao **Marketplace de Resíduos Industriais**, uma plataforma web para conectar empresas geradoras e recicladoras de resíduos, promovendo a **economia circular** 🌍 e a sustentabilidade. Este projeto alinha-se com os **ODS 9.2** (industrialização inclusiva) e **9.4** (práticas sustentáveis), incentivando a gestão responsável de resíduos industriais.

## 🚀 Visão Geral

Empresas geradoras podem registrar resíduos (ex.: Plástico, Metal), enquanto recicladoras podem buscar e negociar transações. A plataforma calcula o **CO2 economizado**, gera **certificados de reciclagem**, exibe **rankings** de impacto ambiental e oferece ferramentas como **calculadora de impacto** e **rotas de coleta**.

### ✨ Funcionalidades
- 📝 **Cadastro e Login**: Registre sua empresa como geradora ou recicladora.
- 🗑️ **Registro de Resíduos**: Geradoras adicionam resíduos com tipo, quantidade e validade.
- 🔍 **Busca de Resíduos**: Filtros por tipo, quantidade, localização e período.
- 🤝 **Propostas e Transações**: Envie propostas e registre transações com cálculo automático de CO2.
- 📊 **Relatórios**: Exporte dados de resíduos ou transações em CSV ou HTML.
- 🏆 **Ranking**: Veja as top recicladoras por CO2 economizado.
- 🧮 **Calculadora de Impacto**: Estime CO2 economizado por tipo de resíduo.
- 🗺️ **Rotas de Coleta**: Visualize mapas com pontos de coleta (usando Leaflet).
- 🔔 **Notificações**: Receba alertas sobre novos resíduos ou propostas.
- 🏅 **Conquistas**: Ganhe badges por metas de reciclagem.
- 📜 **Certificados**: Gere PDFs de transações concluídas.

## 🛠️ Tecnologias Utilizadas
- **Python** 🐍: Backend com Flask.
- **SQLite** 🗄️: Banco de dados leve.
- **Bootstrap 5.3** 🎨: Interface responsiva.
- **Leaflet** 🗺️: Mapas interativos.
- **Pandas** 📈: Exportação de relatórios.
- **Geopy** 🌐: Geolocalização.
- **ReportLab** 📄: Geração de PDFs.

## 📋 Pré-requisitos
- Python 3.10+ 🐍
- Git 📂
- Navegador moderno (Chrome, Firefox, etc.) 🌐


## 📜 Estrutura do Codigo

marketplace-residuos/
├── app.py
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── cadastro.html
│   ├── login.html
│   ├── index.html
│   ├── perfil.html
│   ├── registrar_residuo.html
│   ├── buscar_residuos.html
│   ├── transacoes.html
│   ├── propostas.html
│   ├── relatorios.html
│   ├── ranking.html
│   ├── calculadora.html
│   ├── rota.html
├── static/
│   ├── css/
│   │   ├── style.css
└── marketplace_residuos.db (criado automaticamente)

## ⚙️ Instalação

1. **Clone o repositório**:
   ```bash
   git clone https://github.com/lucastol3do/marketplace_residuos.git
   cd marketplace-residuos

2. **Instale as dependencias**:   
   ```bash
    pip install -r requirements.txt

3. **Execute o projeto:**
   ```bash
    python app.py
    
- Acesse `http://127.0.0.1:5000` e teste:
- Cadastre uma empresa (`/cadastro`).
- Faça login (`/login`).
- Teste `/calculadora`, `/relatorios`, `/ranking`.   



 

    