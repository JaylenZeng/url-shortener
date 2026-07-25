# shortener-cli

A command-line client for the URL shortener service. Register an account, log in,
and manage short links from your terminal.

## Requirements

- Python 3.12+
- Access to a running shortener server (see the [server](../server) directory)

## Installation

Install from the `cli/` directory:

```bash
cd cli
pip install .
```

For local development, install in editable mode:

```bash
pip install -e .
```

This adds a `shortener` command to your PATH.

## Configuration

The CLI needs to know where your server lives. It resolves the base URL in this
order:

1. `base_url` in the config file (`~/.shortener/config.json`)
2. The `SHORTENER_URL` environment variable
3. A built-in default

The quickest way to point at your server is the environment variable:

```bash
export SHORTENER_URL="http://localhost:8000"
```

Your auth token is stored in `~/.shortener/config.json` (permissions `0600`)
after you log in — you don't need to manage it manually.

## Usage

### Register an account

```bash
shortener register you@example.com
```

You'll be prompted for a password (entered twice to confirm).

### Log in

```bash
shortener login you@example.com
```

You'll be prompted for your password. On success, your access token is saved to
the config file and used automatically for subsequent commands.

### Create a short link

```bash
shortener create https://example.com/some/long/url
```

Use a custom alias instead of a generated code:

```bash
shortener create https://example.com/some/long/url --alias my-link
```

### List your links

```bash
shortener list
```

Prints each link as `short_code -> original_url`.

### Delete a link

```bash
shortener delete <link_id>
```

Where `<link_id>` is the numeric ID of the link.

## Help

Every command supports `--help`:

```bash
shortener --help
shortener create --help
```
