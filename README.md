# Vrijwilligers Aanmelding - Voetbalclub

Web-app voor het beheren van vrijwilligersaanmeldingen bij organisaties.

## Functies

- **Openbare kant**: bekijk organisaties, meld je aan voor diensten en taken
- **Beheer**: aanmaken en beheren van organisaties, diensten en taken; aanmeldingen inzien en exporteren

## Starten

```bash
pip install -r requirements.txt
python app.py
```

Open daarna http://localhost:5000

## Beheer inloggen

Ga naar http://localhost:5000/admin en gebruik het wachtwoord `admin123`.

Stel in productie het wachtwoord in via omgevingsvariabelen:

```bash
export ADMIN_PASSWORD=jouwwachtwoord
export SECRET_KEY=eengeheimesleutel
python app.py
```

## Structuur

- **Organisaties** – een evenement of organisatie (datum, locatie, beschrijving)
- **Diensten** – tijdblokken binnen een organisatie (bijv. 09:00–12:00 Ochtendploeg)
- **Taken** – specifieke rollen per dienst (bijv. Kassa, Parkeerregeling) met een maximum aantal vrijwilligers
- **Aanmeldingen** – vrijwilligers melden zich aan voor een taak; exporteerbaar als CSV
