# majal demo
Output demo.gif
Set Shell "zsh"
Set FontSize 13
Set Width 1200
Set Height 700
Set Theme "Catppuccin Mocha"
Set TypingSpeed 25ms
Set Padding 16

Hide
Type "source .venv/bin/activate && clear"
Enter
Sleep 500ms
Show

# Scene 1: Scan
Sleep 300ms
Type "majal scan /tmp/test_arabic.jsonl --severity warning"
Sleep 300ms
Enter
Sleep 6s

# Scene 2: Explain
Type "majal explain"
Sleep 300ms
Enter
Sleep 5s

# Scene 3: Fix
Type "majal fix /tmp/test_arabic.jsonl"
Sleep 300ms
Enter
Sleep 3s
Type "n"
Enter
Sleep 2s

Sleep 2s
