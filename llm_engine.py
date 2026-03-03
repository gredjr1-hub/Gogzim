import os
import re
import json
import random
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_dynamic_room(theme, difficulty):
    """
    Forces the LLM to design an Escape Room with an item-dependency puzzle.
    """
    num_digits = {"Easy": 2, "Normal": 3, "Hard": 4}.get(difficulty, 3)
    master_code = "".join([str(random.randint(1, 9)) for _ in range(num_digits)])
    
    # We ask for num_digits + 1 objects so there is room for a physical tool
    total_objects = num_digits + 1
    
    prompt = f"""
    You are an expert escape room level designer. 
    Create a room based on this theme: {theme}
    The difficulty is {difficulty}.
    
    The master puzzle is a {num_digits}-digit keypad lock. The solution is strictly: {master_code}.
    
    You must create exactly {total_objects} interactable objects in the room. 
    
    PUZZLE LOGIC RULES:
    1. One object must yield a physical TOOL/ITEM (e.g., a rusty key, a battery, a crowbar, a bucket of water). Its loot "type" must be "item".
    2. One of the OTHER objects MUST explicitly require this exact TOOL to be defeated/convinced. Note this requirement in its personality instructions.
    3. The remaining objects (and the one requiring the tool) must each yield exactly ONE digit of the master code. Their loot "type" must be "clue".
    
    Output strictly in this JSON format:
    {{
        "name": "Room Name",
        "visual_description": "2 sentences describing the atmosphere.",
        "master_puzzle": {{
            "solution": "{master_code}",
            "solved": false,
            "success_message": "What happens when the player escapes."
        }},
        "interactables": {{
            "object_1": {{
                "name": "Creative Object Name",
                "status": "active",
                "llm_config": {{
                    "personality": "You are [object]. You will yield if [condition].",
                    "win_flag": "yielded"
                }},
                "loot": {{
                    "type": "item", 
                    "name": "Tool Name",
                    "description": "A description of the physical item."
                }}
            }},
            "object_2": {{
                "name": "Another Object",
                "status": "active",
                "llm_config": {{
                    "personality": "You are [object]. You require the [Tool Name] from object_1 to be bypassed.",
                    "win_flag": "yielded"
                }},
                "loot": {{
                    "type": "clue",
                    "name": "Clue Name",
                    "description": "A hint revealing the digit [Digit 1]."
                }}
            }}
            // ... repeat until you have exactly {total_objects} objects ...
        }}
    }}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Generation Error: {e}")
        return None

def build_system_prompt(player_state, obj_data):
    """Compiles the prompt, heavily emphasizing the player's physical inventory."""
    llm_config = obj_data["llm_config"]
    win_flag = llm_config["win_flag"]
    
    # This string is the secret sauce. It tells the AI exactly what the player is holding.
    inv_string = ", ".join([item["name"] for item in player_state["inventory"]]) if player_state["inventory"] else "Empty hands"

    json_example = f"```json\n{{\n    \"{win_flag}\": true\n}}\n```"

    system_prompt = f"""
You are an entity guarding something in an escape room. 
    
YOUR ROLE AND WIN CONDITION:
{llm_config['personality']}

THE PLAYER'S PHYSICAL INVENTORY:
[{inv_string}]

RULES: 
You must act as the game's physics/logic engine. 
Read the player's physical inventory list above. If your instructions say you require a specific item, you MUST verify the player actually has it in their inventory list before yielding. If they say they use an item, but it is not in the list, tell them they don't have it.
If the player figures out your riddle, OR logically uses an item they possess to solve your problem, you MUST yield. 

When the player succeeds, you MUST append this strict JSON block at the very end of your response:
<your dialogue>
{json_example}
"""
    return system_prompt.strip()

def interact_with_entity(system_prompt, user_message):
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_prompt}\n\nPlayer says: {user_message}"
        )
        return response.text
    except Exception as e:
        return f"Error: {e}"

def parse_llm_response(text, win_flag):
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    dialogue = text
    game_state = {win_flag: False}
    
    if match:
        json_str = match.group(1)
        dialogue = text.replace(match.group(0), "").strip()
        try:
            parsed_data = json.loads(json_str)
            game_state[win_flag] = parsed_data.get(win_flag, False)
        except json.JSONDecodeError:
            pass
            
    return dialogue, game_state