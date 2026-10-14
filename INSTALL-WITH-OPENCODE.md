# Install the LinkedIn Coach — instructions for OpenCode

You are OpenCode on a Windows laptop. The user dragged this file in because they want the
LinkedIn Coach installed. They are not technical. Do the steps below yourself, in order, and talk to
them in short, simple sentences (in Arabic if they write in Arabic). Don't show them commands or
errors unless something fails; then explain in one sentence and say what you'll try next.

## Step 1 — Download and unzip the kit

Run this exactly (one command):

```
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol='Tls12'; $dest='C:\linkedin-coach'; if (Test-Path (Join-Path $dest 'setup.cmd')) { 'ALREADY_INSTALLED' } else { $zip=Join-Path $env:TEMP 'linkedin-coach.zip'; Invoke-WebRequest -UseBasicParsing 'https://github.com/Ali-expandings/linkedin-coach-kit/archive/refs/heads/main.zip' -OutFile $zip; $tmp=Join-Path $env:TEMP 'linkedin-coach-unzip'; if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }; Expand-Archive -Force $zip $tmp; New-Item -ItemType Directory -Force $dest | Out-Null; Copy-Item -Recurse -Force (Join-Path $tmp 'linkedin-coach-kit-main\*') $dest; Get-ChildItem -Recurse $dest | Unblock-File; 'INSTALLED' }"
```

It prints `INSTALLED` or `ALREADY_INSTALLED`. Either is fine. Tell the user: "Downloaded ✓".

## Step 2 — Run setup in its own window

Setup takes several minutes and includes a LinkedIn sign-in, so it must run in its own window, not
inside your command tool. Run:

```
cmd /c start "LinkedIn Coach setup" "C:\linkedin-coach\setup.cmd"
```

Then tell the user, in one message:

- A black setup window has opened. Leave it running.
- If Windows asks for permission, allow it ("More info" → "Run anyway").
- When a browser window opens, sign in to LinkedIn there. It closes by itself.
- When the black window says **Setup finished**, press any key to close it, then come back here and
  type **done**.

Wait for them to say done. Then check that `C:\linkedin-coach\opencode.json` exists. If it doesn't,
setup didn't finish: ask them to run `C:\linkedin-coach\setup.cmd` again by double-clicking it, and
send a screenshot of the window if it shows a red "SETUP STOPPED" message.

## Step 3 — Hand over to the coach

Tell the user:

1. In OpenCode, open the folder `C:\linkedin-coach` as a project (File → Open Project, or the project
   picker under the chat box → Add project).
2. Start a new chat there and type **hi**. The LinkedIn Coach takes it from there.

Optional, before they start: they can put their CV, certificates, a profile photo, or an old ChatGPT
chat about their CV (saved as a .txt file) into `C:\linkedin-coach\inbox`.

That's the end of your job. Don't edit their LinkedIn yourself; the coach in that project does it.
