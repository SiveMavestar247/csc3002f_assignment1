# CSC3002F Assignment 1 – Chat Networking Application

A distributed peer-to-peer chat system with a central server and multiple GUI clients. Users can send messages to each other, create groups, and transfer files via UDP.

The code is organized into separate modules and packages for readability:

- **`client.py`**: Network client with TCP/UDP socket handling; implements `ChatClient` class
- **`server/`**: Central message routing server; implements `ChatServer` class
- **`chat_gui/`**: Tkinter-based GUI package with multiple focused modules

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Central Chat Server                          │
│                  (TCP: 127.0.0.1:5555)                          │
│  • Routes messages between clients                              │
│  • Maintains user list and group memberships                    │
│  • Per-client handler threads for concurrent connections        │
└──────┬──────────────────────┬──────────────────────┬────────────┘
       │                      │                      │
    [TCP]                  [TCP]                  [TCP]
       │                      │                      │
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  GUI Client  │  │  GUI Client  │  │  GUI Client  │
    │   Alice      │  │    Bob       │  │   Carol      │
    │              │  │              │  │              │
    │ ChatClient   │  │ ChatClient   │  │ ChatClient   │
    │ + TCP socket │  │ + TCP socket │  │ + TCP socket │
    │ + UDP socket │──│ + UDP socket │──│ + UDP socket │ (for P2P file transfers)
    │ (receive)    │  │ (receive)    │  │ (receive)    │
    └──────────────┘  └──────────────┘  └──────────────┘
```

### Data Flow
1. **Text Messages**: TCP to server → server routes to target user via TCP
2. **Group Messages**: TCP to server → server broadcasts to all group members
3. **File Transfers**: Direct UDP between clients (peer-to-peer)

## Running the Application

### 1. Start the Server
```bash
python server.py
```
Output:
```
Server is up and listening on 0.0.0.0:5555...
[+] alice(192.168.1.100:12345) connected.
[+] bob(192.168.1.101:12346) connected.
```

**What it does:**
- Binds to port 5555 and accepts client connections
- Registers each user and their UDP address
- Broadcasts user list and group membership updates to all clients
- Receives and routes messages between clients
- Handles group creation, modification, and deletion

### 2. Start Client GUI (repeat for each user)
```bash
python gui.py
```

**What happens:**
1. Login window appears → user enters unique username
2. `ChatClient` connects via TCP to server, registers UDP socket
3. Server broadcasts updated user list to all clients
4. Main chat window opens showing contacts and chat history
5. Background threads listen for incoming messages and file transfers

## Module Overview

### Core Networking

#### `client.py` – ChatClient Class
Handles all client-side networking with separate TCP/UDP sockets:

- **`connect(username, callbacks...)`**: Establishes TCP/UDP connections, starts background listener threads
- **`send_message(target, message)`**: Sends message to user or group via TCP
- **`create_group(name, members)`**: Sends group creation request to server
- **`modify_group(old_name, new_name, users_to_add)`**: Rename group or add members
- **`leave_group(name)`**: Remove self from group membership
- **`send_media(filepath, target)`**: Split file into UDP chunks and send to peer/group
- **`receive_messages()`**: Background thread listening on TCP socket for incoming messages
- **`receive_media()`**: Background thread listening on UDP socket for incoming file transfers
- **`disconnect()`**: Close sockets gracefully

#### `server/core.py` – ChatServer Class
Central message routing with TCP-only communication:

- **`start()`**: Begin accepting client connections in infinite loop
- **`_handle_client(client_socket)`**: Process messages from one client
- **`_broadcast_user_list()`**: Send all online users to all connected clients
- **`_broadcast_group_list()`**: Send group memberships (filtered per user)

**Protocol:**
- User registration: `username|udp_addr`
- Text message: `target_user|message`
- Group message: `GROUP_MESSAGE|group_name|message`
- Group creation: `GROUP_CREATE|group_name|member1,member2,...`
- Group modify: `GROUP_MODIFY|old_name|new_name|users_to_add`
- Group leave: `GROUP_LEAVE|group_name`

### GUI Package (`chat_gui/`)

#### `__init__.py`
Entry point; exports `run()` function to start the application.

#### `state.py` – Shared State Management
Centralized module for all GUI state to avoid scattered globals:
- **Widgets**: login field, chat frames, contact list, message entry
- **State**: current user, current chat contact, online users, group memberships
- **Callbacks**: file transfer handlers
- **Helper**: `reset_gui_state()` clears state on logout

#### `login.py` – Authentication
Builds login window and handles connection:

- **`setup_login_window()`**: Creates username entry field and Connect button
- **`login()`**: Validates input, calls `chat_client.connect()` with callbacks
- On success: hides login, calls `open_main_app()`
- On error: displays error dialog

#### `main_app.py` – Main Chat Interface
Constructs primary window with contacts sidebar and chat area:

**Extracted Helper Functions:**
- **`_open_create_group_dialog(main_window)`**: Dialog to create new group with member selection
- **`_open_group_settings(main_window)`**: Dialog to rename group, add members, or leave
- **`_on_logout(main_window)`**: Disconnect cleanly and reset state

**Layout:**
- **Header** (top): Title, group members subtitle, settings button
- **Sidebar** (left): Create Group button, Online Users list, Logout button
- **Chat area** (right): Message display, text input field
- **Mouse wheel** bindings for scrolling chat history

#### `chat_widgets.py` – UI Components
Reusable widget builders and message display logic:

- **`create_scrollable_area(parent, bg_color)`**: Scrollable frame with canvas and scrollbar
- **`create_chat_frame_for_user(contact_name)`**: Prepare internal structures for new contact
- **`add_message_bubble(message_text, timestamp, contact, is_me, sender)`**: Display message with styling
  - Outgoing messages: green bubble on right
  - Incoming messages: gray bubble on left
  - Group messages: show sender name above
- **`add_file_transfer_bubble(...)`**: Display file transfer notifications

#### `callbacks.py` – Network Event Handlers
Bridge between background network threads and Tkinter main loop:

- **`handle_network_error(error_msg)`**: Display connection error dialog
- **`handle_user_list_update(users)`**: Refresh contact sidebar with online users
- **`handle_group_list_update(groups)`**: Update group memberships, refresh contacts
- **`show_chat(contact_name, is_group)`**: Switch displayed conversation
- **`handle_incoming_message(sender, message, group)`**: Display message bubble
- **`add_incoming_bubble_safely(contact, sender, message, timestamp, is_group)`**: Tkinter-safe GUI update
- **`handle_file_received(sender, filename, filepath)`**: Show file transfer notification

## Complete Application Walkthrough

### Startup Sequence
```
1. python server.py
   → Server binds to 0.0.0.0:5555
   → Enters accept loop waiting for clients

2. python gui.py (first user - Alice)
   → Tkinter root window created
   → setup_login_window() builds login field
   → User enters "alice" and clicks Connect
   → ChatClient.connect("alice", callbacks...) called
   → TCP socket connects to server
   → UDP socket binds to random port (e.g., 12345)
   → TCP: "alice|127.0.0.1:12345" sent to server
   → Server registers alice with her UDP address
   → Server calls broadcast_user_list()
   → Alice receives: "USERS|alice(127.0.0.1:12345)\n"
   → handle_user_list_update() called
   → Contact sidebar shows alice (empty - can't chat with self)
   → Main chat window replaces login window

3. python gui.py (second user - Bob)
   → Similar to Alice
   → Bob's TCP connects to server
   → Server broadcasts updated user list: "USERS|alice(127.0.0.1:12345),bob(192.168.1.101:12346)\n"
   → Alice receives update: contact sidebar updates to show "bob"
   → Bob's contact sidebar shows "alice"
```

### Chat Interaction – Individual Message
```
Step 1: Bob composes message "Hello Alice!"
   → Clicks contact "alice"
   → show_chat("alice", is_group=False)
   → Chat frame becomes visible

Step 2: Bob enters message in text field and clicks Send
   → GUI calls chat_client.send_message("alice", "Hello Alice!")
   → send_message() formats: "alice|Hello Alice!\n"
   → TCP sends to server

Step 3: Server receives message with sender=bob
   → Looks up "alice" in active_clients
   → Sends: "bob|Hello Alice!\n" to alice's TCP socket

Step 4: Alice's receive_messages() background thread receives
   → Parses: sender="bob", msg="Hello Alice!"
   → Calls on_message_received("bob", "Hello Alice!", group=None)
   → handle_incoming_message() in callbacks.py is invoked
   → Timestamp generated: "3:45 PM"
   → state.root.after() schedules GUI update on main thread
   → add_incoming_bubble_safely() displays gray message bubble
```

### Group Chat Interaction
```
Step 1: Alice creates group "team"
   → Clicks "Create Group" button
   → Dialog appears with online users (bob, carol)
   → Selects bob and carol
   → Clicks Create Group
   
Step 2: GUI processes group creation
   → state.groups["team"] = ["alice", "bob", "carol"]
   → Calls chat_client.create_group("team", ["alice", "bob", "carol"])
   → TCP sends: "GROUP_CREATE|team|alice,bob,carol\n"

Step 3: Server receives GROUP_CREATE
   → Stores: self.groups["team"] = ["alice", "bob", "carol"]
   → Calls _broadcast_group_list() to all clients
   → Alice receives: "GROUPS|team:alice,bob,carol\n"
   → Bob receives: "GROUPS|team:alice,bob,carol\n"
   → Carol receives: "GROUPS|team:alice,bob,carol\n"

Step 4: Groups appear in contact sidebar
   → handle_group_list_update() called for each user
   → "TEAM" button with blue styling added to contacts
   → Users can click to start group chat
```

### File Transfer – P2P via UDP
```
Step 1: Alice selects Bob and chooses file "document.pdf"
   → Calls chat_client.send_media("C:\\docs\\document.pdf", "bob")

Step 2: send_media() prepares transfer
   → Splits file into 1200-byte UDP chunks
   → Generates transaction ID: "a3b7c2e1" (8 chars)
   → Sends each chunk: header + payload
   → Header: "a3b7c2e1|0|5|document.pdf\n" + [1200 bytes]
   → Headers include: transaction_id, sequence_number, total_chunks, filename

Step 3: Bob's receive_media() background thread receives UDP packets
   → Collects chunks by transaction ID
   → When all chunks received: reassembles file
   → Saves to "received_files/a3b7c2e1_document.pdf"
   → Calls on_file_received("alice", "document.pdf", filepath)
   → Notification displayed: "Alice sent you document.pdf"

Note: Server is NOT involved in file transfer - it's direct P2P!
```

### Logout
```
Step 1: User clicks Logout button
   → _on_logout() called
   → Chat client disconnects (closes sockets)
   → Server removes user from active_clients
   → Server broadcasts updated user list
   → All remaining clients receive updated list
   → GUI resets state and returns to login window
```

## Project Layout

```text
csc3002f_assignemnt1/
├── client.py                   # ChatClient networking class
├── gui.py                      # Thin launcher for chat_gui.run()
├── server.py                   # Thin launcher for server
│
├── server/                     # Server package
│   ├── __init__.py
│   └── core.py                 # ChatServer class implementation
│
└── chat_gui/                   # GUI package
    ├── __init__.py             # Exports run() entry point
    ├── login.py                # Login window & authentication
    ├── main_app.py             # Main chat interface (~310 lines)
    │   └─ Extracted helpers:
    │      • _open_create_group_dialog()
    │      • _open_group_settings()
    │      • _on_logout()
    ├── chat_widgets.py         # Message bubbles & scrollable areas
    ├── callbacks.py            # Network event handlers
    ├── state.py                # Centralized GUI state
    └── __pycache__/
```

## Key Design Patterns

### Separation of Concerns
- **Network logic** isolated in `client.py` and `server/core.py`
- **GUI building** separated into widget modules
- **State management** centralized in `state.py` to avoid scattered globals
- **Event handling** extracted to `callbacks.py`

### Threading Model
- **Main thread**: Tkinter event loop (UI updates)
- **Background threads** (2 per client):
  - `receive_messages()`: Listens on TCP for server messages
  - `receive_media()`: Listens on UDP for file transfers
- Callbacks use `state.root.after()` for thread-safe GUI updates

### Helper Function Extraction
The refactored `main_app.py` uses module-level helper functions instead of deeply nested closures:
- `_open_create_group_dialog()` – isolated dialog logic
- `_open_group_settings()` – isolated settings dialog
- `_on_logout()` – isolated logout logic

This improves readability and testability.
