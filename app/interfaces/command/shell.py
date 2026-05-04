from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import CompleteStyle
from typer import Typer

from app.common.config import USER_STATE_DIR
from app.interfaces.command import typer_app


def shell_main(app: Typer):
    commands = [command.name for command in app.registered_commands if command.name]
    # for command in app.registered_commands:
    #     commands.append(command.name)

    completer = WordCompleter(commands, ignore_case=True)
    session = PromptSession(
        history=FileHistory(USER_STATE_DIR / '.history'),
        completer=completer,
        complete_style=CompleteStyle.MULTI_COLUMN,
        auto_suggest=AutoSuggestFromHistory()
    )

    while True:
        command = session.prompt('> ')
        if not command:
            continue

        if command == 'exit':
            break


if __name__ == '__main__':
    shell_main(typer_app)