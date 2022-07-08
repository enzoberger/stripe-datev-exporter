import json
from stripe_datev import recognition, csv
import stripe
import decimal, math
from datetime import datetime, timezone
from . import customer, output, dateparser, config
import datedelta

invoices_cached = {}

def listFinalizedInvoices(fromTime, toTime):
  starting_after = None
  invoices = []
  i=0
  while True:
    i=i+1
    response = stripe.Invoice.list(
      starting_after=starting_after,
      created={
        "lt": int(toTime.timestamp())
      },
      due_date={
        "gte": int(fromTime.timestamp()),
      },
      limit=50,
    )
    # Enzo write stripe invoices
    f = open("out/stripe/invoices_raw-" + str(i) + ".txt", "w")
    f.write(str(response))
    f.close()
    print("write invoces_raw-" + str(i) + " done")
    # Enzo End
    # print("Fetched {} invoices".format(len(response.data)))
    if len(response.data) == 0:
      break
    starting_after = response.data[-1].id
    for invoice in response.data:
      if invoice.status == "draft":
        continue
      finalized_date = datetime.fromtimestamp(invoice.status_transitions.finalized_at, timezone.utc).astimezone(config.accounting_tz)
      if finalized_date < fromTime or finalized_date >= toTime:
        # print("Skipping invoice {}, created {} finalized {} due {}".format(invoice.id, created_date, finalized_date, due_date))
        continue
      invoices.append(invoice)
      invoices_cached[invoice.id] = invoice

    if not response.has_more:
      break

  return list(reversed(invoices))

def retrieveInvoice(id):
  if id in invoices_cached:
    return invoices_cached[id]
  invoice = stripe.Invoice.retrieve(id)
  invoices_cached[invoice.id] = invoice
  return invoice

def getLineItemRecognitionRange(line_item, invoice):
  created = datetime.fromtimestamp(invoice.created, timezone.utc)

  start = None
  end = None
  if "period" in line_item:
    start = datetime.fromtimestamp(line_item["period"]["start"], timezone.utc)
    end = datetime.fromtimestamp(line_item["period"]["end"], timezone.utc)
  if start == end:
    start = None
    end = None

  # if start is None and end is None:
  #   desc_parts = line_item.get("description", "").split(";")
  #   if len(desc_parts) >= 3:
  #     date_parts = desc_parts[-1].strip().split(" ")
  #     start = accounting_tz.localize(datetime.strptime("{} {} {}".format(date_parts[1], date_parts[2][:-2], date_parts[3]), "%b %d %Y"))
  #     end = start + timedelta(seconds=24 * 60 * 60 - 1)

  if start is None and end is None:
    try:
      date_range = dateparser.find_date_range(line_item.get("description"), created, tz=config.accounting_tz)
      if date_range is not None:
        start, end = date_range

    except Exception as ex:
      print(ex)
      pass

  if start is None and end is None:
    print("Warning: unknown period for line item --", invoice.id, line_item.get("description"))
    start = created
    end = created

  # else:
  #   print("Period", start, end, "--", line_item.get("description"))

  return start.astimezone(config.accounting_tz), end.astimezone(config.accounting_tz)

def createRevenueItems(invs):
  revenue_items = []
  for invoice in invs:
    voided_at = None
    if invoice.status == "void":
      voided_at = datetime.fromtimestamp(invoice.status_transitions.voided_at, timezone.utc).astimezone(config.accounting_tz)

    if invoice.post_payment_credit_notes_amount > 0:
      cns = stripe.CreditNote.list(invoice=invoice.id).data
      assert len(cns) == 1
      if invoice.post_payment_credit_notes_amount == invoice.total:
        voided_at = datetime.fromtimestamp(cns[0].created, timezone.utc).astimezone(config.accounting_tz)
      else:
        # start Enzo
        print("-----------------------------------------------------------------------------------")
        print("NotImplementedError: Handling of partially credited invoices is not implemented yet")
        print("Nummer:",invoice.number,"credit:",invoice.post_payment_credit_notes_amount,"total:",invoice.total)
        print("-----------------------------------------------------------------------------------")
        # end Enzo
        

    line_items = []
    # Enzo Add payment_intent
    payment_intent = invoice.payment_intent
    # Enzo end
    cus = customer.retrieveCustomer(invoice.customer)
    accounting_props = customer.getAccountingProps(customer.getCustomerDetails(cus), invoice=invoice)
    amount_with_tax = decimal.Decimal(invoice.total) / 100
    amount_net = amount_with_tax
    if invoice.tax:
      amount_net -= decimal.Decimal(invoice.tax) / 100

    finalized_date = datetime.fromtimestamp(invoice.status_transitions.finalized_at, timezone.utc).astimezone(config.accounting_tz)

#    invoice_discount = decimal.Decimal(((invoice.get("discount", None) or {}).get("coupon", None) or {}).get("percent_off", 0))
    invoice_discount_value = ((invoice.get("discount", None) or {}).get("coupon", None) or {}).get("percent_off", 0)
    invoice_discount = decimal.Decimal( 0 if invoice_discount_value is None else invoice_discount_value )

    if invoice.lines.has_more:
      lines = invoice.lines.list().auto_paging_iter()
    else:
      lines = invoice.lines

    for line_item_idx, line_item in enumerate(lines):
      text = "Invoice {} / {}".format(invoice.number, line_item.get("description", ""))
      start, end = getLineItemRecognitionRange(line_item, invoice)

      li_amount = decimal.Decimal(line_item["amount"]) / 100
      discounted_li_net = li_amount * (1 - invoice_discount / 100)
      discounted_li_total = discounted_li_net
      if len(line_item["tax_amounts"]) > 0:
        assert len(line_item["tax_amounts"]) == 1
        li_tax = decimal.Decimal(line_item["tax_amounts"][0]["amount"]) / 100
        if not line_item["tax_amounts"][0]["inclusive"]:
          discounted_li_total += li_tax
        else:
          discounted_li_net -= li_tax

      line_items.append({
        "line_item_idx": line_item_idx,
        "recognition_start": start,
        "recognition_end": end,
        "amount_net": discounted_li_net,
        "text": text,
        "amount_with_tax": discounted_li_total,
      })

    revenue_items.append({
      "id": invoice.id,
      "number": invoice.number,
      "created": finalized_date,
      "amount_net": amount_net,
      "accounting_props": accounting_props,
      "customer": cus,
      "amount_with_tax": amount_with_tax,
      "text": "Invoice {}".format(invoice.number),
      "voided_at": voided_at,
      "line_items": line_items if voided_at is None else [],
      "payment_intent": payment_intent if not payment_intent is None else 'no payment',
    })

  return revenue_items

def createAccountingRecords(revenue_item):
  created = revenue_item["created"]
  amount_with_tax = revenue_item["amount_with_tax"]
  accounting_props = revenue_item["accounting_props"]
  line_items = revenue_item["line_items"]
  text = revenue_item["text"]
  voided_at = revenue_item.get("voided_at", None)
  # Enzo add invoices_raw
  payment_intent = revenue_item["payment_intent"]
  # Enzo get add country
  customer = revenue_item["customer"]
  country = ""
  if "deleted" in customer and customer.deleted:
    country = ""
  else:
    if "address" in customer and customer.address is not None:
      country = customer.address.country
  # Enzo ende
  records = []

  records.append({
    "date": created,
    "Umsatz (ohne Soll/Haben-Kz)": output.formatDecimal(amount_with_tax),
    "Soll/Haben-Kennzeichen": "S",
    "WKZ Umsatz": "EUR",
    "Konto": accounting_props["customer_account"],
    "Gegenkonto (ohne BU-Schlüssel)": accounting_props["revenue_account"],
    "BU-Schlüssel": accounting_props["datev_tax_key"],
    "Buchungstext": text,
    "Identifikationsnummer": payment_intent,
    "Land": country,
  })

  if voided_at is not None:
    print("Voided/refunded", text, "Created", created, 'Voided', voided_at)
    records.append({
      "date": voided_at,
      "Umsatz (ohne Soll/Haben-Kz)": output.formatDecimal(amount_with_tax),
      "Soll/Haben-Kennzeichen": "S",
      "WKZ Umsatz": "EUR",
      "Konto": accounting_props["revenue_account"],
      "Gegenkonto (ohne BU-Schlüssel)": accounting_props["customer_account"],
      "BU-Schlüssel": accounting_props["datev_tax_key"],
      "Buchungstext": "Storno {}".format(text),
      "Identifikationsnummer": payment_intent,
      "Land": country,
    })

  for line_item in line_items:
    amount_with_tax = line_item["amount_with_tax"]
    recognition_start = line_item["recognition_start"]
    recognition_end = line_item["recognition_end"]
    text = line_item["text"]

    months = recognition.split_months(recognition_start, recognition_end, [amount_with_tax])

    base_months = list(filter(lambda month: month["start"] <= created, months))
    base_amount = sum(map(lambda month: month["amounts"][0], base_months))

    forward_amount = amount_with_tax - base_amount

    forward_months = list(filter(lambda month: month["start"] > created, months))

    if len(forward_months) > 0 and forward_amount > 0:
      records.append({
        "date": created,
        "Umsatz (ohne Soll/Haben-Kz)": output.formatDecimal(forward_amount),
        "Soll/Haben-Kennzeichen": "S",
        "WKZ Umsatz": "EUR",
        "Konto": accounting_props["revenue_account"],
        "Gegenkonto (ohne BU-Schlüssel)": config.contra_account_no_bu_key,
        "Buchungstext": "{} / pRAP nach {}".format(text, "{}..{}".format(forward_months[0]["start"].strftime("%Y-%m"), forward_months[-1]["start"].strftime("%Y-%m")) if len(forward_months) > 1 else forward_months[0]["start"].strftime("%Y-%m")),
        "Identifikationsnummer": payment_intent,
        "Land": country,
      })

      for month in forward_months:
        records.append({
          "date": month["start"],
          "Umsatz (ohne Soll/Haben-Kz)": output.formatDecimal(month["amounts"][0]),
          "Soll/Haben-Kennzeichen": "S",
          "WKZ Umsatz": "EUR",
          "Konto": config.contra_account,
          "Gegenkonto (ohne BU-Schlüssel)": accounting_props["revenue_account"],
          "Buchungstext": "{} / pRAP aus {}".format(text, created.strftime("%Y-%m")),
          "Identifikationsnummer": payment_intent,
          "Land": country,
        })

  return records

def to_csv(inv):
  lines = [[
    "invoice_id",
    "invoice_number",
    "date",

    "total_before_tax",
    "tax",
    "tax_percent",
    "total",

    "customer_id",
    "customer_name",
    "country",
    "vat_region",
    "vat_id",
    "tax_exempt",

    "customer_account",
    "revenue_account",
    "datev_tax_key",
  ]]
  for invoice in inv:
    if invoice.status == "void":
      continue
    cus = customer.retrieveCustomer(invoice.customer)
    props = customer.getAccountingProps(customer.getCustomerDetails(cus), invoice=invoice)

    total = decimal.Decimal(invoice.total) / 100
    tax = decimal.Decimal(invoice.tax) / 100 if invoice.tax else None
    total_before_tax = total
    if tax is not None:
      total_before_tax -= tax

    lines.append([
      invoice.id,
      invoice.number,
      datetime.fromtimestamp(invoice.status_transitions.finalized_at, timezone.utc).astimezone(config.accounting_tz).strftime("%Y-%m-%d"),

      format(total_before_tax, ".2f"),
      format(tax, ".2f") if tax else None,
      format(decimal.Decimal(invoice.tax_percent), ".0f") if "tax_percent" in invoice and invoice.tax_percent else None,
      format(total, ".2f"),

      cus.id,
      customer.getCustomerName(cus),
      props["country"],
      props["vat_region"],
      props["vat_id"],
      props["tax_exempt"],

      props["customer_account"],
      props["revenue_account"],
      props["datev_tax_key"],
    ])

  return csv.lines_to_csv(lines)

def to_recognized_month_csv2(revenue_items):
  lines = [[
    "invoice_id",
    "invoice_number",
    "invoice_date",
    "recognition_start",
    "recognition_end",
    "recognition_month",

    "line_item_idx",
    "line_item_desc",
    "line_item_net",

    "customer_id",
    "customer_name",
    "country",

    "accounting_date",
  ]]

  for revenue_item in revenue_items:
    voided_at = revenue_item.get("voided_at", None)
    if voided_at is not None:
      continue

    for line_item in revenue_item["line_items"]:
      for month in recognition.split_months(line_item["recognition_start"], line_item["recognition_end"], [line_item["amount_net"]]):
        accounting_date = max(revenue_item["created"], month["start"])

        lines.append([
          revenue_item["id"],
          revenue_item.get("number", ""),
          revenue_item["created"].strftime("%Y-%m-%d"),
          line_item["recognition_start"].strftime("%Y-%m-%d"),
          line_item["recognition_end"].strftime("%Y-%m-%d"),
          month["start"].strftime("%Y-%m") + "-01",

          str(line_item.get("line_item_idx", 0) + 1),
          line_item["text"],
          format(month["amounts"][0], ".2f"),

          revenue_item["customer"]["id"],
          customer.getCustomerName(revenue_item["customer"]),
          revenue_item["customer"].get("address", {}).get("country", ""),

          accounting_date.strftime("%Y-%m-%d"),
        ])

  return csv.lines_to_csv(lines)

def roundCentsDown(dec):
  return math.floor(dec * 100) / 100

def accrualRecords(invoiceDate, invoiceAmount, customerAccount, revenueAccount, text, firstRevenueDate, revenueSpreadMonths, includeOriginalInvoice=True):
  records = []

  if includeOriginalInvoice:
    records.append({
      "date": invoiceDate,
      "Umsatz (ohne Soll/Haben-Kz)": output.formatDecimal(invoiceAmount),
      "Soll/Haben-Kennzeichen": "S",
      "WKZ Umsatz": "EUR",
      "Konto": str(customerAccount),
      "Gegenkonto (ohne BU-Schlüssel)": str(revenueAccount),
      "Buchungstext": text,
    })

  revenuePerPeriod = roundCentsDown(invoiceAmount / revenueSpreadMonths)
  if invoiceDate < firstRevenueDate:
    accrueAmount = invoiceAmount
    accrueText = "{} / Rueckstellung ({} Monate)".format(text, revenueSpreadMonths)
    periodsBooked = 0
    periodDate = firstRevenueDate
  else:
    accrueAmount = invoiceAmount - revenuePerPeriod
    accrueText = "{} / Rueckstellung Anteilig ({}/{} Monate)".format(text, revenueSpreadMonths-1, revenueSpreadMonths)
    periodsBooked = 1
    periodDate = firstRevenueDate + datedelta.MONTH

  records.append({
    "date": invoiceDate,
    "Umsatz (ohne Soll/Haben-Kz)": output.formatDecimal(accrueAmount),
    "Soll/Haben-Kennzeichen": "S",
    "WKZ Umsatz": "EUR",
    "Konto": str(revenueAccount),
    "Gegenkonto (ohne BU-Schlüssel)": config.contra_account_no_bu_key,
    "Buchungstext": accrueText,
  })

  remainingAmount = accrueAmount

  while periodsBooked < revenueSpreadMonths:
    if periodsBooked < revenueSpreadMonths - 1:
      periodAmount = revenuePerPeriod
    else:
      periodAmount = remainingAmount

    records.append({
      "date": periodDate,
      "Umsatz (ohne Soll/Haben-Kz)": output.formatDecimal(periodAmount),
      "Soll/Haben-Kennzeichen": "S",
      "WKZ Umsatz": "EUR",
      "Konto": config.contra_account,
      "Gegenkonto (ohne BU-Schlüssel)": str(revenueAccount),
      "Buchungstext": "{} / Aufloesung Rueckstellung Monat {}/{}".format(text, periodsBooked+1, revenueSpreadMonths),
    })

    periodDate = periodDate + datedelta.MONTH
    periodsBooked += 1
    remainingAmount -= periodAmount

  return records
