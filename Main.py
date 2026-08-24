print ("Olá sou Burn, seu primeiro prototipo de assistente virtual. Vamos começar a contruir esse primero projeto")

print ("Para começar, me diga seu nome:")
nome = input()
print ("Olá, " + nome + "! Vamos começar!")

print ("Nesse primeiro projeto vamos avaliar seu nível de disposição para te dar uma tarefa condigente a sua disposição. Para isso, me diga se está 1- baixa, 2- média ou 3- alta, qual é o seu nível de disposição hoje?")

disposicao = int(input())


while True:
    if disposicao == 1:
        print ("Entendi, você está com baixa disposição. Então vou te dar uma tarefa mais leve para começar. Que tal organizar sua mesa de trabalho?")
        break
    elif disposicao == 2:
        print ("Ótimo, você está com disposição média. Então vou te dar uma tarefa moderada. Que tal fazer uma lista de tarefas para o dia?")
        break
    elif disposicao == 3:
        print ("Excelente, você está com alta disposição! Então vou te dar uma tarefa mais desafiadora. Que tal começar a estudar um novo assunto ou habilidade?")
        break
    else:
        print ("Desculpe, não entendi sua resposta. Por favor, me diga se está 1- baixa, 2- média ou 3- alta, qual é o seu nível de disposição hoje?")
        disposicao = int(input())


print ("Espero que você consiga realizar a tarefa com sucesso! Lembre-se de que estou aqui para te ajudar sempre que precisar. Boa sorte!")