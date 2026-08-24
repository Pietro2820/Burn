# 🤖 Burn - Assistente Virtual de Produtividade (v2.0)

O Burn é um assistente virtual desenvolvido em Python que avalia o nível de disposição do usuário e sugere tarefas personalizadas. 

Diferente de scripts comuns, esta versão (v2.0) possui **memória persistente**, sendo capaz de lembrar o nome do usuário e seu último estado, criando uma experiência contínua e personalizada.

## 🚀 Funcionalidades

- ✅ **Avaliação de Disposição:** Analisa o nível de energia (baixa, média ou alta) e sugere a tarefa ideal.
- ✅ **Memória Persistente:** Utiliza banco de dados local para lembrar o nome e a última disposição do usuário.
- ✅ **Tratamento de Erros Robusto:** Impede que o programa quebre com entradas inválidas (ex: letras em vez de números).
- ✅ **Lógica de Negócio Inteligente:** Diferencia usuários novos (criação de registro) de usuários recorrentes (atualização de registro).

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3
- **Banco de Dados:** SQLite3 (Nativo do Python)
- **Controle de Versão:** Git & GitHub

## 💻 Como Rodar o Projeto

1. Clone este repositório:
   ```bash
   git clone https://github.com/Pietro2820/Burn.git