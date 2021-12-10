# CredentialLoader

A CredentialLoader loads devices credentials from a source.

Every CredentialLoader plugins must inherit from `.base_credential_loader.CredentialLoader` and override the following methods:
- `init(input_data)`: initialize the credential plugin
- `load(inventory)`: loads the credentials inside each inventory device.

    **Attention**: set device credentials using the function `write_credentials(device, credentials)`.
    This function does credentials validation before inserting.

## CredFile
Loads credentials from a file.
The credential file format is the following
```yaml
- namespace: namespace                  # devices namespace
  devices:                              # devices credentials list
    - name: dcedge01                    # device identification
      credentials:
        keyfile: path/to/key/file       # devices ssh keyfile
        username: username              # ssh username
        passowrd: password              # ssh password
```
And the `CredFile` configuration is
```yaml
  # credential loader
  type: cred_file                               # credential loader type
  file_path: path/to/devices/credentials.yaml   # devices credential file path
```
