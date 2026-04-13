---
name: 3f-create-backend
description: Guia para criar novos projetos Backend compatíveis com o 3F Deploy Orchestrator (Auto-deploy & Auto-update).
---

# ⚙️ Skill: Criar Novo Projeto Backend (3F)

Este guia define como estruturar um novo serviço de backend para garantir performance e compatibilidade com o ecossistema 3F.

## 🏗️ Estrutura Obrigatória

### 1. Gestão de Processos (PM2)
- O Orquestrador usa PM2 para gerenciar os serviços. 
- O backend deve ser capaz de rodar via comando simples (ex: `node dist/index.js` ou `./venv/bin/python main.py`).

### 2. Contrato de Deploy (`ops/project.yml`)
Exemplo robusto para Node.js:
```yaml
kind: backend
runtime: node
install_cmd: pnpm install
build_cmd: pnpm build
start_cmd: node dist/index.js
port: 3000
requires_nginx: true # se precisar de domínio externo
domains:
  - api.meu-app.3fventure.tech
healthcheck: /health
```

## 🚨 Precauções Críticas (Segurança e Estabilidade)

### 🔑 Chaves e Segredos (Multiline)
- Se o backend usa chaves privadas (JWT, SSH), **NUNCA** deixe-as no código.
- Cadastre-as na aba **Segredos Globais** ou no **Ambiente** do projeto no Dashboard. O Orquestrador tratará a formatação multilinha automaticamente.

### 📁 Persistência de Dados
- Evite salvar arquivos locais no diretório do app (eles podem ser deletados num novo deploy).
- Use volumes externos ou bancos de dados (Supabase, PostgreSQL).

### 🔍 Health Check
- Implemente uma rota `/health` que retorne `200 OK`. Isso permite ao Orquestrador saber se o backend iniciou corretamente antes de liberar o tráfego.

## 🛠️ Passo a Passo por Linguagem

### Node.js (Express / Fastify + TS)
1. Inicie com `pnpm init`.
2. Configure o build para gerar a pasta `dist`.
3. Certifique-se de que o app lê `process.env.PORT`.
4. Crie `ops/project.yml`.

### Python (FastAPI / Flask)
1. Use `requirements.txt`.
2. Script de deploy (`ops/project.yml`):
   ```yaml
   install_cmd: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
   start_cmd: ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
   port: 8000
   ```

## 🔄 Fluxo de Deploy
1. Crie o repositório.
2. Adicione os arquivos básicos + `ops/project.yml`.
3. Adicione o projeto no Dashboard do Orquestrador.
4. Configure as variáveis de ambiente necessárias.
5. Clique em **Publicar**.
