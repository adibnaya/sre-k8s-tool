run activate-global-python-argcomplete to eneable auto-completion

If auto-completion does not work, manually configure it by running:

eval "$(register-python-argcomplete python3 sre.py)"


For PowerShell (Windows)
Run this each time you open PowerShell:

powershell
Copy
Edit
Register-ArgumentCompleter -Native -CommandName python -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $CompletionResult = $(python sre.py $wordToComplete)
    $CompletionResult | ForEach-Object { New-Object System.Management.Automation.CompletionResult $_, $_, 'ParameterValue', $_ }
}
To make it persistent, add the above script to your PowerShell profile:

powershell
Copy
Edit
notepad $PROFILE
Paste the script at the end of the file and save.

Then, restart PowerShell and test auto-completion:

powershell
Copy
Edit
python sre.py <TAB>