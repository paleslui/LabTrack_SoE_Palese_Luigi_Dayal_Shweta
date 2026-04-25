# LabTrack — User Guide

> This guide is for lab staff using LabTrack day to day.  
> For setup and technical details see [DEVELOPER.md](DEVELOPER.md).

---

## Getting started

Open your browser and go to the LabTrack URL provided by your lab manager (e.g. `http://160.85.x.x:5001` on the lab network, or a `https://xxx.trycloudflare.com` link for remote access).

Log in with your username and password. After 5 wrong attempts your account locks for 15 minutes. Sessions expire automatically after 8 hours.

### Your role determines what you can do

| Role | Register | Update status | Edit/Delete | Import CSV | Admin panel |
|---|---|---|---|---|---|
| **Researcher** | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Lab Technician** | ❌ | ✅ | ✅ | ❌ | ❌ |
| **Administrator** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Viewer** | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## Dashboard

The dashboard gives you an at-a-glance overview:
- **Stat cards** — total samples, collected, processing, stored, this month
- **Bar charts** — breakdown by type, organism, status, project, and top contributors
- **Recent samples table** — the 10 most recently registered samples with expiry indicators

Click any sample ID in the table to open its detail page.

---

## Registering a sample

1. Click **+ Register sample** (top right of the Samples page)
2. Fill in the required fields:
   - **Sample type** — e.g. blood, DNA, tissue, RNA, plasma
   - **Source organism** — e.g. Homo sapiens, Mus musculus
   - **Collection date** — date the sample was physically collected
   - **Storage location** — e.g. Freezer-A1 (or use structured fields below)
3. Optional fields:
   - **Structured location** — expand to fill in building, room, equipment, position separately
   - **Expiry date** — when the sample should no longer be used
   - **Quantity** — amount remaining with unit (ml, ul, mg, ug, ng, units)
   - **Notes** — any free-text observations
   - **Derived from sample** — if this sample was extracted from another (e.g. DNA from tissue biopsy LT-2025-0003)
   - **Project** — tag to an experiment or study
4. Click **Register sample**

The system assigns an ID automatically in the format `LT-YYYY-NNNN`.

---

## Sample list

The Samples page shows all samples in a searchable, filterable table.

### Filtering
Use the filter bar to narrow results:
- **Type** — partial match (e.g. "blood" matches "whole blood")
- **Status** — exact match dropdown
- **Location** — partial match across all location fields
- **Date from / Date to** — collection date range
- **Submitted by** — username of the registering researcher
- **Project** — filter by experiment/project

Click **Search** to apply, **Clear** to reset all filters.

### Expiry indicators
The **Expiry** column shows:
- 🟢 Green date — expires more than 30 days from now
- 🟡 Amber badge — expires within 30 days
- 🔴 Red badge — already expired

### Reservation indicator
A 🔒 lock icon next to a sample ID means the sample is reserved. Hover to see who reserved it and until when.

---

## Sample detail page

Click **View** on any sample to open its full detail page.

From here you can:
- **✏ Edit** — modify any field except the sample ID
- **Update status** — move the sample to a new lifecycle state
- **↓ Audit log** — download the full status history as CSV
- **🏷 Print label** — download a PNG label with QR code
- **🗑 Delete** — permanently remove the sample (with confirmation)
- **Reserve** — place a soft lock with an expiry date and note
- **Upload attachment** — attach a PDF, image, or document
- **View lineage** — see the parent sample and any derived children

### Lifecycle status
Samples can be in any of these states. All transitions are permitted in both directions — mistakes can always be corrected via the audit log:

```
Collected ↔ Processing ↔ Stored ↔ Consumed
                                 ↕
                              Discarded
```

### Audit log
Every status change is recorded with a timestamp and the name of the person who made it. The audit log is immutable — entries cannot be edited or deleted.

---

## Bulk operations

Select multiple samples using the checkboxes in the sample list. The bulk action bar appears at the bottom:

- **Change status to…** + **Apply** — update all selected samples at once
- **↓ Export selected** — download selected samples as CSV
- **🏷 Print labels** — download a combined label sheet (3 per row)
- **🗑 Delete selected** — permanently delete all selected (with confirmation)

---

## CSV import

Researchers and administrators can bulk-import samples from a CSV file.

**Required columns:**
```
sample_type, source_organism, collection_date, storage_location
```

**Optional columns:**
```
notes
```

**Date format:** `YYYY-MM-DD` (e.g. `2025-04-01`)

The import section appears at the bottom of the Samples page. Drag a CSV file onto the drop zone or click to choose.

- Valid rows are imported; invalid rows are reported without aborting
- Duplicate rows (same type + organism + date + location) are skipped and reported separately
- Exported CSVs can be directly re-imported (dates are in the correct format)

---

## CSV export

Click **↓ Export CSV** on the Samples page to download all currently visible samples (respecting active filters) as a CSV file.

---

## Projects

Click **Projects** in the navigation bar to manage experiments and studies.

- Create a project with a name and optional description
- Assign samples to a project when registering or editing them
- Filter the sample list by project
- The dashboard shows a breakdown of samples per project

---

## QR code labels

Every sample has a printable label available from its detail page (**🏷 Print label**). The label contains:
- Sample ID and key metadata (printed text)
- A QR code that links to the **live** sample page (`/view/<sample_id>`)

When someone scans the QR code they see the **current** state of the sample — status, quantity, expiry, location, recent audit entries — without needing to log in. The physical label never needs to be reprinted; the data behind the QR code always reflects reality.

---

## Language toggle

Click the **🇩🇪 DE / 🇬🇧 EN** button in the top navigation bar to switch between German and English. Your preference is remembered in the browser.

---

## Updating your profile

Click your **username** in the top navigation bar to open the profile editor. You can update your email address or change your password. Your current password is required to save any change.

---

## Getting help

Contact your lab administrator or refer to [DEVELOPER.md](DEVELOPER.md) for technical issues.
