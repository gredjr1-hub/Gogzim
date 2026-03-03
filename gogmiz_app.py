import streamlit as st
import time
# Import our new escape room generation function
from llm_engine import generate_dynamic_escape_room, build_system_prompt, interact_with_entity, parse_llm_response

st.set_page_config(page_title="AI Escape Room", page_icon="🔐", layout="wide")

# --- 1. Session State Initialization ---
# Ensure all necessary state variables exist before rendering
if "setup_complete" not in st.session_state:
    st.session_state.setup_complete = False
if "room_data" not in st.session_state:
    st.session_state.room_data = {}
# We now split player holdings into physical inventory and mental clues
if "player" not in st.session_state:
    st.session_state.player = {"inventory": [], "clues": []}
if "active_entity_id" not in st.session_state:
    st.session_state.active_entity_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_game_logic" not in st.session_state:
    st.session_state.last_game_logic = {}


# ================= MAIN APP LOGIC =================

# --- VIEW 1: THE ARCHITECT'S FORGE (Main Menu) ---
if not st.session_state.setup_complete:
    st.markdown("# 🔐 The Architect's Forge")
    st.markdown("Design the parameters of your confinement.")
    
    with st.form("generation_form"):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
             difficulty = st.select_slider("Difficulty Level", options=["Easy", "Normal", "Hard"], value="Normal", help="Determines the length of the code and complexity of puzzles.")
        with col_f2:
             theme = st.text_input("Room Theme & Setting", placeholder="e.g., A cyberpunk server room on lockdown.")
        
        st.markdown("---")
        submitted = st.form_submit_button("Generate Escape Room ✨", type="primary")
        
        if submitted:
            if not theme.strip():
                 st.error("You must provide a theme for the Architect.")
            else:
                with st.spinner("Constructing puzzles, forging keys, and hiding clues..."):
                    # Call the new generation function
                    new_room = generate_dynamic_escape_room(theme, difficulty)
                    if new_room:
                        st.session_state.room_data = new_room
                        # Reset player state for the new run
                        st.session_state.player = {"inventory": [], "clues": []} 
                        st.session_state.setup_complete = True
                        st.rerun()
                    else:
                        st.error("The Architect failed to stabilize the room simulation. Please try again.")


# --- VIEW 2: THE ESCAPE ROOM (Game Interface) ---
else:
    room = st.session_state.room_data
    master_puzzle = room["master_puzzle"]
    
    # HEADER SECTION
    st.markdown(f"## {room['name']}")
    st.markdown(f"_{room['visual_description']}_")
    st.divider()

    # Main Game Columns
    col_game, col_beholder = st.columns([3, 2], gap="medium")

    # --- LEFT COLUMN: The Room & Keypad ---
    with col_game:
        # 1. THE MASTER KEYPAD INTERFACE
        st.subheader("🔒 Final Lockdown Mechanism")
        if master_puzzle["solved"]:
            st.success(master_puzzle["success_message"])
            st.balloons()
            if st.button("⬅️ Return to the Forge"):
                 st.session_state.setup_complete = False
                 st.session_state.room_data = {}
                 st.rerun()
        else:
            # A simple form for entering the digit code
            with st.form("keypad_form"):
                 cols_key = st.columns([3, 1])
                 with cols_key[0]:
                     code_guess = st.text_input("Enter Passcode:", placeholder="# " * len(master_puzzle["solution"]), label_visibility="collapsed")
                 with cols_key[1]:
                     attempt_unlock = st.form_submit_button("Unlock")
            
            if attempt_unlock:
                 if code_guess.strip() == master_puzzle["solution"]:
                     st.session_state.room_data["master_puzzle"]["solved"] = True
                     st.rerun()
                 else:
                     st.error("🛑 ACCESS DENIED. Incorrect code.")
        
        st.divider()
        
        # 2. POINTS OF INTEREST (Interactables)
        st.subheader("🔎 Points of Interest")
        
        # Display active objects first
        active_objs = {k:v for k,v in room["interactables"].items() if v["status"] == "active"}
        if active_objs and not master_puzzle["solved"]:
             num_cols = 3
             cols = st.columns(num_cols)
             for i, (obj_id, obj_data) in enumerate(active_objs.items()):
                 with cols[i % num_cols]:
                    if st.button(f"{obj_data['name']}", key=f"btn_{obj_id}", use_container_width=True):
                        st.session_state.active_entity_id = obj_id
                        st.session_state.chat_history = [] # Reset chat on new selection
                        st.session_state.last_game_logic = {}
                        st.rerun()
        elif not active_objs and not master_puzzle["solved"]:
             st.info("All objects have been cleared. Solve the final puzzle.")

        # Display cleared objects
        cleared_objs = {k:v for k,v in room["interactables"].items() if v["status"] != "active"}
        if cleared_objs:
             st.markdown("**Cleared Areas:**")
             for obj_data in cleared_objs.values():
                  st.caption(f"✅ {obj_data['name']}")

        st.divider()

        # 3. PLAYER STATUS (Split Inventory/Clues)
        col_inv, col_clues = st.columns(2)
        with col_inv:
            st.subheader("🎒 Backpack (Items)")
            if st.session_state.player["inventory"]:
                for item in st.session_state.player["inventory"]:
                    with st.expander(f"🔑 {item['name']}", expanded=True):
                        st.write(item['description'])
            else:
                st.caption("Empty.")
                
        with col_clues:
            st.subheader("📓 Notebook (Clues)")
            if st.session_state.player["clues"]:
                for clue in st.session_state.player["clues"]:
                     with st.expander(f"📝 Clue Found", expanded=True):
                        st.write(f"**{clue['name']}**: {clue['description']}")
            else:
                st.caption("No data collected.")

    # --- RIGHT COLUMN: The AI Interaction Engine ---
    with col_beholder:
        # Only show chat if an object is selected AND the room isn't solved
        if st.session_state.active_entity_id and not master_puzzle["solved"]:
            active_id = st.session_state.active_entity_id
            entity_data = room["interactables"][active_id]
            win_flag_name = entity_data["llm_config"]["win_flag"]
            
            # Header for the current interaction
            st.subheader(f"Talking to: {entity_data['name']}")
            with st.container(height=400, border=True):
                 # Display Chat History
                 for msg in st.session_state.chat_history:
                     # Use distinct avatars for clarity
                     avatar = "👤" if msg["role"] == "user" else "🤖"
                     st.chat_message(msg["role"], avatar=avatar).write(msg["content"])

            # --- WIN CONDITION CHECK ---
            # We check this *before* input to handle the state change immediately after the AI speaks.
            if st.session_state.get('last_game_logic', {}).get(win_flag_name) == True:
                    loot = entity_data.get("loot", {})
                    
                    # ROUTING LOGIC: Is it a tool or a clue?
                    if loot.get("type") == "item":
                        st.toast(f"Acquired: {loot['name']}!", icon="🎒")
                        st.session_state.player["inventory"].append(loot)
                    else:
                         st.toast("Clue added to notebook!", icon="📓")
                         st.session_state.player["clues"].append(loot)
                    
                    # Update object status
                    st.session_state.room_data["interactables"][active_id]["status"] = "cleared"
                    
                    # Reset selection state
                    st.session_state.active_entity_id = None
                    st.session_state.chat_history = []
                    st.session_state.last_game_logic = {}
                    time.sleep(1) # Brief pause for effect before auto-rerun
                    st.rerun()
            
            # Chat Input
            # Only show input if we haven't just won (prevents double submission)
            elif user_input := st.chat_input(f"Interact with {entity_data['name']}..."):
                 # 1. Append user message
                 st.session_state.chat_history.append({"role": "user", "content": user_input})
                 
                 # 2. Generate & Parse AI response
                 with st.spinner(f"{entity_data['name']} is reacting..."):
                     sys_prompt = build_system_prompt(st.session_state.player, entity_data)
                     raw_response = interact_with_entity(sys_prompt, user_input)
                     dialogue, game_logic = parse_llm_response(raw_response, win_flag_name)
                     
                     # 3. Save state and rerun
                     st.session_state.last_game_logic = game_logic
                     st.session_state.chat_history.append({"role": "assistant", "content": dialogue})
                     st.rerun()

        # Default empty state for the right column
        elif not master_puzzle["solved"]:
             with st.container(height=400, border=True):
                  st.empty()
             st.info("👈 Select an object from the room to begin investigating.")