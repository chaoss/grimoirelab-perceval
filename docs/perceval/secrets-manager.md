# Secrets Manager

Perceval supports retrieving credentials from a secrets manager instead of
passing them directly on the command line. This is useful for automated
pipelines and environments where storing credentials in plain text is not
acceptable.

The following backends support secrets manager authentication: `bugzilla`,
`bugzillarest`, `confluence`, `discourse`, `gerrit`, `git`, `github`,
`gitlab`, `gitter`, `googlehits`, `groupsio`, `jenkins`, `rocketchat`,
`stackexchange`.

## Installation

To use **HashiCorp Vault**, install Perceval with the `hashicorp-manager` group:

```
$ poetry install --with hashicorp-manager
```

**Bitwarden** does not require any extra Python package, but the
[Bitwarden CLI](https://bitwarden.com/help/cli/) (`bw`) must be installed
and available on your `PATH`.

## Common arguments

All secrets manager providers share the following arguments:

- `--secrets-manager` — Provider to use: `bitwarden` or `hashicorp`
- `--secret-name` — Name of the secret entry in the secrets manager

Credentials must be stored in the vault using the same field names that
Perceval expects: `user`, `password`, `api_token`, `email`, `access_token`,
`user_id`. Perceval automatically looks up all of these fields and uses
whichever ones are present.

## Expected field names

Store your credentials in the vault using these exact names:

- `api_token` — used by `github`, `gitlab`, `bugzillarest`, `stackexchange`, `gitter`
- `user` — used by `bugzilla`, `confluence`, `discourse`, `gerrit`, `jenkins`
- `password` — used by `bugzilla`, `confluence`, `discourse`, `gerrit`, `jenkins`
- `email` — used by `groupsio`
- `access_token` — used by `groupsio`
- `user_id` — used by `rocketchat`

Only the fields present in the vault are used; the rest are silently ignored.

Fields present in the vault must have a value. Empty fields, or values
that are not strings or numbers, produce an error. Numbers are
converted to strings.

### Pools of API tokens

Backends that accept a pool of API tokens (`github` and `githubql`)
receive `api_token` as a list. The tokens can be stored in a single
field, separated by commas or new lines (e.g. `ghp_xxxx,ghp_yyyy`).
In HashiCorp Vault they can also be stored as a JSON list.

Any other backend receives `api_token` as a single value, so storing
several tokens for them will produce an error.

## Bitwarden

Store your credentials in a Bitwarden item using Perceval's expected field
names. Fields can be stored as login fields or as custom fields.

For example, to store a GitHub API token, create a Bitwarden item named
`GitHub` with a custom field named `api_token` containing the token value.

Bitwarden-specific arguments:

- `--bw-client-id` — Bitwarden API client ID
- `--bw-client-secret` — Bitwarden API client secret
- `--bw-master-password` — Bitwarden master password

### Example
```
$ perceval github \
    --secrets-manager bitwarden \
    --secret-name 'GitHub' \
    --bw-client-id $BW_CLIENT_ID \
    --bw-client-secret $BW_CLIENT_SECRET \
    --bw-master-password $BW_MASTER_PASSWORD \
    --from-date '2020-01-01' --no-archive \
    chaoss grimoirelab-perceval
```

## HashiCorp Vault

Store your credentials as key-value pairs in a HashiCorp Vault KV secret
using Perceval's expected field names.

For example, to store a GitHub API token:
```
$ vault kv put secret/GitHub api_token=ghp_xxxxxxxxxxxx
```

HashiCorp-specific arguments:

- `--vault-url` — HashiCorp Vault server URL
- `--vault-token` — Vault authentication token
- `--vault-certificate` — Path to CA certificate for TLS verification (optional)

### Example
```
$ perceval github \
    --secrets-manager hashicorp \
    --secret-name 'GitHub' \
    --vault-url $VAULT_URL \
    --vault-token $VAULT_TOKEN \
    --from-date '2020-01-01' --no-archive \
    chaoss grimoirelab-perceval
```

## Programmatic usage

When Perceval is used as a library, `BackendItemsGenerator` and `fetch`
accept a credential manager and the name of the secret. The credentials
are retrieved before the backend is initialized and they override any
argument with the same name. They are not added to the given dict of
arguments.

```python
from perceval.backend import BackendItemsGenerator
from perceval.backends.core.github import GitHub
from perceval.credentials import build_credential_manager

manager = build_credential_manager(
    'hashicorp',
    vault_url='https://vault.example.com',
    vault_token='hvs.your-token'
)

args = {'owner': 'chaoss', 'repository': 'grimoirelab-perceval'}

with BackendItemsGenerator(GitHub, args, 'issue',
                           credential_manager=manager,
                           secret_name='GitHub') as big:
    for item in big.items:
        print(item['uuid'])
```

`build_credential_manager` accepts `bw_client_id`, `bw_client_secret`
and `bw_master_password` for Bitwarden, and `vault_url`, `vault_token`
and `vault_certificate` for HashiCorp Vault. The secret name for
HashiCorp Vault is the path of the secret in the `secret` KV engine,
so `GitHub` is read from `secret/GitHub`.

The managers are also available in `grimoirelab-toolkit` via the
`CredentialManager` base class:

```python
from grimoirelab_toolkit.credential_manager import BitwardenManager
from grimoirelab_toolkit.credential_manager.hc_manager import HashicorpManager

# Bitwarden example
bw_manager = BitwardenManager("your-client-id", "your-client-secret", "your-master-password")
credentials = bw_manager.resolve_credentials("GitHub", ["api_token"])
print(credentials)  # {'api_token': 'ghp_...'}

# HashiCorp Vault example
hc_manager = HashicorpManager("https://vault.example.com", "hvs.your-token")
credentials = hc_manager.resolve_credentials("GitHub", ["api_token"])
print(credentials)  # {'api_token': 'ghp_...'}
```
