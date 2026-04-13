---
name: 3f-deploy-integration
description: Guia Mestre para gerenciar, criar e adaptar projetos no 3F Deploy Orchestrator.
---

# 🚀 3F Deploy Integration & Manual de Uso

Este guia é a fonte única de verdade para gerenciar sua frota de aplicações. Ele combina as regras técnicas de infraestrutura com o manual de operação do usuário.

---

## 📖 1. Visão Geral
O 3F Deploy Orchestrator automatiza o ciclo de vida das aplicações na VPS:
- **Sincronização Git**: Clonagem inteligente com suporte a `main`/`master`.
- **Gerenciamento PM2**: Deploy limpo (Delete + Start) com liberação de porta (`killPort`).
- **Nginx & SSL**: Proxy reverso e Certbot automáticos via contrato.
- **Monorepos**: Suporte nativo via `app_path`.

---

## 🛠️ 2. Fazendo um Deploy (Passo a Passo)

### 2.1. Criar ou Adaptar um Sistema
Utilize as skills de criação/adaptação. O coração do sistema é o arquivo **`ops/project.yml`**.

**Checklist Técnico de Adaptação:**
- [ ] **project.yml**: Ele existe e segue o padrão (veja seção 3)?
- [ ] **Porta**: A porta no YML é a mesma que o app escuta?
- [ ] **Host**: Se for Vite/Frontend, o `start_cmd` tem `--host 0.0.0.0`?
- [ ] **Libs**: Dependências críticas estão listadas (ex: `PyJWT` para Python SSO)?
- [ ] **Checklist MANUAL**: Use o prompt: *"Crie um projeto seguindo a skill de integração e o checklist do MANUAL.md"*.

### 2.2. Adicionando no Dashboard
1. Clique em **"Adicionar Projeto"**.
2. **Slug (ID)**: Nome único (ex: `sistema-vendas`).
3. **Repositório**: Formato `Usuario/Repositorio`.
4. **Caminho na VPS**: Onde o código vive (ex: `/opt/apps/meu-app`).
5. **Sub-pasta (App Path)**: **Exclusivo para Monorepos.** Se o app estiver em uma pasta interna (ex: `apps/frontend`), coloque aqui para o `.env` ser criado no lugar certo.

### 2.3. Configurando e Publicando
1. Clique na **Engrenagem** e adicione os Segredos/Variáveis do `.env`.
2. Clique no botão **"Implantar"** (Nuvem).
3. Verifique o status. Se falhar, consulte o **Histórico** para ver o log de erro.

---

## 📋 3. Requisitos do Contrato (`ops/project.yml`)

```yaml
kind: frontend         # frontend | backend | fullstack
runtime: node          # ambiente (node, python)
install_cmd: pnpm install
build_cmd: pnpm build
start_cmd: pnpm run preview
pm2_name: "meu-app-exemplo"
port: 4000
domains:
  - "meu-app.3fventure.tech"
```

---

## 🚨 4. Regras de Ouro (Anti-Erros)

### 4.1. Segredos Multilinha
Cole chaves SSH/JWT no Dashboard exatamente como elas são. O Orquestrador cuida do escape automático para o `.env`.

### 4.2. Execução PM2 Robusta
O sistema injeta o `node_modules/.bin` no `PATH` e força `NODE_ENV=development` no `npm install` para garantir que ferramentas de build estejam presentes.

### 4.3. Python (FastAPI/Flask)
- Sempre use `venv`.
- `requirements.txt` deve ter `PyJWT` (SSO) e `httpx[http2]` (APIs modernas).

---

## 🔍 5. Resolução de Problemas (Troubleshooting)

- **"Address already in use"**: O sistema já tenta `killPort`. Se persistir, rode `fuser -k PORTA/tcp` na VPS.
- **"Couldn't find remote ref"**: Conflito de Monorepo. O sistema agora usa **Fila de Sincronização (Path Lock)** para evitar isso.
- **Erro de Permissão Git**: Verifique se a **Deploy Key** da VPS está no GitHub.
- **Site não abre**: Verifique se o DNS aponta para o IP da VPS e se o Nginx reiniciou sem erros.

---
*Manual integrado e atualizado para a equipe 3F Tech.*
