from openai import OpenAI
from agent.instruction import SYSTEM_INSTRUCTION
from agent.outputstructure import AIResponse
from typing import AsyncGenerator
from dotenv import load_dotenv
import json
import re

import os
import chromadb
load_dotenv(override=True)


class AgentFunstions:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.chroma_client = chromadb.PersistentClient(path="./vector_db")
        self.collection = self.chroma_client.get_or_create_collection(name="web_chunks",)
        self.db_fetch_size = 5
        self.llm_model = "gpt-4.1" # "gpt-4o-mini"

    async def query_process(self ,user_input: str):
        try:

            # Get result fom vector DB
            results = self.collection.query(query_texts=[user_input], n_results=self.db_fetch_size)

            # LLM parsing
            response = self.client.responses.parse(
                model="gpt-4o-mini", 
                input=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": f"This is the feched content from the DB:-\n\n{results}\n\n User Question:- {user_input}"}
                ],
                temperature=0.3,
                text_format=AIResponse,
                # stream=True
            )

            ai_answer = response.output_parsed.model_dump()
            return {"status": 0, "message": "", "data": ai_answer}


        except Exception as e:
            return {"status": -1, "message": str(e), "data": {}}

    # # Querry stream
    # def query_process_stream(self, user_input: str):
    #     try:
    #         # 1. Fetch from Vector DB
    #         results = self.collection.query(
    #             query_texts=[user_input],
    #             n_results=self.db_fetch_size
    #         )

    #         # 2. Start Stream
    #         with self.client.responses.stream(
    #             model= self.llm_model,
    #             input=[
    #                 {"role": "system", "content": SYSTEM_INSTRUCTION},
    #                 {"role": "user", "content": f"DB Result:\n{results}\n\nUser query: {user_input}"}
    #             ],
    #             text_format=AIResponse,
    #             temperature=0.3,
    #         ) as stream:
                
    #             # --- FILTERING LOGIC ---
    #             buffer = ""
    #             answer_started = False
    #             answer_ended = False
                
    #             for event in stream:
    #                 if event.type == "response.output_text.delta":
    #                     chunk = event.delta
                        
    #                     # If we already finished the answer text, ignore the rest of the stream
    #                     # (This hides the "cards": [...] JSON syntax from the UI)
    #                     if answer_ended:
    #                         continue

    #                     buffer += chunk

    #                     # Step A: Look for the start of the answer field
    #                     if not answer_started:
    #                         # Regex finds "answer": " (ignoring whitespace)
    #                         match = re.search(r'"answer"\s*:\s*"', buffer)
    #                         if match:
    #                             answer_started = True
    #                             # Remove the key and start quote from buffer, keep the content
    #                             buffer = buffer[match.end():]
                        
    #                     # Step B: Process and stream the answer content
    #                     if answer_started:
    #                         i = 0
    #                         clean_chunk = ""
                            
    #                         while i < len(buffer):
    #                             char = buffer[i]
                                
    #                             # Handle Escape Sequences (e.g., \n, \", \\)
    #                             if char == '\\':
    #                                 # If we have a backslash but no next char, wait for next chunk
    #                                 if i + 1 >= len(buffer):
    #                                     break 
                                    
    #                                 next_char = buffer[i+1]
    #                                 # Convert JSON escapes to real characters for the UI
    #                                 if next_char == 'n': clean_chunk += '\n'
    #                                 elif next_char == '"': clean_chunk += '"'
    #                                 elif next_char == '\\': clean_chunk += '\\'
    #                                 else: clean_chunk += next_char
    #                                 i += 2 # Skip \ and the char
                                
    #                             # Handle End of Answer
    #                             elif char == '"':
    #                                 answer_ended = True
    #                                 i += 1 # Consume the closing quote
    #                                 break # Stop processing
                                
    #                             # Handle Normal Characters
    #                             else:
    #                                 clean_chunk += char
    #                                 i += 1
                            
    #                         # Send the clean text to frontend
    #                         if clean_chunk:
    #                             yield json.dumps({"type": "delta", "content": clean_chunk}) + "\n"
                            
    #                         # Remove processed characters from buffer
    #                         buffer = buffer[i:]

    #             # 3. Send Final Structured Result (Cards + Answer)
    #             final = stream.get_final_response()
    #             final_json = final.output_parsed.model_dump()
    #             yield json.dumps({"type": "result", "content": final_json}) + "\n"

    #     except Exception as e:
    #         yield json.dumps({"type": "error", "content": str(e)}) + "\n"



    # ---------------------------------------------------#
    # Different types of responses
    def query_process_stream(self, user_input: str):
        try:
            # 1. Fetch from Vector DB
            results = self.collection.query(
                query_texts=[user_input],
                n_results=self.db_fetch_size
            )

            # 2. Start Stream
            with self.client.responses.stream(
                model=self.llm_model,
                input=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": f"DB Result:\n{results}\n\nUser query: {user_input}"}
                ],
                text_format=AIResponse,
                temperature=0.3,
            ) as stream:
                
                buffer = ""
                
                # --- STATES ---
                # 0: Searching for "answer": "
                # 1: Streaming Answer Text
                # 2: Searching for "cards": [
                # 3: Parsing Card Objects { ... }
                state = 0 
                
                for event in stream:
                    if event.type == "response.output_text.delta":
                        chunk = event.delta
                        buffer += chunk
                        
                        # === STATE 0: LOOK FOR START OF ANSWER ===
                        if state == 0:
                            match = re.search(r'"answer"\s*:\s*"', buffer)
                            if match:
                                # Advance buffer past the key
                                buffer = buffer[match.end():]
                                state = 1
                        
                        # === STATE 1: STREAM ANSWER CONTENT ===
                        if state == 1:
                            i = 0
                            clean_text = ""
                            while i < len(buffer):
                                char = buffer[i]
                                
                                # Handle Escapes (\n, \", \\)
                                if char == '\\':
                                    if i + 1 >= len(buffer): break # Incomplete escape, wait for next chunk
                                    next_char = buffer[i+1]
                                    if next_char == 'n': clean_text += '\n'
                                    elif next_char == '"': clean_text += '"'
                                    elif next_char == '\\': clean_text += '\\'
                                    else: clean_text += next_char
                                    i += 2
                                # Handle End of Answer
                                elif char == '"':
                                    state = 2 # Move to finding cards
                                    i += 1 
                                    
                                    # Send whatever text we collected so far
                                    if clean_text:
                                        yield json.dumps({"type": "delta", "content": clean_text}) + "\n"
                                    
                                    buffer = buffer[i:] # Keep remaining buffer
                                    break 
                                # Normal Character
                                else:
                                    clean_text += char
                                    i += 1
                            
                            # If we are still in state 1, yield the text chunk
                            if state == 1 and clean_text:
                                yield json.dumps({"type": "delta", "content": clean_text}) + "\n"
                                buffer = buffer[i:] # Remove processed chars

                        # === STATE 2: LOOK FOR START OF CARDS ARRAY ===
                        if state == 2:
                            # We are looking for: "cards": [
                            # Use Regex to ignore whitespace/newlines/commas
                            match = re.search(r'"cards"\s*:\s*\[', buffer)
                            if match:
                                buffer = buffer[match.end():] # Cut past the [
                                state = 3
                        
                        # === STATE 3: EXTRACT JSON OBJECTS ===
                        if state == 3:
                            # We are inside the array [ ... ]
                            # We need to find matching { and }
                            
                            while True:
                                # Find the first opening brace
                                start_idx = buffer.find('{')
                                if start_idx == -1:
                                    break # No object started yet, wait for more chunks
                                
                                # Now scan for the matching closing brace
                                # We must count depth in case of nested objects (though unlikely for cards)
                                depth = 0
                                end_idx = -1
                                
                                for k in range(start_idx, len(buffer)):
                                    if buffer[k] == '{':
                                        depth += 1
                                    elif buffer[k] == '}':
                                        depth -= 1
                                        if depth == 0:
                                            end_idx = k
                                            break
                                
                                if end_idx != -1:
                                    # We have a full JSON string: { ... }
                                    raw_json = buffer[start_idx : end_idx+1]
                                    
                                    try:
                                        card_obj = json.loads(raw_json)
                                        yield json.dumps({"type": "card_item", "content": card_obj}) + "\n"
                                    except:
                                        pass # Skip if malformed
                                    
                                    # Remove this object from buffer and continue loop
                                    buffer = buffer[end_idx+1:]
                                else:
                                    # Object started but not finished (wait for next chunk)
                                    break

        except Exception as e:
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"