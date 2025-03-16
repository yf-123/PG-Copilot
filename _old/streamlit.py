
# from openai import OpenAI
import streamlit as st
import requests
import json

base_url = "http://localhost:8088/v1/"
headers = {"accept": "application/json"}

agent_name="recruiter_agent"
user_name=st.text_input("Enter your name", value="Abd")
agent_details_URL=base_url+f"agents?agent_name={agent_name}"
response = requests.get(agent_details_URL, headers=headers)
response=response.json()
print(response)
if "agent_id" not in response:    
    st.warning('No MemGPT server running', icon="⚠️")
else:
    agent_id=response["agent_id"]
    if agent_id is None:
        st.warning('No agents available. Make sure you set up the agents.', icon="⚠️")
    else:    
        # agent_name = st.selectbox("Choose agent", agent_names, index=0)
        
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("What is up?"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            messages = [
                {"role": "agent", "content": agent_id},
            ]
            messages.extend([
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ])
            payload = {
                "messages": messages,
                "stream": False,
            }
            send_message_URL = base_url + "chat/completions-ns"
            response = requests.post(send_message_URL, json=payload, stream=False)
    


            # HIDDEN for handling stream response
            # st_response = st.empty()
            # full_response = ""
            # for line in response.iter_lines(decode_unicode=True):
            #     if line.startswith("data: "):
            #         line = line[len("data: "):]  # Remove the "data: " prefix
            #         if line == "[DONE]":
            #             break
            #         data = json.loads(line)
            #         if "choices" in data:
            #             delta = data["choices"][0].get("delta", {})
            #             content = delta.get("content", "")
            #             if content:
            #                 full_response += content
            #                 st_response.markdown(full_response)

            # st.session_state.messages.append({"role": "assistant", "content": full_response})

              # Handle the new response structure
            if "messages" in response.json():
                for msg in response.json()["messages"]:
                    if msg["message_type"] == "internal_monologue":
                        st.session_state.messages.append({"role": "assistant", "content": msg["internal_monologue"]})
                    elif msg["message_type"] == "function_call":
                        st.session_state.messages.append({"role": "assistant", "content": msg["function_call"]["arguments"]})
                    elif msg["message_type"] == "function_return":
                        st.session_state.messages.append({"role": "assistant", "content": msg["function_return"]})
            else:
                st.session_state.messages.append({"role": "assistant", "content": "No response from the agent."})