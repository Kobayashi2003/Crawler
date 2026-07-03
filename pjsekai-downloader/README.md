# pjsekai-downloader

Downloads character images (profiles, stamps, SD characters, 3D models, comics and cards) from [Project Sekai Database](https://pjsekai.gamedbs.jp). Images are saved under `output/<character>/<type>/`.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py [options]
```

| Option | Description | Default |
|---|---|---|
| `-o, --output` | Output directory | `downloads` |
| `--char` | Download a specific character id (repeatable). Omit to download all | all |
| `--delay` | Delay between image downloads (s) | `0.3` |

### Example

```bash
python main.py -o downloads            # all characters
python main.py --char 1 --char 2       # specific characters
```

Importable: `from main import download_all, download_character`.
