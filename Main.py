import sqlite3

# 1. Conexão e Criação da Gaveta
conn = sqlite3.connect('burn.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    ultima_disposicao INTEGER
)''')
conn.commit()

# 2. O Burn tenta lembrar de você
# (Corrigido o espaço e as aspas duplas)
cursor.execute("SELECT nome, ultima_disposicao FROM usuarios ORDER BY id DESC LIMIT 1")
usuario_salvo = cursor.fetchone()

eh_usuario_novo = False

if usuario_salvo:
    nome = usuario_salvo[0]
    ultima_disp = usuario_salvo[1]
    print(f"Olá novamente, {nome}! Bom ter você de volta.")
    print(f"Lembro que na última vez sua disposição estava como: {ultima_disp}.")
else:
    print("Olá! Eu sou o Burn, seu protótipo de assistente virtual.")
    nome = input("Para começarmos, como devo te chamar? ")
    eh_usuario_novo = True
    print(f"Prazer, {nome}! Vou te cadastrar na minha memória.")

# 3. Avaliando a disposição (Seu código original estava ótimo aqui!)
print("\nNesse projeto vamos avaliar seu nível de disposição.")
print("Digite 1- baixa, 2- média ou 3- alta.")

tarefa = "" # Criamos a variável vazia antes para evitar o "Bug 4"

while True:
    try: # Adicionei o try/except para ele não quebrar se digitar letra!
        disposicao = int(input())
        
        if disposicao == 1:
            tarefa = "organizar sua mesa de trabalho"
            break
        elif disposicao == 2:
            tarefa = "fazer uma lista de tarefas para o dia"
            break
        elif disposicao == 3:
            tarefa = "estudar um novo assunto ou habilidade"
            break
        else:
            print("Desculpe, não entendi. Digite 1, 2 ou 3.")
    except ValueError:
        print("Ei! Digite apenas números (1, 2 ou 3).")

# 4. O Pulo do Gato: Salvar no Banco (Corrigindo o Bug 3)
if eh_usuario_novo:
    # Se é novo, a gente CRIA (INSERT) já com a disposição
    cursor.execute("INSERT INTO usuarios (nome, ultima_disposicao) VALUES (?, ?)", (nome, disposicao))
else:
    # Se já existe, a gente ATUALIZA (UPDATE) a disposição
    cursor.execute("UPDATE usuarios SET ultima_disposicao = ? WHERE nome = ?", (disposicao, nome))
    
conn.commit()

print(f"\nEntendi! Sua tarefa de hoje é: {tarefa}.")
print("Estou salvando isso para o seu histórico. Boa sorte!")

conn.close()