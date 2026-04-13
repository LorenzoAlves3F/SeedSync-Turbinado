---
name: 3f-monorepo-new-project
description: Instruções para criar um novo sub-projeto dentro de um monorepo já integrado ao 3F Orchestrator.
---

# 🆕 Skill: Novo Projeto no Monorepo

Use esta skill quando precisar adicionar um novo serviço (API, Front ou Worker) em um monorepo que já possui o Orquestrador configurado.

## 🛠️ Passo a Passo para a IA

### 1. Estrutura de Pastas
- Identifique se o projeto vai para `apps/` (aplicações) ou `packages/` (bibliotecas/shared).
- Use `mkdir apps/nome-do-app`.

### 2. Inicialização e Nomenclatura
- O `name` no `package.json` deve seguir o padrão do monorepo (ex: `@3f/nome-do-app`).
- Adicione as dependências básicas e a referência ao `@3f/shared` se necessário.

### 3. Configuração do TypeScript
- Adicione a referência no `tsconfig.json` da raiz (se estiver usando project references).
- Configure o `tsconfig.json` local para estender a base do monorepo.

### 4. Integração com o Orquestrador
- **Crucial:** Crie o `apps/nome-do-app/ops/project.yml`.
- **Diferença:** Note que o Orquestrador do monorepo geralmente busca os contratos em locais específicos. Se o monorepo já tiver um seletor, siga o padrão. Se for um contrato único por repo, o `project.yml` deve estar na raiz com os filtros corretos.

## 💡 Prompt de Exemplo para Antigravity:
> "Crie um novo app de frontend em Vue dentro da pasta `apps/` deste monorepo. Nomeie como `@3f/admin-dashboard`. Use o pacote `@3f/shared` para os tipos e configure o `ops/project.yml` para rodar na porta 4005."

## 🚀 Verificação de Deploy
- Após criar o app, valide se o comando `pnpm --filter "@3f/admin-dashboard" build` funciona a partir da raiz.
- Verifique se a porta escolhida não conflita com outros apps já rodando na mesma VPS.
