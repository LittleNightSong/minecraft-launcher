import typer.cli

typer

def my_function(name, id, *args:str):
    print(name)
    print(id)
    print(args)