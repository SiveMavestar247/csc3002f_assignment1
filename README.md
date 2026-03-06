# CSC3002F Assignment 1 – Chat Networking Application

This repository contains a simple peer‑to‑peer chat system implemented in
Python.  The code has been split into separate modules and packages to
make it easier to read and document:

- ``client.py``: network client logic encapsulated in :class:`ChatClient`.
- ``server/``: chat server implementation; start it by running
  ``python server.py`` (internally it uses :class:`server.ChatServer`).
- ``chat_gui/``: graphical user interface package.  ``gui.py`` is a thin
  launcher – the real implementation lives under ``chat_gui/`` with modules
  such as ``login.py``, ``main_app.py`` and ``callbacks.py``.

## Running

1. Launch the server in a terminal::

    python server.py

2. Open another terminal and start the client GUI::

    python gui.py

   Repeat for additional clients; each must enter a unique username.


## Project layout

```text
csc3002f_assignemnt1/
├── client.py           # networking helper used by the GUI
├── chat_gui/           # GUI package with multiple small modules
│   ├── __init__.py
│   ├── login.py
│   ├── main_app.py
│   ├── chat_widgets.py
│   ├── callbacks.py
│   └── state.py
├── server/             # server package
│   ├── __init__.py
│   └── core.py
└── server.py           # entry point for the server
```