import sqlite3
from datetime import datetime

conn = sqlite3.connect('burn.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    ultima_disposicao INTEGER
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS historico_burn (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_usuario TEXT,
    data_hora TEXT,
    disposicao INTEGER,
    tarefa_sugerida TEXT
)''')
conn.commit()

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

print("\nNesse projeto vamos avaliar seu nível de disposição.")
print("Digite 1- baixa, 2- média ou 3- alta.")

tarefa = ""

while True:
    try:
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

if eh_usuario_novo:
    cursor.execute("INSERT INTO usuarios (nome, ultima_disposicao) VALUES (?, ?)", (nome, disposicao))
else:
    cursor.execute("UPDATE usuarios SET ultima_disposicao = ? WHERE nome = ?", (disposicao, nome))

hoje_agora = datetime.now().strftime("%d/%m/%Y às %H:%M")

cursor.execute('''
    INSERT INTO historico_burn (nome_usuario, data_hora, disposicao, tarefa_sugerida) 
    VALUES (?, ?, ?, ?)
''', (nome, hoje_agora, disposicao, tarefa))

conn.commit()

print(f"\nEntendi! Sua tarefa de hoje é: {tarefa}.")
print(f"Registrei isso no meu diário em: {hoje_agora}.")

print("\n" + "="*60)
print("📊 SEU HISTÓRICO COMPLETO")
print("="*60)

cursor.execute('''
    SELECT data_hora, disposicao, tarefa_sugerida 
    FROM historico_burn 
    WHERE nome_usuario = ? 
    ORDER BY id ASC
''', (nome,))

historico = cursor.fetchall()

total_registros = len(historico)
print(f"\n{nome}, você tem {total_registros} registro(s) no total:\n")

for i, registro in enumerate(historico, 1):
    print(f"#{i} | {registro[0]} | Disposição: {registro[1]} | Tarefa: {registro[2]}")

print("\n" + "="*60)
print("Burn desligando... Até a próxima!")
conn.close()