# Interactive secret entry for explicit initial setup. Never invoked by MCP startup.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$configPath = Join-Path $env:LOCALAPPDATA 'codex/telegram-notify/config.json'
if (Test-Path -LiteralPath $configPath) {
    Write-Output '{"configured":true,"existing_config_preserved":true}'
    exit 0
}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Telegram bridge setup'
$form.Size = New-Object System.Drawing.Size(540, 275)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$intro = New-Object System.Windows.Forms.Label
$intro.Text = 'Enter the bot token from BotFather and your numeric private chat ID. Credentials stay on this computer; do not paste the token into Codex chat.'
$intro.SetBounds(15, 15, 500, 45)
$form.Controls.Add($intro)
$tokenLabel = New-Object System.Windows.Forms.Label
$tokenLabel.Text = 'Bot token'
$tokenLabel.SetBounds(15, 75, 110, 25)
$form.Controls.Add($tokenLabel)
$tokenBox = New-Object System.Windows.Forms.TextBox
$tokenBox.UseSystemPasswordChar = $true
$tokenBox.SetBounds(130, 72, 375, 25)
$form.Controls.Add($tokenBox)
$chatLabel = New-Object System.Windows.Forms.Label
$chatLabel.Text = 'Private chat ID'
$chatLabel.SetBounds(15, 115, 110, 25)
$form.Controls.Add($chatLabel)
$chatBox = New-Object System.Windows.Forms.TextBox
$chatBox.SetBounds(130, 112, 375, 25)
$form.Controls.Add($chatBox)
$save = New-Object System.Windows.Forms.Button
$save.Text = 'Validate and save'
$save.SetBounds(270, 175, 140, 30)
$form.Controls.Add($save)
$cancel = New-Object System.Windows.Forms.Button
$cancel.Text = 'Cancel'
$cancel.SetBounds(420, 175, 85, 30)
$cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.Controls.Add($cancel)
$form.CancelButton = $cancel
$form.AcceptButton = $save
$save.Add_Click({
    $token = $tokenBox.Text.Trim()
    $chat = $chatBox.Text.Trim()
    if ($token -notmatch '^[0-9]+:[A-Za-z0-9_-]+$' -or $chat -notmatch '^[1-9][0-9]*$') {
        [System.Windows.Forms.MessageBox]::Show('Enter a complete bot token and a positive numeric private chat ID.') | Out-Null
        return
    }
    $save.Enabled = $false
    $temporary = $null
    try {
        $baseUri = 'https://api.telegram.org/bot' + $token + '/'
        $webhook = Invoke-RestMethod -Method Post -Uri ($baseUri + 'getWebhookInfo') -TimeoutSec 20
        if (-not $webhook.ok -or $webhook.result.url) { throw 'Existing webhook or API failure.' }
        $destination = Invoke-RestMethod -Method Post -Uri ($baseUri + 'getChat') -Body @{chat_id=$chat} -TimeoutSec 20
        if (-not $destination.ok -or $destination.result.type -ne 'private' -or [string]$destination.result.id -ne $chat) { throw 'Private chat validation failed.' }
        $bot = Invoke-RestMethod -Method Post -Uri ($baseUri + 'getMe') -TimeoutSec 20
        if (-not $bot.ok) { throw 'Bot validation failed.' }
        $directory = Split-Path -Parent $configPath
        [IO.Directory]::CreateDirectory($directory) | Out-Null
        $temporary = Join-Path $directory ([Guid]::NewGuid().ToString() + '.tmp')
        [IO.File]::WriteAllText($temporary, '')
        $acl = New-Object Security.AccessControl.FileSecurity
        $acl.SetAccessRuleProtection($true, $false)
        foreach ($sid in @([Security.Principal.WindowsIdentity]::GetCurrent().User, [Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
            $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'Allow'))
        }
        Set-Acl -LiteralPath $temporary -AclObject $acl
        $payload = @{version=1;bot_token=$token;chat_id=$chat} | ConvertTo-Json
        [IO.File]::WriteAllText($temporary, $payload, [Text.UTF8Encoding]::new($false))
        # Move without overwrite: a concurrent configuration must be preserved.
        [IO.File]::Move($temporary, $configPath)
        $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $form.Close()
    } catch {
        [System.Windows.Forms.MessageBox]::Show('Could not validate or save. Check the token, send /start to the bot, verify the private chat ID, and ensure the bot has no webhook. No existing configuration was replaced.') | Out-Null
    } finally {
        if ($temporary -and (Test-Path -LiteralPath $temporary)) { Remove-Item -LiteralPath $temporary }
        $save.Enabled = $true
        $token = $null
        $payload = $null
        $baseUri = $null
    }
})
$result = $form.ShowDialog()
$tokenBox.Clear()
$form.Dispose()
if ($result -ne [System.Windows.Forms.DialogResult]::OK) { exit 1 }
Write-Output '{"configured":true,"credentials_printed":false}'
