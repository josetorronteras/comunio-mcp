# Security policy

## Reporting a vulnerability

Report privately through
[GitHub's advisory form](https://github.com/josetorronteras/comunio-mcp/security/advisories/new).
Please do not open a public issue for a vulnerability.

Expect an acknowledgement within a week. This is a spare-time project, so a fix has no
promised deadline, but you will be told what is happening either way.

**Never include your Comunio password, a session token or a real account id in a report.**
Describe the shape of the problem; invented values are enough to reproduce anything here.

## What is in scope

This server holds a Comunio account's credentials and can spend that account's money.
The things worth reporting:

- A token or password reaching tool output, an error message or a log.
- A field carrying somebody else's personal data — email, invitation code — through a
  response model that should have allowlisted it away.
- A write tool that acts on the wrong target: `game:offer:withdraw` and
  `game:offer:decline` share a path, so a missing id check *declines* another manager's
  offer instead of withdrawing your bid.
- A write that can fire twice from one call, such as a retried `POST`.
- A `get_*` tool that mutates anything.

## What is not

- Comunio's own API, its authentication or its rate limits. Report those to Comunio.
- The account you point this at doing something you regret. Every mutating tool declares
  itself as one; approving the call is the client's job and yours.
- Credentials leaking from your own MCP client configuration file.

## Handling credentials

`COMUNIO_USERNAME` and `COMUNIO_PASSWORD` are passed to the container as environment
variables and are never baked into the image or committed. `--env-file` keeps them out of
your client's config file; see [docs/setup.md](docs/setup.md).
