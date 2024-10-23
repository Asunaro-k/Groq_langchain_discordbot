import discord
import os
import Client
import pathlib
import OllamaLangModel
import LangModel
from langchain_groq import ChatGroq

Global_llm = None

def get_prompt(path: str) -> str:
    path = pathlib.Path(path)
    if path.exists():
        with open(path, 'r') as f:
            return f.read()
    else:
        prompts = [
            'あなたは知識豊富なアシスタントです。会話を良く理解し、適切な返答を行います。基本的に日本語で答えてください。'
            'あなたの一人称は「僕」です。'
        ]
        prompt = '\n'.join(prompts)
        return prompt
    
def get_system_prompt(path: str) -> str:
    return get_prompt(path)

if __name__ == '__main__':
    intents = discord.Intents.default()
    #intents = discord.Intents.none()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    system_prompt_path = '/prompts/system_prompt.md'
    system_prompt = get_prompt(system_prompt_path)
    
    # llm = OllamaLangModel.OllamaAPIChatModel(
    #     lang_model=LangModel.LangModel(
    #         api_key=os.environ['OLLAMA_API_KEY'],
    #         api_url=os.environ['OLLAMA_URL'],
    #         model_name="gemma2:9b",
    #     )
    # )
    #model="gemma2-9b-it",
    #llama-3.2-11b-vision-preview
    #llama-3.1-70b-versatile
    llm = ChatGroq(
        model="llama-3.2-90b-text-preview",
        temperature=0.7,
    )
    Global_llm = llm

    langchainbot = Client.LangchainBot(
        llm=llm,
        intents=intents,
        system_prompt=system_prompt,
        system_prompt_getter=lambda : get_system_prompt(system_prompt_path),
    )
    langchainbot.run(os.environ['DISCORD_API_KEY'])
