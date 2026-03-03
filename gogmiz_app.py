import streamlit as st
from game_data import game_world, starting_player_state
from llm_engine import build_system_prompt, interact_with_entity, parse_llm_response

# Set up the visual real estate
st.set_page_config(page_title="The Mad Architect's Dungeon", layout="wide")

# --- 1. Initialize Session State ---
# This keeps the game running continuously without resetting on every button click
if "player" not in st.session_state:
    st.session_state.player = starting_player_state.copy()
if "world" not in st.session_state:
    st.session_state.world = game_world.copy()
if "active_entity_id" not in st.session_state:
    st.session_state.active_entity_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Helper variables for the current view ---
current_room_id = st.session_state.player["current_room"]
room_data = st.session_state.world["rooms"][current_room_id]

# --- 2. Main UI Layout ---
col1, col2 = st.columns([1, 1])

# Left Column: The Room and Navigation
with col1:
    st.title(room_data["name"])
    st.write(f"*{room_data['visual_description']}*")
    st.divider()
    
    st.subheader("Interactables")
    
    # Generate buttons for everything in the room that is still locked
    for obj_id, obj_data in room_data["interactables"].items():
        if obj_data["status"] == "locked":
            if st.button(f"🔍 Inspect {obj_data['name']}"):
                st.session_state.active_entity_id = obj_id
                st.session_state.chat_history = [] # Clear the chat when switching objects
                st.rerun()
        else:
            # Show what has already been bypassed
            st.write(f"✅ {obj_data['name']} (Cleared)")

    st.divider()
    
    # The HUD
    st.subheader("Inventory & Stats")
    st.write("**Inventory:**")
    if st.session_state.player["inventory"]:
        for item in st.session_state.player["inventory"]:
            st.write(f"- {item['name']}")
    else:
        st.write("Empty")
        
    st.write("**Stats:**")
    st.json(st.session_state.player["stats"])

# Right Column: The AI Interaction Engine
with col2:
    if st.session_state.active_entity_id:
        active_id = st.session_state.active_entity_id
        entity_data = room_data["interactables"][active_id]
        
        st.subheader(f"Talking to: {entity_data['name']}")
        
        # Display the ongoing conversation
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                
        # The Chat Input Box
        if user_input := st.chat_input("State your case..."):
            
            # 1. Show the user's message immediately
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.write(user_input)
            
            # 2. Process the AI response
            with st.spinner("The entity is thinking..."):
                sys_prompt = build_system_prompt(st.session_state.player, room_data, entity_data)
                raw_response = interact_with_entity(sys_prompt, user_input)
                
                win_flag_name = entity_data["llm_config"]["win_flag"]
                dialogue, game_logic = parse_llm_response(raw_response, win_flag_name)
                st.session_state.last_game_logic = game_logic
                st.session_state.chat_history.append({"role": "assistant", "content": dialogue})
                st.rerun()

        # --- 3. Win Condition Checking ---
        # We check this outside the chat input loop so the UI updates correctly
        if len(st.session_state.chat_history) > 0 and st.session_state.chat_history[-1]["role"] == "assistant":
            
            # Re-run the parser purely to check the state of the last message
            last_assistant_msg = st.session_state.chat_history[-1]["content"]
            
            # We need to re-fetch raw_response logic if it exists in the session, 
            # but since we process it above, we can just check our parser function
            # Note: We need the raw text with JSON here. Since we stripped it for chat_history,
            # we must rely on the game_logic variable from the interaction step. 
            
            # To make this robust across reruns, we intercept the logic right after generation:
            pass # The logic handling is safely managed below instead.

    else:
        st.info("Click an object in the room to the left to interact with it.")

# --- 4. State Management Failsafe ---
# Because Streamlit reruns top-to-bottom, we handle the win logic check here
# to ensure it captures the exact moment the AI yields.
if st.session_state.active_entity_id:
    active_id = st.session_state.active_entity_id
    entity_data = st.session_state.world["rooms"][current_room_id]["interactables"][active_id]
    win_flag_name = entity_data["llm_config"]["win_flag"]
    
    # Check if the last interaction successfully parsed a True flag
    # (We could store the last parsed JSON in session_state, but for simplicity we'll assume
    # if the flag is triggered, we process it). 
    
    # A cleaner way: Let's store the last evaluated logic in session state during the chat phase.
    pass

# Update for robust logic handling:
if 'last_game_logic' not in st.session_state:
    st.session_state.last_game_logic = {}

if len(st.session_state.chat_history) > 0 and st.session_state.chat_history[-1]["role"] == "assistant":
     if st.session_state.active_entity_id:
        active_id = st.session_state.active_entity_id
        entity_data = st.session_state.world["rooms"][current_room_id]["interactables"][active_id]
        win_flag_name = entity_data["llm_config"]["win_flag"]
        
        # Check if the logic dict triggered a win
        if st.session_state.get('last_game_logic', {}).get(win_flag_name) == True:
            st.success(f"You have bested the {entity_data['name']}!")
            
            # Execute the reward logic
            st.session_state.world["rooms"][current_room_id]["interactables"][active_id]["status"] = "unlocked"
            
            if entity_data["type"] == "exit":
                st.session_state.player["current_room"] = entity_data["destination"]
                st.balloons() # A little celebration for clearing a room
            elif entity_data["type"] == "container":
                st.session_state.player["inventory"].append(entity_data["loot"])
            
            # Reset interaction state
            st.session_state.active_entity_id = None
            st.session_state.chat_history = []
            st.session_state.last_game_logic = {} # Clear the logic
            
            # Provide a button to refresh the screen and show the new room/inventory
            if st.button("Continue"):
                st.rerun()

# --- Modification to the Chat Input to save logic ---
# Ensure you update the chat input block above to save the logic:
# dialogue, game_logic = parse_llm_response(raw_response, win_flag_name)
# st.session_state.last_game_logic = game_logic