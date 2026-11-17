# Customer Segmentation using RFM and K-Means

A data mining mini project that groups customers by their buying behaviour.
Each customer is described by three values (RFM), and k-means clustering
places similar customers into segments such as *Champions* or *Hibernating*.
Businesses use these segments to decide where to focus marketing.

## Project structure

```
customer-segmentation/
├── data/
│   └── transactions.csv      # created by generate_data.py (or your own dataset)
├── output/                   # results and charts are written here
├── src/
│   ├── generate_data.py      # builds a synthetic transaction dataset
│   ├── rfm.py                # cleaning and RFM feature engineering
│   ├── segment.py            # scaling, k-means, k selection, segment naming
│   └── main.py               # runs the full pipeline and saves outputs
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python src/generate_data.py       # step 1: create the sample dataset
python src/main.py                # step 2: segment customers (k chosen automatically)
python src/main.py --k 4          # optional: force exactly 4 segments
python src/main.py --source retail2   # optional: use the real Online Retail II file
```

### Real data (UCI Online Retail II)

Download the Excel workbook (about 45 MB) from:

<https://archive.ics.uci.edu/dataset/502/online+retail+ii>

Save it as `data/online_retail_II.xlsx`, then run:

```bash
pip install openpyxl                       # needed to read .xlsx files
python src/main.py --source retail2        # results go to output_real/
```

`--source synthetic` (the default) reads `data/transactions.csv` and writes to
`output/`. `--source retail2` reads the Excel file and writes to
`output_real/`, so the two sets of results sit side by side and neither
overwrites the other. `--data` and `--out` override the file and folder.

Every segment name, `k` and profile table is produced by exactly the same
code path for both sources, so the comparison is fair.

### Quintile scores (R, F and M from 1 to 5)

`src/main.py` also writes `output/rfm_scores.csv`. Each customer gets an
`R_score`, `F_score` and `M_score` between 1 (worst) and 5 (best), plus an
`RFM_code` such as `555`. The scores come from `pandas.qcut`, which splits the
customers into five equal-sized groups. **Recency is scored backwards**: a
small number of days is good, so a customer who bought yesterday scores 5.
Read `555` as "best on all three measures".

### Churn view

`output/churn_summary.csv` counts how many customers have not bought in the
last 90, 180 and 365 days, and what share of all customers that is. The days
are counted from the **last date in the data**, not from today. The same
numbers are printed in the terminal when `main.py` runs.

The code is in `src/churn.py`; change the periods in `CHURN_PERIODS` there.

### Comparing the two runs

```bash
python src/compare_runs.py
```

Prints the number of customers, the chosen `k`, and each segment's share of
customers and of revenue, for the synthetic run and the real run.

### Business case (assumption-based)

```bash
python src/business_case.py
```

Reads the assumptions in `config/assumptions.json`:

- `win_back_rate` - the share of quiet customers an offer wins back (0.20 = 20%)
- `offer_cost_per_customer` - what the offer costs per person
- `average_order_value` - leave it `null` to take a value from the data
- `orders_per_year_if_returned` - how often a returning customer buys

It writes `output/business_case.csv` and prints a short summary.

**Every figure this script produces is assumption-based.** The data says how
many customers are in each segment; it says nothing about whether they will
come back. The guesses live in `config/assumptions.json` and a different guess
gives a different answer. Present these numbers as "what would happen if...",
never as a finding of the analysis. The output file labels each column
`assumption_based_` and carries a `figures_are` column saying the same.

## Add your own data (dashboard)

Start the dashboard first:

```bash
python dashboard/app.py           # then open http://localhost:8000/add-data
```

The page has three large tabs at the top. You pick one; all three give the same
result cards, pie chart, bar chart and plain-English sentences.

### Option A: upload a CSV file

1. Click **Download sample file** to see the shape we expect.
2. Drag your file onto the dashed box, or press **Choose file**.
3. Press **Upload and work it out**, then read the results.

The file needs one row per item sold, with a customer ID, an invoice (or
order) number, a date, a quantity and a price. Common other names are
understood automatically, so "Customer ID", "InvoiceDate" and "Price" all
work. Only `.csv` files up to 20 MB are accepted.

The page tells you exactly what it did with the file, for example
"30 rows read. 26 used. 4 removed.", and breaks the removed rows down by
reason: no customer ID, returns (quantity below 1), price of 0 or less, and
unreadable dates. From what is left it counts the buyers and runs the same
RFM and k-means pipeline as `src/main.py`, using the plain group names
**Best buyers**, **Good buyers**, **Buyers at risk** and **Inactive buyers**.

The uploaded file is only read in memory and is never written to disk, so
there is nothing left behind to delete.

### Option B: type the numbers

Fill in the seven boxes (whole numbers only), or use the **Type a list** tab
and write one line per item, such as `Most buyers: 233`. Capital letters and
extra spaces do not matter. Any line the page cannot read is shown back to
you.

The Save button stays disabled until every box is filled. A box that is empty
or holds something that is not a whole number gets a message next to it. If
the numbers do not add up you get a warning, but you can still save.

### Option C: upload a document

Already have the numbers written down? Put them in a Word file, a PDF or a
plain text file and upload that instead of typing them.

1. Open the **Upload a document** tab.
2. Drag the file onto the dashed box, or press **Choose a document**.
3. Press **Read the numbers**.

The numbers are read out of the document and dropped into the seven boxes of
Option B, so you can check each one before you save. Anything the page could
not find is listed by name, and any line it did not understand is shown back to
you. Word files are read paragraph by paragraph and table by table, and a
number on the line below its name is still found, which is common in PDFs.

A scanned PDF has no text in it, so the page says so and asks you to type the
numbers instead. Like the CSV upload, the document is only read in memory and
is never written to disk.

### Where the numbers come from

All the counting lives in `src/summary.py`, with the thresholds at the top of
that file (`MOST_ORDERS = 10`, `REGULAR_ORDERS = 3`, `LAST_MONTH_DAYS = 30`,
`FREQUENT_TOP_PERCENT = 20`, `BIG_SPENDER_TOP_PERCENT = 10`). Change one of
those and the whole page follows.

"Bought last month" uses the latest date in your file as "today", not the real
date, so an older file still gives sensible numbers.

Every run is saved to a local SQLite file (`dashboard/entries.db`) with its
source, date and time. **Past entries** lists them; each one can be opened or
deleted.

### Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The test files are:

| File | What it checks |
|------|----------------|
| `tests/test_cleaning.py` | Bad rows (no customer ID, a return, a zero price) are removed |
| `tests/test_rfm.py` | Recency, frequency and monetary values worked out by hand |
| `tests/test_segment.py` | Scaling keeps every row and centres each column at zero; names are unique |
| `tests/test_pipeline.py` | The whole pipeline runs on 50 customers and writes every output file |
| `tests/test_scores.py` | The 1-to-5 scores, the churn counts, and the Excel column renaming |
| `tests/test_summary.py` | Typed numbers and the list parser on the dashboard |
| `tests/test_add_data.py` | The dashboard CSV cleaning, counting and segments |
| `tests/test_document.py` | Reading numbers out of Word / PDF / text files |

`tests/test_summary.py`, `test_add_data.py` and `test_document.py` can also be
run on their own with `python tests/test_summary.py` and so on.

## Method

1. **Cleaning**: remove anonymous rows, returns (negative quantities) and invalid prices.
2. **RFM**: for each customer compute
   - *Recency*: days since the last purchase
   - *Frequency*: number of distinct orders
   - *Monetary*: total amount spent
3. **Scaling**: apply a log transform (spending is heavily skewed), then standardise.
4. **Clustering**: k-means for k = 2 to 8. The k with the highest silhouette score is used unless you pass `--k`.
5. **Naming**: each cluster is compared with the overall median and labelled (Champions, Loyal Customers, Promising / New, Big Spenders at Risk, Lapsing Regulars, Hibernating).

## Outputs

| File | Contents |
|------|----------|
| `output/segments.csv` | Each customer with cluster number and segment name |
| `output/segment_profile.csv` | Size, average RFM and revenue share per segment |
| `output/k_selection.csv` | Inertia and silhouette score for each k |
| `output/elbow_plot.png` | Elbow curve |
| `output/segments_plot.png` | Recency vs spend scatter plot coloured by segment |
| `output/segment_sizes.png` | Customers per segment |
| `output/rfm_scores.csv` | R, F and M scores from 1 to 5, plus the code (e.g. `555`) |
| `output/churn_summary.csv` | Customers not seen for 90, 180 and 365 days |
| `output/run_info.json` | Which source and which `k` produced this run |
| `output/business_case.csv` | **Assumption-based** extra revenue and net gain per segment |
| `output_real/` | The same files, produced from the Online Retail II data |

## Using a real dataset

The pipeline expects a file with these columns:

`customer_id, invoice_id, invoice_date, quantity, unit_price`

The **Online Retail II** dataset from the UCI Machine Learning Repository is
read directly by `--source retail2`; you do not need to rename anything.
`src/load_online_retail.py` does the renaming:

| In the Excel file | Used by the pipeline |
|---|---|
| `Customer ID` | `customer_id` |
| `Invoice` | `invoice_id` |
| `InvoiceDate` | `invoice_date` |
| `Quantity` | `quantity` |
| `Price` | `unit_price` |

That module also drops **cancellations** (invoices whose number starts with
`C`) before cleaning. The remaining cleaning rules are unchanged: rows with no
customer ID, quantities below 1 and prices of 0 or less are removed.

For any other dataset, save it as a CSV with the five columns above and run
`python src/main.py --data path/to/your.csv`.

## Viva talking points

- **Why RFM?** It is a standard, interpretable way to measure customer value with only three features.
- **Why log transform?** A few very large spenders would otherwise dominate the distance calculation.
- **Why standardise?** Recency is measured in days and monetary in currency; without scaling, the largest-valued feature would control the clusters.
- **How is k chosen?** Elbow method (look for the bend in inertia) and silhouette score (how well separated the clusters are). The silhouette score is used automatically.
- **Is k-means supervised?** No. It is unsupervised: the algorithm finds groups without labelled examples.
- **Limitations:** k-means assumes roughly spherical clusters, is sensitive to outliers, and the segment names are rule-based, so they should be reviewed by a person.
