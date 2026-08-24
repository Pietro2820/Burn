```markdown
# 🤖 Burn - Assistente Virtual de Produtividade (v3.0)

O Burn é um assistente virtual que eu criei em Python. Ele avalia seu nível de disposição e sugere tarefas adequadas.

O diferencial dele é que ele **lembra de você**. Diferente de scripts comuns que esquecem tudo quando fecham, o Burn usa banco de dados pra guardar seu nome, sua última disposição e um histórico completo de todas as suas interações.

## 🚀 O que ele faz

- Avalia sua disposição (baixa, média ou alta) e sugere a tarefa ideal
- Lembra seu nome e sua última disposição
- Mantém um histórico completo de todas as interações com data e hora
- Mostra quantos registros você tem no total
- Lista todos os registros numerados em ordem cronológica
- Não quebra se você digitar letra em vez de número (tratamento de erro)
- Diferencia usuários novos de usuários recorrentes

## 🛠️ Tecnologias que usei

- **Python 3** (linguagem principal)
- **SQLite3** (banco de dados nativo do Python)
- **datetime** (pra trabalhar com datas e horas)
- **Git & GitHub** (controle de versão)

## 💻 Como rodar

1. Clona o repositório:
   ```bash
   git clone https://github.com/Pietro2820/Burn.git
   ```
2. Entra na pasta:
   ```bash
   cd Burn
   ```
3. Roda o script:
   ```bash
   python burn.py
   ```

O arquivo `burn.db` (banco de dados) é criado automaticamente na primeira execução.

## 📊 Como o banco de dados funciona

O Burn usa duas tabelas separadas por responsabilidade:

**Tabela `usuarios`** (guarda quem é você):
- `id`: identificador único
- `nome`: seu nome
- `ultima_disposicao`: última disposição registrada

**Tabela `historico_burn`** (guarda todas as interações):
- `id`: identificador único
- `nome_usuario`: seu nome
- `data_hora`: quando foi usado
- `disposicao`: nível (1, 2 ou 3)
- `tarefa_sugerida`: o que o Burn sugeriu

## 🧠 Conceitos de Backend que apliquei

- **Persistência de dados** com SQLite (banco local sem precisar de servidor)
- **Modelagem relacional** (múltiplas tabelas com propósitos diferentes)
- **Operações CRUD** (INSERT, SELECT, UPDATE com commit)
- **Consultas eficientes** (ORDER BY, LIMIT, WHERE)
- **Tratamento de erros** (try/except pra não quebrar com entrada inválida)
- **Manipulação de datas** (datetime e strftime)

## 📝 Histórico de versões

- **v1.0**: Assistente básico com avaliação de disposição e validação de entrada
- **v2.0**: Adicionei persistência de dados com SQLite (lembra o nome do usuário)
- **v3.0**: Implementei histórico completo com múltiplas tabelas e contagem total

## 🔮 Próximos passos

- [ ] **v4.0**: Cardápio de tarefas elaboradas para cada nível de disposição
- [ ] **v5.0**: Transformar em API REST com FastAPI ou Flask
- [ ] **v6.0**: Integrar com IA (OpenAI) pra respostas em linguagem natural
- [ ] **v7.0**: Interface web ou desktop

---

*Desenvolvido por [Pietro](https://github.com/Pietro2820) como parte do meu aprendizado em Backend.*
```