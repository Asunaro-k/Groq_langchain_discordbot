discord-bot

## docker compose 起動方法
`.env`を作成し、以下のように環境変数を記述する。
```.env
DISCORD_API_KEY=value
GROQ_API_KEY=value
OLLAMA_API_KEY=value
OLLAMA_URL=https://target/ollama/api
```

`googleconsoleのjson`を作成し、フォルダに入れる。

起動する。

```bash
docker compose up -d
```
