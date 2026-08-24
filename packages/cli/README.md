# @wyy/unifiles-cli

Install globally with `npm install -g @wyy/unifiles-cli`, then run `unifiles --help`.

```bash
printf '%s' "$UNIFILES_API_KEY" | unifiles config set production \
  --base-url https://api.unifiles.dev \
  --api-key-stdin
unifiles files list
```
