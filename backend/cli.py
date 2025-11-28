"""CLI for LLM Council - Multi-LLM deliberation from your terminal."""

import asyncio
import sys
import json
from typing import List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.layout import Layout
from rich import box

from .council import run_full_council
from .github_client import get_github_client
from .storage.sqlite_storage import SQLiteStorageBackend
from .storage.models import Repository, ConversationRepository
from .logging_config import configure_logging

console = Console()


def print_stage1(stage1_results: List[dict], show_costs: bool = True):
    """Print Stage 1 results with rich formatting."""
    console.print("\n[bold cyan]━━━ Stage 1: Individual Responses ━━━[/bold cyan]\n")

    for i, result in enumerate(stage1_results, 1):
        model_name = result['model'].split('/')[-1] if '/' in result['model'] else result['model']

        # Create panel for each model's response
        panel = Panel(
            Markdown(result['response']),
            title=f"[bold]{model_name}[/bold]",
            border_style="blue",
            box=box.ROUNDED,
        )
        console.print(panel)

        if show_costs and 'cost_usd' in result:
            console.print(f"  [dim]Cost: ${result['cost_usd']:.6f}[/dim]\n")


def print_stage2(stage2_results: List[dict], label_to_model: dict, aggregate_rankings: List[dict], show_costs: bool = True):
    """Print Stage 2 results with rich formatting."""
    console.print("\n[bold magenta]━━━ Stage 2: Peer Rankings ━━━[/bold magenta]\n")

    # Show each model's evaluation
    for result in stage2_results:
        model_name = result['model'].split('/')[-1] if '/' in result['model'] else result['model']

        panel = Panel(
            Markdown(result['evaluation']),
            title=f"[bold]{model_name}'s Evaluation[/bold]",
            border_style="magenta",
            box=box.ROUNDED,
        )
        console.print(panel)

        if 'parsed_ranking' in result and result['parsed_ranking']:
            console.print(f"  [dim]Ranking: {' > '.join(result['parsed_ranking'])}[/dim]")

        if show_costs and 'cost_usd' in result:
            console.print(f"  [dim]Cost: ${result['cost_usd']:.6f}[/dim]\n")

    # Show aggregate rankings table
    if aggregate_rankings:
        console.print("\n[bold]Aggregate Rankings:[/bold]")
        table = Table(box=box.SIMPLE)
        table.add_column("Rank", style="cyan", justify="center")
        table.add_column("Model", style="bold")
        table.add_column("Avg Position", justify="right")
        table.add_column("Votes", justify="center")

        for i, ranking in enumerate(aggregate_rankings, 1):
            model_display = ranking['model'].split('/')[-1] if '/' in ranking['model'] else ranking['model']
            table.add_row(
                str(i),
                model_display,
                f"{ranking['average_rank']:.2f}",
                str(ranking['rankings_count'])
            )

        console.print(table)
        console.print()


def print_stage3(stage3_result: dict, show_costs: bool = True):
    """Print Stage 3 results with rich formatting."""
    console.print("\n[bold green]━━━ Stage 3: Final Council Answer ━━━[/bold green]\n")

    chairman = stage3_result['model'].split('/')[-1] if '/' in stage3_result['model'] else stage3_result['model']

    panel = Panel(
        Markdown(stage3_result['response']),
        title=f"[bold]Chairman: {chairman}[/bold]",
        border_style="green",
        box=box.DOUBLE,
    )
    console.print(panel)

    if show_costs and 'cost_usd' in stage3_result:
        console.print(f"  [dim]Cost: ${stage3_result['cost_usd']:.6f}[/dim]\n")


def print_costs(metadata: dict):
    """Print cost summary."""
    if 'costs' not in metadata:
        return

    costs = metadata['costs']

    table = Table(title="[bold]💰 Cost Breakdown[/bold]", box=box.ROUNDED)
    table.add_column("Stage", style="cyan")
    table.add_column("Cost (USD)", justify="right", style="yellow")

    table.add_row("Stage 1 (Responses)", f"${costs['stage1_usd']:.6f}")
    table.add_row("Stage 2 (Rankings)", f"${costs['stage2_usd']:.6f}")
    table.add_row("Stage 3 (Synthesis)", f"${costs['stage3_usd']:.6f}")
    table.add_row("[bold]Total[/bold]", f"[bold]${costs['total_usd']:.6f}[/bold]")

    console.print(table)
    console.print()


async def run_council_with_progress(question: str, repo_context: Optional[str] = None, show_progress: bool = True):
    """Run council with live progress updates."""

    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Running 3-stage council process...", total=3)

            # Run the council
            stage1, stage2, stage3, metadata = await run_full_council(question, repo_context)

            progress.update(task, completed=3)
    else:
        stage1, stage2, stage3, metadata = await run_full_council(question, repo_context)

    return stage1, stage2, stage3, metadata


def build_repo_context(repos: List[str]) -> Optional[str]:
    """Build repository context from GitHub repo names."""
    if not repos:
        return None

    github_client = get_github_client()
    if not github_client.is_available():
        console.print("[yellow]Warning: GITHUB_TOKEN not configured. Skipping repo context.[/yellow]")
        return None

    # Try to load from database first, then fetch if needed
    backend = SQLiteStorageBackend()
    session = backend.SessionLocal()

    repo_summaries = []

    try:
        for repo_full_name in repos:
            with console.status(f"[cyan]Fetching {repo_full_name}..."):
                # Check if repo exists in DB
                repo_db = session.query(Repository).filter_by(full_name=repo_full_name).first()

                if repo_db and repo_db.summary:
                    repo_summaries.append(repo_db.summary)
                    console.print(f"[green]✓[/green] Loaded {repo_full_name} from cache")
                else:
                    # Fetch from GitHub
                    repo_metadata = github_client.get_repo(repo_full_name)
                    if not repo_metadata:
                        console.print(f"[red]✗[/red] Could not find {repo_full_name}")
                        continue

                    tree = github_client.get_repo_tree(repo_full_name)
                    key_files = github_client.get_key_files(repo_full_name)
                    summary = github_client.generate_repo_summary(repo_metadata, key_files, tree)

                    # Cache in database
                    if not repo_db:
                        repo_db = Repository(
                            full_name=repo_metadata['full_name'],
                            name=repo_metadata['name'],
                            description=repo_metadata.get('description'),
                            language=repo_metadata.get('language'),
                            default_branch=repo_metadata.get('default_branch', 'main'),
                            stars=repo_metadata.get('stars', 0),
                            tree_structure=tree,
                            key_files=key_files,
                            summary=summary
                        )
                        session.add(repo_db)
                        session.commit()

                    repo_summaries.append(summary)
                    console.print(f"[green]✓[/green] Fetched and cached {repo_full_name}")

        if repo_summaries:
            return "# Repository Context\n\n" + "\n\n---\n\n".join(repo_summaries)

        return None

    finally:
        session.close()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """LLM Council - Multi-LLM deliberation from your terminal.

    A transparent, collaborative decision-making system where multiple LLMs
    deliberate through 3 stages: individual responses, peer rankings, and
    final synthesis.
    """
    # Configure logging (suppress for CLI)
    configure_logging(log_level="ERROR")


@main.command()
@click.argument('question', required=False)
@click.option('--repo', '-r', multiple=True, help='GitHub repository (owner/repo). Can be used multiple times.')
@click.option('--format', '-f', type=click.Choice(['text', 'json', 'markdown']), default='text', help='Output format')
@click.option('--no-costs', is_flag=True, help='Hide cost information')
@click.option('--stage', type=click.Choice(['1', '2', '3', 'all']), default='all', help='Show only specific stage')
@click.option('--stdin', is_flag=True, help='Read question from stdin')
def ask(question, repo, format, no_costs, stage, stdin):
    """Ask the council a question.

    Examples:
        llm-council ask "What is the best Python web framework?"
        llm-council ask "Review this architecture" --repo myorg/myapp
        llm-council ask "Analyze these projects" -r user/repo1 -r user/repo2
        echo "Explain async/await" | llm-council ask --stdin
        llm-council ask "..." --format json > output.json
    """

    # Get question from stdin if requested
    if stdin:
        question = sys.stdin.read().strip()

    if not question:
        console.print("[red]Error: Please provide a question[/red]")
        console.print("Usage: llm-council ask \"Your question here\"")
        console.print("   or: echo \"Your question\" | llm-council ask --stdin")
        sys.exit(1)

    # Build repo context if repos specified
    repo_context = None
    if repo:
        repo_context = build_repo_context(list(repo))
        if repo_context:
            console.print(f"[green]📚 Loaded {len(repo)} repositories into context[/green]\n")

    # Show question
    console.print(Panel(
        question,
        title="[bold]Question[/bold]",
        border_style="yellow",
        box=box.ROUNDED
    ))
    console.print()

    # Run council
    show_progress = format == 'text'
    stage1, stage2, stage3, metadata = asyncio.run(
        run_council_with_progress(question, repo_context, show_progress=show_progress)
    )

    # Output based on format
    if format == 'json':
        output = {
            'question': question,
            'stage1': stage1,
            'stage2': stage2,
            'stage3': stage3,
            'metadata': metadata
        }
        console.print(json.dumps(output, indent=2))

    elif format == 'markdown':
        # Output as markdown
        print(f"# Question\n\n{question}\n")
        print(f"## Stage 1: Individual Responses\n")
        for result in stage1:
            print(f"### {result['model']}\n")
            print(f"{result['response']}\n")
        print(f"## Stage 2: Peer Rankings\n")
        for result in stage2:
            print(f"### {result['model']}\n")
            print(f"{result['evaluation']}\n")
        print(f"## Stage 3: Final Answer\n")
        print(f"{stage3['response']}\n")

    else:  # text format
        show_costs_flag = not no_costs

        # Show stages based on --stage flag
        if stage in ['1', 'all']:
            print_stage1(stage1, show_costs=show_costs_flag)

        if stage in ['2', 'all']:
            print_stage2(stage2, metadata.get('label_to_model', {}),
                        metadata.get('aggregate_rankings', []), show_costs=show_costs_flag)

        if stage in ['3', 'all']:
            print_stage3(stage3, show_costs=show_costs_flag)

        # Show cost summary
        if show_costs_flag and stage == 'all':
            print_costs(metadata)


@main.command()
def version():
    """Show version information."""
    console.print("[bold cyan]LLM Council[/bold cyan] v0.1.0")
    console.print("Multi-LLM deliberation system")
    console.print("\nFeatures:")
    console.print("  • 3-stage deliberation process")
    console.print("  • Anonymous peer ranking")
    console.print("  • GitHub repository context")
    console.print("  • Cost tracking")
    console.print("  • Web UI + CLI")


if __name__ == '__main__':
    main()
