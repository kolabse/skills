[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$Config,
    [string]$ChatId,
    [string]$ThreadId,
    [switch]$SkipTest,
    [switch]$SelfTest
)

$ErrorActionPreference = "Stop"

function Normalize-BotToken {
    param([AllowNull()][string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }
    $normalized = $Value.Trim()
    if ($normalized -notmatch '^[0-9]+:[A-Za-z0-9_-]+$') {
        return $null
    }
    return $normalized
}

function Test-TokenValidator {
    $accepted = @("1:a", "123456789:abc_DEF-", " 123:token ")
    $rejected = @("", " ", "123", "bot:token", "123:abc def", "123:abcà")
    foreach ($sample in $accepted) {
        if ($null -eq (Normalize-BotToken $sample)) {
            throw "Token validator rejected an accepted fixture"
        }
    }
    foreach ($sample in $rejected) {
        if ($null -ne (Normalize-BotToken $sample)) {
            throw "Token validator accepted a rejected fixture"
        }
    }
}

if ($SelfTest) {
    try {
        Test-TokenValidator
        [Console]::Out.WriteLine("Windows token-entry self-test passed.")
        exit 0
    }
    catch {
        [Console]::Error.WriteLine("ERROR: Windows token-entry self-test failed.")
        exit 1
    }
}

try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Configure Telegram notifications"
    $form.StartPosition = "CenterScreen"
    $form.ClientSize = New-Object System.Drawing.Size(520, 160)
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.TopMost = $true

    $label = New-Object System.Windows.Forms.Label
    $label.Text = "Paste the bot token received from BotFather:"
    $label.AutoSize = $true
    $label.Location = New-Object System.Drawing.Point(18, 18)
    $form.Controls.Add($label)

    $tokenBox = New-Object System.Windows.Forms.TextBox
    $tokenBox.Location = New-Object System.Drawing.Point(20, 48)
    $tokenBox.Size = New-Object System.Drawing.Size(480, 24)
    $tokenBox.UseSystemPasswordChar = $true
    $tokenBox.ShortcutsEnabled = $true
    $form.Controls.Add($tokenBox)

    $okButton = New-Object System.Windows.Forms.Button
    $okButton.Text = "Continue"
    $okButton.Location = New-Object System.Drawing.Point(324, 100)
    $okButton.Size = New-Object System.Drawing.Size(84, 30)
    $okButton.Add_Click({
        $normalized = Normalize-BotToken $tokenBox.Text
        if ($null -eq $normalized) {
            [System.Windows.Forms.MessageBox]::Show(
                $form,
                "The token is empty or malformed. Copy the complete token from BotFather.",
                "Invalid Telegram token",
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Warning
            ) | Out-Null
            $tokenBox.SelectAll()
            $tokenBox.Focus()
            return
        }
        $form.Tag = $normalized
        $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $form.Close()
    })
    $form.Controls.Add($okButton)

    $cancelButton = New-Object System.Windows.Forms.Button
    $cancelButton.Text = "Cancel"
    $cancelButton.Location = New-Object System.Drawing.Point(416, 100)
    $cancelButton.Size = New-Object System.Drawing.Size(84, 30)
    $cancelButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $form.Controls.Add($cancelButton)

    $form.AcceptButton = $okButton
    $form.CancelButton = $cancelButton
    $form.Add_Shown({ $tokenBox.Focus() })
    $result = $form.ShowDialog()
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
        [Console]::Error.WriteLine("ERROR: Telegram configuration was cancelled.")
        exit 1
    }

    $token = [string]$form.Tag
    $scriptPath = Join-Path $PSScriptRoot "telegram_notify.py"
    $pythonArguments = @($scriptPath)
    if ($Config) {
        $pythonArguments += @("--config", $Config)
    }
    $pythonArguments += "configure"
    if ($ChatId) {
        $pythonArguments += @("--chat-id", $ChatId)
    }
    if ($ThreadId) {
        $pythonArguments += @("--thread-id", $ThreadId)
    }
    if ($SkipTest) {
        $pythonArguments += "--skip-test"
    }

    try {
        $env:TELEGRAM_BOT_TOKEN = $token
        & $Python @pythonArguments
        $pythonExitCode = $LASTEXITCODE
    }
    finally {
        Remove-Item Env:TELEGRAM_BOT_TOKEN -ErrorAction SilentlyContinue
        $token = $null
        $form.Tag = $null
        $tokenBox.Clear()
        $form.Dispose()
    }
    exit $pythonExitCode
}
catch {
    [Console]::Error.WriteLine("ERROR: Telegram configuration could not be started.")
    exit 1
}
