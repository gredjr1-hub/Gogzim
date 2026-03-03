import streamlit as st
from llm_engine import generate_dynamic_room, build_system_prompt, interact_with_entity, parse_llm_response

st.set_page_config(page_title="AI Escape Room", layout="wide")

# --- 1. Session State Initialization ---
if "setup_complete" not in st.session_state:
    st.session_state.setup_complete = False
if "room_data" not in st.session_state:
    st.session_state.room_data = {}
if "player" not in st.session_state:
    # Notice we track physical inventory AND mental clues separately
    st.session_state.player = {"inventory": [], "clues": []}
if "active_entity_id" not in st.session_state:
    st.session_state.active_entity_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_game_logic" not in st.session_state:
    st.session_state.last_game_logic = {}

# --- 2. The Main Menu ---
if not st.session_state.setup_complete:
    st.title("The Architect's Forge")
    st.write("Specify the parameters for your next escape room.")
    
    with st.form("generation_form"):
        difficulty = st.select_slider("Difficulty", options=["Easy", "Normal", "Hard"], value="Normal")
        theme = st.text_area("Setting & Theme", placeholder="e.g., A pirate captain's sunken quarters.")
        
        submitted = st.form_submit_button("Generate Level")
        
        if submitted and theme:
            with st.spinner("The Architect is building the puzzles..."):
                new_room = generate_dynamic_room(theme, difficulty)
                if new_room:
                    st.session_state.room_data = new_room
                    st.session_state.player = {"inventory": [], "clues": []} 
                    st.session_state.setup_complete = True
                    st.rerun()
                else:
                    st.error("The Architect failed. Try again.")

# --- 3. The Game View ---
else:
    room = st.session_state.room_data
    col1, col2 = st.columns([1, 1])

    # Left Column: Navigation & UI
    with col1:
        st.title(room["name"])
        st.write(f"*{room['visual_description']}*")
        
        st.divider()
        st.subheader("Escape Keypad")
        if room["master_puzzle"]["solved"]:
            st.success(room["master_puzzle"]["success_message"])
            if st.button("Start a New Room"):
                st.session_state.setup_complete = False
                st.rerun()
        else:
            guess = st.text_input("Enter the Master Code:")
            if st.button("Attempt Unlock"):
                if guess == room["master_puzzle"]["solution"]:
                    st.session_state.room_data["master_puzzle"]["solved"] = True
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Incorrect code.")

        st.divider()
        st.subheader("Points of Interest")
        
        for obj_id, obj_data in room["interactables"].items():
            if obj_data["status"] == "active":
                if st.button(f"🔍 Inspect {obj_data['name']}"):
                    st.session_state.active_entity_id = obj_id
                    st.session_state.chat_history = []
                    st.rerun()
            else:
                st.write(f"✅ {obj_data['name']} (Searched)")

        st.divider()
        
        # --- NEW: Split Inventory and Clues UI ---
        col_inv, col_clues = st.columns(2)
        
        with col_inv:
            st.subheader("🎒 Backpack (Items)")
            if st.session_state.player["inventory"]:
                for item in st.session_state.player["inventory"]:
                    st.info(f"**{item['name']}**\n\n{item['description']}")
            else:
                st.write("Empty.")
                
        with col_clues:
            st.subheader("📓 Notebook (Clues)")
            if st.session_state.player["clues"]:
                for clue in st.session_state.player["clues"]:
                    st.warning(f"**{clue['name']}**\n\n{clue['description']}")
            else:
                st.write("No clues found.")

    # Right Column: AI Interaction Engine
    with col2:
        if st.session_state.active_entity_id and not room["master_puzzle"]["solved"]:
            active_id = st.session_state.active_entity_id
            entity_data = room["interactables"][active_id]
            
            st.subheader(f"Interacting: {entity_data['name']}")
            
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
                    
            if user_input := st.chat_input("Take an action or speak..."):
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with st.chat_message("user"):
                    st.write(user_input)
                
                with st.spinner("Processing..."):
                    sys_prompt = build_system_prompt(st.session_state.player, entity_data)
                    raw_response = interact_with_entity(sys_prompt, user_input)
                    
                    win_flag_name = entity_data["llm_config"]["win_flag"]
                    dialogue, game_logic = parse_llm_response(raw_response, win_flag_name)
                    
                    st.session_state.last_game_logic = game_logic
                    st.session_state.chat_history.append({"role": "assistant", "content": dialogue})
                    st.rerun()

            # --- NEW: The Routing Logic ---
            if len(st.session_state.chat_history) > 0 and st.session_state.chat_history[-1]["role"] == "assistant":
                win_flag_name = entity_data["llm_config"]["win_flag"]
                if st.session_state.get('last_game_logic', {}).get(win_flag_name) == True:
                    
                    # Check what kind of loot we just won
                    loot = entity_data.get("loot", {})
                    if loot.get("type") == "item":
                        st.success(f"You acquired an item: {loot['name']}!")
                        st.session_state.player["inventory"].append(loot)
                    else:
                        st.success("You extracted a clue!")
                        st.session_state.player["clues"].append(loot)
                    
                    # Mark object as cleared
                    st.session_state.room_data["interactables"][active_id]["status"] = "cleared"
                    
                    # Reset Interaction
                    st.session_state.active_entity_id = None
                    st.session_state.chat_history = []
                    st.session_state.last_game_logic = {}
                    
                    if st.button("Continue"):
                        st.rerun()
        else:
            if not room["master_puzzle"]["solved"]:
                st.info("Select an object on the left to investigate.")