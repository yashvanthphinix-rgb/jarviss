# Fix: ModuleNotFoundError: No module named 'cogs'

The deployed repository must have `main.py` and the `cogs/` directory at the same root level.

Expected repository layout:

```
main.py
config.py
database.py
requirements.txt
Procfile
cogs/
  __init__.py
  core.py
  moderation.py
  security.py
  anti_nuke.py
  bot_guard.py
  logging_system.py
  community.py
  voice.py
  backup.py
  performance.py
services/
utils/
tests/
```

Do not upload the ZIP itself, and do not put `cogs/` inside an extra `jarvis_ultimate/` folder when `main.py` is at the repository root.

## Browser upload repair
1. Extract this archive on your computer.
2. In GitHub, open the repository and verify that `main.py` is at the repository root.
3. Upload the contents of the extracted folder to that same repository root, ensuring the `cogs`, `services`, `utils`, and `tests` folders are included. If GitHub's browser upload doesn't preserve folders, use GitHub Desktop to clone the repo, copy these extracted contents into the cloned folder, then commit and push.
4. In Railway, confirm the service is connected to that repository/branch and redeploy the latest commit.

The `discord.py[voice]` extra installs optional PyNaCl and davey dependencies so voice features can initialize where supported. This does not guarantee voice playback; that depends on the voice feature and hosting runtime.
