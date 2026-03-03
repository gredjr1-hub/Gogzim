import re
import json
import random
from google import genai
import streamlit as st


# Initialize Gemini Client
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def generate_dynamic_escape_room(theme, difficulty):
    """
    Acts as the Lead Level Designer. It decides the master code, determines
    the number of puzzle steps based on difficulty, and forces the LLM
    to generate interlocking puzzles with physical item dependencies.
    """
    # 1. Define Difficulty Parameters
    # Easy: 2-digit code, 3 objects total (1 item puzzle + 1 standalone clue)
    # Normal: 3-digit code, 4 objects total (1 item puzzle + 2 standalone clues)
    # Hard: 4-digit code, 5 objects total (1 item puzzle + 3 standalone clues)
    configs = {
        "Easy": {"digits": 2, "total_objs": 3},
        "Normal": {"digits": 3, "total_objs": 4},
        "Hard": {"digits": 4, "total_objs": 5}
    }
    config = configs.get(difficulty, configs["Normal"])
    num_digits = config["digits"]
    total_objects = config["total_objs"]

    # 2. Procedurally create the Master Solution strictly in Python
    # This guarantees the puzzle is solvable because we know the answer beforehand.
    master_code = "".join([str(random.randint(0, 9)) for _ in range(num_digits)])
    print(f"DEBUG: Generated Master Code: {master_code}") # Useful for testing

    # 3. The Architect Prompt
    # We give the LLM the answers and tell it to design the questions.
    prompt = f"""
    You are an expert real-world escape room designer. 
    Design a single-room escape experience based on this theme: "{theme}".
    The Difficulty level is: {difficulty}.

    ---THE MASTER PUZZLE---
    The players must find a {num_digits}-digit numerical code to unlock the final door.
    The strictly defined solution code is: {master_code}

    ---DESIGN CONSTRAINTS---
    You must create exactly {total_objects} unique interactable objects in the room.
    You must structure the puzzles with an item dependency chain:

    1.  **The Tool Provider:** Create one object that yields a physical TOOL when solved (e.g., a rusty key, a battery, a screwdriver). Its "loot" type must be "item".
    2.  **The Tool User:** Create another object that EXPLICITLY requires that specific tool to be solved. This object holds the clue for the FIRST digit of the master code ({master_code[0]}). Its "loot" type must be "clue".
    3.  **The Remaining Clues:** The other {num_digits - 1} objects should hold the clues for the remaining digits of the code. Their "loot" type must be "clue".

    Output strictly valid JSON following this structure only. Do not add markdown formatting outside the JSON block.
    {{
        "name": "Creative Room Title",
        "visual_description": "Two vivid sentences describing the sights, sounds, and smells of the room.",
        "master_puzzle": {{
            "type": "keypad",
            "solution": "{master_code}",
            "solved": false,
            "success_message": "The keypad beeps green. The heavy locking mechanisms disengage, and the way forward opens. You have escaped!"
        }},
        "interactables": {{
            "unique_id_1": {{
                "name": "Name of Object",
                "status": "active",
                "llm_config": {{
                    "personality": "Describe the object's persona and the exact condition needed to make it yield. If it requires a physical tool, state that requirement clearly here.",
                    "win_flag": "yielded_loot"
                }},
                "loot": {{
                    "type": "item OR clue", 
                    "name": "Name of the Key or Clue",
                    "description": "If item: Physical description. If clue: The actual hint pointing to a specific digit."
                }}
            }},
            // ... Repeat for exactly {total_objects} objects defined above ...
        }}
    }}
    """
    
    try:
        # Force Gemini to output pure JSON
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Escape Room Generation Error: {e}")
        # In a real app, you might retry generation here.
        return None

def build_system_prompt(player_state, obj_data):
    """
    Compiles the interaction prompt, heavily emphasizing physical inventory reality.
    """
    llm_config = obj_data["llm_config"]
    win_flag = llm_config["win_flag"]
    
    # Create a clear list of physical items the player is holding
    inv_list = [item["name"] for item in player_state["inventory"]]
    inv_string = ", ".join(inv_list) if inv_list else "Nothing visible in hands."

    # Pre-format the JSON success block
    json_example = f"```json\n{{\n    \"{win_flag}\": true\n}}\n```"

    system_prompt = f"""
You are a sentient entity or complex mechanism in an escape room.
    
YOUR PUZZLE ROLE & WIN CONDITION:
{llm_config['personality']}

THE PLAYER'S PHYSICAL REALITY:
The player is currently holding the following physical items: [{inv_string}]

CRITICAL RULES FOR THE AI: 
1.  **Verify Physics:** You act as the game's physics engine. If your instructions above state that you require a specific physical tool (like a 'Brass Key' or 'Battery'), you MUST verify that exact item name exists in the player's physical inventory list above.
2.  **Reject Lies:** If the player claims to use an item they do not physically possess based on the list above, you must reject their action and tell them they don't have it.
3.  **Yield on Success:** If the player meets your condition (by solving a riddle OR correctly using a possessed physical item), you must yield your loot.
    
When the player successfully solves your puzzle, append this exact JSON block to the end of your dialogue:
{json_example}
"""
    return system_prompt.strip()

def interact_with_entity(system_prompt, user_message):
    """Sends the prompt and user message to Gemini."""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_prompt}\n\nPlayer says: {user_message}"
        )
        return response.text
    except Exception as e:
        return f"Connection Error: {e}"

def parse_llm_response(text, win_flag):
    """Extracts dialogue and the JSON win-signal from the response."""
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    dialogue = text
    # Default logic state is False
    game_logic = {win_flag: False}
    
    if match:
        json_str = match.group(1)
        # Clean the dialogue by removing the JSON block
        dialogue = text.replace(match.group(0), "").strip()
        try:
            parsed_data = json.loads(json_str)
            # Safely extract the boolean flag
            game_logic[win_flag] = parsed_data.get(win_flag, False)
        except json.JSONDecodeError:
            print("Warning: LLM output malformed JSON.")
            pass
            
    return dialogue, game_logic