import sqlite3
from datetime import datetime
import os
import tempfile
import wave
import asyncio
import uuid

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
import edge_tts
import pygame
import sounddevice as sd
from scipy.io.wavfile import write as write_wav

# Carrega as variáveis do arquivo .env
load_dotenv()

# ==========================================
# BURN v5.0 - Assistente com IA + Voz
# ==========================================

# 1. Cliente Groq (mesma chave usada pro chat E pro Whisper)
client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

# 2. Engine de voz (TTS) - edge-tts, voz neural natural em português do Brasil
pygame.mixer.init()
VOZ_BURN = "pt-BR-AntonioNeural"  # outras opções: pt-BR-FranciscaNeural (feminina)

async def _gerar_audio_fala(texto, caminho_saida):
    comunicador = edge_tts.Communicate(texto, voice=VOZ_BURN)
    await comunicador.save(caminho_saida)

def falar(texto):
    """Faz o Burn falar em voz alta usando uma voz neural (edge-tts)."""
    print(f"Burn: {texto}\n")

    # nome único por fala, pra evitar 'Permission denied' no Windows
    # (o pygame mantém o arquivo anterior travado por um tempo depois de tocar)
    nome_arquivo = f"burn_fala_{uuid.uuid4().hex}.mp3"
    caminho_audio = os.path.join(tempfile.gettempdir(), nome_arquivo)

    asyncio.run(_gerar_audio_fala(texto, caminho_audio))

    pygame.mixer.music.load(caminho_audio)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    pygame.mixer.music.unload()  # libera o arquivo pra poder ser apagado
    try:
        os.remove(caminho_audio)
    except OSError:
        pass  # se não conseguir apagar, não é grave, só sobra lixo no temp

def gravar_audio(taxa_amostragem=16000, limiar_silencio=1400, duracao_silencio=1.2,
                  duracao_maxima=20, tamanho_bloco=0.1):
    """
    Grava áudio do microfone até detectar silêncio (ou até atingir a duração máxima).

    - limiar_silencio: volume abaixo do qual é considerado "silêncio" (ajuste conforme seu mic)
    - duracao_silencio: quantos segundos de silêncio seguido pra parar de gravar
    - duracao_maxima: teto de segurança, pra nunca gravar pra sempre
    - tamanho_bloco: tamanho de cada pedaço de áudio analisado, em segundos
    """
    print("🎙️  Pode falar... (a gravação para sozinha quando você ficar quieto)")

    blocos = []
    blocos_silencio_seguidos = 0
    blocos_para_parar = int(duracao_silencio / tamanho_bloco)
    blocos_maximos = int(duracao_maxima / tamanho_bloco)
    frames_por_bloco = int(tamanho_bloco * taxa_amostragem)

    stream = sd.InputStream(samplerate=taxa_amostragem, channels=1, dtype='int16')
    stream.start()

    falou_alguma_coisa = False

    for _ in range(blocos_maximos):
        bloco, _ = stream.read(frames_por_bloco)
        blocos.append(bloco.copy())

        volume = np.abs(bloco).mean()

        if volume > limiar_silencio:
            falou_alguma_coisa = True
            blocos_silencio_seguidos = 0
        else:
            blocos_silencio_seguidos += 1

        # só para por silêncio depois que a pessoa já começou a falar
        if falou_alguma_coisa and blocos_silencio_seguidos >= blocos_para_parar:
            break

    stream.stop()
    stream.close()
    print("✅ Gravação concluída.")

    audio_completo = np.concatenate(blocos, axis=0)
    caminho_temp = os.path.join(tempfile.gettempdir(), "burn_audio.wav")
    write_wav(caminho_temp, taxa_amostragem, audio_completo)
    return caminho_temp

def transcrever_audio(caminho_arquivo):
    """Manda o áudio pro Whisper da Groq e retorna o texto transcrito."""
    with open(caminho_arquivo, "rb") as arquivo_audio:
        transcricao = client.audio.transcriptions.create(
            file=arquivo_audio,
            model="whisper-large-v3-turbo",
            language="pt",
            response_format="text"
        )
    return transcricao.strip() if isinstance(transcricao, str) else transcricao.text.strip()

# 3. Conexão com o banco de dados
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

# 4. Verifica usuário
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
print("🔥 MODO CONVERSA ATIVADO (voz + texto)")
print("Digite 'sair' para encerrar, ou 'voz' para falar com o Burn.")
print("="*60 + "\n")

# 5. Loop de conversa
modo_voz = False

while True:
    if modo_voz:
        entrada = input("🎙️  (modo voz ativo) Enter pra falar, ou digite algo pra voltar ao texto: ").strip()
    else:
        entrada = input("Você (ou 'voz' pra ativar o modo voz): ").strip()

    if entrada.lower() in ['sair', 'tchau', 'encerrar']:
        falar("Até mais! Foi ótimo conversar com você.")
        break

    if not modo_voz and entrada.lower() == 'voz':
        modo_voz = True
        print("🔊 Modo voz ativado! Aperte Enter quando quiser falar.")
        continue

    if modo_voz and entrada == '':
        try:
            caminho_audio = gravar_audio()
            mensagem_usuario = transcrever_audio(caminho_audio)
            print(f"Você disse: {mensagem_usuario}")
        except Exception as e:
            print(f"🚨 Erro ao gravar/transcrever áudio: {e}")
            continue
    elif modo_voz and entrada != '':
        # digitou algo em texto -> sai do modo voz e usa essa mensagem
        modo_voz = False
        print("⌨️  Voltando ao modo texto.")
        mensagem_usuario = entrada
    else:
        mensagem_usuario = entrada

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

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": contexto},
                {"role": "user", "content": mensagem_usuario}
            ],
            temperature=0.7,
            max_tokens=500
        )

        resposta_burn = response.choices[0].message.content
        print(" " * 30, end="\r")

        # Salva no banco
        hoje_agora = datetime.now().strftime("%d/%m/%Y às %H:%M")
        cursor.execute('''
            INSERT INTO historico_burn
            (nome_usuario, data_hora, mensagem_usuario, resposta_burn)
            VALUES (?, ?, ?, ?)
        ''', (nome, hoje_agora, mensagem_usuario, resposta_burn))
        conn.commit()

        falar(resposta_burn)

    except Exception as e:
        print(" " * 30, end="\r")
        print("\n" + "="*60)
        print("🚨 ERRO NA API")
        print(f"Detalhe: {e}")
        print("Dica: Verifique se o arquivo .env está na pasta e tem a chave GROQ_API_KEY")
        print("="*60 + "\n")
        break

conn.close()