# setup_git.ps1
# RODAR UMA VEZ (PowerShell normal, dentro desta pasta):
#   cd C:\Users\ricar\OneDrive\Documentos\GitHub\git_takeya\cerveja_monitor
#   .\setup_git.ps1
#
# Conecta esta pasta ao repositorio GitHub e baixa os arquivos que faltam
# (gerar_relatorio.py, publicar_relatorio.py, grupos.xlsx, data/, etc.).
# No primeiro push o Windows abre o navegador para voce logar no GitHub
# (Git Credential Manager) - depois disso o push diario e automatico.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Remove .git incompleto de tentativa anterior, se existir
if (Test-Path ".git") { Remove-Item -Recurse -Force ".git" }

git init -b master
git remote add origin https://github.com/ricardotakeya-boop/cerveja-monitor.git
git fetch origin
git reset origin/master
git checkout -- .
git branch --set-upstream-to=origin/master master

git config user.name "Ricardo Takeya"
git config user.email "ricardotakeya@gmail.com"

# Primeiro push: abre o navegador para autenticar no GitHub
git push -u origin master

Write-Host ""
Write-Host "Pronto! Pasta conectada ao GitHub. Agora rode .\agendar_tarefa.ps1 como ADMINISTRADOR para agendar o envio diario."
