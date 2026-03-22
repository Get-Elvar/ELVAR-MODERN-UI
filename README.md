# Elvar

Elvar is a desktop workflow launcher and browser-session utility built with CustomTkinter.

## Repository Layout

- `src/` application source code (UI, API, storage, security, services)
- `scripts/` build and installer scripts
- `extension/` browser extension templates exported by Elvar
- `requirements.txt` pinned Python dependencies

## Run (dev)

```bash
python -m pip install -r requirements.txt
python src/elvar.py
```

## Build (Windows)

Run:

```bat
scripts\build_windows.bat
```

The build script packages icon and extension templates into the executable bundle.

## License

See `LICENSE`.
