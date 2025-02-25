# CommitLens - Git Change Visualization Tool

CommitLens is a powerful tool that provides natural language explanations of git diffs, making it easier to understand changes between branches or commits. It uses OpenAI's GPT models to generate clear, human-readable summaries of code changes.

[![GitHub license](https://img.shields.io/github/license/alessandrodorazio/commitlens)](https://github.com/alessandrodorazio/commitlens/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/alessandrodorazio/commitlens)](https://github.com/alessandrodorazio/commitlens/stargazers)

## Features

- **Natural Language Explanations**: Clear summaries of git diffs.
- **Branch Comparison**: Ability to compare any two branches in the repository.
- **Uncommitted Changes Summary**: Summary of current working directory changes.
- **Commit Range Summary**: Summary of changes from a specific commit to HEAD.
- **Raw Diff Mode**: View raw git diff with added statistics.
- **Preview Mode**: Check token count and estimated cost before sending to OpenAI.
- **Markdown Formatting**: Proper formatting and syntax highlighting in the terminal.
- **Global Configuration**: Persistent configuration using a config file.
- **Model Selection**: Choose between different OpenAI models.

## Requirements

- Python 3.6+
- Git
- OpenAI API key (for natural language explanations)

## Installation

### Option 1: Clone the repository

```bash
git clone https://github.com/alessandrodorazio/commitlens.git
cd commitlens
pip install -r requirements.txt
```

### Option 2: Install as a package

```bash
pip install commitlens
```

Or directly from the repository:

```bash
pip install git+https://github.com/alessandrodorazio/commitlens.git
```

## Configuration

CommitLens offers two ways to configure your OpenAI API key:

### 1. Using the config command (Recommended)

After installing CommitLens, you can set your API key using the config command:

```bash
commitlens config --api-key your_api_key_here
```

You can also set the model to use:

```bash
commitlens config --model gpt-4
```

To view your current configuration:

```bash
commitlens config --show
```

This stores your configuration in `~/.commitlens/config.json` with restricted permissions.

### 2. Using environment variables

You can set the API key as an environment variable:

```bash
export OPENAI_API_KEY=your_api_key_here
```

CommitLens will check these locations in the following order:
1. Environment variables
2. Config file in `~/.commitlens/config.json`

## Usage

### Compare Two Branches

To compare two branches and get a natural language explanation of the differences:

```
commitlens compare feature-branch
```

This will compare `feature-branch` to your current branch.

You can also specify the base branch:

```
commitlens compare feature-branch main
```

or if you cloned the repository without installing:

```
./commitlens.py compare feature-branch main
```

### Summarize Uncommitted Changes

To get a summary of your current uncommitted changes:

```
commitlens summary
```

You can also summarize changes from a specific commit to the current HEAD:

```
commitlens summary --from <commit-hash>
```

For example:
```
commitlens summary --from 797b3398a
```

This will show you a summary of all changes that have occurred since that commit.

### Options

Both commands support the following options:

- `--raw`: Show the raw git diff output instead of a natural language explanation. This option doesn't require an OpenAI API key. The raw output includes a summary of the total number of commits, files changed, and lines added/deleted.

- `--preview`: Show token count, estimated cost, diff statistics, and a list of commits without sending anything to OpenAI. This is useful to check how large the diff is, see which commits are included, and estimate the cost before proceeding with the natural language explanation. When using with `--from`, the list includes the starting commit.

- `--no-color`: Disable colored Markdown formatting in the terminal. By default, the tool renders the output with syntax highlighting and formatting.

## License

[MIT](https://github.com/alessandrodorazio/commitlens/blob/main/LICENSE) © [Alessandro D'Orazio](https://github.com/alessandrodorazio)

Test 

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Author

- **Alessandro D'Orazio** - [GitHub](https://github.com/alessandrodorazio)
