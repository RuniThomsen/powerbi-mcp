# XMLA Authentication Notes

Most Power BI XMLA diagnostics and scripts in this repository default to Azure CLI tokens. Azure CLI issues delegated tokens with the single `user_impersonation` scope, which is insufficient for the XMLA endpoint. XMLA requires dataset or model scopes such as `Dataset.Read.All` that are granted to first-party Power BI desktop clients.

To acquire an XMLA-ready token without creating an app registration:

1. Run the diagnostic helper with the MSAL device code flow:

   ```bash
   python scripts/test_cli_xmla_connection.py --xmla "powerbi://api.powerbi.com/v1.0/myorg/CN_DEV" \
       --catalog "Model" --tenant "17f69c66-2114-4826-9fb1-6e496607aebc" --auth-mode msal
   ```

2. Follow the device code prompt and approve the sign-in for the Power BI public client (Power Query for Excel).
3. Rerun your XMLA command once the script confirms `Acquired token via MSAL`.

> Tip: The MSAL flow caches credentials locally. After the first device code sign-in, rerunning the command usually succeeds silently via the cached token.
