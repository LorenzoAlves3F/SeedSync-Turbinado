# Exemplo de Adaptação: Projeto Vite Legado para Produção

### package.json original:
```json
"scripts": {
  "dev": "vite",
  "build": "tsc && vite build",
  "preview": "vite preview"
}
```

### Problemas encontrados:
1. `preview` sem `--host`: Nginx não vai conseguir "falar" com o Vite.
2. `preview` sem porta fixa: O Orquestrador não saberá em qual porta o app subiu.

### Correção sugerida para o Antigravity:
```json
"scripts": {
  "build": "tsc && vite build",
  "preview": "vite preview --host --port 3000"
}
```

### ops/project.yml adaptado:
```yaml
kind: frontend
runtime: node
install_cmd: pnpm install
build_cmd: pnpm build
start_cmd: pnpm preview
pm2_name: projeto-legado-vps
port: 3000
requires_nginx: true
domains:
  - legado.3fventure.tech
```
