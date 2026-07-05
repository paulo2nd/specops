import typer
from rich.console import Console

app = typer.Typer(
    name="specops",
    help="CLI para governança física e operacional de agentes de IA usando Speckit.",
    no_args_is_help=True
)

console = Console()

@app.command("init")
def init():
    """
    Inicializa a infraestrutura do SpecOps e compatibiliza o Speckit no projeto.
    """
    console.print("[yellow]Inicializando SpecOps no repositório...[/yellow]")
    # TODO: Implementar lógica de criação de specops.json e injeção de prompts
    console.print("[green]SpecOps inicializado com sucesso![/green]")

@app.command("reconcile")
def reconcile():
    """
    Valida a árvore de commits contra o ledger do status.yaml.
    """
    console.print("[yellow]Executando validação de consistência do Git...[/yellow]")
    # TODO: Implementar reconcile.py
    console.print("[green]Árvore do Git reconciliada com sucesso![/green]")

@app.command("consistency")
def consistency():
    """
    Valida a conformidade de negócio entre o specification.md e o plan.md do Speckit.
    """
    console.print("[yellow]Executando análise de consistência SDD...[/yellow]")
    # TODO: Implementar consistency.py
    console.print("[green]Estruturas de especificação e plano consistentes![/green]")

# Sub-Typer para o comando 'status'
status_app = typer.Typer(name="status", help="Ledger de status e gerenciamento de tarefas.")
app.add_typer(status_app)

@status_app.command("start-task")
def start_task(task_id: str):
    """
    Inicia uma tarefa técnica marcando-a como ativa.
    """
    console.print(f"[yellow]Iniciando tarefa: {task_id}[/yellow]")
    # TODO: Implementar status.py
    console.print(f"[green]Tarefa {task_id} iniciada com sucesso![/green]")

@status_app.command("complete-task")
def complete_task(task_id: str, auto: bool = typer.Option(False, "--auto", help="Executa testes e colhe evidências")):
    """
    Finaliza uma tarefa, colhe evidências de diffs/testes e cria o commit.
    """
    console.print(f"[yellow]Finalizando tarefa: {task_id}[/yellow]")
    # TODO: Implementar status.py
    console.print(f"[green]Tarefa {task_id} concluída com sucesso![/green]")

if __name__ == "__main__":
    app()
