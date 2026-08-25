"""
cache_semantico.py — Cache local de respostas por similaridade semântica

Ideia: antes de gastar uma chamada de API (chat completion), verifica se
uma pergunta PARECIDA já foi respondida antes — mesmo com palavras
diferentes — usando embeddings gerados localmente (sentence-transformers).
Se achar uma correspondência confiante, reusa a resposta salva na hora,
sem tocar na API. Só perguntas realmente novas (ou parecidas demais com
nada do que já foi respondido) vão pra API — e o resultado é salvo pra
da próxima vez.

Cresce com o uso: é o mesmo espírito da memória do barge-in — quanto mais
você conversa, mais rápido o Burn fica pras coisas que se repetem.

IMPORTANTE: perguntas que dependem de algo que muda com o tempo (hora,
data, "agora", clima, etc.) nunca são respondidas nem salvas a partir do
cache — a resposta ficaria desatualizada e errada.

Requisitos:
    pip install sentence-transformers
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime

import numpy as np
from sentence_transformers import SentenceTransformer

MODELO_PADRAO = "paraphrase-multilingual-MiniLM-L12-v2"

# qualquer pergunta que bata com isso é sempre mandada pra API e nunca
# entra (nem sai) do cache — porque a resposta certa muda com o tempo
PADROES_NAO_CACHEAVEIS = re.compile(
    r"\b(hora|horas|data de hoje|que dia|hoje|agora|amanh[ãa]|ontem|essa semana|"
    r"semana que vem|clima|previs[ãa]o do tempo|est[áa] fazendo)\b",
    flags=re.IGNORECASE,
)


class CacheSemantico:
    """
    Guarda pares pergunta/resposta por usuário (nome_usuario), cada um com
    o embedding da pergunta, num SQLite próprio (separado do burn.db, pra
    não misturar histórico de conversa com cache de respostas).
    """

    def __init__(
        self,
        caminho_banco: str = "burn_cache.db",
        limiar_similaridade: float = 0.88,
        nome_modelo: str = MODELO_PADRAO,
    ):
        self.limiar_similaridade = limiar_similaridade
        print("Carregando modelo de embeddings do cache semântico...", end="\r")
        self._modelo = SentenceTransformer(nome_modelo)
        print(" " * 50, end="\r")

        self._conn = sqlite3.connect(caminho_banco)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_respostas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_usuario TEXT,
                pergunta TEXT,
                resposta TEXT,
                embedding BLOB,
                data_hora TEXT
            )
            """
        )
        self._conn.commit()

    def _pode_cachear(self, pergunta: str) -> bool:
        return not PADROES_NAO_CACHEAVEIS.search(pergunta)

    @staticmethod
    def _similaridade_cosseno(a: np.ndarray, b: np.ndarray) -> float:
        denominador = np.linalg.norm(a) * np.linalg.norm(b)
        if denominador == 0:
            return 0.0
        return float(np.dot(a, b) / denominador)

    def buscar(self, pergunta: str, nome_usuario: str):
        """
        Retorna a resposta em cache se achar, pro mesmo usuário, uma
        pergunta antiga parecida o suficiente (acima do limiar de
        similaridade). Retorna None se não achar nada bom o bastante, ou
        se a pergunta é do tipo que nunca pode vir do cache (hora/data/etc).
        """
        if not self._pode_cachear(pergunta):
            return None

        linhas = self._conn.execute(
            "SELECT resposta, embedding FROM cache_respostas WHERE nome_usuario = ?",
            (nome_usuario,),
        ).fetchall()
        if not linhas:
            return None

        vetor_pergunta = self._modelo.encode(pergunta)

        melhor_resposta = None
        melhor_similaridade = 0.0
        for resposta_salva, embedding_bytes in linhas:
            vetor_salvo = np.frombuffer(embedding_bytes, dtype=np.float32)
            similaridade = self._similaridade_cosseno(vetor_pergunta, vetor_salvo)
            if similaridade > melhor_similaridade:
                melhor_similaridade = similaridade
                melhor_resposta = resposta_salva

        if melhor_similaridade >= self.limiar_similaridade:
            return melhor_resposta
        return None

    def salvar(self, pergunta: str, resposta: str, nome_usuario: str):
        """Guarda a pergunta (com embedding) e a resposta pra reuso futuro."""
        if not self._pode_cachear(pergunta):
            return  # pergunta dependente de tempo — nunca entra no cache

        vetor = self._modelo.encode(pergunta).astype(np.float32)
        self._conn.execute(
            """
            INSERT INTO cache_respostas (nome_usuario, pergunta, resposta, embedding, data_hora)
            VALUES (?, ?, ?, ?, ?)
            """,
            (nome_usuario, pergunta, resposta, vetor.tobytes(),
             datetime.now().strftime("%d/%m/%Y às %H:%M")),
        )
        self._conn.commit()

    def fechar(self):
        self._conn.close()