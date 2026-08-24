# 🔥 Burn — Assistente Virtual com IA

Assistente de conversação em terminal, com memória persistente, entrada e saída de voz, usando a API da Groq.

## Funcionalidades

- 💬 Conversa por texto ou por voz
- 🎙️ Entrada de voz com detecção automática de silêncio (grava até você parar de falar)
- 🔊 Saída de voz natural com [edge-tts](https://github.com/rany2/edge-tts) (voz neural em português do Brasil)
- 🧠 Memória de conversas anteriores, salva em banco de dados SQLite
- ⚡ Respostas rápidas via [Groq API](https://groq.com/) (modelo `openai/gpt-oss-20b`)
- 📝 Transcrição de voz via Whisper (Groq)

## Pré-requisitos

- Python 3.10+
- Uma chave de API gratuita da Groq ([console.groq.com](https://console.groq.com))

## Instalação

1. Clone o repositório:
```bash
git clone <url-do-seu-repositorio>
cd Burn
```

2. Crie um arquivo `.env` na raiz do projeto (use o `.env.example` como base):
```
GROQ_API_KEY=sua_chave_aqui
```

3. Instale as dependências:
```bash
pip install openai python-dotenv edge-tts pygame sounddevice scipy numpy
```

## Como usar

Rode o script principal:
```bash
python Main.py
```

- Digite normalmente para conversar por texto
- Digite `voz` para ativar o modo voz — depois disso, é só apertar **Enter** para falar
- Digite qualquer texto durante o modo voz para voltar ao modo texto
- Digite `sair`, `tchau` ou `encerrar` para finalizar

## Estrutura do projeto

```
Burn/
├── Main.py              # script principal (loop de conversa)
├── testar_microfone.py  # utilitário para diagnosticar captura de áudio
├── burn.db               # banco de dados local (histórico e usuário)
├── .env                   # chave de API (não versionado)
└── .env.example          # modelo do .env
```

## Tecnologias

- [Groq API](https://groq.com/) — inferência de LLM e transcrição (Whisper)
- [edge-tts](https://github.com/rany2/edge-tts) — síntese de voz neural
- [sounddevice](https://python-sounddevice.readthedocs.io/) — captura de áudio do microfone
- SQLite — persistência de dados local

## Roadmap

- [ ] Guardar fatos específicos do usuário de forma segura (sem expor dados sensíveis à API)
- [ ] Personalidade e regras customizadas via prompt de sistema
- [ ] Ferramentas externas (acesso à internet, execução de código)