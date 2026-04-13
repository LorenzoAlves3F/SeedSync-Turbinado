---
name: 3f-adapt-existing-project
description: Guia para adaptar projetos legados ou existentes para o fluxo de Autodeploy e Autoupdate do 3F Orchestrator.
---

# 🛠️ Skill: Adaptar Projeto para 3F Deploy

Esta skill é focada em diagnosticar e corrigir problemas em projetos que já existem mas precisam ser integrados ao **3F Deploy Orchestrator**.

## 🚨 Checkpoint de Sobrevivência (Antipatterns)
Antes de configurar o deploy, verifique se o projeto comete algum destes erros que impedem o funcionamento na VPS:

### 1. Hardcoded IPs e Portas
- **Problema:** O código aponta para `http://123.123.123.123:3000` ou `localhost:3000`.
- **Solução:** Substitua tudo por variáveis de ambiente (`process.env.VITE_API_URL`, etc).
- **Ajuste:** O Orquestrador vai injetar as variáveis corretas. Se o IP estiver "chumbado", o deploy vai falhar ao tentar conectar.

### 2. Vite "Preso" no Localhost
- **Problema:** O Vite por padrão só ouve no `127.0.0.1`. O Nginx da VPS não conseguirá acessar o container/processo.
- **Solução:** O script de `start` ou `preview` **DEVE** incluir o parâmetro `--host`.
- **Exemplo Correcto:** `vite preview --host --port 4173`.

### 3. Falta de Configuração de Proxy (CORS)
- **Problema:** Front-end tentando acessar o back-end sem passar pelo domínio correto.
- **Solução:** Utilize o `domain_map` no `project.yml` se for um projeto fullstack, ou garanta que as URLs de API nos arquivos `.env` apontem para os domínios configurados no Nginx do Orquestrador.

## 📋 Checklist de Adaptação

1.  **Auditoria de Dependências**: Garanta que o comando de install (ex: `pnpm install`) funciona em ambiente Linux/Headless.
2.  **Scripts de Produção**:
    - Verifique se o `package.json` tem um comando que faz o build **E** o preview/start de forma estável.
    - Evite scripts que usem `nodemon` em produção (use o `start_cmd` para apontar para o arquivo compilado ou para o próprio `node`).
3.  **Configuração de Memória**:
    - Se o projeto for grande, adicione `max_memory_restart: '1G'` (ou similar) no `start_cmd` se estiver usando PM2 diretamente, ou confie no padrão do Orquestrador.
4.  **Criação do Contrato**:
    - Crie o `ops/project.yml` baseado nos exemplos da pasta `examples/`.

## ⚠️ Atenção com Nginx e SSL
- Projetos adaptados costumam ter configurações de Nginx antigas. O Orquestrador vai tentar criar uma nova.
- **Ação:** Certifique-se de que o domínio desejado já aponta (DNS A Record) para o IP da VPS antes de ativar o `requires_nginx: true`, caso contrário a geração do SSL (Certbot) vai travar o deploy.
