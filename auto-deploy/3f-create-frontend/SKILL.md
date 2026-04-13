---
name: 3f-create-frontend
description: Guia para criar novos projetos Frontend compatíveis com o 3F Deploy Orchestrator (Auto-deploy & Auto-update).
---

# 🎨 Skill: Criar Novo Projeto Frontend (3F)

Este guia define como estruturar um novo projeto Frontend para garantir compatibilidade total com o sistema 3F, independente da linguagem escolhida.

## 🏗️ Estrutura Obrigatória

### 1. Configuração do Framework (Vite, Next, etc.)
- **Host**: A aplicação **DEVE** ouvir em `0.0.0.0` (exposto para a rede). No Vite, use `host: true` no config ou `--host` no script.
- **Porta**: Defina uma porta fixa (ex: `4000`). Não use portas aleatórias.
- **Preview**: Recomendamos usar o comando de `preview` (ou `serve`) para rodar os arquivos de build final, não o modo `dev`.

### 2. Contrato de Deploy (`ops/project.yml`)
Crie este arquivo na raiz do projeto:
```yaml
kind: frontend
runtime: node # ou o runtime adequado
install_cmd: pnpm install
build_cmd: pnpm build
start_cmd: pnpm preview --host --port 4000
port: 4000
requires_nginx: true
domains:
  - meu-app.3fventure.tech
healthcheck: /
```

## 🚨 Precauções Críticas (Evite Erros)

### 🧼 Limpeza de Variáveis
- Use o arquivo `.env.example` para listar todas as variáveis que o app precisa.
- O Orquestrador vai preencher o `.env` real baseado no que você cadastrar no Dashboard.

### 🔄 Auto-Update (GitHub Webhooks)
- Para que o código atualize sozinho, o projeto **DEVE** estar em um repositório Git.
- Configure o Webhook no GitHub apontando para a API do Orquestrador.

### 🌐 Conexão com Backend (CORS)
- Ao criar o front, lembre-se que em produção ele rodará sob HTTPS (via Nginx).
- Configure suas chamadas de API para usar variáveis de ambiente (ex: `VITE_API_BASE_URL`).

## 🛠️ Passo a Passo por Linguagem

### React / Vue (Vite + TS + pnpm)
1. `pnpm create vite .`
2. Ajuste `package.json`:
   ```json
   "scripts": {
     "preview": "vite preview --host --port 4000"
   }
   ```
3. Crie `ops/project.yml`.

### Next.js (Standalone Mode)
1. Configure `next.config.js`: `output: 'standalone'`.
2. O `start_cmd` deve ser: `node .next/standalone/server.js`.
3. Certifique-se de que a porta 3000 (padrão) esteja mapeada no `project.yml`.

## 💎 Design Premium (3F Standard)
- Use **Tailwind CSS** ou **Vanilla CSS** com paletas HSL.
- Adicione micro-animações.
- Responsividade é obrigatória.
