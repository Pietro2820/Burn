# 🔥 Burn v4.1 - Assistente Pessoal com IA

Um assistente virtual estilo JARVIS, desenvolvido em Python, que utiliza a API da Groq (Llama 3) para conversas inteligentes, mantendo histórico local e memória do usuário.

## 🚀 Funcionalidades
- Reconhecimento de usuário e saudação personalizada.
- Histórico de conversas salvo em banco de dados SQLite.
- Integração com API da Groq (baixa latência).
- Estrutura preparada para expansão com "Tools" (automação de tarefas).

## ⚙️ Como rodar
1. Clone o repositório.
2. Instale as dependências: `pip install openai python-dotenv`
3. Crie um arquivo `.env` e adicione sua chave: `GROQ_API_KEY=sua_chave_aqui`
4. Execute: `python burn.py`