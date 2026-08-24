import sqlite3
from datetime import datetime
import os
from dotenv import load_dotenv
from openai import OpenAI

# Carrega as variáveis do arquivo .env
load_dotenv()

# ==========================================
# BURN v4.0 - Assistente com IA (Estrutura Profissional)
# ==========================================

# 1. SUA ESTRUTURA PREFERIDA (Segura e com base_url da Groq)
client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
    
# 2. Conexão com o banco de dados
conn = sqlite3.connect('burn.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS historico_burn (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_usuario TEXT,
    data_hora TEXT,
    mensagem_usuario TEXT,
    resposta_burn TEXT
)''')
conn.commit()

# 3. Verifica usuário
cursor.execute("SELECT nome FROM usuarios ORDER BY id DESC LIMIT 1")
usuario_salvo = cursor.fetchone()

if usuario_salvo:
    nome = usuario_salvo[0]
    print(f"Olá novamente, {nome}! Sou o Burn, seu assistente com IA. 🤖")
else:
    print("Olá! Eu sou o Burn, seu novo assistente virtual com Inteligência Artificial.")
    nome = input("Como devo te chamar? ")
    cursor.execute("INSERT INTO usuarios (nome) VALUES (?)", (nome,))
    conn.commit()
    print(f"Prazer, {nome}! Vou lembrar de você a partir de agora. 💾")

print("\n" + "="*60)
print("🔥 MODO CONVERSA ATIVADO")
print("Digite 'sair' para encerrar.")
print("="*60 + "\n")

# 4. Loop de conversa
while True:
    mensagem_usuario = input("Você: ").strip()
    
    if mensagem_usuario.lower() in ['sair', 'tchau', 'encerrar']:
        print("\nBurn: Até mais! Foi ótimo conversar com você. 👋")
        break
    
    if not mensagem_usuario:
        continue

    # Busca histórico
    cursor.execute('''
        SELECT mensagem_usuario, resposta_burn 
        FROM historico_burn 
        WHERE nome_usuario = ? 
        ORDER BY id DESC 
        LIMIT 5
    ''', (nome,))
    historico_recente = cursor.fetchall()
    
    # Monta contexto
    contexto = f"Você é o Burn, um assistente virtual amigável e direto. O usuário se chama {nome}."
    if historico_recente:
        contexto += "\n\nHistórico recente:\n"
        for msg_user, resp_burn in reversed(historico_recente):
            contexto += f"Você: {msg_user}\nBurn: {resp_burn}\n"
    
    try:
        print("Burn está pensando...", end="\r")
        
        # ✅ AQUI USAMOS O MÉTODO GARANTIDO DA GROQ (chat.completions)
        # E um modelo que sabemos que está ativo e gratuito.
        response = client.chat.completions.create(
    model="openai/gpt-oss-20b",   # <- modelo atualizado
    messages=[
        {"role": "system", "content": contexto},
        {"role": "user", "content": mensagem_usuario}
    ],
    temperature=0.7,
    max_tokens=500
)
        
        # Extrai a resposta (equivalente ao output_text que você queria)
        resposta_burn = response.choices[0].message.content
        print(" " * 30, end="\r") # Limpa o "pensando"
        
        # Salva no banco
        hoje_agora = datetime.now().strftime("%d/%m/%Y às %H:%M")
        cursor.execute('''
            INSERT INTO historico_burn 
            (nome_usuario, data_hora, mensagem_usuario, resposta_burn) 
            VALUES (?, ?, ?, ?)
        ''', (nome, hoje_agora, mensagem_usuario, resposta_burn))
        conn.commit()
        
        print(f"Burn: {resposta_burn}\n")
        
    except Exception as e:
        print(" " * 30, end="\r")
        print("\n" + "="*60)
        print("🚨 ERRO NA API")
        print(f"Detalhe: {e}")
        print("Dica: Verifique se o arquivo .env está na pasta e tem a chave GROQ_API_KEY")
        print("="*60 + "\n")
        break

conn.close()