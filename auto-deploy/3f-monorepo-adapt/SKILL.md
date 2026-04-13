---
name: 3f-monorepo-adapt
description: Guia para adaptar monorepos existentes (pnpm/turborepo) ao 3F Orchestrator, garantindo que builds parciais e dependências compartilhadas funcionem.
---

# 📦 Skill: Adaptar Monorepo para 3F Deploy

Adaptar um monorepo é um desafio diferente pois o Orquestrador clona o repositório inteiro, mas você precisa fazer o deploy de apenas um app específico dentro dele.

## 🏗️ Estratégia de Build em Monorepo

No 3F Orchestrator, o campo `path` no banco de dados deve apontar para a **raiz do monorepo** (onde está o `pnpm-workspace.yaml`), mas os comandos devem ser filtrados.

### 1. Comandos com Filtro (pnpm)
Nunca rode comandos genéricos de build. Use o filtro do pnpm para garantir que apenas o app e suas dependências internas sejam processados.

**Modelo de `ops/project.yml` para sub-projeto:**
```yaml
kind: frontend
runtime: node
# Root do monorepo é onde o comando roda
install_cmd: pnpm install
# Filtra apenas o app necessário e suas dependências locais
build_cmd: pnpm --filter "@3f/meu-app" build
# O comando de start deve apontar para o diretório correto
start_cmd: pnpm --filter "@3f/meu-app" preview --host --port 3000
pm2_name: monorepo-app-1
port: 3000
```

## 🚨 Pontos de Atenção (Gargalos)

### 1. Dependências Compartilhadas (`packages/*`)
- **Problema:** O app falha no build porque não encontra um pacote local (ex: `@3f/shared`).
- **Solução:** Garanta que o `build_cmd` do app alvo também desencadeie o build dos pacotes dependentes. O `turborepo` faz isso automaticamente, mas o comando `pnpm --filter ... build` também costuma resolver se o workspace estiver bem configurado.

### 2. Variáveis de Ambiente em Monorepos
- **Automação Novo:** O Orquestrador agora detecta automaticamente a subpasta (ex: `apps/meu-app/`) através do seu `start_cmd`.
- Se o comando for `pnpm --filter "@3f/app" preview`, ele buscará a pasta onde o app reside e criará o arquivo `.env` **lá dentro**.
- Isso evita que você tenha que copiar o arquivo manualmente. Certifique-se apenas de que o `start_cmd` aponte claramente para o caminho da app ou use o filtro correto do pnpm.

### 3. Caminhos Relativos no `project.yml`
- Lembre-se que o Orquestrador executa os comandos a partir da raiz. Certifique-se de que os scripts no `package.json` lidam bem com caminhos ou use o prefixo de diretório se necessário.

## 🤖 Guia de Integração para a IA (Passo a Passo)

Se você é uma IA adaptando este monorepo, siga este fluxo:

1.  **Mapear as Apps**: Liste as pastas em `apps/`.
2.  **Criar Contratos Únicos**: Para cada app, crie um arquivo em `ops/` com o nome da app (ex: `ops/admin-panel.yml`).
3.  **Configurar pnpm filters**: No contrato, o `install_cmd` deve ser `pnpm install` (na raiz) e o `build_cmd` deve usar `--filter`.
4.  **Cadastrar no Orquestrador**: Ao adicionar o projeto no Dashboard/Banco:
    - `Path`: Sempre a raiz do monorepo.
    - `Contract File`: O nome do arquivo que você criou em `ops/` (ex: `admin-panel.yml`).
5.  **Ajustar scripts**: Se o script de `preview` no `package.json` do app não tiver `--host` ou porta fixa, adicione-os.
