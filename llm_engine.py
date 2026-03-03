import os
import re
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Initialize the client. Make sure your .env file is set up!
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def build_system_prompt(player_state, room_data, obj_data):
    """Compiles the player state and NPC personality into the master prompt."""
    llm_config = obj_data["llm_config"]
    win_flag = llm_config["win_flag"]
    
    stat_string = ", ".join([f"{k.capitalize()}: {v}" for k, v in player_state["stats"].items()])
    inv_string = ", ".join([item["name"] for item in player_state["inventory"]]) if player_state["inventory"] else "Empty hands"

    # Safely construct the markdown formatting so it doesn't break syntax highlighting
    json_example = f"```json\n{{\n    \"{win_flag}\": true\n}}\n```"

    system_prompt = f"""
You are an NPC entity in a dungeon-crawling RPG game. 
    
YOUR ROLE:
{llm_config['personality']}

THE PLAYER:
- Stats: {stat_string}
- Inventory: {inv_string}

STAT RULES: 
Subtly adjust your stubbornness based on the player's stats. If they mention an item in their inventory that logically solves your problem, you MUST concede.

CRITICAL ENGINE INSTRUCTIONS:
You are also functioning as the game's logic engine. You must evaluate if the player has successfully met your conditions.
At the very end of your response, you MUST append a strict JSON block communicating the game state. 

Format your response exactly like this:
<your dialogue>
{json_example}
"""
    return system_prompt.strip()

def interact_with_entity(system_prompt, user_message):
    """Sends the prompt and user message to the LLM."""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_prompt}\n\nPlayer says: {user_message}"
        )
        return response.text
    except Exception as e:
        return f"Error connecting to the AI realm: {e}"

def parse_llm_response(text, win_flag):
    """Extracts the JSON block from the LLM's response and separates the dialogue."""
    # Find everything between ```json and ```
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    
    dialogue = text
    game_state = {win_flag: False}
    
    if match:
        json_str = match.group(1)
        # Remove the JSON block from the text to get clean dialogue
        dialogue = text.replace(match.group(0), "").strip()
        try:
            parsed_data = json.loads(json_str)
            # Safely get the boolean value, defaulting to False if something goes wrong
            game_state[win_flag] = parsed_data.get(win_flag, False)
        except json.JSONDecodeError:
            pass # Failsafe if the LLM outputs malformed JSON
            
    return dialogue, game_state