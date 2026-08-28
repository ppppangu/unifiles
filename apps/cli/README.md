# @wyy/unifiles-cli

Install globally with `npm install -g @wyy/unifiles-cli`, then run `unifiles --help`.

This is a handwritten product application. Command design, profiles, credential handling and output
formatting live here; HTTP protocol details come exclusively from the `@wyy/unifiles` SDK.

```bash
printf '%s' "$UNIFILES_API_KEY" | unifiles config set production \
  --base-url https://api.unifiles.dev \
  --api-key-stdin
unifiles files list
```
