import pulp

# Lista os solvers disponíveis no seu sistema
available_solvers = pulp.listSolvers(onlyAvailable=True)
print(available_solvers)