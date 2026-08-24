# PASS-PAC Mock Data Tools

## Flipper Importer

`import_flipper.py` converts local Flipper Zero `.nfc` and `.rfid` files into the PASS-PAC simulator card JSON format.

The importer expects a local clone or downloaded copy of the source repository:

```powershell
git clone https://github.com/UberGuidoZ/Flipper.git C:\Datasets\Flipper
```

Create an imported simulator dataset:

```powershell
python mock-data\tools\import_flipper.py --source C:\Datasets\Flipper --output mock-data\flipper-imported-cards.json
```

Merge imported cards with the existing demo cards:

```powershell
python mock-data\tools\import_flipper.py --source C:\Datasets\Flipper --merge-existing mock-data\sample-cards.json --output mock-data\sample-cards.json
```

Use the imported file without overwriting `sample-cards.json`:

```powershell
$env:SIMULATOR_CARD_FILE="flipper-imported-cards.json"
docker compose up --build
```

The importer keeps the raw Flipper fields in `raw_output` and stores source file metadata under `metadata`.
