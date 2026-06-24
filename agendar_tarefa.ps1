# agendar_tarefa.ps1
# Cria uma tarefa agendada no Windows para rodar o monitor todos os dias.
#
# Como usar:
#   1. Edite a variável $CaminhoProjeto abaixo para o caminho real da pasta
#      onde está este projeto no seu PC.
#   2. Abra o PowerShell COMO ADMINISTRADOR.
#   3. Rode: .\agendar_tarefa.ps1
#
# Isso cria uma tarefa chamada "MonitorPrecosCerveja" que executa todo dia
# às 08:00. Para alterar o horário, mude o valor de -At.

$CaminhoProjeto = "C:\Users\ricar\Downloads\cerveja_monitor\cerveja_monitor"
$CaminhoPython  = "python"  # ou o caminho completo do python.exe, se necessário

$Acao = New-ScheduledTaskAction -Execute $CaminhoPython `
    -Argument "price_monitor.py" `
    -WorkingDirectory $CaminhoProjeto

$Gatilho = New-ScheduledTaskTrigger -Daily -At 8:00AM

Register-ScheduledTask -TaskName "MonitorPrecosCerveja" `
    -Action $Acao -Trigger $Gatilho `
    -Description "Monitora diariamente os preços de cerveja no Sonda Delivery / Zé Delivery / Sun's Club" `
    -RunLevel Highest

Write-Host "Tarefa 'MonitorPrecosCerveja' criada com sucesso! Ela vai rodar todo dia às 08:00."
