# 🧠 Diário de Aprendizado - Burn v2.0

Nesta versão, o projeto evoluiu de um script simples para um sistema com **persistência de dados**. Aqui estão os principais conceitos de Backend que aprendi e apliquei:

### 1. Persistência de Dados com SQLite (`sqlite3`)
Aprendi que um programa sem banco de dados "esquece" tudo quando é fechado. Com o módulo nativo `sqlite3` do Python, criei um arquivo local (`burn.db`) que atua como a memória de longo prazo do assistente, sem precisar instalar servidores complexos.

### 2. Modelagem de Banco de Dados (`CREATE TABLE`)
Entendi a importância de criar a estrutura de dados (a "gaveta") de forma segura, usando `CREATE TABLE IF NOT EXISTS`. Isso garante que o programa possa ser rodado múltiplas vezes sem dar erro de "tabela já existe".

### 3. A Arte da Busca (`SELECT` + `ORDER BY` + `LIMIT`)
Aprendi a fazer consultas inteligentes. Em vez de baixar todos os dados, usei `ORDER BY id DESC LIMIT 1` para buscar apenas o **último registro** salvo, identificando rapidamente se o usuário já é conhecido pelo sistema.

### 4. A Regra de Ouro: INSERT vs UPDATE
Esta foi a lição mais valiosa:
- **`INSERT`**: Usado para **criar** um novo registro no banco (ex: quando o usuário usa o Burn pela primeira vez).
- **`UPDATE`**: Usado para **modificar** um registro que já existe (ex: quando o usuário volta e só precisa atualizar sua disposição do dia).
Saber a diferença e aplicar a lógica correta (`if eh_usuario_novo`) evitou bugs críticos de duplicidade de dados.

### 5. Robustez e Tratamento de Erros (`try / except`)
Aprendi a proteger o sistema contra entradas inválidas. O bloco `try / except ValueError` impede que o programa quebre (crash) se o usuário digitar uma letra em vez de um número, guiando-o gentilmente a tentar novamente.