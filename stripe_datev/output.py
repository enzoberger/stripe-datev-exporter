from datetime import datetime
from . import config

fields = [
  "Umsatz (ohne Soll/Haben-Kz)",
  "Soll/Haben-Kennzeichen",
  "WKZ Umsatz",
  "Kurs",
  "Basis-Umsatz",
  "WKZ Basis-Umsatz",
  "Konto",
  "Gegenkonto (ohne BU-Schlüssel)",
  "BU-Schlüssel",
  "Belegdatum",
  "Belegfeld 1",
  "Belegfeld 2",
  "Skonto",
  "Buchungstext",
  "Postensperre",
  "Diverse Adressnummer",
  "Geschäftspartnerbank",
  "Sachverhalt",
  "Zinssperre",
  "Beleglink",
  "Beleginfo - Art 1",
  "Beleginfo - Inhalt 1",
  "Beleginfo - Art 2",
  "Beleginfo - Inhalt 2",
  "Beleginfo - Art 3",
  "Beleginfo - Inhalt 3",
  "Beleginfo - Art 4",
  "Beleginfo - Inhalt 4",
  "Beleginfo - Art 5",
  "Beleginfo - Inhalt 5",
  "Beleginfo - Art 6",
  "Beleginfo - Inhalt 6",
  "Beleginfo - Art 7",
  "Beleginfo - Inhalt 7",
  "Beleginfo - Art 8",
  "Beleginfo - Inhalt 8",
  "KOST1 - Kostenstelle",
  "KOST2 - Kostenstelle",
  "Kost-Menge",
  "EU-Land u. UStID",
  "EU-Steuersatz",
  "Abw. Versteuerungsart",
  "Sachverhalt L+L",
  "Funktionsergänzung L+L",
  "BU 49 Hauptfunktionstyp",
  "BU 49 Hauptfunktionsnummer",
  "BU 49 Funktionsergänzung",
  "Zusatzinformation - Art 1",
  "Zusatzinformation- Inhalt 1",
  "Zusatzinformation - Art 2",
  "Zusatzinformation- Inhalt 2",
  "Zusatzinformation - Art 3",
  "Zusatzinformation- Inhalt 3",
  "Zusatzinformation - Art 4",
  "Zusatzinformation- Inhalt 4",
  "Zusatzinformation - Art 5",
  "Zusatzinformation- Inhalt 5",
  "Zusatzinformation - Art 6",
  "Zusatzinformation- Inhalt 6",
  "Zusatzinformation - Art 7",
  "Zusatzinformation- Inhalt 7",
  "Zusatzinformation - Art 8",
  "Zusatzinformation- Inhalt 8",
  "Zusatzinformation - Art 9",
  "Zusatzinformation- Inhalt 9",
  "Zusatzinformation - Art 10",
  "Zusatzinformation- Inhalt 10",
  "Zusatzinformation - Art 11",
  "Zusatzinformation- Inhalt 11",
  "Zusatzinformation - Art 12",
  "Zusatzinformation- Inhalt 12",
  "Zusatzinformation - Art 13",
  "Zusatzinformation- Inhalt 13",
  "Zusatzinformation - Art 14",
  "Zusatzinformation- Inhalt 14",
  "Zusatzinformation - Art 15",
  "Zusatzinformation- Inhalt 15",
  "Zusatzinformation - Art 16",
  "Zusatzinformation- Inhalt 16",
  "Zusatzinformation - Art 17",
  "Zusatzinformation- Inhalt 17",
  "Zusatzinformation - Art 18",
  "Zusatzinformation- Inhalt 18",
  "Zusatzinformation - Art 19",
  "Zusatzinformation- Inhalt 19",
  "Zusatzinformation - Art 20",
  "Zusatzinformation- Inhalt 20",
  "Stück",
  "Gewicht",
  "Zahlweise",
  "Forderungsart",
  "Veranlagungsjahr",
  "Zugeordnete Fälligkeit",
  "Skontotyp",
  "Auftragsnummer",
  "Buchungstyp",
  "USt-Schlüssel (Anzahlungen)",
  "EU-Land (Anzahlungen)",
  "Sachverhalt L+L (Anzahlungen)",
  "EU-Steuersatz (Anzahlungen)",
  "Erlöskonto (Anzahlungen)",
  "Herkunft-Kz",
  "Buchungs GUID",
  "KOST-Datum",
  "SEPA-Mandatsreferenz",
  "Skontosperre",
  "Gesellschaftername",
  "Beteiligtennummer",
  "Identifikationsnummer",
  "Zeichnernummer",
  "Postensperre bis",
  "Bezeichnung SoBil-Sachverhalt",
  "Kennzeichen SoBil-Buchung",
  "Festschreibung",
  "Leistungsdatum",
  "Datum Zuord. Steuerperiode",
  "Fälligkeit",
  "Generalumkehr (GU)",
  "Steuersatz",
  "Land",
  "",
]

def filterRecords(records, fromTime=None, toTime=None):
  return list(filter(lambda r: (fromTime is None or r["date"] >= fromTime) and (toTime is None or r["date"] <= toTime), records))

def writeRecords(fileName, records, fromTime=None, toTime=None):
  if len(records) == 0:
    return
  with open(fileName, 'w', encoding="latin1", errors="replace", newline="\r\n") as fp:
    printRecords(fp, records, fromTime=fromTime, toTime=toTime)

def printRecords(textFileHandle, records, fromTime=None, toTime=None):
  if fromTime is not None or toTime is not None:
    records = filterRecords(records, fromTime, toTime)

  minTime = fromTime or min([r["date"] for r in records])
  maxTime = toTime or max([r["date"] for r in records])
  years = set(r["date"].astimezone(config.accounting_tz).strftime("%Y") for r in records)
  if len(years) > 1:
    raise Exception("May not print records from multiple years: {}".format(years))

  header = [
    '"EXTF"', # DATEV-Format (DTVF - von DATEV erzeugt, EXTF Fremdprogramm)
    '700', # Version des DATEV-Formats (141 bedeutet 1.41)
    '21', # Datenkategorie (21 = Buchungsstapel, 67 = Buchungstextkonstanten, 16 = Debitoren/Kreditoren, 20 = Kontenbeschriftungen usw.)
    'Buchungsstapel', # Formatname (Buchungsstapel, Buchungstextkonstanten, Debitoren/Kreditoren, Kontenbeschriftungen usw.)
    '9', # Formatversion (bezogen auf Formatname)
    datetime.today().astimezone(config.accounting_tz).strftime("%Y%m%d%H%M%S"), # '20190211202957107', # erzeugt am
    '', # importiert am
    'BH', # Herkunft
    '', # exportiert von
    '', # importiert von
    '1', # Beraternummer
    '1', # Mandantennummer
    minTime.astimezone(config.accounting_tz).strftime('%Y') + '0101', # Wirtschaftsjahresbeginn
    '4', # Sachkontenlänge
    minTime.astimezone(config.accounting_tz).strftime('%Y%m%d'), # Datum Beginn Buchungsstapel
    maxTime.astimezone(config.accounting_tz).strftime('%Y%m%d'), # Datum Ende Buchungsstapel
    '', # Bezeichnung (Vorlaufname, z. B. Buchungsstapel)
    '', # Diktatkürzel
    '1', # Buchungstyp (bei Buchungsstapel = 1)
    '0', # Rechnungslegungszweck
    '0', # Festschreibung
    # 'EUR', # WKZ
  ]
  textFileHandle.write(";".join(header))
  textFileHandle.write("\n")

  textFileHandle.write(";".join(fields))
  textFileHandle.write("\n")

  for record in records:
    record["Belegdatum"] = formatDateDatev(record["date"])
    record["Buchungstext"] = "\"{}\"".format(record["Buchungstext"])

    # print(record)
    recordValues = [record.get(f, '') for f in fields]
    textFileHandle.write(";".join(recordValues))
    textFileHandle.write("\n")

def formatDateDatev(date):
  return date.astimezone(config.accounting_tz).strftime("%d%m")

def formatDateHuman(date):
  return date.astimezone(config.accounting_tz).strftime("%d.%m.%Y")

def formatDecimal(d):
  return "{0:.2f}".format(d).replace(",", "").replace(".", ",")
