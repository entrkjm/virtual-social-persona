import game_sdk
import inspect

print("Modules in game_sdk:")
print(dir(game_sdk))

try:
    from game_sdk import Agent, Worker
    print("\nAgent class found.")
    print(inspect.signature(Agent.__init__))
except ImportError:
    print("\nCould not import Agent or Worker directly.")
