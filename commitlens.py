#!/usr/bin/env python3
"""
CommitLens - Git Change Visualization Tool

A command-line tool that compares git branches and provides a natural language explanation
of the differences using OpenAI's GPT models.
"""

import os
import sys
import subprocess
import argparse
import tiktoken
from pathlib import Path
from dotenv import load_dotenv
import textwrap
import json

# Try to import rich for Markdown rendering
try:
    from rich.console import Console
    from rich.markdown import Markdown
    rich_available = True
except ImportError:
    rich_available = False

# Define config paths
HOME_DIR = Path.home()
CONFIG_DIR = HOME_DIR / ".commitlens"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Load environment variables from multiple locations
def load_environment():
    """Load environment variables from multiple locations in order of precedence."""
    # 1. Check environment variables first (highest precedence)
    if "OPENAI_API_KEY" in os.environ:
        return True
    
    # 2. Check for config file in user's home directory
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                if "OPENAI_API_KEY" in config:
                    os.environ["OPENAI_API_KEY"] = config["OPENAI_API_KEY"]
                    if "OPENAI_MODEL" in config:
                        os.environ["OPENAI_MODEL"] = config["OPENAI_MODEL"]
                    return True
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Error reading config file: {e}")
    
    # 3. Check for .env in script directory
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    env_path = script_dir / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        if "OPENAI_API_KEY" in os.environ:
            return True
    
    # 4. Check for .env in current directory
    current_dir_env = Path('.') / '.env'
    if current_dir_env.exists():
        load_dotenv(dotenv_path=current_dir_env)
        if "OPENAI_API_KEY" in os.environ:
            return True
    
    return False

# Function to set up configuration
def setup_config(api_key=None, model=None):
    """Set up the configuration file in the user's home directory."""
    # Create config directory if it doesn't exist
    CONFIG_DIR.mkdir(exist_ok=True)
    
    # Load existing config if it exists
    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            config = {}
    
    # Update config with new values
    if api_key:
        config["OPENAI_API_KEY"] = api_key
    if model:
        config["OPENAI_MODEL"] = model
    
    # Save config
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
    
    # Set permissions to restrict access
    os.chmod(CONFIG_FILE, 0o600)
    
    return True

# Initialize OpenAI client if API key is available
client = None
def init_openai_client():
    global client
    if "OPENAI_API_KEY" not in os.environ:
        return False
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        return True
    except ImportError:
        return False

def is_git_repository():
    """Check if the current directory is a git repository."""
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], 
                      check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

def get_current_branch():
    """Get the name of the current git branch."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return result.stdout.strip()

def branch_exists(branch_name):
    """Check if a branch exists in the repository."""
    result = subprocess.run(
        ["git", "branch", "--list", branch_name],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return bool(result.stdout.strip())

def get_git_diff(base_branch, compare_branch):
    """Get the git diff between two branches."""
    try:
        result = subprocess.run(
            ["git", "diff", f"{base_branch}...{compare_branch}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting diff: {e.stderr}")
        sys.exit(1)

def get_diff_stats(base_branch, compare_branch):
    """Get statistics about the diff between two branches."""
    stats = {}
    
    # Get number of commits
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{base_branch}...{compare_branch}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stats["commits"] = int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        stats["commits"] = 0
    
    # Get number of files changed and lines added/deleted
    try:
        result = subprocess.run(
            ["git", "diff", "--shortstat", f"{base_branch}...{compare_branch}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        shortstat = result.stdout.strip()
        
        # Parse the shortstat output
        stats["files"] = 0
        stats["insertions"] = 0
        stats["deletions"] = 0
        
        if shortstat:
            parts = shortstat.split(", ")
            for part in parts:
                if "file" in part:
                    stats["files"] = int(part.split()[0])
                elif "insertion" in part:
                    stats["insertions"] = int(part.split()[0])
                elif "deletion" in part:
                    stats["deletions"] = int(part.split()[0])
    except subprocess.CalledProcessError:
        pass
    
    return stats

def count_tokens(text):
    """Count the number of tokens in the text using tiktoken."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
        return len(encoding.encode(text))
    except Exception as e:
        print(f"Warning: Could not count tokens: {e}")
        return -1  # Return -1 to indicate error

def get_natural_language_diff(diff_text):
    """Get a natural language description of the diff using OpenAI."""
    if client is None:
        if not init_openai_client():
            print("Error: OpenAI API key not set. Please set OPENAI_API_KEY in your environment or .env file.")
            print("Alternatively, use the --raw option to see the raw diff without using OpenAI.")
            sys.exit(1)
    
    try:
        # Get the model from environment variable or use default
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        
        # Create a more structured and comprehensive system prompt
        system_prompt = """You are an expert git diff analyzer that creates clear, detailed, and scannable summaries.

Your task is to analyze git diffs and produce summaries that are:
1. Immediately understandable at a glance
2. Organized by functional areas or components
3. Detailed enough to understand the scope and impact of changes
4. Formatted for maximum readability with clear hierarchy

Follow these guidelines:
- Start with a concise but informative overview sentence
- Group changes by component, feature, or type of change
- Use bullet points with clear indentation hierarchy
- Highlight critical changes that affect functionality, performance, or security
- Include specific details like function names, file paths, and parameter changes when relevant
- Mention potential impacts or considerations for important changes
- Ignore trivial changes like whitespace, formatting, or minor comments

Format your response with Markdown for readability:
- Use ## for main section headings
- Use bold **text** for important components or features
- Use bullet hierarchies (•, -, *) for different levels of detail
- Use code formatting for function names, variables, and paths"""

        # Create a more detailed user prompt
        user_prompt = f"""Analyze this git diff and provide a detailed, scannable summary:

{diff_text}

Structure your response as follows:

## Overview
A 1-2 sentence summary of the overall changes

## Key Changes
Organized by component/feature with hierarchical bullets:
• **Component/Feature Name**:
  - Specific change with technical details
  - Another specific change
  
• **Another Component/Feature**:
  - Changes with relevant details

## Technical Details
- Important implementation details
- Potential impacts or considerations
- Any notable refactoring or architectural changes

Make your summary comprehensive but scannable, with enough detail to understand the changes without reading the full diff."""
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent, focused responses
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        sys.exit(1)

def get_commit_list(base_branch, compare_branch):
    """Get a list of commits between two branches."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"{base_branch}...{compare_branch}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except subprocess.CalledProcessError as e:
        print(f"Error getting commit list: {e.stderr}")
        return []

def get_commit_list_from_hash(commit_hash):
    """Get a list of commits from a specific commit to HEAD, including the starting commit."""
    try:
        # First get the commit itself
        start_commit_result = subprocess.run(
            ["git", "log", "--oneline", "-n", "1", commit_hash],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        start_commit = start_commit_result.stdout.strip()
        
        # Then get all commits from the commit to HEAD (exclusive of the start commit)
        result = subprocess.run(
            ["git", "log", "--oneline", f"{commit_hash}..HEAD"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        later_commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        # Combine the lists with the start commit first (chronologically last)
        all_commits = later_commits
        if start_commit:
            all_commits.append(start_commit)
            
        # Reverse to get chronological order (oldest first)
        all_commits.reverse()
        
        return all_commits
    except subprocess.CalledProcessError as e:
        print(f"Error getting commit list: {e.stderr}")
        return []

def compare_branches(base_branch, compare_branch, raw=False, preview=False):
    """Compare two branches and return a description of the differences."""
    print(f"Comparing {compare_branch} to {base_branch}...")
    
    # Get the diff
    diff_text = get_git_diff(base_branch, compare_branch)
    
    if not diff_text:
        return "No differences found between the branches."
    
    # Get stats for both raw and preview modes
    stats = get_diff_stats(base_branch, compare_branch)
    stats_text = f"\n\nSummary:\n"
    stats_text += f"- {stats['commits']} commit{'s' if stats['commits'] != 1 else ''}\n"
    stats_text += f"- {stats['files']} file{'s' if stats['files'] != 1 else ''} changed\n"
    stats_text += f"- {stats['insertions']} insertion{'s' if stats['insertions'] != 1 else ''}(+)\n"
    stats_text += f"- {stats['deletions']} deletion{'s' if stats['deletions'] != 1 else ''}(-)"
    
    # If raw option is selected, return the diff with stats
    if raw:
        return diff_text + stats_text
    
    # Count tokens
    token_count = count_tokens(diff_text)
    
    # If preview option is selected, just return the token count and stats
    if preview:
        preview_text = f"Preview of sending this diff to OpenAI:\n\n"
        if token_count >= 0:
            preview_text += f"- The diff contains {token_count} tokens\n"
            # Calculate approximate cost based on current OpenAI pricing for gpt-4o-mini
            # These rates might change, so they're just estimates
            cost_per_1k_input = 0.00015  # $0.00015 per 1K tokens for GPT-4o-mini input
            cost_per_1k_output = 0.0006  # $0.0006 per 1K tokens for GPT-4o-mini output
            estimated_output_tokens = min(token_count // 3, 4000)  # Rough estimate of output tokens
            estimated_cost = (token_count / 1000 * cost_per_1k_input) + (estimated_output_tokens / 1000 * cost_per_1k_output)
            preview_text += f"- Estimated cost: ${estimated_cost:.6f} (based on current GPT-4o-mini pricing)\n"
        else:
            preview_text += "- Could not calculate token count\n"
        
        # Add commit list to preview
        commit_list = get_commit_list(base_branch, compare_branch)
        if commit_list:
            preview_text += f"\nCommits ({len(commit_list)}):\n"
            # Limit to 20 commits to avoid overwhelming output
            max_commits_to_show = 20
            for i, commit in enumerate(commit_list[:max_commits_to_show]):
                preview_text += f"- {commit}\n"
            if len(commit_list) > max_commits_to_show:
                preview_text += f"- ... and {len(commit_list) - max_commits_to_show} more commits\n"
        
        return preview_text + stats_text
    
    if token_count >= 0:  # Only show if token counting was successful
        token_limit = 100000  # Setting a reasonable limit
        
        if token_count > token_limit:
            print(f"Warning: The diff contains {token_count} tokens, which exceeds the recommended limit of {token_limit}.")
            response = input("Do you want to continue anyway? (y/n): ")
            if response.lower() != 'y':
                return f"Operation cancelled. The diff contained {token_count} tokens."
        else:
            print(f"The diff contains {token_count} tokens.")
    
    # Get natural language description
    return get_natural_language_diff(diff_text)

def print_formatted_output(text, use_markdown=True):
    """Print text with optional Markdown formatting if rich is available."""
    if use_markdown and rich_available:
        console = Console()
        md = Markdown(text)
        print("\n" + "=" * 80 + "\n")
        console.print(md)
        print("\n" + "=" * 80 + "\n")
    else:
        print("\n" + "=" * 80 + "\n")
        print(text)
        print("\n" + "=" * 80 + "\n")

def get_uncommitted_changes():
    """Get the diff of uncommitted changes in the working directory."""
    try:
        # First check if there are any changes
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        if not status_result.stdout.strip():
            return None  # No changes
        
        # Get staged changes
        staged_result = subprocess.run(
            ["git", "diff", "--staged"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        staged_diff = staged_result.stdout
        
        # Get unstaged changes
        unstaged_result = subprocess.run(
            ["git", "diff"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        unstaged_diff = unstaged_result.stdout
        
        # Combine both diffs with headers
        combined_diff = ""
        if staged_diff:
            combined_diff += "# Staged Changes\n" + staged_diff + "\n"
        if unstaged_diff:
            combined_diff += "# Unstaged Changes\n" + unstaged_diff
            
        return combined_diff.strip() or None
    except subprocess.CalledProcessError as e:
        print(f"Error getting uncommitted changes: {e.stderr}")
        sys.exit(1)

def get_uncommitted_stats():
    """Get statistics about uncommitted changes."""
    stats = {"commits": 0, "files": 0, "insertions": 0, "deletions": 0}
    
    try:
        # Get number of files changed and lines added/deleted
        result = subprocess.run(
            ["git", "diff", "--shortstat"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        unstaged_shortstat = result.stdout.strip()
        
        # Get stats for staged changes
        staged_result = subprocess.run(
            ["git", "diff", "--staged", "--shortstat"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        staged_shortstat = staged_result.stdout.strip()
        
        # Parse the shortstat outputs
        for shortstat in [unstaged_shortstat, staged_shortstat]:
            if shortstat:
                parts = shortstat.split(", ")
                for part in parts:
                    if "file" in part:
                        stats["files"] += int(part.split()[0])
                    elif "insertion" in part:
                        stats["insertions"] += int(part.split()[0])
                    elif "deletion" in part:
                        stats["deletions"] += int(part.split()[0])
    except subprocess.CalledProcessError:
        pass
    
    return stats

def get_commit_changes(commit_hash):
    """Get the diff from a specific commit to HEAD."""
    try:
        # Verify the commit exists
        verify_result = subprocess.run(
            ["git", "cat-file", "-t", commit_hash],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if verify_result.stdout.strip() != "commit":
            return None  # Not a valid commit
        
        # Get the diff from the commit to HEAD
        result = subprocess.run(
            ["git", "diff", f"{commit_hash}..HEAD"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.stdout.strip() or None
    except subprocess.CalledProcessError as e:
        print(f"Error getting changes from commit {commit_hash}: {e.stderr}")
        sys.exit(1)

def get_commit_stats(commit_hash):
    """Get statistics about changes from a specific commit to HEAD."""
    stats = {"commits": 0, "files": 0, "insertions": 0, "deletions": 0}
    
    try:
        # Get number of commits
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{commit_hash}..HEAD"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stats["commits"] = int(result.stdout.strip())
        
        # Get number of files changed and lines added/deleted
        result = subprocess.run(
            ["git", "diff", "--shortstat", f"{commit_hash}..HEAD"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        shortstat = result.stdout.strip()
        
        # Parse the shortstat output
        if shortstat:
            parts = shortstat.split(", ")
            for part in parts:
                if "file" in part:
                    stats["files"] = int(part.split()[0])
                elif "insertion" in part:
                    stats["insertions"] = int(part.split()[0])
                elif "deletion" in part:
                    stats["deletions"] = int(part.split()[0])
    except subprocess.CalledProcessError:
        pass
    
    return stats

def main():
    """Main function to parse arguments and execute commands."""
    parser = argparse.ArgumentParser(
        description="CommitLens - Git Change Visualization Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          commitlens compare feature-branch
          commitlens compare feature-branch main
          commitlens compare feature-branch --raw
          commitlens compare feature-branch --preview
          commitlens summary
          commitlens summary --from 797b3398a
          commitlens config --api-key sk-your-api-key
        """)
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two branches")
    compare_parser.add_argument("branch", nargs="?", help="Branch to compare with current branch")
    compare_parser.add_argument("base_branch", nargs="?", help="Base branch to compare against (default: current branch)")
    compare_parser.add_argument("--raw", action="store_true", help="Show raw diff output instead of natural language description")
    compare_parser.add_argument("--preview", action="store_true", help="Show token count and stats without sending to OpenAI")
    compare_parser.add_argument("--no-color", action="store_true", help="Disable colored Markdown output")
    
    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Summarize uncommitted changes or changes from a specific commit")
    summary_parser.add_argument("--raw", action="store_true", help="Show raw diff output instead of natural language description")
    summary_parser.add_argument("--preview", action="store_true", help="Show token count and stats without sending to OpenAI")
    summary_parser.add_argument("--no-color", action="store_true", help="Disable colored Markdown output")
    summary_parser.add_argument("--from", dest="from_commit", help="Show changes from this commit to HEAD")
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Configure CommitLens settings")
    config_parser.add_argument("--api-key", help="Set your OpenAI API key")
    config_parser.add_argument("--model", help="Set the OpenAI model to use (default: gpt-4o-mini)")
    config_parser.add_argument("--show", action="store_true", help="Show current configuration")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Handle config command
    if args.command == "config":
        if args.show:
            # Show current configuration
            if CONFIG_FILE.exists():
                try:
                    with open(CONFIG_FILE, 'r') as f:
                        config = json.load(f)
                        print("Current configuration:")
                        if "OPENAI_API_KEY" in config:
                            # Show only the first and last 4 characters of the API key
                            api_key = config["OPENAI_API_KEY"]
                            masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"
                            print(f"API Key: {masked_key}")
                        if "OPENAI_MODEL" in config:
                            print(f"Model: {config['OPENAI_MODEL']}")
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error reading config file: {e}")
            else:
                print("No configuration file found.")
                print(f"You can create one at {CONFIG_FILE}")
            sys.exit(0)
        
        # Set configuration
        if args.api_key or args.model:
            if setup_config(api_key=args.api_key, model=args.model):
                print(f"Configuration saved to {CONFIG_FILE}")
                if args.api_key:
                    print("API key has been set.")
                if args.model:
                    print(f"Model set to: {args.model}")
            else:
                print("Error saving configuration.")
            sys.exit(0)
        else:
            config_parser.print_help()
            sys.exit(1)
    
    # Load environment variables from all possible locations
    load_environment()
    
    if not is_git_repository():
        print("Error: Not in a git repository.")
        sys.exit(1)
    
    if args.command == "compare":
        if not args.branch:
            print("Error: Please specify a branch to compare.")
            print("Usage: commitlens compare [branch-to-compare] [base-branch] [--raw] [--preview] [--no-color]")
            sys.exit(1)
        
        # Use specified base branch or current branch
        base_branch = args.base_branch if args.base_branch else get_current_branch()
        
        if not branch_exists(args.branch):
            print(f"Error: Branch '{args.branch}' does not exist.")
            sys.exit(1)
        
        # Make sure raw and preview aren't both specified
        if args.raw and args.preview:
            print("Error: Cannot use both --raw and --preview options together.")
            sys.exit(1)
        
        result = compare_branches(base_branch, args.branch, raw=args.raw, preview=args.preview)
        
        # Use Markdown formatting for natural language output, but not for raw diffs
        use_markdown = not args.raw and not args.no_color
        print_formatted_output(result, use_markdown=use_markdown)
    
    elif args.command == "summary":
        # Make sure raw and preview aren't both specified
        if args.raw and args.preview:
            print("Error: Cannot use both --raw and --preview options together.")
            sys.exit(1)
        
        # Get changes based on whether --from is specified
        if hasattr(args, 'from_commit') and args.from_commit:
            print(f"Analyzing changes from commit {args.from_commit} to HEAD...")
            diff_text = get_commit_changes(args.from_commit)
            if not diff_text:
                print(f"No changes found from commit {args.from_commit} to HEAD or invalid commit hash.")
                sys.exit(0)
            
            # Get stats for commit changes
            stats = get_commit_stats(args.from_commit)
        else:
            # Get uncommitted changes
            diff_text = get_uncommitted_changes()
            if not diff_text:
                print("No uncommitted changes found.")
                sys.exit(0)
            
            # Get stats for uncommitted changes
            stats = get_uncommitted_stats()
        
        stats_text = f"\n\nSummary:\n"
        if hasattr(args, 'from_commit') and args.from_commit and stats["commits"] > 0:
            stats_text += f"- {stats['commits']} commit{'s' if stats['commits'] != 1 else ''}\n"
        stats_text += f"- {stats['files']} file{'s' if stats['files'] != 1 else ''} changed\n"
        stats_text += f"- {stats['insertions']} insertion{'s' if stats['insertions'] != 1 else ''}(+)\n"
        stats_text += f"- {stats['deletions']} deletion{'s' if stats['deletions'] != 1 else ''}(-)"
        
        # If raw option is selected, return the diff with stats
        if args.raw:
            result = diff_text + stats_text
            print_formatted_output(result, use_markdown=False)
            sys.exit(0)
        
        # Count tokens
        token_count = count_tokens(diff_text)
        
        # If preview option is selected, just return the token count and stats
        if args.preview:
            preview_text = f"Preview of sending changes to OpenAI:\n\n"
            if token_count >= 0:
                preview_text += f"- The diff contains {token_count} tokens\n"
                # Calculate approximate cost based on current OpenAI pricing for gpt-4o-mini
                cost_per_1k_input = 0.00015  # $0.00015 per 1K tokens for GPT-4o-mini input
                cost_per_1k_output = 0.0006  # $0.0006 per 1K tokens for GPT-4o-mini output
                estimated_output_tokens = min(token_count // 3, 4000)  # Rough estimate of output tokens
                estimated_cost = (token_count / 1000 * cost_per_1k_input) + (estimated_output_tokens / 1000 * cost_per_1k_output)
                preview_text += f"- Estimated cost: ${estimated_cost:.6f} (based on current GPT-4o-mini pricing)\n"
            else:
                preview_text += "- Could not calculate token count\n"
            
            # Add commit list to preview if using --from option
            if hasattr(args, 'from_commit') and args.from_commit:
                commit_list = get_commit_list_from_hash(args.from_commit)
                if commit_list:
                    preview_text += f"\nCommits ({len(commit_list)}):\n"
                    # Limit to 20 commits to avoid overwhelming output
                    max_commits_to_show = 20
                    for i, commit in enumerate(commit_list[:max_commits_to_show]):
                        preview_text += f"- {commit}\n"
                    if len(commit_list) > max_commits_to_show:
                        preview_text += f"- ... and {len(commit_list) - max_commits_to_show} more commits\n"
            
            result = preview_text + stats_text
            print_formatted_output(result, use_markdown=False)
            sys.exit(0)
        
        if token_count >= 0:  # Only show if token counting was successful
            token_limit = 100000  # Setting a reasonable limit
            
            if token_count > token_limit:
                print(f"Warning: The diff contains {token_count} tokens, which exceeds the recommended limit of {token_limit}.")
                response = input("Do you want to continue anyway? (y/n): ")
                if response.lower() != 'y':
                    print(f"Operation cancelled. The diff contained {token_count} tokens.")
                    sys.exit(0)
            else:
                print(f"The diff contains {token_count} tokens.")
        
        # Get natural language description
        result = get_natural_language_diff(diff_text)
        
        # Use Markdown formatting for natural language output
        use_markdown = not args.no_color
        print_formatted_output(result, use_markdown=use_markdown)

if __name__ == "__main__":
    main() 