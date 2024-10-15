import discord
import LangTools
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.language_models import BaseChatModel
#from langchain_core.prompts import PromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_vertexai.vision_models import (
    VertexAIImageEditorChat,
    VertexAIImageGeneratorChat,
    VertexAIImageCaptioning,
)
import base64
import io
from PIL import Image
import aiohttp

generator = VertexAIImageGeneratorChat()
# Create Image Editor model Object
editor = VertexAIImageEditorChat()
caption_model = VertexAIImageCaptioning()

class LangchainBot(discord.Client):
    def __init__(self, llm:BaseChatModel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generated_image_base64 = None
        
        self.llm = llm
        
        self.system_prompt_getter = None
        if 'system_prompt_getter' in kwargs:
            self.system_prompt_getter = kwargs['system_prompt_getter']
            print(self.system_prompt_getter())
        
        self.system_prompt = None
        if 'system_prompt' in kwargs:
            self.system_prompt = {
                "role": "system",
                "content": kwargs['system_prompt'],
            }

    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        #print("on massege")
        if message.author.bot or message.author == self.user:
            #print("on 1")
            return
        # メンションされているユーザーのリストを取得
        mentioned_users = message.mentions

        #print(message.mentions)
        #print(message.content)
        #print(message)
        # 特定のユーザーがメンションされているか確認
        if self.user not in mentioned_users:
        #if f'<@{self.user.id}>' in message.content:
            #print("on 2")
            return
        
         # urlを含むか確認
        urls = LangTools.has_url(message.content)
        if message.attachments:
            flag = False
            for attachment in message.attachments:
                    if attachment.content_type.startswith("image/"):
                        #print(attachment.url)
                        flag = True
                        # Call the function to handle image caption generation
                        completion = await self.analyze_image(message, attachment.url)
                        reply = f"分析結果: {completion}"
                        #reply = await self.generate_caption_for_image(message, attachment.url)
            if not flag:
                await message.reply("Please provide a keyword to start the conversation.")
        elif urls:
            # とりあえずひとつだけ読む
            url = urls[0]
            reply = await self.generate_reply_with_webpage_content(
                message, url, history_limit=10)
        else:
            #print(message.content)
            command_content = message.content.replace(f'<@{self.user.id}>', '').strip()
            #print(command_content)
            if command_content.startswith('!conversation'):
                #print("aa")
                keyword = command_content[len('!conversation '):].strip()
                #print(keyword)
                if keyword:
                    reply = await self.generate_conversation_with_keyword(message, keyword)
                else:
                    await message.reply("Please provide a keyword to start the conversation.")

            elif command_content.startswith('!check'):
                sentence = command_content[len('!check '):].strip()
                if sentence:
                    corrected_sentence = await self.check_and_correct_grammar(message, sentence)
                    reply = f"Your original sentence: {sentence}\nCorrected sentence: {corrected_sentence}"
                else:
                    await message.reply("Please provide a sentence to check.")

            elif command_content.startswith('!generateimage'):
                #print("aa")
                keyword = command_content[len('!generateimage '):].strip()
                #print(keyword)
                if keyword:
                    reply = await self.generate_image_with_keyword(message, keyword)
                else:
                    await message.reply("Please provide a keyword to generate the image.")
            elif command_content.startswith('!editimage'):
                new_description = command_content[len('!editimage '):].strip()
                if self.generated_image_base64 and new_description:
                    reply = await self.edit_generated_image(message, new_description)
                else:
                    await message.reply("No generated image found or invalid description.")
            else:
                reply = await self.generate_reply(message, history_limit=10)
        await message.reply(reply)

    async def generate_image_with_keyword(self, message, keyword):
        # Generate image using the specified keyword
        try:
            messages = [HumanMessage(content=keyword)]
            response = generator.invoke(messages)

            # To view the generated Image
            self.generated_image_base64 = response.content[0]
            # Parse response object to get base64 string for image
            img_base64 = self.generated_image_base64["image_url"]["url"].split(",")[-1]

            # Convert base64 string to Image
            img = Image.open(io.BytesIO(base64.decodebytes(bytes(img_base64, "utf-8"))))

            # Save image to file (optional step)
            img_path = f"./image/{keyword}.png"
            img.save(img_path)

            # Send the image back to the user
            with open(img_path, "rb") as f:
                await message.channel.send(file=discord.File(f, img_path))

            return f"Here is the image generated for the keyword: {keyword}"

        except Exception as e:
            return f"Failed to generate image: {str(e)}"
        
    async def edit_generated_image(self, message, new_description):
        try:
            # 生成された画像を新しい説明で編集
            messages = [HumanMessage(content=[self.generated_image_base64, new_description])]
            editor_response = editor.invoke(messages)

            # 編集された画像を取得
            edited_img_base64 = editor_response.content[0]["image_url"]["url"].split(",")[-1]

            # Base64文字列を画像としてデコード
            edited_img = Image.open(io.BytesIO(base64.decodebytes(bytes(edited_img_base64, "utf-8"))))

            # 編集された画像を保存
            edited_img_path = f"./image/{new_description}_edited.png"
            edited_img.save(edited_img_path)

            # 編集された画像を送信
            with open(edited_img_path, "rb") as f:
                await message.channel.send(file=discord.File(f, edited_img_path))

            return f"Here is the edited image with description: {new_description}"

        except Exception as e:
            return f"Failed to edit image: {str(e)}"
        
    async def analyze_image(self, message, image_url,history_limit=1) -> str:
        try:
            # メッセージから英語の文章を抽出するためのプロンプトを作成
            sentence = f"画像: {image_url} に関連する英語の説明をしてください"
            
            # 評価用のプロンプトを作成（文法の評価とフィードバック）
            prompt = f"{sentence}"
            
            # チャット履歴を取得して、メッセージに追加
            messages = await self.generate_chat_prompt(message, history_limit)
            messages.append(HumanMessage(content=prompt))
            
            # Chat modelに文法のチェックと訂正を行わせる
            response = await self.llm.ainvoke(messages)
            
            # 改行や余計なテキストのサニタイズ
            response = LangTools.sanitize_breakrow(response.content)
            
            return response

        except Exception as e:
            return f"Failed to analyze image: {str(e)}"
        
    async def generate_caption_for_image(self, message, image_url):
        try:
            # Download the image from the URL
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        img_bytes = await resp.read()
                        
                        # Convert the image to base64 string
                        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                        messages = [HumanMessage(content=f"data:image/jpeg;base64,{img_base64}")]
                        # Use the base64 encoded image in VertexAI for captioning
                        response = caption_model.invoke(messages)
                        print(response)
                        caption = response  # The generated caption

                        # Send the generated caption back to the Discord channel
                        return f"Generated Caption: {caption}"

                    else:
                        return "Failed to download the image."

        except Exception as e:
            return f"Error while generating caption: {str(e)}"
    
    
    async def generate_conversation_with_keyword(self, message, keyword, history_limit=10) -> str:
        prompt = f"キーワードに基づいた簡単な英会話をあなたとしたいです。日本語で会話をしたうえで英語で私に何か問いかけてください。：'{keyword}'。"
        messages = await self.generate_chat_prompt(message, history_limit)
        messages.append(HumanMessage(content=prompt))
    
        # Chat modelに会話の続きを生成させる
        response = await self.llm.ainvoke(messages)
        response = LangTools.sanitize_breakrow(response.content)
        return response
    
    async def check_and_correct_grammar(self, message, sentence, history_limit=10) -> str:
        prompt = f"あなたの目標は、ユーザーが楽しく英会話を練習し、上達できるようにサポートすることです。次の文章の英語の正しさを日本語で評価し、あっている場合は褒めてください。間違っている場合は修正を提案してください。: '{sentence}'"
        messages = await self.generate_chat_prompt(message, history_limit)
        messages.append(HumanMessage(content=prompt))
    
        # Chat modelに文法のチェックと訂正を行わせる
        response = await self.llm.ainvoke(messages)
        response = LangTools.sanitize_breakrow(response.content)
        return response
    
    async def generate_chat_prompt(self, message, history_limit:int=10) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        messages_generator = message.channel.history(limit=history_limit)
        # メッセージを取得 (最新のメッセージから取得)
        # messageを取得するたびに、HumanMessageかAIMessageに変換してmessagesに追加
        async for msg in messages_generator:
            content = LangTools.sanitize_mention(msg)
            if msg.author.bot:
                messages.append(AIMessage(content=content))
            else:
                name = LangTools.get_name(msg.author)
                name = name+': '
                messages.append(HumanMessage(content=f'{name}{content}'))
        
        # システムプロンプトを追加
        if self.system_prompt_getter is not None:
            self.system_prompt = self.system_prompt_getter()
        if self.system_prompt is not None:
            messages.append(SystemMessage(content=self.system_prompt))
        messages.reverse()
        
        return messages
    
    async def generate_reply(self, message, history_limit:int=10) -> str:
        messages: list[BaseMessage] = await self.generate_chat_prompt(
            message, history_limit)
        response: AIMessage = await self.llm.ainvoke(messages)
        response = response.content
        #print(f"response;{response}")
        response = LangTools.sanitize_breakrow(response)

        return response
    
    async def generate_reply_with_webpage_content(self, message, url:str, history_limit:int=10) -> str:
        async with message.channel.typing():
            messages: list[BaseMessage] = await self.generate_chat_prompt(
                message, history_limit)
            summary_with_info: tuple[str, list[str]] = LangTools.summarize(
                url, self.llm, 
                read_max_chars=20000, 
                summarize_chunk_size=2000,
                summarize_max_chars=2000)
            summary = summary_with_info[0]
            info = summary_with_info[1]
            if len(info) > 0:
                info = '\n'.join(info)
                messages.append(
                    SystemMessage(content=f'１つ目のURL要約中: {info}'))
            messages.append(
                SystemMessage(content=f'メインのコンテンツはなにかということを考えたうえで、適切な返答を考えてください。広告や関連記事などに気を取られないでください。'))
            messages.append(
                SystemMessage(content=f'1つ目のURLの要約: {summary}'))
            self.debug = True
            response: AIMessage = await self.llm.ainvoke(messages)
            response = response.content
            response = LangTools.sanitize_breakrow(response)
            
        return response
